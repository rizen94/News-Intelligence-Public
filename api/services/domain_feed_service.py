"""Domain Feed Service — derive enrichment cycles from domain YAML specs.

Production has migrated away from config-driven enrichment to DB-driven pending-items,
but ``collection_executor.py`` (the dead code path) still reaches for
``domain_feed_service.get_domain_config(domain_name)`` expecting a dict with:

    enrichment_cycles      list[dict]  – each entry {items, subtypes}
    enrichment_item_limit  int
    analysis_phases        list[dict]  – each entry {type, name, enabled}
    step_time_budgets      dict[str, float]

This module **derives** that surface from the canonical domain YAML files in
``api/config/domains/*.yaml``, so there is no hand-rolled enrichment schema to maintain.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────────
_API_DIR = Path(__file__).resolve().parent.parent               # api/
DOMAINS_DIR = _API_DIR / "config" / "domains"                 # api/config/domains/


# ── Defaults (when domain YAML lacks explicit enrichment data) ───────────
_DEFAULT_ITEM_LIMIT = 20

_DEFAULT_PHASES = [
    {"type": "content_enrichment", "name": "Content Enrichment", "enabled": True},
    {"type": "entity_extraction", "name": "Entity Extraction", "enabled": True},
    {"type": "sentiment_analysis", "name": "Sentiment Analysis", "enabled": True},
]

_DEFAULT_BUDGETS = {p["name"]: 30.0 for p in _DEFAULT_PHASES}


# ── Helper ───────────────────────────────────────────────────────────────
def _load_domain_spec(domain_name: str) -> dict[str, Any] | None:
    """Load the YAML spec for *domain_name* (case-insensitive)."""
    domain_key = domain_name.lower().replace(" ", "-")
    candidate = DOMAINS_DIR / f"{domain_key}.yaml"

    if not candidate.is_file():
        logger.warning(
            "Domain feed config not found at %s — returning empty spec.", candidate
        )
        return None

    with open(candidate, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _feeds_from_spec(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract a flat list of feed dicts from ``data_sources.rss.seed_feed_urls``."""
    feeds: list[dict[str, Any]] = []
    try:
        raw = spec["data_sources"]["rss"]["seed_feed_urls"]
    except (KeyError, TypeError):
        return feeds

    for entry in raw:
        if isinstance(entry, str):
            feeds.append({"feed_url": entry})
        elif isinstance(entry, dict):
            entry.setdefault("feed_url", "")
            feeds.append(dict(entry))
    return feeds


def _subtypes_for_feed(feed: dict[str, Any]) -> list[str]:
    """arc_relevance when present; fall back to [\"general\"]."""
    arcs = feed.get("arc_relevance")
    if isinstance(arcs, list) and arcs:
        return [str(s) for s in arcs]
    return ["general"]


def _build_enrichment_cycles(feeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Turn each RSS feed into an enrichment cycle entry."""
    cycles: list[dict[str, Any]] = []
    for i, feed in enumerate(feeds):
        url = feed.get("feed_url", "")
        cycles.append({
            "subtypes": _subtypes_for_feed(feed),
            "items": [
                {
                    "url": url,
                    "_source": feed.get("feed_name", f"feed-{i}"),
                    "_type": "rss_seed",
                    "_priority": i + 1,
                }
            ],
        })
    return cycles


def _item_limit_from_spec(spec: dict[str, Any]) -> int:
    """Prefer workload_assumptions.expected_active_feeds; fall back to default."""
    try:
        return spec["workload_assumptions"]["expected_active_feeds"] or 20
    except (KeyError, TypeError):
        return _DEFAULT_ITEM_LIMIT


def _phases_from_spec(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull analysis_phases from domain YAML if present."""
    try:
        raw = spec.get("analysis_phases")
        if isinstance(raw, list) and len(raw) > 0:
            return [dict(p) for p in raw]
    except Exception:
        pass
    return list(_DEFAULT_PHASES)


# ── Public API ───────────────────────────────────────────────────────────

def get_domain_config(domain_name: str) -> dict[str, Any]:
    """Return enrichment-ready config derived from the domain YAML spec.

    Returns a dict keyed exactly as *collection_executor.py* expects:

        enrichment_cycles
        enrichment_item_limit
        analysis_phases
        step_time_budgets

    If the domain YAML is missing or empty, sensible defaults are returned
    so that callers never crash on ``KeyError`` / ``AttributeError``.
    """
    spec = _load_domain_spec(domain_name)
    feeds = _feeds_from_spec(spec) if spec else []

    return {
        "enrichment_cycles": _build_enrichment_cycles(feeds),
        "enrichment_item_limit": _item_limit_from_spec(spec) if spec else _DEFAULT_ITEM_LIMIT,
        "analysis_phases": _phases_from_spec(spec) if spec else _DEFAULT_PHASES,
        "step_time_budgets": dict(_DEFAULT_BUDGETS),
    }
