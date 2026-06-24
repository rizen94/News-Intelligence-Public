"""Two-tier mention matching: anchor exact then blocked fuzzy."""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from nri_core.config import get_config
from nri_core.spine.store import postgres_store

ANCHOR_KEYS = {
    "cik": "cik",
    "lei": "lei",
    "fec_id": "fec_id",
    "qid": "wikidataId",
    "opensanctions": "opensanctions",
}


@dataclass
class MatchResult:
    ftm_id: str | None
    score: float
    tier: int
    status: str
    candidates: list[dict]


def _normalize_name(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text)


def _fuzzy_score(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize_name(a), _normalize_name(b)).ratio()


def resolve_mention(
    text: str,
    anchors: dict[str, str] | None = None,
    schema_name: str | None = None,
) -> MatchResult:
    cfg = get_config()
    anchors = anchors or {}

    # Tier 1: exact anchor lookup
    for key, anchor_type in ANCHOR_KEYS.items():
        value = anchors.get(key) or anchors.get(anchor_type)
        if not value:
            continue
        hits = postgres_store.lookup_by_anchor(anchor_type, str(value))
        if len(hits) == 1:
            return MatchResult(
                ftm_id=hits[0]["id"],
                score=1.0,
                tier=1,
                status="auto_linked",
                candidates=hits,
            )
        if hits:
            return MatchResult(
                ftm_id=None,
                score=0.0,
                tier=1,
                status="parked",
                candidates=hits,
            )

    # Tier 2: blocked fuzzy against name index
    candidates = postgres_store.search_name_candidates(text, schema_name=schema_name, limit=50)
    scored: list[dict] = []
    for cand in candidates:
        caption = cand.get("caption") or ""
        score = _fuzzy_score(text, caption)
        scored.append({**cand, "score": score})
    scored.sort(key=lambda x: x["score"], reverse=True)

    if not scored:
        return MatchResult(ftm_id=None, score=0.0, tier=2, status="parked", candidates=[])

    best = scored[0]
    score = float(best["score"])
    if score >= cfg.ftm_auto_link_threshold:
        status = "auto_linked"
        ftm_id = best["id"]
    elif score >= cfg.ftm_park_threshold:
        status = "parked"
        ftm_id = None
    else:
        status = "parked"
        ftm_id = None

    return MatchResult(
        ftm_id=ftm_id,
        score=score,
        tier=2,
        status=status,
        candidates=scored[:10],
    )
