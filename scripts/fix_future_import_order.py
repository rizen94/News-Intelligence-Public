#!/usr/bin/env python3
"""Ensure from __future__ comes before config.runtime import (after shebang/docstring)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "api"
FUTURE = "from __future__ import annotations\n"
RUNTIME = (
    "from config.runtime import env_bool, env_float, env_int, env_pop, env_set, env_setdefault, env_str\n"
)


def fix_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if FUTURE not in text or RUNTIME not in text:
        return False
    fi = text.find(FUTURE)
    ri = text.find(RUNTIME)
    if fi < ri:
        return False
    # Remove both lines, reinsert in correct order after header
    text_wo = text.replace(FUTURE, "").replace(RUNTIME, "")
    lines = text_wo.splitlines(keepends=True)
    insert_at = 0
    if lines and lines[0].startswith("#!"):
        insert_at = 1
    if insert_at < len(lines) and lines[insert_at].strip().startswith('"""'):
        for i in range(insert_at + 1, len(lines)):
            if '"""' in lines[i]:
                insert_at = i + 1
                break
    lines.insert(insert_at, FUTURE)
    lines.insert(insert_at + 1, RUNTIME)
    path.write_text("".join(lines), encoding="utf-8")
    return True


def main() -> None:
    n = 0
    for path in API.rglob("*.py"):
        if fix_file(path):
            n += 1
            print(path.relative_to(ROOT))
    print(f"Fixed {n}")


if __name__ == "__main__":
    main()
