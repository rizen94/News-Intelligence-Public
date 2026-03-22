"""
RSS/DB poll DataSource for Newsroom Orchestrator v6.

Phase 1: does not run RSS; returns new articles from DB poll (same as Reporter tick).
Used by Reporter to centralize poll logic.
"""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from shared.domain_registry import domain_key_to_schema, get_active_domain_keys

logger = logging.getLogger("orchestration")


def get_new_articles(
    get_db_connection: Callable,
    window_minutes: int = 15,
    domains: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Poll DB for articles with discovered_at in last window_minutes.
    Returns list of dicts: domain_key, article_id, title, summary.
    """
    from psycopg2 import sql

    conn = get_db_connection()
    if not conn:
        return []
    domains = domains or list(get_active_domain_keys())
    since = (datetime.now(timezone.utc) - timedelta(minutes=window_minutes)).isoformat()
    out = []
    try:
        for domain_key in domains:
            try:
                schema = domain_key_to_schema(domain_key)
            except KeyError:
                continue
            try:
                cur = conn.cursor()
                cur.execute(
                    sql.SQL("""
                        SELECT id, title, COALESCE(excerpt, content, '') AS summary
                        FROM {schema}.articles
                        WHERE discovered_at IS NOT NULL AND discovered_at >= %s
                        ORDER BY discovered_at DESC
                        LIMIT 500
                    """).format(schema=sql.Identifier(schema)),
                    (since,),
                )
                for row in cur.fetchall():
                    out.append(
                        {
                            "domain_key": domain_key,
                            "article_id": row[0],
                            "title": row[1] or "",
                            "summary": (row[2] or "")[:2000],
                        }
                    )
                cur.close()
            except Exception as e:
                logger.warning("get_new_articles failed for %s: %s", domain_key, e)
    finally:
        conn.close()
    return out
