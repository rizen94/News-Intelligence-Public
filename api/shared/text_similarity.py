"""Shared string similarity helpers for entity resolution and deduplication."""

from __future__ import annotations

from difflib import SequenceMatcher


def normalize_match_text(value: str) -> str:
    return " ".join((value or "").lower().split())


def sequence_similarity(a: str, b: str) -> float:
    """Ratio similarity in [0, 1] using normalized lowercase strings."""
    na = normalize_match_text(a)
    nb = normalize_match_text(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()
