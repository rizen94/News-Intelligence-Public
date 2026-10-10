"""
SQL-only spine tail (Pass 2): claims_to_facts, profile links, fast topic match, event markers.

No LLM — runs after fused unified intake completes.
"""

from __future__ import annotations

import logging
from typing import Any

from config.runtime import env_str
from shared.database.connection import get_db_connection, get_db_connection_context
from shared.domain_registry import pipeline_url_schema_pairs
from shared.pipeline_batch_drain import DrainStallTracker, RunBudget, phase_run_budget_seconds
from shared.pipeline_pass_marker import (
    TERMINAL_PROCESSED_EMPTY_LEGITIMATE,
    TERMINAL_PROCESSED_WITH_OUTPUT,
    phase_backlog_uses_pass_marker,
    record_article_phase_pass,
    record_context_phase_pass,
    sql_article_pass_cleared,
)

logger = logging.getLogger(__name__)


def _spine_tail_batch_limit() -> int:
    try:
        return max(10, min(2000, int(env_str("SPINE_SQL_TAIL_BATCH_LIMIT", "200"))))
    except (TypeError, ValueError):
        return 200


async def run_spine_sql_tail_drain(*, budget_seconds: int | None = None) -> dict[str, Any]:
    """
    Drain SQL tail steps until idle, stall, or optional budget circuit breaker.
    """
    budget = RunBudget(
        budget_seconds
        if budget_seconds is not None
        else phase_run_budget_seconds("spine_sql_tail", 0)
    )
    stall = DrainStallTracker()
    totals = {
        "claims_to_facts": 0,
        "profile_links": 0,
        "topic_fast_match": 0,
        "event_context_markers": 0,
        "link_indexer_articles": 0,
        "link_indexer_entity_edges": 0,
        "rounds": 0,
    }

    while not budget.expired():
        round_processed = 0
        totals["rounds"] += 1

        c2f_n, c2f_batches = await _drain_claims_to_facts_once()
        totals["claims_to_facts"] += c2f_n
        round_processed += c2f_n

        profile_n = _bulk_link_profiles()
        totals["profile_links"] += profile_n
        round_processed += profile_n

        topic_n = _batch_fast_topic_match()
        totals["topic_fast_match"] += topic_n
        round_processed += topic_n

        evt_n = _mark_event_tracking_for_unified_contexts()
        totals["event_context_markers"] += evt_n
        round_processed += evt_n

        link_stats = _run_link_indexer_batch()
        link_n = int(link_stats.get("articles") or 0)
        totals["link_indexer_articles"] = totals.get("link_indexer_articles", 0) + link_n
        totals["link_indexer_entity_edges"] = totals.get("link_indexer_entity_edges", 0) + int(
            link_stats.get("entity_edges") or 0
        )
        round_processed += link_n

        had_pending = c2f_n > 0 or profile_n > 0 or topic_n > 0 or evt_n > 0 or link_n > 0
        if stall.record_round(processed=round_processed, had_pending=had_pending):
            break
        if round_processed == 0:
            break

    logger.info("spine_sql_tail drain: %s", totals)
    return totals


async def _drain_claims_to_facts_once() -> tuple[int, int]:
    try:
        from services.claim_extraction_service import (
            claims_to_facts_drain_enabled,
            drain_claims_to_facts_for_automation_task,
        )

        if not claims_to_facts_drain_enabled():
            return 0, 0
        total, batches = await drain_claims_to_facts_for_automation_task(
            max_batches=5,
            enforce_nightly_window=False,
        )
        return int(total or 0), int(batches or 0)
    except Exception as e:
        logger.warning("spine_sql_tail claims_to_facts: %s", e)
        return 0, 0


def _bulk_link_profiles() -> int:
    """Link context_entity_mentions for articles with cleared unified intake."""
    from services.context_processor_service import link_context_to_article_entities

    limit = _spine_tail_batch_limit()
    linked = 0
    try:
        from shared.pipeline_resource_policy import intake_extraction_suppressed

        entity_phase = (
            "unified_intake_extraction" if intake_extraction_suppressed() else "entity_extraction"
        )
    except Exception:
        entity_phase = "unified_intake_extraction"

    for domain_key, schema_name in pipeline_url_schema_pairs():
        try:
            with get_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT atc.context_id, atc.article_id
                        FROM intelligence.article_to_context atc
                        JOIN {schema_name}.articles a ON a.id = atc.article_id
                        WHERE atc.domain_key = %s
                          AND ({sql_article_pass_cleared(entity_phase, "a")})
                          AND NOT EXISTS (
                              SELECT 1 FROM intelligence.context_entity_mentions cem
                              WHERE cem.context_id = atc.context_id
                              LIMIT 1
                          )
                        ORDER BY a.updated_at DESC NULLS LAST
                        LIMIT %s
                        """,
                        (domain_key, limit),
                    )
                    rows = cur.fetchall()
            for context_id, article_id in rows:
                try:
                    n = link_context_to_article_entities(int(context_id), domain_key, int(article_id))
                    if n > 0:
                        linked += n
                except Exception as e:
                    logger.debug("spine profile link %s/%s: %s", domain_key, article_id, e)
        except Exception as e:
            logger.warning("spine_sql_tail profile link %s: %s", schema_name, e)
    return linked


def _batch_fast_topic_match() -> int:
    from domains.content_analysis.services.topic_fast_match_service import apply_fast_match

    limit = _spine_tail_batch_limit()
    matched = 0
    for _domain_key, schema_name in pipeline_url_schema_pairs():
        try:
            with get_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT a.id FROM {schema_name}.articles a
                        WHERE ({sql_article_pass_cleared("unified_intake_extraction", "a")})
                          AND NOT EXISTS (
                              SELECT 1 FROM {schema_name}.article_topic_clusters atc
                              WHERE atc.article_id = a.id
                          )
                          AND NOT ({_sql_topic_pass_cleared("a")})
                        ORDER BY a.updated_at DESC NULLS LAST
                        LIMIT %s
                        """,
                        (limit,),
                    )
                    ids = [int(r[0]) for r in cur.fetchall()]
                for aid in ids:
                    with conn.cursor() as cur:
                        out = apply_fast_match(cur, schema_name, aid)
                        if out:
                            matched += 1
                            if phase_backlog_uses_pass_marker("topic_clustering"):
                                record_article_phase_pass(
                                    schema_name,
                                    aid,
                                    "topic_clustering",
                                    "fast_match",
                                    terminal_state=TERMINAL_PROCESSED_WITH_OUTPUT,
                                )
                conn.commit()
        except Exception as e:
            logger.warning("spine_sql_tail topic fast match %s: %s", schema_name, e)
    return matched


def _sql_topic_pass_cleared(alias: str) -> str:
    if not phase_backlog_uses_pass_marker("topic_clustering"):
        return "false"
    return f"({sql_article_pass_cleared('topic_clustering', alias)})"


def _mark_event_tracking_for_unified_contexts() -> int:
    """
  Contexts for unified-intake articles with chronological events: mark event_tracking
  pass so backlog clears without per-context LLM (full discovery remains nightly tail).
    """
    if not phase_backlog_uses_pass_marker("event_tracking"):
        return 0
    limit = _spine_tail_batch_limit()
    marked = 0
    conn = get_db_connection()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT DISTINCT c.id
                FROM intelligence.contexts c
                JOIN intelligence.article_to_context atc ON atc.context_id = c.id
                JOIN public.chronological_events ce ON ce.source_article_id = atc.article_id
                WHERE ce.extraction_method IN ('unified_intake', 'unified_intake_extraction')
                  AND c.metadata #>> '{{pipeline,event_tracking,last_pass_at}}' IS NULL
                ORDER BY c.id DESC
                LIMIT %s
                """,
                (limit,),
            )
            for (context_id,) in cur.fetchall():
                record_context_phase_pass(
                    int(context_id),
                    "event_tracking",
                    "unified_events_present",
                    terminal_state=TERMINAL_PROCESSED_WITH_OUTPUT,
                )
                marked += 1
        conn.commit()
    except Exception as e:
        logger.warning("spine_sql_tail event markers: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()
    return marked


def _run_link_indexer_batch() -> dict[str, int]:
    try:
        from services.link_indexer_service import index_spine_complete_articles

        return index_spine_complete_articles()
    except Exception as e:
        logger.warning("spine_sql_tail link_indexer: %s", e)
        return {"articles": 0, "entity_edges": 0}
