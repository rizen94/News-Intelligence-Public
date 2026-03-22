"""
Topic Merge Suggestions — second-layer clustering over existing topic_clusters.
Finds semantically similar topics that could be merged (e.g. "Remove Former Prince Andrew"
and "Removing Prince Andrew Succession").
"""

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class TopicClusterInfo:
    """Lightweight topic cluster for similarity computation."""

    id: int
    cluster_name: str
    article_count: int
    keywords: list[str]


@dataclass
class MergeSuggestion:
    """A suggested merge of 2+ topics."""

    primary: TopicClusterInfo  # Keep this one
    secondary: TopicClusterInfo  # Merge into primary
    score: float
    reason: str


def _normalize_word(w: str) -> str:
    """Simple normalization: lowercase, strip, optional stem."""
    w = w.lower().strip()
    if len(w) <= 2:
        return w
    # Simple suffix strip for common variations (remove/removing, etc.)
    for suffix in ("ing", "ed", "tion", "sion", "s", "es"):
        if len(w) > len(suffix) + 2 and w.endswith(suffix):
            return w[: -len(suffix)]
    return w


def _get_words(text: str) -> set:
    """Extract normalized words from a topic name."""
    words = re.findall(r"[a-z0-9']+", text.lower())
    return {_normalize_word(w) for w in words if len(w) >= 2}


def _get_bigrams(text: str) -> set:
    """Extract bigrams (2-word phrases) for stronger matching."""
    words = text.lower().split()
    return {
        f"{words[i]} {words[i + 1]}"
        for i in range(len(words) - 1)
        if len(words[i]) >= 2 and len(words[i + 1]) >= 2
    }


def _compute_similarity(
    name1: str, keywords1: list[str], name2: str, keywords2: list[str]
) -> tuple[float, str]:
    """
    Compute similarity score (0-1) and a human-readable reason.
    Uses word overlap, bigram overlap, and optional keyword overlap.
    """
    words1 = _get_words(name1)
    words2 = _get_words(name2)
    bigrams1 = _get_bigrams(name1)
    bigrams2 = _get_bigrams(name2)

    # Word overlap (Jaccard-like, but we want high recall for "Prince Andrew" type matches)
    shared_words = words1 & words2
    union_words = words1 | words2
    word_score = len(shared_words) / len(union_words) if union_words else 0

    # Bigram overlap — strong signal (e.g. "Prince Andrew" in both)
    shared_bigrams = bigrams1 & bigrams2
    bigram_bonus = min(1.0, len(shared_bigrams) * 0.5) if shared_bigrams else 0

    # Shared significant phrase (2+ words) — very strong
    phrase_bonus = 0.4 if shared_bigrams else 0

    # Containment: one name largely contained in the other
    if words1 and words2:
        containment = len(shared_words) / min(len(words1), len(words2))
        if containment >= 0.5:
            phrase_bonus = max(phrase_bonus, 0.3)

    # Keyword overlap (if we have keywords)
    kw1 = set(k.lower() for k in (keywords1 or []) if isinstance(k, str) and len(k) >= 2)
    kw2 = set(k.lower() for k in (keywords2 or []) if isinstance(k, str) and len(k) >= 2)
    if kw1 and kw2:
        kw_overlap = len(kw1 & kw2) / len(kw1 | kw2) if (kw1 | kw2) else 0
        word_score = max(word_score, kw_overlap * 0.8)

    score = min(1.0, word_score * (1 + phrase_bonus) + bigram_bonus)

    # Build reason
    reasons = []
    if shared_bigrams:
        reasons.append(f"shared phrase: '{list(shared_bigrams)[0]}'")
    if shared_words:
        reasons.append(f"shared words: {', '.join(sorted(shared_words)[:5])}")
    reason = "; ".join(reasons) if reasons else f"similarity {score:.2f}"

    return score, reason


def _keywords_list_from_db(raw: Any) -> list[str]:
    """Normalize topics.keywords from DB (jsonb list or dict) into string keywords."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw if isinstance(x, str) and len(x.strip()) >= 2]
    if isinstance(raw, dict):
        inner = raw.get("keywords", raw.get("terms", []))
        if isinstance(inner, list):
            return [str(x) for x in inner if isinstance(x, str) and len(x.strip()) >= 2]
    return []


def find_best_matching_topic(
    name: str,
    keywords: list[str] | None,
    existing_rows: list[tuple[int, str, Any]],
    min_score: float = 0.58,
) -> tuple[int, str, float] | None:
    """
    Pick the existing topic row that best matches the proposed name/keywords.

    Used by automation (topic_clustering) to attach articles to canonical topics
    instead of inserting near-duplicate rows. Scoring matches merge_suggestions.
    """
    name = (name or "").strip()
    if not name or not existing_rows:
        return None
    kw = keywords if isinstance(keywords, list) else []
    best: tuple[int, str, float] | None = None
    for tid, existing_name, raw_kw in existing_rows:
        if not existing_name or not isinstance(existing_name, str):
            continue
        ekw = _keywords_list_from_db(raw_kw)
        score, _reason = _compute_similarity(name, kw, existing_name.strip(), ekw)
        if score >= min_score and (best is None or score > best[2]):
            best = (int(tid), existing_name.strip(), float(score))
    return best


def get_merge_suggestions(
    topics: list[dict[str, Any]],
    min_score: float = 0.35,
    max_suggestions: int = 50,
    name_key: str = "name",
) -> list[dict[str, Any]]:
    """
    Analyze a list of topics and return suggested merges.
    Topics can be dicts with id, name/cluster_name, article_count, keywords, etc.
    """
    # Normalize to TopicClusterInfo
    infos: list[TopicClusterInfo] = []
    for t in topics:
        name = t.get(name_key) or t.get("cluster_name") or ""
        if not name or not isinstance(name, str) or len(name.strip()) < 2:
            continue
        kw = t.get("keywords") or t.get("cluster_keywords") or []
        if isinstance(kw, dict):
            kw = kw.get("keywords", []) or []
        infos.append(
            TopicClusterInfo(
                id=t.get("id", 0),
                cluster_name=name.strip(),
                article_count=t.get("article_count", 0) or t.get("recent_articles", 0),
                keywords=kw if isinstance(kw, list) else [],
            )
        )

    suggestions: list[MergeSuggestion] = []
    used = set()  # Track which topics we've already suggested (as secondary)

    for i, a in enumerate(infos):
        for j, b in enumerate(infos):
            if i >= j:
                continue
            if (a.id, b.id) in used or (b.id, a.id) in used:
                continue
            score, reason = _compute_similarity(
                a.cluster_name, a.keywords, b.cluster_name, b.keywords
            )
            if score < min_score:
                continue
            # Prefer keeping the one with more articles
            if a.article_count >= b.article_count:
                primary, secondary = a, b
            else:
                primary, secondary = b, a
            suggestions.append(
                MergeSuggestion(
                    primary=primary, secondary=secondary, score=round(score, 3), reason=reason
                )
            )
            used.add((primary.id, secondary.id))

    # Sort by score descending
    suggestions.sort(key=lambda s: s.score, reverse=True)

    # Limit
    suggestions = suggestions[:max_suggestions]

    return [
        {
            "primary": {
                "id": s.primary.id,
                "cluster_name": s.primary.cluster_name,
                "article_count": s.primary.article_count,
            },
            "secondary": {
                "id": s.secondary.id,
                "cluster_name": s.secondary.cluster_name,
                "article_count": s.secondary.article_count,
            },
            "score": s.score,
            "reason": s.reason,
            "suggested_name": s.primary.cluster_name,  # Keep primary's name
        }
        for s in suggestions
    ]
