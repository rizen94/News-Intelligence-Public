"""Title normalization and similarity for episode deduplication (no DB)."""

from __future__ import annotations

import re
from difflib import SequenceMatcher


def normalize_episode_title(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "").strip().lower())


def episode_title_similarity(a: str, b: str) -> float:
    na, nb = normalize_episode_title(a), normalize_episode_title(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    return SequenceMatcher(None, na, nb).ratio()
