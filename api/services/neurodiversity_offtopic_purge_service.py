"""
Purge off-topic neurodiversity articles that fail topic_filter.include_keywords.

Soft-removes articles (enrichment_status=removed), deletes storyline memberships,
and uncouples package members. Never deletes source article rows.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

DOMAIN_KEY = "neurodiversity"
SCHEMA = "neurodiversity"


def _gate_text(title: str | None, content: str | None, abstract: str | None = None) -> str:
    from services.domain_synthesis_config import topic_gate_text

    return topic_gate_text(title, (content or "")[:4000], abstract=abstract)


def list_offtopic_article_ids(conn, *, limit: int | None = None) -> list[int]:
    from services.domain_synthesis_config import get_domain_synthesis_config

    cfg = get_domain_synthesis_config(DOMAIN_KEY)
    if not cfg.topic_filter.include_keywords:
        logger.warning("neurodiversity has no include_keywords; refusing mass purge")
        return []

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = %s AND table_name = 'articles' AND column_name = 'abstract'
            """,
            (SCHEMA,),
        )
        has_abstract = cur.fetchone() is not None

        if has_abstract:
            sql = f"""
                SELECT id, title, content, COALESCE(abstract, '')
                FROM {SCHEMA}.articles
                WHERE enrichment_status IS DISTINCT FROM 'removed'
                ORDER BY id
            """
        else:
            sql = f"""
                SELECT id, title, content, ''
                FROM {SCHEMA}.articles
                WHERE enrichment_status IS DISTINCT FROM 'removed'
                ORDER BY id
            """
        params: tuple[Any, ...] = ()
        if limit is not None:
            sql += " LIMIT %s"
            params = (int(limit),)
        cur.execute(sql, params)
        rows = cur.fetchall() or []

    return [
        int(aid)
        for aid, title, content, abstract in rows
        if not cfg.passes_include_topic_gate(_gate_text(title, content, abstract))
    ]


def purge_neurodiversity_offtopic(
    *,
    dry_run: bool = True,
    limit: int | None = None,
) -> dict[str, Any]:
    from shared.database.connection import get_db_connection
    from shared.domain_registry import resolve_domain_schema

    if resolve_domain_schema(DOMAIN_KEY) != SCHEMA:
        return {"ok": False, "error": "unexpected_schema"}

    conn = get_db_connection()
    if not conn:
        return {"ok": False, "error": "database_unavailable"}

    stats: dict[str, Any] = {
        "ok": True,
        "dry_run": dry_run,
        "offtopic_articles": 0,
        "storyline_links_removed": 0,
        "topic_cluster_links_removed": 0,
        "articles_marked_removed": 0,
        "package_members_uncoupled": 0,
        "storylines_recounted": 0,
        "sample_ids": [],
    }

    try:
        ids = list_offtopic_article_ids(conn, limit=limit)
        stats["offtopic_articles"] = len(ids)
        stats["sample_ids"] = ids[:20]
        if not ids or dry_run:
            return stats

        with conn.cursor() as cur:
            cur.execute(
                f"""
                DELETE FROM {SCHEMA}.storyline_articles
                WHERE article_id = ANY(%s)
                """,
                (ids,),
            )
            stats["storyline_links_removed"] = int(cur.rowcount or 0)

            cur.execute(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = %s AND table_name = 'article_topic_clusters'
                """,
                (SCHEMA,),
            )
            if cur.fetchone():
                cur.execute(
                    f"DELETE FROM {SCHEMA}.article_topic_clusters WHERE article_id = ANY(%s)",
                    (ids,),
                )
                stats["topic_cluster_links_removed"] = int(cur.rowcount or 0)

            cur.execute(
                f"""
                UPDATE {SCHEMA}.articles
                SET enrichment_status = 'removed', updated_at = NOW()
                WHERE id = ANY(%s)
                  AND enrichment_status IS DISTINCT FROM 'removed'
                """,
                (ids,),
            )
            stats["articles_marked_removed"] = int(cur.rowcount or 0)

            cur.execute(
                """
                UPDATE intelligence.editorial_package_members
                SET status = 'uncoupled',
                    metadata = COALESCE(metadata, '{}'::jsonb)
                      || jsonb_build_object(
                           'uncouple_reason', 'neurodiversity_include_allowlist_miss'
                         )
                WHERE domain_key = %s
                  AND member_family = 'article'
                  AND member_id = ANY(%s)
                  AND status = 'active'
                """,
                (DOMAIN_KEY, ids),
            )
            stats["package_members_uncoupled"] = int(cur.rowcount or 0)

            cur.execute(
                f"""
                UPDATE {SCHEMA}.storylines s
                SET article_count = COALESCE(sub.n, 0),
                    total_articles = COALESCE(sub.n, 0),
                    updated_at = NOW()
                FROM (
                  SELECT s2.id AS sid, COUNT(sa.article_id)::int AS n
                  FROM {SCHEMA}.storylines s2
                  LEFT JOIN {SCHEMA}.storyline_articles sa ON sa.storyline_id = s2.id
                  GROUP BY s2.id
                ) sub
                WHERE s.id = sub.sid
                  AND (
                    COALESCE(s.article_count, 0) IS DISTINCT FROM sub.n
                    OR COALESCE(s.total_articles, 0) IS DISTINCT FROM sub.n
                  )
                """
            )
            stats["storylines_recounted"] = int(cur.rowcount or 0)

        conn.commit()
        return stats
    except Exception as e:
        logger.warning("purge_neurodiversity_offtopic failed: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return {**stats, "ok": False, "error": str(e)}
    finally:
        try:
            conn.close()
        except Exception:
            pass
