"""Application version SSOT — read from repo-root VERSION file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def get_version() -> str:
    version_file = Path(__file__).resolve().parents[2] / "VERSION"
    if version_file.is_file():
        text = version_file.read_text(encoding="utf-8").strip()
        if text:
            return text
    return "10.1.0"


__version__ = get_version()
