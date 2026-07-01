#!/usr/bin/env python3
"""Repository complexity inventory for unification baseline."""

from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "api"
WEB = ROOT / "web" / "src"
DOCS = ROOT / "docs"


def count_lines(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return 0


def scan_py(base: Path) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for p in base.rglob("*.py"):
        if any(x in p.parts for x in (".venv", "__pycache__", "node_modules")):
            continue
        rel = str(p.relative_to(base).parent)
        out[rel] += count_lines(p)
    return dict(sorted(out.items(), key=lambda x: -x[1]))


def main() -> None:
    py_files = list(API.rglob("*.py"))
    py_files = [p for p in py_files if ".venv" not in p.parts and "__pycache__" not in p.parts]
    ts_files = list(WEB.rglob("*.ts")) + list(WEB.rglob("*.tsx"))
    md_files = list(DOCS.rglob("*.md"))

    nri_core = API / "nri_core"
    print("=== News Intelligence complexity inventory ===")
    print(f"Python files (api/): {len(py_files)}")
    print(f"TypeScript files (web/src): {len(ts_files)}")
    print(f"Markdown files (docs/): {len(md_files)}")
    print(f"nri_core Python files: {len(list(nri_core.rglob('*.py'))) if nri_core.exists() else 0}")
    print()
    print("Top api/ directories by LOC:")
    by_dir = scan_py(API)
    for d, loc in list(by_dir.items())[:15]:
        print(f"  {d or '.'}: {loc:,}")


if __name__ == "__main__":
    main()
