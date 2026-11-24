"""Spine compounding — event rail health and gated auto_approve (no full HITL).

When chronological_events are flowing, domains may use auto_approve for scored
automation + continuation while patch v1 keeps embedding discovery dry-run only.
"""

from __future__ import annotations

import logging
from typing import Any

from api.config.runtime import env_bool, env_int
from api.shared.database import get_db_connection_context
from api.shared.domain_registry import resolve_domain_schema

logger = logging.getLogger(__name__)

_VALID = frozenset({"auto_approve", "suggest_only", "manual", "review_queue"})


def ce_writes_for_domain(
    domain_key: str,
    *,
    hours: int | None = None,
) -> int:
    """Chronological_events rows whose source_article_id maps to this domain schema."""
    schema = resolve_domain_schema(domain_key)
    window = hours if hours is not None else env_int("SPINE_COMPOUNDING_CE_WINDOW_HOURS", 24)
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT COUNT(*)::int
                    FROM public.chronological_events ce
                    JOIN {schema}.articles a ON a.id = ce.source_article_id
                    WHERE ce.extraction_timestamp >= NOW() - (%s || ' hours')::interval
                       OR a.created_at >= NOW() - (%s || ' hours')::interval
                    """,
                    (str(window), str(window)),
                )
                row = cur.fetchone()
                return int(row[0] or 0) if row else 0
    except Exception as exc:
        logger.debug("ce_writes_for_domain %s: %s", domain_key, exc)
        return 0


def spine_compounding_ready(domain_key: str) -> bool:
    """True when recent CE volume suggests event rail is alive for this domain."""
    if not env_bool("SPINE_COMPOUNDING_ENABLED", True):
        return False
    min_writes = env_int("SPINE_COMPOUNDING_MIN_CE_24H", 5)
    return ce_writes_for_domain(domain_key) >= min_writes


def effective_automation_mode(domain_key: str, configured_mode: str | None) -> str:
    """Upgrade suggest_only → auto_approve when spine is green (domain allow-list)."""
    mode = (configured_mode or "suggest_only").strip()
    if mode not in _VALID:
        mode = "suggest_only"
    if mode != "suggest_only":
        return mode
    if not env_bool("SPINE_COMPOUNDING_AUTO_APPROVE", True):
        return mode
    allow = env_bool(f"SPINE_COMPOUNDING_AUTO_APPROVE_{domain_key.upper()}", True)
    if domain_key == "politics":
        allow = env_bool("SPINE_COMPOUNDING_AUTO_APPROVE_POLITICS", allow)
    if not allow:
        return mode
    if spine_compounding_ready(domain_key):
        return "auto_approve"
    return mode


def spine_compounding_status(domain_key: str) -> dict[str, Any]:
    window = env_int("SPINE_COMPOUNDING_CE_WINDOW_HOURS", 24)
    ce_n = ce_writes_for_domain(domain_key, hours=window)
    return {
        "domain_key": domain_key,
        "ce_writes_in_window": ce_n,
        "window_hours": window,
        "min_ce_required": env_int("SPINE_COMPOUNDING_MIN_CE_24H", 5),
        "spine_ready": spine_compounding_ready(domain_key),
        "auto_approve_eligible": spine_compounding_ready(domain_key)
        and env_bool("SPINE_COMPOUNDING_AUTO_APPROVE", True),
    }