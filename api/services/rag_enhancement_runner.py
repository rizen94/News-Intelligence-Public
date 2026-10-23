"""Event-driven RAG enhancement runner (replaces archived handler SQL on missing rag_enhanced_at)."""

from __future__ import annotations

import logging
from typing import Any

from shared.database.connection import get_db_connection
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema
from shared.rag_enhancement_eligibility import sql_rag_select_storylines_for_domain

logger = logging.getLogger(__name__)

_DEFAULT_PER_DOMAIN = 9


def _per_domain_limit() -> int:
    from config.runtime import env_str

    try:
        return max(1, min(50, int(env_str("RAG_ENHANCEMENT_BATCH_PER_DOMAIN", str(_DEFAULT_PER_DOMAIN)))))
    except ValueError:
        return _DEFAULT_PER_DOMAIN


async def run_rag_enhancement_batch() -> int:
    """Enhance storylines due for RAG (never enhanced or new articles since last pass)."""
    from services.rag import get_rag_service

    rag_service = get_rag_service()
    enhanced_count = 0
    limit = _per_domain_limit()

    for domain in get_pipeline_active_domain_keys():
        schema = resolve_domain_schema(domain)
        conn = get_db_connection()
        if not conn:
            continue
        rows: list[tuple[Any, ...]] = []
        try:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '8s'")
                cur.execute(sql_rag_select_storylines_for_domain(domain, schema, limit=limit))
                rows = cur.fetchall()
        except Exception as e:
            logger.warning("RAG enhancement select %s: %s", domain, e)
        finally:
            try:
                conn.close()
            except Exception:
                pass

        for sid, title in rows:
            sid_int = int(sid)
            articles_for_rag: list[dict[str, Any]] = []
            conn = get_db_connection()
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            f"""
                            SELECT a.id, a.title, a.content, a.summary, a.source_domain
                            FROM {schema}.storyline_articles sa
                            JOIN {schema}.articles a ON a.id = sa.article_id
                            WHERE sa.storyline_id = %s
                            ORDER BY COALESCE(a.published_at, a.created_at) DESC NULLS LAST
                            LIMIT 30
                            """,
                            (sid_int,),
                        )
                        for r in cur.fetchall():
                            articles_for_rag.append(
                                {
                                    "id": r[0],
                                    "title": r[1],
                                    "content": r[2] or "",
                                    "summary": r[3],
                                    "source": r[4],
                                }
                            )
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass
            try:
                await rag_service.enhance_storyline_context(
                    storyline_id=str(sid_int),
                    storyline_title=title or "",
                    articles=articles_for_rag,
                    domain=domain,
                )
                enhanced_count += 1
            except Exception as e:
                logger.debug("RAG enhance %s storyline %s: %s", domain, sid_int, e)

    if enhanced_count > 0:
        logger.info("RAG enhancement completed: %s storylines enhanced", enhanced_count)
    return enhanced_count
