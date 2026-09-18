#!/usr/bin/env python3
"""Close unbalanced env_set( ... calls introduced by migrate_env_to_runtime."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "api"


def balance_env_set_calls(text: str) -> str:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if "env_set(" in line:
            chunk = line
            open_p = chunk.count("(") - chunk.count(")")
            j = i + 1
            while open_p > 0 and j < len(lines):
                chunk += lines[j]
                open_p = chunk.count("(") - chunk.count(")")
                j += 1
            if open_p > 0:
                chunk = chunk.rstrip("\n") + ")" * open_p + "\n"
            out.append(chunk)
            i = j
            continue
        out.append(line)
        i += 1
    return "".join(out)


def main() -> None:
    n = 0
    for path in API.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "env_set(" not in text:
            continue
        new = balance_env_set_calls(text)
        if new != text:
            path.write_text(new, encoding="utf-8")
            n += 1
            print(path.relative_to(ROOT))
    print(f"Fixed {n}")


if __name__ == "__main__":
    main()
