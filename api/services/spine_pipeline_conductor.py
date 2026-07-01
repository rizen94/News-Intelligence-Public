"""
Ordered spine pipeline conductor — enrich → fused intake → SQL tail.

Work-completion based (no time-budget throttling). ``SPINE_PIPELINE_MODE=shadow`` logs only.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from config.runtime import env_str
from shared.pipeline_batch_drain import DrainStallTracker, RunBudget, phase_run_budget_seconds
from shared.spine_phase_order import (
    SPINE_PHASE_ORDER,
    spine_pipeline_mode,
    spine_pipeline_ordered_active,
    spine_pipeline_shadow_active,
)

logger = logging.getLogger(__name__)


def _conductor_idle_seconds() -> float:
    try:
        return max(5.0, float(env_str("SPINE_CONDUCTOR_IDLE_SECONDS", "30")))
    except (TypeError, ValueError):
        return 30.0


async def run_spine_conductor_cycle(
    automation: Any | None = None,
    *,
    budget_seconds: int | None = None,
) -> dict[str, Any]:
    """
    One full ordered spine sweep. Returns per-step stats.
    """
    mode = spine_pipeline_mode()
    budget = RunBudget(
        budget_seconds
        if budget_seconds is not None
        else phase_run_budget_seconds("spine_conductor", 0)
    )
    stats: dict[str, Any] = {"mode": mode, "steps": {}}

    for phase in SPINE_PHASE_ORDER:
        if budget.expired():
            break
        step_stats = await _drain_spine_phase(phase, automation=automation, shadow=mode == "shadow")
        stats["steps"][phase] = step_stats
        if mode == "shadow":
            logger.info("spine conductor shadow would run %s: %s", phase, step_stats)

    return stats


async def spine_conductor_loop(automation: Any) -> None:
    """Background loop when SPINE_PIPELINE_MODE=ordered or shadow."""
    logger.info("spine conductor loop started (mode=%s)", spine_pipeline_mode())
    while getattr(automation, "is_running", False):
        try:
            if spine_pipeline_ordered_active() or spine_pipeline_shadow_active():
                await run_spine_conductor_cycle(automation)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("spine conductor cycle failed: %s", e)
        await asyncio.sleep(_conductor_idle_seconds())


async def _drain_spine_phase(
    phase: str,
    *,
    automation: Any | None,
    shadow: bool,
) -> dict[str, Any]:
    if shadow:
        try:
            from services.backlog_metrics import get_all_backlog_counts

            pending = int(get_all_backlog_counts().get(phase, 0) or 0)
        except Exception:
            pending = -1
        return {"shadow": True, "pending": pending}

    if phase == "content_enrichment":
        return await _drain_enrichment(automation)
    if phase == "unified_intake_extraction":
        return await _drain_unified_intake(automation)
    if phase == "spine_sql_tail":
        from services.spine_sql_tail_service import run_spine_sql_tail_drain

        return await run_spine_sql_tail_drain()
    return {"skipped": phase}


async def _drain_enrichment(automation: Any | None) -> dict[str, Any]:
    import asyncio

    from services.article_content_enrichment_service import enrich_articles_batch

    stall = DrainStallTracker()
    total = 0
    rounds = 0
    while True:
        rounds += 1
        n = 0
        try:
            loop = asyncio.get_event_loop()
            n = int(
                await loop.run_in_executor(
                    None, lambda: enrich_articles_batch(batch_size=60) or 0
                )
            )
        except Exception as e:
            logger.warning("spine conductor enrichment: %s", e)
        had_pending = n > 0
        if not had_pending:
            try:
                from services.backlog_metrics import get_all_pending_counts

                had_pending = int(get_all_pending_counts().get("content_enrichment") or 0) > 0
            except Exception:
                pass
        total += n
        if stall.record_round(processed=n, had_pending=had_pending):
            break
        if n == 0:
            break
    return {"rounds": rounds, "processed": total}


async def _drain_unified_intake(automation: Any | None) -> dict[str, Any]:
    from shared.unified_intake_extraction_runner import run_unified_intake_extraction_batch_drain

    stall = DrainStallTracker()
    total_processed = 0
    rounds = 0
    while True:
        rounds += 1
        result = await run_unified_intake_extraction_batch_drain(
            budget_seconds=0,
        )
        n = int(result.get("articles_processed") or 0)
        total_processed += n
        had_pending = n > 0 or int(result.get("batch_rounds") or 0) > 0
        if stall.record_round(processed=n, had_pending=had_pending):
            break
        if n == 0:
            break
    return {"rounds": rounds, "articles_processed": total_processed}


def spine_phase_should_suppress_scheduler(phase_name: str) -> bool:
    """When ordered mode active, individual spine phases are conductor-owned."""
    if not spine_pipeline_ordered_active():
        return False
    p = (phase_name or "").strip().lower().replace("-", "_")
    return p in SPINE_PHASE_ORDER or p == "spine_sql_tail"
