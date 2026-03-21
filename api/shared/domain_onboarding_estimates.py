"""
Catch-up / workload snapshots for new domains (template core).

Uses backlog-style counts per automation phase where available. See
docs/DOMAIN_EXTENSION_TEMPLATE.md § Catch-up and workload.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from shared.domain_registry import domain_key_to_schema, get_active_domain_keys

logger = logging.getLogger(__name__)


def peer_article_counts() -> dict[str, int]:
    """Return approximate article counts per URL domain_key for peer comparison."""
    try:
        from shared.database.connection import get_db_connection
    except Exception as e:  # pragma: no cover
        logger.warning("peer_article_counts: DB unavailable: %s", e)
        return {}

    out: dict[str, int] = {}
    conn = get_db_connection()
    if not conn:
        return {}
    try:
        with conn.cursor() as cur:
            for key in get_active_domain_keys():
                schema = domain_key_to_schema(key)
                cur.execute(
                    f"SELECT COUNT(*) FROM {schema}.articles"  # noqa: S608 — schema from registry
                )
                row = cur.fetchone()
                out[key] = int(row[0]) if row else 0
    except Exception as e:
        logger.warning("peer_article_counts: %s", e)
    finally:
        conn.close()
    return out


def build_catchup_summary(domain_key: str) -> dict[str, Any]:
    """
    Lightweight summary for monitoring / onboarding UI.
    Extend with backlog_metrics integration in a follow-up.
    """
    peers = peer_article_counts()
    self_count = peers.get(domain_key, 0)
    others = [c for k, c in peers.items() if k != domain_key]
    median_peer = sorted(others)[len(others) // 2] if others else 0
    return {
        "domain_key": domain_key,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "articles_in_silo": self_count,
        "peer_median_articles": median_peer,
        "note": "Per-phase backlog counts: wire to backlog_metrics in follow-up.",
    }
