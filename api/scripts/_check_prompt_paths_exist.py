#!/usr/bin/env python3
"""One-shot gate: every declared file-based LLM prompt must exist on disk.

Sources:
  1. ``api/config/features.yaml`` module entries ending in ``.md`` under
     ``api/config/prompts/`` (skip ``_archived/``).
  2. Python ``PROMPT_PATH`` / ``_PROMPT_PATH`` / ``PUBLISH_PROMPT_PATH`` Path
     chains under ``api/`` that resolve to ``config/prompts/**/*.md``
     (skip ``_archived/`` and ``api/_archived/``).

Exit 0 when all live paths exist; exit 1 listing missing paths.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # api/
REPO = ROOT.parent
FEATURES = ROOT / "config" / "features.yaml"
PROMPTS_ROOT = ROOT / "config" / "prompts"

_MD_IN_FEATURES = re.compile(
    r"^\s*-\s+(api/config/prompts/[^\s#]+\.md)\s*$", re.MULTILINE
)
_PATH_NAME_RE = re.compile(
    r"^(PROMPT_PATH|_PROMPT_PATH|PUBLISH_PROMPT_PATH)$"
)


def _is_archived(rel_posix: str) -> bool:
    return "/_archived/" in f"/{rel_posix}" or rel_posix.startswith("_archived/")


def _features_prompt_paths() -> set[Path]:
    if not FEATURES.is_file():
        return set()
    text = FEATURES.read_text(encoding="utf-8", errors="replace")
    out: set[Path] = set()
    for m in _MD_IN_FEATURES.finditer(text):
        rel = m.group(1)
        if _is_archived(rel):
            continue
        out.add(REPO / rel)
    return out


def _resolve_path_assign(node: ast.AST, *, api_root: Path) -> Path | None:
    """Resolve ``Path(__file__).resolve().parents[N] / "a" / ... / "x.md"``."""
    if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Div):
        return None

    parts: list[str] = []
    cur: ast.AST = node
    while isinstance(cur, ast.BinOp) and isinstance(cur.op, ast.Div):
        right = cur.right
        if isinstance(right, ast.Constant) and isinstance(right.value, str):
            parts.append(right.value)
        else:
            return None
        cur = cur.left

    # Expect Path(__file__).resolve().parents[N] or Path(__file__).parent...
    # We only care that the joined relative path ends under config/prompts.
    parts.reverse()
    if not parts or not parts[-1].endswith(".md"):
        return None
    if "prompts" not in parts:
        return None
    try:
        idx = parts.index("config")
    except ValueError:
        try:
            idx = parts.index("prompts")
            # parents[1] == api when chain is config/prompts/...
            return api_root / Path(*parts[idx:])
        except ValueError:
            return None
    return api_root / Path(*parts[idx:])


def _python_prompt_paths() -> set[Path]:
    out: set[Path] = set()
    skip_dirs = {
        ".venv",
        "node_modules",
        "__pycache__",
        ".git",
        "archive",
        "_archived",
    }
    for path in ROOT.rglob("*.py"):
        norm = str(path).replace("\\", "/")
        if any(f"/{d}/" in norm or norm.endswith(f"/{d}") for d in skip_dirs):
            continue
        if "/scripts/_check_prompt_paths_exist.py" in norm:
            continue
        try:
            src = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(src, filename=str(path))
        except (OSError, SyntaxError):
            continue
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            for t in node.targets:
                if isinstance(t, ast.Name) and _PATH_NAME_RE.match(t.id):
                    resolved = _resolve_path_assign(node.value, api_root=ROOT)
                    if resolved is None:
                        continue
                    rel = resolved.relative_to(ROOT).as_posix()
                    if _is_archived(rel):
                        continue
                    out.add(resolved)
    return out


def main() -> int:
    required = _features_prompt_paths() | _python_prompt_paths()
    if not required:
        print("No live prompt path declarations found (unexpected).", file=sys.stderr)
        return 1

    missing = sorted(p for p in required if not p.is_file())
    ok = sorted(p for p in required if p.is_file())

    print(f"Live prompt paths checked: {len(required)} ({len(ok)} present)")
    for p in ok:
        try:
            print(f"  OK  {p.relative_to(REPO)}")
        except ValueError:
            print(f"  OK  {p}")

    if missing:
        print("\nMissing:", file=sys.stderr)
        for p in missing:
            try:
                print(f"  MISSING  {p.relative_to(REPO)}", file=sys.stderr)
            except ValueError:
                print(f"  MISSING  {p}", file=sys.stderr)
        return 1

    # Soft note: archived prompts are not gated
    archived = list(PROMPTS_ROOT.glob("_archived/**/*.md")) if PROMPTS_ROOT.is_dir() else []
    if archived:
        print(f"Archived prompt markdown (not gated): {len(archived)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
