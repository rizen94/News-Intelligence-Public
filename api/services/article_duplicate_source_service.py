"""Track duplicate-source links for canonical articles."""

from __future__ import annotations

import logging
from datetime import datetime

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)


def record_duplicate_source_link(
    *,
    domain_key: str,
    schema_name: str,
    canonical_article_id: int,
    duplicate_url: str | None,
    duplicate_source_domain: str | None,
    duplicate_title: str | None,
    duplicate_published_at: datetime | None,
    match_method: str = "title_source",
) -> bool:
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.article_duplicate_sources (
                    domain_key, schema_name, canonical_article_id,
                    duplicate_url, duplicate_source_domain, duplicate_title,
                    duplicate_published_at, match_method, first_seen_at, last_seen_at, seen_count
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), 1)
                ON CONFLICT (domain_key, canonical_article_id, duplicate_url, duplicate_source_domain, duplicate_title)
                DO UPDATE SET
                    last_seen_at = NOW(),
                    seen_count = intelligence.article_duplicate_sources.seen_count + 1,
                    duplicate_published_at = COALESCE(
                        EXCLUDED.duplicate_published_at,
                        intelligence.article_duplicate_sources.duplicate_published_at
                    ),
                    match_method = EXCLUDED.match_method
                """,
                (
                    (domain_key or "").strip(),
                    (schema_name or "").strip(),
                    int(canonical_article_id),
                    (duplicate_url or "").strip(),
                    (duplicate_source_domain or "").strip(),
                    (duplicate_title or "").strip(),
                    duplicate_published_at,
                    (match_method or "title_source").strip()[:64],
                ),
            )
        conn.commit()
        return True
    except Exception as e:
        logger.debug("record_duplicate_source_link failed: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass
