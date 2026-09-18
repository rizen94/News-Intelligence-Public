#!/usr/bin/env python3
"""
Pull latest weights for configured Ollama models (same tags, updated blobs).

Uses config.settings.ollama_pull_model_names() — typically:
  nomic-embed-text, primary (llama3.1:8b), secondary (mistral-nemo:12b by default), Phi/Qwen when configured.
Optional large models (e.g. llama3.1:70b): set OLLAMA_EXTRA_PULL_MODELS=llama3.1:70b
Verify installed names vs config: PYTHONPATH=api uv run python api/scripts/verify_ollama_model_tags.py

Run from repo root (requires `ollama` on PATH):
  PYTHONPATH=api uv run python api/scripts/refresh_ollama_models.py

Optional cron (weekly):
  0 4 * * 0 cd /path/to/repo && PYTHONPATH=api uv run python api/scripts/refresh_ollama_models.py >>/var/log/ollama-refresh.log 2>&1
"""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, api_dir)

    try:
        from config.settings import ollama_pull_model_names
    except Exception as e:
        print(f"ERROR: cannot load settings: {e}", file=sys.stderr)
        return 1

    names = ollama_pull_model_names()
    if not names:
        print("No Ollama model tags configured to pull.")
        return 0

    print("Refreshing Ollama models:", ", ".join(names))
    rc_all = 0
    for name in names:
        print(f"\n--- ollama pull {name} ---")
        p = subprocess.run(
            ["ollama", "pull", name],
            check=False,
        )
        if p.returncode != 0:
            rc_all = p.returncode
            print(f"WARNING: pull failed for {name} (exit {p.returncode})", file=sys.stderr)

    if rc_all == 0:
        print("\nDone — all pulls succeeded.")
    else:
        print("\nFinished with errors — check output above.", file=sys.stderr)
    return rc_all


if __name__ == "__main__":
    sys.exit(main())
