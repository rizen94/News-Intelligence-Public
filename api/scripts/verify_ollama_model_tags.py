#!/usr/bin/env python3
"""
Compare locally installed Ollama image names (`ollama list`) with tags from
config.settings.ollama_pull_model_names() so ops can confirm pulls before deploy.

Exit 0 always if `ollama` is missing (CI / laptops without Ollama); prints warnings for missing tags.

  PYTHONPATH=api uv run python api/scripts/verify_ollama_model_tags.py
"""

from __future__ import annotations

import os
import subprocess
import sys


def _ollama_list_names() -> list[str] | None:
    try:
        p = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if p.returncode != 0:
        return None
    lines = [ln.strip() for ln in (p.stdout or "").splitlines() if ln.strip()]
    if not lines:
        return []
    # Skip header: NAME  ID  SIZE  MODIFIED
    out: list[str] = []
    for ln in lines[1:]:
        parts = ln.split()
        if parts:
            out.append(parts[0])
    return out


def main() -> int:
    api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, api_dir)
    try:
        from config.settings import ollama_pull_model_names
    except Exception as e:
        print(f"ERROR: cannot load settings: {e}", file=sys.stderr)
        return 1

    required = set(ollama_pull_model_names())
    installed = _ollama_list_names()
    if installed is None:
        print("ollama CLI not found or `ollama list` failed — skip tag verification.")
        return 0

    def _base(name: str) -> str:
        return name.split(":", 1)[0].strip().lower()

    installed_bases = {_base(x) for x in installed}
    missing: list[str] = []
    for tag in sorted(required):
        if not tag or "/" in tag:
            continue
        if _base(tag) not in installed_bases:
            missing.append(tag)

    print("Configured pull tags:", ", ".join(sorted(required)))
    print("Installed (ollama list):", ", ".join(installed) if installed else "(none)")
    if missing:
        print("WARNING — not obviously present (pull may be needed):", ", ".join(missing))
        print("Run: PYTHONPATH=api uv run python api/scripts/refresh_ollama_models.py")
        return 1
    print("OK — all configured Ollama tags appear present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
