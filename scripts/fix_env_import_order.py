#!/usr/bin/env python3
"""Fix scripts where migrate_env_to_runtime inserted import before shebang."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "api"
IMPORT_RE = re.compile(
    r"^from config\.runtime import env_bool, env_float, env_int, env_pop, env_set, env_setdefault, env_str\n",
    re.MULTILINE,
)


def fix_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if "#!/usr/bin" not in text:
        return False
    if not text.startswith("from config.runtime import"):
        return False
    import_line = IMPORT_RE.search(text)
    if not import_line:
        return False
    line = import_line.group(0)
    rest = text[len(line) :]
    # Insert after shebang + optional module docstring
    lines = rest.splitlines(keepends=True)
    insert_at = 0
    if lines and lines[0].startswith("#!"):
        insert_at = 1
    if insert_at < len(lines) and lines[insert_at].strip().startswith('"""'):
        for i in range(insert_at + 1, len(lines)):
            if '"""' in lines[i]:
                insert_at = i + 1
                break
    lines.insert(insert_at, line)
    path.write_text("".join(lines), encoding="utf-8")
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
