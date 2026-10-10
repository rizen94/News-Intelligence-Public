"""
AI research storyline policy: thin paper clusters are one-offs; multi-paper arcs only.

Used by discovery, proactive promote, and reader-facing story_kind stamping.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

AI_DOMAIN_KEYS = frozenset({"artificial-intelligence", "artificial_intelligence"})
# One or two papers/articles → explainer one-off (not an evolving storyline arc).
ONE_OFF_MAX_ARTICLES = 2
# Prefer at least this many member articles before promoting a full AI storyline.
STORYLINE_MIN_ARTICLES = 3

_ARXIV_HOST_RE = re.compile(r"(?:^|\.)arxiv\.org$", re.I)
_ARXIV_LABEL_RE = re.compile(r"arxiv", re.I)


def is_ai_domain(domain: str | None) -> bool:
    if not domain:
        return False
    key = domain.strip().lower().replace("_", "-")
    return key == "artificial-intelligence" or domain.strip().lower() in AI_DOMAIN_KEYS


def normalize_publisher_key(source_domain: str | None, url: str | None = None) -> str:
    """Collapse fragmented arXiv labels to one publisher key."""
    raw = (source_domain or "").strip().lower()
    host = ""
    if url:
        try:
            host = (urlparse(url).hostname or "").lower()
        except Exception:
            host = ""
    if host and _ARXIV_HOST_RE.search(host):
        return "arxiv.org"
    if raw and (_ARXIV_LABEL_RE.search(raw) or "arxiv.org" in raw):
        return "arxiv.org"
    if host:
        return host
    return raw or "unknown"


def unique_article_count(articles: list[Any]) -> int:
    """Count distinct member articles (ids or urls)."""
    ids: set[int] = set()
    urls: set[str] = set()
    for a in articles or []:
        if isinstance(a, dict):
            aid = a.get("id") if a.get("id") is not None else a.get("article_id")
            url = (a.get("url") or "").strip().lower()
        else:
            aid = getattr(a, "article_id", None) or getattr(a, "id", None)
            url = (getattr(a, "url", None) or "").strip().lower()
        if aid is not None:
            try:
                n = int(aid)
                if n > 0:
                    ids.add(n)
                    continue
            except (TypeError, ValueError):
                pass
        if url:
            urls.add(url)
    return len(ids) + len(urls)


def distinct_publisher_count(articles: list[Any]) -> int:
    keys: set[str] = set()
    for a in articles or []:
        if isinstance(a, dict):
            keys.add(
                normalize_publisher_key(a.get("source_domain"), a.get("url"))
            )
        else:
            keys.add(
                normalize_publisher_key(
                    getattr(a, "source_domain", None),
                    getattr(a, "url", None),
                )
            )
    keys.discard("unknown")
    return len(keys) if keys else 0


def is_thin_research_cluster(domain: str | None, articles: list[Any]) -> bool:
    """True when this AI cluster should surface as a one-off (≤2 papers)."""
    if not is_ai_domain(domain):
        return False
    return unique_article_count(articles) <= ONE_OFF_MAX_ARTICLES


def should_create_full_storyline(domain: str | None, articles: list[Any]) -> bool:
    """
    Full automation-enabled storyline only when the cluster has enough papers
    to look like an arc (≥3 articles). Thin AI clusters are still savable as
    one-offs via story_kind.
    """
    if not is_ai_domain(domain):
        return True
    return unique_article_count(articles) >= STORYLINE_MIN_ARTICLES


def story_kind_for_cluster(domain: str | None, articles: list[Any]) -> str:
    if is_thin_research_cluster(domain, articles):
        return "one_off"
    return "storyline"
