"""Batched entity extraction drain for AutomationManager and catch-up."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from config.runtime import env_str
from services.article_entity_extraction_service import ArticleEntityExtractionService
from shared.bulk_catchup_llm_routing import (
    assign_extraction_lane,
    create_lane_semaphores,
    dual_lane_extraction_active,
)
from shared.domain_registry import pipeline_url_schema_pairs
from shared.pipeline_batch_drain import (
    DrainStallTracker,
    RunBudget,
    phase_batch_limit,
    phase_run_budget_seconds,
)
from shared.pipeline_pass_marker import phase_backlog_uses_pass_marker, sql_article_pass_null
from shared.pipeline_article_selection import sql_order_created_at
from shared.services.llm_service import pop_llm_execution_lane, push_llm_execution_lane

logger = logging.getLogger(__name__)

ArticleFailureHandler = Callable[[str, int, Exception], Awaitable[None]]


async def run_entity_extraction_batch_drain(
    *,
    articles_per_domain: int | None = None,
    budget_seconds: int | None = None,
    batch_size: int | None = None,
    on_article_failure: ArticleFailureHandler | None = None,
) -> dict[str, int]:
    per_domain = articles_per_domain
    if per_domain is None:
        per_domain = phase_batch_limit("entity_extraction", 40)
    per_domain = max(5, min(120, int(per_domain)))

    budget = RunBudget(
        budget_seconds
        if budget_seconds is not None
        else phase_run_budget_seconds("entity_extraction", 0)
    )

    llm_batch = batch_size
    if llm_batch is None:
        try:
            llm_batch = int(env_str("ENTITY_EXTRACTION_BATCH_SIZE", "3"))
        except ValueError:
            llm_batch = 3
    llm_batch = max(1, min(6, llm_batch))

    try:
        parallel = int(env_str("ENTITY_EXTRACTION_PARALLEL", "6"))
    except ValueError:
        parallel = 6
    parallel = max(1, min(16, parallel))

    gpu_sem, cpu_sem, single_sem, gpu_p, cpu_p, dual = create_lane_semaphores(parallel=parallel)
    dual = dual_lane_extraction_active()

    svc = ArticleEntityExtractionService()
    loop = asyncio.get_event_loop()
    extracted_count = 0
    batch_rounds = 0

    pass_clause = ""
    if phase_backlog_uses_pass_marker("entity_extraction"):
        pass_clause = f" AND ({sql_article_pass_null('entity_extraction', 'a')}) "
    from shared.article_signal_gate import (
        article_signal_enabled,
        sql_article_signal_full_lane_filter,
    )

    order = sql_order_created_at()
    domains = list(pipeline_url_schema_pairs())

    def _fetch_domain_articles() -> dict[str, list[tuple]]:
        from shared.database.connection import get_db_connection_context

        out: dict[str, list[tuple]] = {}
        with get_db_connection_context() as conn:
            with conn.cursor() as cursor:
                for domain_key, schema_name in domains:
                    sig = ""
                    if article_signal_enabled():
                        sig = f" AND ({sql_article_signal_full_lane_filter('a', schema_name)}) "
                    try:
                        cursor.execute(
                            f"""
                            SELECT a.id, a.title, a.content
                            FROM {schema_name}.articles a
                            LEFT JOIN {schema_name}.article_entities ae ON ae.article_id = a.id
                            WHERE ae.id IS NULL
                              AND COALESCE((a.metadata #>> '{{pipeline_skip,entity_extraction_skip}}')::boolean, false) = false
                              AND a.content IS NOT NULL
                              AND LENGTH(a.content) > 100
                              AND (
                                LENGTH(a.content) >= 500
                                OR a.created_at < NOW() - INTERVAL '2 hours'
                                OR COALESCE(a.enrichment_status, '') IN (
                                    'enriched', 'failed', 'inaccessible'
                                )
                              )
                              {pass_clause}
                              {sig}
                            ORDER BY a.created_at {order}
                            LIMIT {per_domain}
                            """
                        )
                        out[schema_name] = cursor.fetchall()
                    except Exception as e:
                        logger.warning("Entity extraction query for %s: %s", schema_name, e)
                        out[schema_name] = []
        return out

    stall = DrainStallTracker()

    try:
        lane_idx = 0
        while not budget.expired():
            domain_articles = await loop.run_in_executor(None, _fetch_domain_articles)
            pending_rows: list[tuple[str, str, tuple]] = []
            for domain_key, schema_name in domains:
                for row in domain_articles.get(schema_name, []):
                    pending_rows.append((domain_key, schema_name, row))

            if not pending_rows:
                break

            batch_rounds += 1
            round_ok = 0

            for i in range(0, len(pending_rows), llm_batch):
                batch_slice = pending_rows[i : i + llm_batch]
                articles_for_batch = [
                    {
                        "article_id": row[0],
                        "title": row[1] or "",
                        "content": row[2],
                        "schema": schema,
                    }
                    for _dk, schema, row in batch_slice
                ]

                lane = (
                    assign_extraction_lane(lane_idx, gpu_parallel=gpu_p, cpu_parallel=cpu_p)
                    if dual
                    else "gpu"
                )
                lane_idx += 1
                lane_sem = (
                    gpu_sem
                    if dual and lane == "gpu"
                    else (cpu_sem if dual and lane == "cpu" else single_sem)
                )

                async def _extract() -> dict[int, dict[str, Any]]:
                    return await svc.extract_entities_batch(articles_for_batch)

                token = push_llm_execution_lane(lane)
                try:
                    if lane_sem is not None:
                        async with lane_sem:
                            results = await _extract()
                    else:
                        results = await _extract()
                except Exception as e:
                    logger.error("entity_extraction batch failed: %s", e)
                    results = {}
                finally:
                    pop_llm_execution_lane(token)

                for _dk, schema, row in batch_slice:
                    article_id = row[0]
                    result = results.get(article_id, {"success": False})
                    try:
                        from shared.pipeline_pass_marker import (
                            infer_entity_extraction_terminal,
                            record_article_phase_pass,
                        )

                        ok = bool(result.get("success"))
                        cnt = int((result.get("counts") or {}).get("entities") or 0)
                        content_len = len(row[2] or "")
                        terminal, outcome = infer_entity_extraction_terminal(
                            entities_count=cnt,
                            content_length=content_len,
                            success=ok,
                        )
                        record_article_phase_pass(
                            schema,
                            article_id,
                            "entity_extraction",
                            outcome,
                            terminal_state=terminal,
                        )
                        if ok:
                            round_ok += 1
                    except Exception as e:
                        if on_article_failure:
                            await on_article_failure(schema, article_id, e)

                if budget.expired():
                    break

            extracted_count += round_ok
            if stall.record_round(processed=round_ok, had_pending=bool(pending_rows)):
                break
            if round_ok == 0:
                break

        logger.info(
            "entity_extraction batch drain: articles=%s rounds=%s batch_size=%s dual_lane=%s",
            extracted_count,
            batch_rounds,
            llm_batch,
            dual,
        )
        return {
            "processed": extracted_count,
            "articles_processed": extracted_count,
            "batch_rounds": batch_rounds,
        }
    finally:
        pass
