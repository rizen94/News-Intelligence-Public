"""
Shared batched event-extraction drain for AutomationManager and catch-up scripts.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from config.runtime import env_str
from services.event_extraction_service import EventExtractionService
from shared.bulk_catchup_llm_routing import (
    assign_extraction_lane,
    create_lane_semaphores,
    dual_lane_extraction_active,
)
from shared.database.connection import get_db_connection
from shared.database.db_availability import schema_has_table
from shared.domain_registry import get_pipeline_schema_names_active, schema_to_primary_domain_key
from shared.pipeline_article_selection import sql_order_coalesce_pub_created
from shared.pipeline_batch_drain import (
    DrainStallTracker,
    RunBudget,
    phase_batch_limit,
    phase_run_budget_seconds,
)
from shared.pipeline_pass_marker import phase_backlog_uses_pass_marker, sql_article_pass_null
from shared.services.llm_service import pop_llm_execution_lane, push_llm_execution_lane

logger = logging.getLogger(__name__)

ArticleFailureHandler = Callable[[str, int, Exception], Awaitable[None]]


async def run_event_extraction_batch_drain(
    *,
    articles_per_schema: int | None = None,
    budget_seconds: int | None = None,
    batch_size: int | None = None,
    on_article_failure: ArticleFailureHandler | None = None,
) -> dict[str, int]:
    """
    Drain event_extraction backlog using batched LLM calls (EVENT_EXTRACTION_BATCH_SIZE).

    Returns counts: articles_processed, events_saved, batch_rounds.
    """
    per_schema = articles_per_schema
    if per_schema is None:
        per_schema = phase_batch_limit("event_extraction", 30)
    per_schema = max(5, min(120, int(per_schema)))

    budget = RunBudget(
        budget_seconds
        if budget_seconds is not None
        else phase_run_budget_seconds("event_extraction", 0)
    )
    llm_batch = batch_size
    if llm_batch is None:
        try:
            llm_batch = int(env_str("EVENT_EXTRACTION_BATCH_SIZE", "3"))
        except ValueError:
            llm_batch = 3
    llm_batch = max(1, min(8, llm_batch))

    try:
        ev_parallel = int(env_str("EVENT_EXTRACTION_PARALLEL", "4"))
    except ValueError:
        ev_parallel = 4
    ev_parallel = max(1, min(16, ev_parallel))

    gpu_sem, cpu_sem, single_sem, gpu_p, cpu_p, dual = create_lane_semaphores(parallel=ev_parallel)
    dual = dual_lane_extraction_active()

    svc = EventExtractionService()
    loop = asyncio.get_event_loop()
    total_events = 0
    articles_processed = 0
    batch_rounds = 0

    ev_pass = ""
    if phase_backlog_uses_pass_marker("event_extraction"):
        ev_pass = f" AND ({sql_article_pass_null('event_extraction', 'a')}) "

    stall = DrainStallTracker()

    try:
        while not budget.expired():
            work_by_domain: dict[str, list[tuple[str, tuple]]] = {}
            pending_this_round = 0

            for schema in get_pipeline_schema_names_active():
                if not schema_has_table(schema, "articles"):
                    continue
                try:
                    domain_key = schema_to_primary_domain_key(schema)
                except KeyError:
                    domain_key = schema.replace("_", "-")

                conn = await loop.run_in_executor(None, get_db_connection)
                if not conn:
                    continue
                try:
                    cur = conn.cursor()
                    cur.execute(
                        f"""
                        SELECT a.id, a.content, a.published_at,
                               (
                                   SELECT sa.storyline_id::text
                                   FROM {schema}.storyline_articles sa
                                   WHERE sa.article_id = a.id
                                   ORDER BY sa.added_at DESC NULLS LAST
                                   LIMIT 1
                               ) AS storyline_id
                        FROM {schema}.articles a
                        WHERE a.timeline_processed = false
                          AND COALESCE((a.metadata #>> '{{pipeline_skip,event_extraction_skip}}')::boolean, false) = false
                          AND a.content IS NOT NULL
                          AND LENGTH(a.content) > 100
                          AND (
                              a.processing_status = 'completed'
                              OR a.enrichment_status IN ('completed', 'enriched')
                          )
                          {ev_pass}
                        ORDER BY {sql_order_coalesce_pub_created("a")}
                        LIMIT %s
                        """,
                        (per_schema,),
                    )
                    rows = cur.fetchall()
                    cur.close()
                finally:
                    conn.close()

                for row in rows:
                    work_by_domain.setdefault(domain_key, []).append((schema, row))
                    pending_this_round += 1

            if pending_this_round == 0:
                break

            batch_rounds += 1
            round_processed = 0
            round_events = 0

            for domain_key, items in work_by_domain.items():
                for i in range(0, len(items), llm_batch):
                    batch_items = items[i : i + llm_batch]
                    articles_for_batch: list[dict[str, Any]] = []
                    for schema, row in batch_items:
                        article_id, content, pub_date, storyline_id = row
                        articles_for_batch.append(
                            {
                                "article_id": article_id,
                                "content": content,
                                "pub_date": pub_date if pub_date else datetime.now(timezone.utc),
                                "storyline_id": storyline_id,
                                "schema": schema,
                            }
                        )

                    lane_idx = round_processed + i
                    lane = (
                        assign_extraction_lane(lane_idx, gpu_parallel=gpu_p, cpu_parallel=cpu_p)
                        if dual
                        else "gpu"
                    )
                    lane_sem = (
                        gpu_sem
                        if dual and lane == "gpu"
                        else (cpu_sem if dual and lane == "cpu" else single_sem)
                    )

                    async def _extract_batch() -> dict[int, list[dict[str, Any]]]:
                        return await svc.extract_events_batch(
                            articles_for_batch,
                            domain=domain_key,
                        )

                    token = push_llm_execution_lane(lane)
                    try:
                        if lane_sem is not None:
                            async with lane_sem:
                                events_by_article = await _extract_batch()
                        else:
                            events_by_article = await _extract_batch()
                    except Exception as e:
                        logger.error("event_extraction batch failed domain=%s: %s", domain_key, e)
                        events_by_article = {}
                    finally:
                        pop_llm_execution_lane(token)

                    for art in articles_for_batch:
                        article_id = art["article_id"]
                        schema = art["schema"]
                        content_len = len(art.get("content") or "")
                        events = events_by_article.get(article_id, [])
                        try:
                            saved = await _persist_article_events(
                                svc,
                                loop,
                                schema,
                                article_id,
                                events,
                                content_length=content_len,
                                batch_had_results=bool(events_by_article),
                                article_in_parse=article_id in events_by_article,
                            )
                            round_processed += 1
                            round_events += int(saved or 0)
                        except Exception as e:
                            logger.error(
                                "event_extraction save failed %s/%s: %s",
                                schema,
                                article_id,
                                e,
                            )
                            if on_article_failure:
                                await on_article_failure(schema, article_id, e)

                    if budget.expired():
                        break
                if budget.expired():
                    break

            articles_processed += round_processed
            total_events += round_events
            if stall.record_round(
                processed=round_processed, had_pending=pending_this_round > 0
            ):
                break
            if round_processed == 0:
                break

        logger.info(
            "event_extraction batch drain: articles=%s events=%s rounds=%s batch_size=%s dual_lane=%s",
            articles_processed,
            total_events,
            batch_rounds,
            llm_batch,
            dual,
        )
        return {
            "articles_processed": articles_processed,
            "processed": articles_processed,
            "events_saved": total_events,
            "batch_rounds": batch_rounds,
        }
    finally:
        await svc.close()


async def _persist_article_events(
    svc: EventExtractionService,
    loop: asyncio.AbstractEventLoop,
    schema: str,
    article_id: int,
    events: list[dict[str, Any]],
    *,
    content_length: int = 0,
    batch_had_results: bool = True,
    article_in_parse: bool = True,
) -> int:
    from shared.pipeline_pass_marker import (
        CLEARED_TERMINAL_STATES,
        infer_event_extraction_terminal,
        record_article_phase_pass,
    )

    success = batch_had_results and article_in_parse
    terminal, outcome = infer_event_extraction_terminal(
        events_count=len(events),
        content_length=content_length,
        success=success,
    )
    cleared = terminal in CLEARED_TERMINAL_STATES

    conn_a = await loop.run_in_executor(None, get_db_connection)
    if not conn_a:
        return 0
    try:
        saved = 0
        if events:
            saved = int(await svc.save_events(events, conn_a) or 0)
        cur = conn_a.cursor()
        if cleared:
            cur.execute(
                f"""
                UPDATE {schema}.articles
                SET timeline_processed = true,
                    timeline_events_generated = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (len(events), article_id),
            )
        elif not success:
            cur.execute(
                f"""
                UPDATE {schema}.articles
                SET timeline_processed = false,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (article_id,),
            )
        conn_a.commit()
        record_article_phase_pass(
            schema, article_id, "event_extraction", outcome, terminal_state=terminal
        )
        cur.close()
        return saved
    except Exception:
        try:
            conn_a.rollback()
        except Exception:
            pass
        raise
    finally:
        conn_a.close()
