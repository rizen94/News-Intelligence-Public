#!/usr/bin/env python3
"""Fail if politics_2, finance_2, politics-2, or finance-2 appear outside historical migrations."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
_PATTERNS = (
    re.compile(r"politics_2"),
    re.compile(r"finance_2"),
    re.compile(r"politics-2"),
    re.compile(r"finance-2"),
)
_SCAN_ROOTS = (_REPO / "api", _REPO / "web", _REPO / "tests", _REPO / "docs")
_SKIP_PARTS = frozenset(
    {
        "api/database/migrations",
        "api/scripts/run_migration",
        "docs/LEGACY_DOMAIN_RETIREMENT",
        "api/scripts/copy_domain_silo",
        "api/scripts/audit_politics_finance",
        "api/scripts/check_domain_suffix_cruft.py",
        "docs/_archive",
        "docs/DOMAIN_CUTOVER",
        "docs/DOMAIN_EXTENSION_TEMPLATE.md",
        "repomix-output",
        "node_modules",
        ".venv",
        "tests/unit/test_politics2_finance2",
    }
)


def _should_scan(path: Path) -> bool:
    rel = path.relative_to(_REPO).as_posix()
    if not path.is_file():
        return False
    if path.suffix not in {".py", ".ts", ".tsx", ".yaml", ".yml", ".md", ".sql"}:
        return False
    for skip in _SKIP_PARTS:
        if skip in rel:
            return False
    return True


def main() -> int:
    hits: list[str] = []
    for root in _SCAN_ROOTS:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not _should_scan(path):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                for pat in _PATTERNS:
                    if pat.search(line):
                        hits.append(f"{path.relative_to(_REPO)}:{i}: {line.strip()[:120]}")
                        break
    if hits:
        print("Found politics/finance *_2 / *-2 suffix references (disallowed outside migrations):")
        for h in hits[:50]:
            print(f"  {h}")
        if len(hits) > 50:
            print(f"  ... and {len(hits) - 50} more")
        return 1
    print("OK: no politics_2/finance_2/politics-2/finance-2 cruft in api/web/tests/docs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
