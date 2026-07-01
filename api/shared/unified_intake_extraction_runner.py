"""Batched unified intake extraction drain for AutomationManager and catch-up."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from config.runtime import env_str
from services.unified_intake_extraction_service import UnifiedIntakeExtractionService
from shared.article_processing_gates import sql_ml_ready_and_content_bounds
from shared.bulk_catchup_llm_routing import (
    assign_extraction_lane,
    create_lane_semaphores,
    dual_lane_extraction_active,
)
from shared.domain_registry import pipeline_url_schema_pairs
from shared.pipeline_article_selection import sql_order_coalesce_pub_created
from shared.pipeline_batch_drain import (
    DrainStallTracker,
    RunBudget,
    phase_batch_limit,
    phase_run_budget_seconds,
)
from shared.pipeline_pass_marker import phase_backlog_uses_pass_marker, sql_article_pass_null
from shared.unified_intake_backlog import (
    backfill_unified_pass_from_legacy_batch,
    sql_actionable_unified_intake,
    unified_intake_legacy_aware_backlog_enabled,
)
from shared.services.llm_service import pop_llm_execution_lane, push_llm_execution_lane
from shared.monitor_pulse_debug import monitor_pulse_debug

logger = logging.getLogger(__name__)

ArticleFailureHandler = Callable[[str, int, Exception], Awaitable[None]]


async def run_unified_intake_extraction_batch_drain(
    *,
    articles_per_domain: int | None = None,
    budget_seconds: int | None = None,
    batch_size: int | None = None,
    on_article_failure: ArticleFailureHandler | None = None,
    on_batch_complete: Callable[[int, dict[str, Any]], Awaitable[None]] | None = None,
) -> dict[str, int]:
    per_domain = articles_per_domain
    if per_domain is None:
        per_domain = phase_batch_limit("unified_intake_extraction", 40)
    per_domain = max(5, min(120, int(per_domain)))

    budget = RunBudget(
        budget_seconds
        if budget_seconds is not None
        else phase_run_budget_seconds("unified_intake_extraction", 0)
    )

    llm_batch = batch_size
    if llm_batch is None:
        try:
            llm_batch = int(env_str("UNIFIED_INTAKE_EXTRACTION_BATCH_SIZE", "3"))
        except ValueError:
            llm_batch = 3
    llm_batch = max(1, min(6, llm_batch))

    try:
        parallel = int(env_str("UNIFIED_INTAKE_EXTRACTION_PARALLEL", "6"))
    except ValueError:
        parallel = 6
    parallel = max(1, min(16, parallel))

    gpu_sem, cpu_sem, single_sem, gpu_p, cpu_p, dual = create_lane_semaphores(parallel=parallel)
    dual = dual_lane_extraction_active()

    svc = UnifiedIntakeExtractionService()
    loop = asyncio.get_event_loop()
    processed_count = 0
    backfill_count = 0
    batch_rounds = 0

    pass_clause = ""
    if phase_backlog_uses_pass_marker("unified_intake_extraction"):
        pass_clause = f" AND ({sql_article_pass_null('unified_intake_extraction', 'a')}) "
    from shared.article_signal_gate import (
        article_signal_enabled,
        defer_signal_light_unified_intake_batch,
        sql_article_signal_full_lane_filter,
    )

    if article_signal_enabled():
        defer_signal_light_unified_intake_batch(per_domain_limit=per_domain * 2)
    ml_ready = sql_ml_ready_and_content_bounds("a")
    order = sql_order_coalesce_pub_created("a")
    domains = list(pipeline_url_schema_pairs())

    def _backfill_legacy_complete() -> int:
        if not unified_intake_legacy_aware_backlog_enabled():
            return 0
        n = 0
        backfill_limit = max(per_domain * 4, 200)
        for _domain_key, schema_name in domains:
            try:
                n += len(
                    backfill_unified_pass_from_legacy_batch(
                        schema_name=schema_name,
                        limit=backfill_limit,
                    )
                )
            except Exception as e:
                logger.warning("unified_intake legacy backfill %s: %s", schema_name, e)
        return n

    def _fetch_domain_articles() -> dict[str, list[tuple]]:
        """One short-lived connection per domain — release before LLM batches run."""
        from shared.database.connection import get_db_connection_context

        out: dict[str, list[tuple]] = {}

        def _fetch_one_schema(schema_name: str) -> list[tuple]:
            sig = ""
            if article_signal_enabled():
                sig = f" AND ({sql_article_signal_full_lane_filter('a', schema_name)}) "
            if unified_intake_legacy_aware_backlog_enabled():
                where_sql = sql_actionable_unified_intake(schema_name, "a")
            else:
                where_sql = f"""
                    COALESCE(
                        (a.metadata #>> '{{pipeline_skip,unified_intake_extraction_skip}}')::boolean,
                        false
                    ) = false
                      AND a.content IS NOT NULL
                      AND LENGTH(a.content) > 100
                      AND ({ml_ready})
                      AND (
                          LENGTH(a.content) >= 500
                          OR a.created_at < NOW() - INTERVAL '2 hours'
                          OR COALESCE(a.enrichment_status, '') IN (
                              'enriched', 'failed', 'inaccessible'
                          )
                      )
                      {pass_clause}
                """
            with get_db_connection_context() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"""
                        SELECT a.id, a.title, a.content, a.published_at,
                               (
                                   SELECT sa.storyline_id::text
                                   FROM {schema_name}.storyline_articles sa
                                   WHERE sa.article_id = a.id
                                   ORDER BY sa.added_at DESC NULLS LAST
                                   LIMIT 1
                               ) AS storyline_id
                        FROM {schema_name}.articles a
                        WHERE {where_sql}
                          {sig}
                        ORDER BY {order}
                        LIMIT {per_domain}
                        """
                    )
                    return cursor.fetchall()

        for _domain_key, schema_name in domains:
            try:
                out[schema_name] = _fetch_one_schema(schema_name)
            except Exception as e:
                logger.warning(
                    "unified_intake_extraction query for %s: %s", schema_name, e
                )
                out[schema_name] = []
        return out

    stall = DrainStallTracker()

    try:
        lane_idx = 0
        while not budget.expired():
            round_backfill = await loop.run_in_executor(None, _backfill_legacy_complete)
            backfill_count += round_backfill
            domain_articles = await loop.run_in_executor(None, _fetch_domain_articles)
            pending_rows: list[tuple[str, str, tuple]] = []
            for domain_key, schema_name in domains:
                for row in domain_articles.get(schema_name, []):
                    pending_rows.append((domain_key, schema_name, row))

            if not pending_rows:
                if round_backfill == 0:
                    break
                continue

            batch_rounds += 1
            round_ok = 0

            batch_slices = [
                pending_rows[i : i + llm_batch]
                for i in range(0, len(pending_rows), llm_batch)
            ]

            async def _process_batch(
                batch_slice: list[tuple[str, str, tuple]],
                batch_lane_idx: int,
            ) -> tuple[list[tuple[str, str, tuple]], dict[int, dict[str, Any]]]:
                articles_for_batch = [
                    {
                        "article_id": row[0],
                        "title": row[1] or "",
                        "content": row[2],
                        "pub_date": row[3],
                        "storyline_id": row[4],
                        "schema": schema,
                        "domain_key": dk,
                    }
                    for dk, schema, row in batch_slice
                ]

                lane = (
                    assign_extraction_lane(batch_lane_idx, gpu_parallel=gpu_p, cpu_parallel=cpu_p)
                    if dual
                    else "gpu"
                )
                lane_sem = (
                    gpu_sem
                    if dual and lane == "gpu"
                    else (cpu_sem if dual and lane == "cpu" else single_sem)
                )

                token = push_llm_execution_lane(lane)
                batch_t0 = time.monotonic()
                try:
                    if lane_sem is not None:
                        async with lane_sem:
                            results = await svc.extract_batch(articles_for_batch)
                    else:
                        results = await svc.extract_batch(articles_for_batch)
                    return batch_slice, results
                except Exception as e:
                    logger.error("unified_intake_extraction batch failed: %s", e)
                    return batch_slice, {}
                finally:
                    pop_llm_execution_lane(token)
                    monitor_pulse_debug(
                        "unified_intake_extraction_runner.py:_process_batch",
                        "batch wave slot finished",
                        {
                            "lane": lane,
                            "articles": len(articles_for_batch),
                            "seconds": round(time.monotonic() - batch_t0, 2),
                        },
                        hypothesis_id="concurrent_batches",
                        run_id="post-fix",
                    )

            for wave_start in range(0, len(batch_slices), parallel):
                if budget.expired():
                    break
                wave = batch_slices[wave_start : wave_start + parallel]
                wave_t0 = time.monotonic()
                wave_outcomes = await asyncio.gather(
                    *[
                        _process_batch(batch_slice, lane_idx + offset)
                        for offset, batch_slice in enumerate(wave)
                    ]
                )
                lane_idx += len(wave)
                monitor_pulse_debug(
                    "unified_intake_extraction_runner.py:wave",
                    "batch wave complete",
                    {
                        "wave_batches": len(wave),
                        "parallel": parallel,
                        "seconds": round(time.monotonic() - wave_t0, 2),
                    },
                    hypothesis_id="concurrent_batches",
                    run_id="post-fix",
                )

                for batch_slice, results in wave_outcomes:
                    for dk, schema, row in batch_slice:
                        article_id = row[0]
                        result = results.get(article_id, {"success": False})
                        if result.get("success") or result.get("attempted"):
                            round_ok += 1
                        elif on_article_failure and not result.get("success"):
                            await on_article_failure(
                                schema,
                                article_id,
                                Exception(
                                    result.get("error") or result.get("reason") or "failed"
                                ),
                            )

                if budget.expired():
                    break

            processed_count += round_ok
            if on_batch_complete is not None:
                await on_batch_complete(
                    batch_rounds,
                    {
                        "round_processed": round_ok,
                        "total_processed": processed_count,
                        "backfill_count": backfill_count,
                    },
                )
            had_pending = bool(pending_rows)
            if stall.record_round(processed=round_ok, had_pending=had_pending):
                break
            if round_ok == 0 and round_backfill == 0:
                break

        logger.info(
            "unified_intake_extraction batch drain: articles=%s backfilled=%s rounds=%s batch_size=%s dual_lane=%s",
            processed_count,
            backfill_count,
            batch_rounds,
            llm_batch,
            dual,
        )
        if processed_count > 0 or backfill_count > 0:
            try:
                from services.backlog_metrics import invalidate_backlog_metrics_cache

                invalidate_backlog_metrics_cache()
            except Exception:
                pass
        return {
            "processed": processed_count + backfill_count,
            "articles_processed": processed_count + backfill_count,
            "llm_processed": processed_count,
            "legacy_backfilled": backfill_count,
            "batch_rounds": batch_rounds,
        }
    finally:
        await svc.close()
