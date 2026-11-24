"""Title-alignment helpers for storyline bag hygiene (reader + batch clean)."""

from __future__ import annotations

import re
from typing import Any


_TITLE_STOP = frozenset(
    {
        "the", "and", "for", "with", "from", "that", "this", "amid", "ahead",
        "after", "over", "into", "near", "fueling", "ongoing", "shares", "stock",
        "stocks", "market", "markets", "episode", "story", "rise", "fall", "slip",
    }
)
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9'-]{3,}")


def title_match_tokens(title: str) -> set[str]:
    return {
        t
        for t in _TOKEN_RE.findall((title or "").lower())
        if t not in _TITLE_STOP
    }


def article_title_aligns_with_story(story_title: str, article_title: str) -> bool:
    arc = title_match_tokens(story_title)
    if not arc:
        return True
    head = (article_title or "").lower()
    at = title_match_tokens(article_title)
    if arc & at:
        return True
    for tok in arc:
        if len(tok) >= 5 and tok in head:
            return True
    return False


def citations_aligned_with_story(
    title: str, citations: list[dict[str, Any]], *, limit: int = 8
) -> list[dict[str, Any]]:
    if not citations:
        return []
    arc_tokens = title_match_tokens(title)
    if not arc_tokens:
        return citations[:limit]
    scored: list[tuple[int, dict[str, Any]]] = []
    for cite in citations:
        head = str(cite.get("title") or "")
        overlap = len(arc_tokens & title_match_tokens(head))
        if overlap == 0:
            for tok in arc_tokens:
                if len(tok) >= 5 and tok in head.lower():
                    overlap = 1
                    break
        if overlap > 0:
            scored.append((overlap, cite))
    if not scored:
        return []
    scored.sort(key=lambda x: (-x[0], str(x[1].get("published_at") or "")))
    return [c for _, c in scored[:limit]]