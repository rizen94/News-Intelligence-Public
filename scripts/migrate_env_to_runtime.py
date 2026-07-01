#!/usr/bin/env python3
"""Migrate os.environ reads to config.runtime public accessors (SSOT bake)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "api"

SKIP_DIRS = {".venv", "__pycache__", "nri_core", "archive"}
SKIP_FILES = {
    API / "config" / "runtime.py",
    API / "config" / "settings.py",
    API / "config" / "paths.py",
    API / "config" / "logging_config.py",
}

IMPORT_LINE = "from config.runtime import env_bool, env_float, env_int, env_pop, env_set, env_setdefault, env_str\n"

GET_RE = re.compile(r"os\.environ\.get\(")
GETENV_RE = re.compile(r"os\.getenv\(")
SET_RE = re.compile(r"os\.environ\[([^\]]+)\]\s*=")
POP_RE = re.compile(r"os\.environ\.pop\(")
SETDEFAULT_RE = re.compile(r"os\.environ\.setdefault\(")
BRACKET_GET_RE = re.compile(r"os\.environ\[([^\]]+)\](?!\s*=)")


def needs_runtime_import(text: str) -> bool:
    return bool(
        GET_RE.search(text)
        or GETENV_RE.search(text)
        or SET_RE.search(text)
        or POP_RE.search(text)
        or SETDEFAULT_RE.search(text)
        or BRACKET_GET_RE.search(text)
    )


def migrate_text(text: str) -> tuple[str, bool]:
    if not needs_runtime_import(text):
        return text, False

    new = text
    new = GET_RE.sub("env_str(", new)
    new = GETENV_RE.sub("env_str(", new)
    new = SET_RE.sub(r"env_set(\1, ", new)
    new = POP_RE.sub("env_pop(", new)
    new = SETDEFAULT_RE.sub("env_setdefault(", new)
    new = BRACKET_GET_RE.sub(r"env_str(\1", new)

    if "from config.runtime import" in new:
        changed = new != text
        return new, changed

    lines = new.splitlines(keepends=True)
    insert_at = 0
    doc_end = 0
    if lines and lines[0].startswith('"""'):
        for i, line in enumerate(lines[1:], 1):
            if '"""' in line:
                doc_end = i + 1
                break
    for i in range(doc_end, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("from __future__"):
            insert_at = i + 1
            continue
        if stripped.startswith(("import ", "from ")) and "config.runtime" not in stripped:
            insert_at = i + 1
            continue
        if stripped and not stripped.startswith("#"):
            break
    lines.insert(insert_at, IMPORT_LINE)
    return "".join(lines), True


def main() -> int:
    dry = "--dry-run" in sys.argv
    changed_files: list[Path] = []
    for path in sorted(API.rglob("*.py")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path in SKIP_FILES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if not needs_runtime_import(text):
            continue
        new_text, changed = migrate_text(text)
        if not changed:
            continue
        changed_files.append(path)
        if not dry:
            path.write_text(new_text, encoding="utf-8")

    print(f"{'Would migrate' if dry else 'Migrated'} {len(changed_files)} files")
    for p in changed_files[:20]:
        print(f"  - {p.relative_to(ROOT)}")
    if len(changed_files) > 20:
        print(f"  ... and {len(changed_files) - 20} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
