#!/usr/bin/env python3
"""Automated dependency graph generator for codebase documentation.

Scans Python imports, TypeScript/TSX modules, and Docker Compose service
references to produce Mermaid graphs embeddable in AGENTS.md or CODEBASE_MAP.

Tracks which domains/services have added new import edges since last run
by diffing against a JSON snapshot stored alongside the output.

Usage:
    python scripts/gen_deps.py [--project <repo>] [--output <path>] [--verbose]

Output structure (per project):
    docs/DEP_GRAPH.md              -- Mermaid graphs for embedding
    docs/.dep_graph_snapshot.json  -- edge list for diffing
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional


# ===================================================================
# Data model
# ===================================================================

class Lang(str, Enum):
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    YAML = "yaml"


@dataclass
class Edge:
    src: str
    dst: str
    lang: Lang
    kind: str


def _edge_to_dict(e: Edge) -> dict:
    return {"src": e.src, "dst": e.dst, "lang": str(e.lang), "kind": e.kind}

def _dict_to_edge(d: dict) -> Edge:
    return Edge(src=d["src"], dst=d["dst"], lang=Lang(d["lang"]), kind=d["kind"])


# ===================================================================
# Configurable scan scopes per repo type
# ===================================================================

# Which directories to scan for Python files (relative to repo root)
PY_SCAN_DIRS = ["api", "scripts", "tests"]

# Directories to exclude (relative path components)
PY_EXCLUDE = {"__pycache__", ".venv", "venv", "env", "node_modules"}

# Project-owned import prefixes — only keep these, discard stdlib/third-party
PROJECT_PY_PREFIXES = ("api.", "config.", "collectors.")


def _is_project_python_path(p: Path, repo_root: Path) -> bool:
    """Return True if this .py file is in a scanable, non-excluded dir."""
    try:
        rel = p.relative_to(repo_root)
    except ValueError:
        return False
    parts = list(rel.parts)
    # Must start with a scan directory
    if not parts[0] in PY_SCAN_DIRS:
        return False
    # Exclude any part matches
    if any(part in PY_EXCLUDE for part in parts):
        return False
    return True


# ===================================================================
# Scanners
# ===================================================================

def scan_python_imports(repo_root: Path) -> list[Edge]:
    """Scan project-owned dirs for internal Python imports only.

    Filters out stdlib, third-party, and site-packages by keeping only
    imports that start with known project package prefixes.
    """
    edges: list[Edge] = []
    py_files = [p for p in repo_root.rglob("*.py") if _is_project_python_path(p, repo_root)]

    for fpath in py_files:
        rel = fpath.relative_to(repo_root)
        src = str(rel).replace("\\", "/")
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # from X.Y.Z import ...
            m = re.match(r"^from\s+([\w.]+)\s+import", stripped)
            if m:
                mod_path = m.group(1)
                # Only keep project-owned imports (discard stdlib / third-party)
                if any(mod_path.startswith(p) for p in PROJECT_PY_PREFIXES):
                    edges.append(Edge(src=src, dst=mod_path, lang=Lang.PYTHON, kind="import"))
                continue

            # import X.Y  (not "import X" without dot — that's a single package name)
            m = re.match(r"^import\s+([\w.]+)\s*($|,)", stripped)
            if m:
                mod_path = m.group(1)
                if any(mod_path.startswith(p) for p in PROJECT_PY_PREFIXES):
                    edges.append(Edge(src=src, dst=mod_path, lang=Lang.PYTHON, kind="import"))

    return edges


def scan_typescript_imports(repo_root: Path) -> list[Edge]:
    """Scan web/src/ for relative TypeScript imports (local modules only)."""
    edges: list[Edge] = []
    src_dir = repo_root / "web" / "src"
    if not src_dir.exists():
        return edges

    ts_files = list(src_dir.rglob("*.ts")) + list(src_dir.rglob("*.tsx"))

    for fpath in ts_files:
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        rel = str(fpath.relative_to(repo_root)).replace("\\", "/")

        # from './X' or '../X' — skip node_modules / @mui etc.
        for m in re.finditer(r"""from\s+['"](\.[^'"]+)['"]""", content):
            target = m.group(1)
            if "node_modules" in target or "@" in target[:3]:
                continue
            resolved = _resolve_ts_import(repo_root, rel, target)
            edges.append(Edge(src=rel, dst=(resolved or target), lang=Lang.TYPESCRIPT, kind="import"))

        # export { ... } from './X'
        for m in re.finditer(r"""export\s+.*?\s+from\s+['"](\.[^'"]+)['"]""", content):
            target = m.group(1)
            if "node_modules" in target:
                continue
            resolved = _resolve_ts_import(repo_root, rel, target)
            edges.append(Edge(src=rel, dst=(resolved or target), lang=Lang.TYPESCRIPT, kind="export"))

    return edges


def _resolve_ts_import(repo_root: Path, src_file: str, target: str) -> Optional[str]:
    """Resolve a relative TS import to a clean display path."""
    src_dir = repo_root / src_file
    resolved = (src_dir.parent / target).resolve()
    try:
        rel = resolved.relative_to(repo_root)
        if rel.suffix in {".ts", ".tsx"}:
            return str(rel.with_suffix(""))
        return str(rel)
    except ValueError:
        return None


def scan_yaml_services(repo_root: Path) -> list[Edge]:
    """Scan docker-compose files for service dependencies."""
    edges: list[Edge] = []
    compose_files = (list(repo_root.rglob("docker-compose*.yml")) +
                     list(repo_root.rglob("docker-compose*.yaml")))

    for fpath in compose_files:
        rel = fpath.relative_to(repo_root)
        src_name = "compose:" + str(rel).replace("\\", "/")
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for m in re.finditer(r"depends_on:\s*\n\s*- ([\w_-]+)", content):
            edges.append(Edge(src=src_name, dst=m.group(1), lang=Lang.YAML, kind="depends_on"))

    return edges


# ===================================================================
# Snapshot / diffing
# ===================================================================

def load_snapshot(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text())
        raw["edges"] = [_dict_to_edge(e) for e in raw.get("edges", [])]
        return raw
    except Exception:
        return None


def save_snapshot(path: Path, project: str, edges: list[Edge]) -> None:
    path.write_text(
        json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "project": project,
            "edges": [_edge_to_dict(e) for e in edges],
        }, indent=2),
        encoding="utf-8",
    )


def compute_diff(old: Optional[dict], new_edges: list[Edge]) -> set[str]:
    if not old:
        return {"NEW " + "/" + "/".join((str(e.lang), e.dst)) for e in new_edges}
    old_set = {(e.src, e.dst, str(e.lang)) for e in old["edges"]}
    new_set = {(e.src, e.dst, str(e.lang)) for e in new_edges}
    added = new_set - old_set
    removed = old_set - new_set
    return {"+ " + "/".join(s) for s in added} | {"- " + "/".join(s) for s in removed}


# ===================================================================
# Mermaid graph generation
# ===================================================================

def _safe_id(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", text)[:35]


def _display(text: str) -> str:
    if len(text) > 48:
        return "\u2026" + text[-45:]
    return text


def mermaid_graph(edges: list[Edge], direction: str = "TB") -> str:
    """Build a Mermaid flowchart from edges."""
    if not edges:
        return "_No dependencies found._"

    nodes: set[str] = set()
    edge_lines: list[str] = []
    for e in sorted(edges, key=lambda x: (x.src, x.dst)):
        s, d = _safe_id(e.src), _safe_id(e.dst)
        nodes.add(e.src)
        nodes.add(e.dst)
        edge_lines.append(f'    "{s}" --|" {e.kind} "| "{d}"')

    node_defs = "\n".join(f'    "{_safe_id(n)}"["{_display(n)}"]' for n in sorted(nodes))
    return f"```mermaid\ngraph {direction}\n{node_defs}\n{'\n'.join(edge_lines)}\n```\n"


# ===================================================================
# Report generation
# ===================================================================

def generate_report(project: str, py_edges: list[Edge], ts_edges: list[Edge],
                    yaml_edges: list[Edge], snapshot_path: Path, verbose: bool) -> str:

    old = load_snapshot(snapshot_path)
    all_edges = py_edges + ts_edges + yaml_edges
    changes = compute_diff(old, all_edges)
    is_first = old is None or len(old["edges"]) == 0

    lines = [
        "<!--",
        "Generated by scripts/gen_deps.py -- DO NOT edit manually.",
        f"   Regenerate: python scripts/gen_deps.py --project {project}",
        f"   Timestamp: {datetime.now(timezone.utc).isoformat()}",
        "-->",
        "",
        f"## {project} — Dependency Graph",
    ]

    if is_first:
        lines.append("> First run. All edges shown.")
    elif changes:
        lines.append("### Changes since last run")
        for c in sorted(changes):
            lines.append(f"- {c}")
    else:
        lines.append("> No dependency changes detected since last run.")
    lines.append("")

    # -- Python imports grouped by top-level package --
    py_groups: dict[str, list[Edge]] = {}
    for e in py_edges:
        grp = e.dst.split(".")[0] if "." in e.dst else "root"
        py_groups.setdefault(grp, []).append(e)

    lines.append("### Python Imports")
    lines.append(f"_{len(py_edges)} internal import edges detected._\n")

    for grp, ge in sorted(py_groups.items()):
        uniq = { (e.src, e.dst): e for e in ge }.values()
        ulist = list(uniq)
        lines.append(f"**Group: `{grp}`** ({len(ulist)} edges)")
        if verbose:
            for e in ulist[:20]:
                lines.append(f"- `{e.src}` -> `{e.dst}`")
        if len(ulist) > 20:
            lines.append(f"_... and {len(ulist)-20} more edges_")
        lines.append("")

    # -- TypeScript Mermaid graph --
    lines.append("### TypeScript / TSX Modules")
    lines.append(f"_{len(ts_edges)} internal module edges detected._\n")
    lines.append("**Mermaid Graph:**")
    lines.append(mermaid_graph(ts_edges, "LR"))
    lines.append("")

    # -- Docker Compose --
    lines.append("### Docker Compose Services")
    if yaml_edges:
        svcs = {e.dst for e in yaml_edges if not e.dst.startswith("volume:")}
        lines.append(f"_**{len(svcs)}** services detected:_")
        for s in sorted(svcs):
            lines.append(f"- `{s}`")
        lines.append("")
        lines.append("**Mermaid Graph:**")
        lines.append(mermaid_graph(yaml_edges, "TB"))
    else:
        lines.append("_No docker-compose services detected._")

    return "\n".join(lines)


# ===================================================================
# MemPalace helper (optional)
# ===================================================================

def feed_to_mempalace(project: str, all_edges: list[Edge]) -> None:
    py_mods = {e.dst for e in all_edges if str(e.lang) == "python"}
    owned = [m for m in py_mods if any(m.startswith(p) for p in PROJECT_PY_PREFIXES)]
    if owned:
        print(f"[mempalace] Would feed {len(owned)} internal modules for '{project}'")


# ===================================================================
# CLI entry-point
# ===================================================================

def main() -> None:
    p = argparse.ArgumentParser(description="Automated dependency graph generator")
    p.add_argument("--project", default="", help="Project display name")
    p.add_argument("-o", "--output", default=None, help="Output path (default: docs/DEP_GRAPH.md)")
    p.add_argument("--no-mempalace", action="store_true", help="Skip MemPalace feed")
    p.add_argument("-v", "--verbose", action="store_true", help="List all edges individually")
    args = p.parse_args()

    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent

    if not args.project:
        args.project = repo_root.name.replace(" ", " ").title()

    print(f"Scanning project: {args.project}")
    print(f"  Repo root: {repo_root}\n")

    py_edges    = scan_python_imports(repo_root)
    ts_edges    = scan_typescript_imports(repo_root)
    yaml_edges  = scan_yaml_services(repo_root)
    total       = len(py_edges) + len(ts_edges) + len(yaml_edges)
    print(f"Found {total} edges: Python={len(py_edges)}, TS={len(ts_edges)}, YAML={len(yaml_edges)}\n")

    out     = Path(args.output) if args.output else repo_root / "docs" / "DEP_GRAPH.md"
    snap    = out.parent / ".dep_graph_snapshot.json"

    report  = generate_report(args.project, py_edges, ts_edges, yaml_edges, snap, args.verbose)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"Report written to: {out}")

    save_snapshot(snap, args.project, py_edges + ts_edges + yaml_edges)
    print(f"Snapshot saved to: {snap}")

    if not args.no_mempalace:
        feed_to_mempalace(args.project, py_edges + ts_edges + yaml_edges)


if __name__ == "__main__":
    main()
