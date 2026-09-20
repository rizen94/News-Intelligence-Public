#!/usr/bin/env python3
"""Remove config.runtime import lines wrongly inserted inside multi-line imports."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "api"
RUNTIME_IMPORT = (
    "from config.runtime import env_bool, env_float, env_int, env_pop, env_set, env_setdefault, env_str\n"
)
PATTERN = re.compile(
    r"(from [^\n]+ import \(\n)" + re.escape(RUNTIME_IMPORT),
    re.MULTILINE,
)


def fix_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if RUNTIME_IMPORT not in text:
        return False
    new = PATTERN.sub(r"\1", text)
    if new == text:
        return False
    # Ensure single runtime import after last top-level import block start
    if RUNTIME_IMPORT not in new:
        lines = new.splitlines(keepends=True)
        insert_at = 0
        for i, line in enumerate(lines):
            if line.startswith(("import ", "from ")) and not line.rstrip().endswith("("):
                insert_at = i + 1
            elif line.startswith(("import ", "from ")) and line.rstrip().endswith("("):
                # skip until closing paren
                for j in range(i + 1, len(lines)):
                    if ")" in lines[j]:
                        insert_at = j + 1
                        break
        lines.insert(insert_at, RUNTIME_IMPORT)
        new = "".join(lines)
    path.write_text(new, encoding="utf-8")
    return True


def main() -> None:
    fixed = 0
    for path in API.rglob("*.py"):
        if fix_file(path):
            fixed += 1
            print(path.relative_to(ROOT))
    print(f"Fixed {fixed} files")


if __name__ == "__main__":
    main()
