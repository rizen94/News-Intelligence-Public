#!/usr/bin/env python3
"""
Compare FastAPI registered routes with frontend /api/... paths (web/src).

Exit 0 when every frontend path matches at least one backend route (method + path pattern).
Exit 1 and print misses when gaps exist.

Usage:
  PYTHONPATH=api uv run python api/scripts/audit_api_route_alignment.py
  PYTHONPATH=api uv run python api/scripts/audit_api_route_alignment.py --write-docs
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WEB_SRC = REPO / "web" / "src"

# getApi().get|post|put|delete|patch(`...`) or ('...')
HTTP_CALL = re.compile(
    r"""getApi\(\)\.(get|post|put|delete|patch)\s*\(\s*"""
    r"""(?:`([^`]+)`|'([^']+)'|"([^"]+)")""",
    re.IGNORECASE,
)

# fetch(`...`, { method: 'POST' })
FETCH_CALL = re.compile(
    r"""fetch\s*\(\s*`([^`]+)`\s*,\s*\{[^}]*method:\s*['"](GET|POST|PUT|DELETE|PATCH)['"]""",
    re.IGNORECASE,
)

# api.post(`...`) in legacy jsx (axios instance named api)
LEGACY_API = re.compile(
    r"""\bapi\.(get|post|put|delete|patch)\s*\(\s*['"](/api/[^'"]+)['"]""",
    re.IGNORECASE,
)


def _norm_path(p: str) -> str:
    p = p.strip()
    if "?" in p:
        p = p.split("?", 1)[0]
    p = re.sub(r"\$\{[^}]+\}", "{param}", p)
    p = re.sub(r":\w+", "{param}", p)
    p = re.sub(r"/+", "/", p)
    if not p.startswith("/"):
        p = "/" + p
    return p.rstrip("/") or "/"


def _path_match(fe: str, be: str) -> bool:
    fe_parts = _norm_path(fe).split("/")
    be_parts = _norm_path(be).split("/")
    if len(fe_parts) != len(be_parts):
        return False
    for a, b in zip(fe_parts, be_parts):
        if a == b:
            continue
        if a == "{param}" or b == "{param}":
            continue
        if a.startswith("{") or b.startswith("{"):
            continue
        return False
    return True


def collect_backend_routes() -> list[tuple[str, str]]:
    sys.path.insert(0, str(REPO / "api"))
    from main import app

    out: list[tuple[str, str]] = []
    for r in app.routes:
        methods = getattr(r, "methods", None) or set()
        path = getattr(r, "path", None)
        if not path or not str(path).startswith("/api"):
            continue
        for m in methods:
            if m in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                out.append((m, str(path)))
    return sorted(set(out))


def collect_frontend_calls() -> list[tuple[str, str, str]]:
    calls: list[tuple[str, str, str]] = []
    for p in WEB_SRC.rglob("*"):
        if p.suffix not in (".ts", ".tsx", ".js", ".jsx"):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = str(p.relative_to(REPO))
        for m in HTTP_CALL.finditer(text):
            method = m.group(1).upper()
            path = m.group(2) or m.group(3) or m.group(4)
            if path and path.startswith("/api"):
                calls.append((rel, method, path))
        for m in FETCH_CALL.finditer(text):
            calls.append((rel, m.group(2).upper(), m.group(1)))
        for m in LEGACY_API.finditer(text):
            calls.append((rel, m.group(1).upper(), m.group(2)))
    seen: set[tuple[str, str]] = set()
    unique: list[tuple[str, str, str]] = []
    for item in calls:
        key = (item[1], _norm_path(item[2]))
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-docs", action="store_true", help="Write diagnostics/api_route_audit.txt")
    args = parser.parse_args()

    backend = collect_backend_routes()
    frontend = collect_frontend_calls()

    misses: list[tuple[str, str, str, str]] = []
    for rel, method, path in frontend:
        np = _norm_path(path)
        if np.startswith("/api/v4"):
            misses.append((rel, method, path, "obsolete /api/v4 prefix"))
            continue
        ok = any(m == method and _path_match(path, bp) for m, bp in backend)
        if not ok:
            path_ok = any(_path_match(path, bp) for _, bp in backend)
            hint = "path exists, method mismatch" if path_ok else "no matching route"
            misses.append((rel, method, path, hint))

    lines = [
        f"Backend routes: {len(backend)}",
        f"Frontend API paths (unique method+path): {len(frontend)}",
        f"Potential mismatches: {len(misses)}",
        "",
    ]
    for rel, method, path, hint in sorted(misses):
        lines.append(f"  [{method}] {path}  ({hint})  <- {rel}")
    if not misses:
        lines.append("All frontend API paths match a backend route.")

    report = "\n".join(lines)
    print(report)

    if args.write_docs:
        out = REPO / "diagnostics" / "api_route_audit.txt"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report + "\n", encoding="utf-8")
        print(f"\nWrote {out}")

    return 1 if misses else 0


if __name__ == "__main__":
    raise SystemExit(main())
