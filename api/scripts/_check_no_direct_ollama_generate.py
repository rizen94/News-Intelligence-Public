#!/usr/bin/env python3
"""Grep gate: production code must not call Ollama /api/generate or /api/embeddings
outside the CB hub and unload helpers.

Allowed paths (substring match on file path):
  - shared/services/llm_service.py
  - shared/backlog_orchestration.py  (keep_alive unload)
  - shared/llm/resource_manager.py   (keep_alive unload)
  - deep_content_synthesis.py       (streaming preview only; shed-gated)

Exit 1 if any other *.py under api/ still posts to those endpoints.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERN = re.compile(r"/api/(generate|embeddings)")

ALLOW_PATH_SUBSTR = (
    "shared/services/llm_service.py",
    "shared/backlog_orchestration.py",
    "shared/llm/resource_manager.py",
    # Interactive stream remains raw HTTP; admission gated by any_ollama_circuit_shedding
    "services/deep_content_synthesis.py",
    # This gate script and starve debug
    "scripts/_check_no_direct_ollama_generate.py",
    "scripts/_debug_ollama_cb_starve.py",
    "scripts/_debug_ollama_cb_trip.py",
)


def _allowed(path: Path) -> bool:
    s = str(path).replace("\\", "/")
    return any(a in s for a in ALLOW_PATH_SUBSTR)


def main() -> int:
    hits: list[str] = []
    for path in ROOT.rglob("*.py"):
        norm = str(path).replace("\\", "/")
        # Skip venvs, archives, and accidental nested workspace copies under /opt
        if any(
            x in norm
            for x in (
                "/archive/",
                "/.venv/",
                "/home/",
                "/node_modules/",
                "/__pycache__/",
            )
        ):
            continue
        if _allowed(path):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if PATTERN.search(line) and not line.lstrip().startswith("#"):
                # Docstrings / comments about the endpoint are OK if not a URL concat
                if "/api/generate" not in line and "/api/embeddings" not in line:
                    continue
                if "f\"" in line or "f'" in line or '"' in line or "'" in line:
                    if any(
                        tok in line
                        for tok in (
                            "/api/generate",
                            "/api/embeddings",
                        )
                    ) and (
                        "post(" in line.lower()
                        or "f\"{" in line
                        or "f'{" in line
                        or "+ \"/api/" in line
                        or "+ '/api/" in line
                        or "/api/generate\"" in line
                        or "/api/generate'" in line
                        or "/api/embeddings\"" in line
                        or "/api/embeddings'" in line
                    ):
                        hits.append(f"{path.relative_to(ROOT)}:{i}:{line.strip()[:120]}")

    if hits:
        print("FAIL: direct Ollama HTTP outside hub/unload:")
        for h in hits:
            print(" ", h)
        return 1
    print("OK: no unexpected /api/generate or /api/embeddings callers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
