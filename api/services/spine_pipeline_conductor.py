"""
Ordered spine pipeline conductor — enrich → fused intake → SQL tail.

Work-completion based (no time-budget throttling). ``SPINE_PIPELINE_MODE=shadow`` logs only.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from config.runtime import env_str
from shared.pipeline_batch_drain import DrainStallTracker, RunBudget, phase_run_budget_seconds
from shared.spine_phase_order import (
    SPINE_PHASE_ORDER,
    spine_pipeline_mode,
    spine_pipeline_ordered_active,
    spine_pipeline_shadow_active,
)
from shared.services.conductor_run_history import (
    persist_conductor_phase_run_async,
    record_conductor_phase_heartbeat,
)

logger = logging.getLogger(__name__)


def _conductor_idle_seconds() -> float:
    try:
        return max(5.0, float(env_str("SPINE_CONDUCTOR_IDLE_SECONDS", "5")))
    except (TypeError, ValueError):
        return 5.0


def _spine_phase_pending_count(phase: str) -> int | None:
    """Pending rows for a spine phase; None when unknown (run drain — e.g. spine_sql_tail composite)."""
    p = (phase or "").strip().lower().replace("-", "_")
    if p not in SPINE_PHASE_ORDER:
        return None
    if p == "spine_sql_tail":
        return None
    try:
        from services.backlog_metrics import get_all_pending_counts

        return int(get_all_pending_counts().get(p, 0) or 0)
    except Exception:
        return None


def _spine_phase_cycle_budget_seconds(phase: str) -> int:
    """
    Wall-clock cap per spine phase within one conductor cycle.

    Enrichment must not monopolize the loop — slow HTTP fetches were blocking
    unified_intake_extraction indefinitely. 0 = drain until stall (unlimited).
    """
    p = (phase or "").strip().lower().replace("-", "_")
    defaults: dict[str, int] = {
        "content_enrichment": 120,
        # Shorter cycles complete before API restarts; drain loops until budget inside runner.
        "unified_intake_extraction": 900,
        "spine_sql_tail": 300,
    }
    default = defaults.get(p, 0)
    key = f"SPINE_{p.upper()}_CYCLE_BUDGET_SECONDS"
    try:
        raw = env_str(key, "")
        if raw is not None and str(raw).strip() != "":
            return max(0, int(raw))
    except (TypeError, ValueError):
        pass
    return default


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
        pending = _spine_phase_pending_count(phase)
        if pending is not None and pending <= 0:
            stats["steps"][phase] = {"skipped": "empty", "pending": 0}
            logger.debug("spine conductor skip %s — no pending work", phase)
            continue
        phase_budget_sec = _spine_phase_cycle_budget_seconds(phase)
        logger.info(
            "spine conductor draining %s (cycle_budget_seconds=%s pending=%s)",
            phase,
            phase_budget_sec,
            pending,
        )
        step_stats = await _drain_spine_phase(
            phase,
            automation=automation,
            shadow=mode == "shadow",
            cycle_budget_seconds=phase_budget_sec,
        )
        stats["steps"][phase] = step_stats
        if mode == "shadow":
            logger.info("spine conductor shadow would run %s: %s", phase, step_stats)
        elif mode == "ordered":
            logger.info("spine conductor finished %s: %s", phase, step_stats)
            try:
                processed = int(
                    step_stats.get("articles_processed")
                    or step_stats.get("processed")
                    or 0
                )
                record_conductor_phase_heartbeat(
                    phase,
                    scheduler_path="spine_conductor",
                    items_processed=processed,
                    detail=step_stats,
                )
            except Exception:
                pass

    return stats


async def _drain_spine_phase(
    phase: str,
    *,
    automation: Any | None,
    shadow: bool,
    cycle_budget_seconds: int = 0,
) -> dict[str, Any]:
    if shadow:
        try:
            from services.backlog_metrics import get_all_backlog_counts

            pending = int(get_all_backlog_counts().get(phase, 0) or 0)
        except Exception:
            pending = -1
        return {"shadow": True, "pending": pending}

    if phase == "content_enrichment":
        return await _drain_enrichment(automation, budget_seconds=cycle_budget_seconds)
    if phase == "unified_intake_extraction":
        return await _drain_unified_intake(automation, budget_seconds=cycle_budget_seconds)
    if phase == "spine_sql_tail":
        from services.spine_sql_tail_service import run_spine_sql_tail_drain

        return await run_spine_sql_tail_drain()
    return {"skipped": phase}


async def _drain_enrichment(automation: Any | None, *, budget_seconds: int = 120) -> dict[str, Any]:
    import asyncio

    from services.article_content_enrichment_service import enrich_articles_batch
    from services.spine_work_queue_service import (
        claim_fair_share_batch,
        count_all_pending,
        finalize_content_enrichment_queue_round,
        spine_work_queues_enabled,
    )

    budget = RunBudget(budget_seconds)
    stall = DrainStallTracker()
    total = 0
    rounds = 0
    queues_active = spine_work_queues_enabled()
    claim_batch = 60
    enrich_batch = 60
    try:
        from shared.adaptive_batch_policy import resolve_adaptive_batch

        claim_batch, _meta = resolve_adaptive_batch("content_enrichment", claim_batch)
        enrich_batch = claim_batch
    except Exception:
        pass
    while not budget.expired():
        rounds += 1
        n = 0
        claimed: dict[str, list[int]] = {}
        use_queue_round = False
        try:
            loop = asyncio.get_event_loop()
            if queues_active:
                claimed = await loop.run_in_executor(
                    None, lambda: claim_fair_share_batch("content_enrichment", claim_batch)
                )
                use_queue_round = bool(claimed)
                if not use_queue_round:
                    pending_q = await loop.run_in_executor(
                        None, lambda: count_all_pending("content_enrichment")
                    )
                    if pending_q > 0:
                        had_pending = True
                        if stall.record_round(processed=0, had_pending=True):
                            break
                        continue
            n = int(
                await loop.run_in_executor(
                    None,
                    lambda c=claimed if use_queue_round else None: enrich_articles_batch(
                        batch_size=enrich_batch,
                        scoped_ids_by_schema=c,
                    )
                    or 0,
                )
            )
            if use_queue_round and claimed:
                for schema_name, article_ids in claimed.items():
                    await loop.run_in_executor(
                        None,
                        lambda s=schema_name, ids=article_ids: finalize_content_enrichment_queue_round(
                            s, ids
                        ),
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
    return {"rounds": rounds, "processed": total, "budget_seconds": budget_seconds}


async def _drain_unified_intake(
    automation: Any | None, *, budget_seconds: int = 0
) -> dict[str, Any]:
    from shared.unified_intake_extraction_runner import run_unified_intake_extraction_batch_drain

    drain_started = datetime.now(timezone.utc)
    batch_window_started: datetime | None = None
    scheduler_path = "spine_conductor"

    record_conductor_phase_heartbeat(
        "unified_intake_extraction",
        scheduler_path=scheduler_path,
        items_processed=0,
        detail={"status": "drain_started", "budget_seconds": budget_seconds},
    )

    await persist_conductor_phase_run_async(
        "unified_intake_extraction",
        drain_started,
        drain_started,
        scheduler_path=scheduler_path,
        loops_processed=0,
        stats={"status": "drain_started", "budget_seconds": budget_seconds},
    )

    async def _persist_batch(
        batch_n: int, stats: dict[str, Any], *, status: str = "batch_round"
    ) -> None:
        nonlocal batch_window_started
        now = datetime.now(timezone.utc)
        if batch_window_started is None:
            batch_window_started = now
        await persist_conductor_phase_run_async(
            "unified_intake_extraction",
            batch_window_started,
            now,
            scheduler_path=scheduler_path,
            loops_processed=batch_n,
            status=status,
            stats=stats,
        )
        record_conductor_phase_heartbeat(
            "unified_intake_extraction",
            scheduler_path=scheduler_path,
            items_processed=int(
                stats.get("round_processed")
                or stats.get("total_processed")
                or stats.get("articles_processed")
                or 0
            ),
            detail={"batch": batch_n, **stats},
        )
        batch_window_started = now

    async def _on_batch(batch_n: int, stats: dict[str, Any]) -> None:
        await _persist_batch(batch_n, stats)

    per_domain = None
    try:
        from shared.adaptive_batch_policy import resolve_adaptive_batch
        from shared.pipeline_batch_drain import phase_batch_limit

        default_pd = phase_batch_limit("unified_intake_extraction", 40)
        per_domain, _meta = resolve_adaptive_batch("unified_intake_extraction", default_pd)
    except Exception:
        pass

    result: dict[str, Any] = {}
    drain_error: str | None = None
    total_processed = 0
    batch_rounds = 0
    try:
        result = await run_unified_intake_extraction_batch_drain(
            budget_seconds=budget_seconds,
            articles_per_domain=per_domain,
            on_batch_complete=_on_batch,
        )
        if not isinstance(result, dict):
            result = {}
    except Exception as exc:
        drain_error = str(exc)[:500]
        raise
    finally:
        total_processed = int(result.get("articles_processed") or 0)
        batch_rounds = int(result.get("batch_rounds") or 0)
        drain_finished = datetime.now(timezone.utc)
        finish_stats: dict[str, Any] = {
            "round_processed": total_processed,
            "total_processed": total_processed,
            "articles_processed": total_processed,
            "batch_rounds": batch_rounds,
            "backfill_count": int(result.get("legacy_backfilled") or 0),
            "budget_seconds": budget_seconds,
        }
        if drain_error:
            finish_stats["error"] = drain_error
        await persist_conductor_phase_run_async(
            "unified_intake_extraction",
            drain_started,
            drain_finished,
            success=drain_error is None,
            scheduler_path=scheduler_path,
            loops_processed=max(1, batch_rounds),
            status="drain_finished",
            stats=finish_stats,
        )

    return {
        "rounds": batch_rounds,
        "articles_processed": total_processed,
        "budget_seconds": budget_seconds,
    }


def spine_phase_should_suppress_scheduler(phase_name: str) -> bool:
    """Retired — PipelineController owns spine phase scheduling."""
    return False
