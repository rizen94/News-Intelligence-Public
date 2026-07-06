"""Persist automation_run_history rows for spine/assembly conductor phases."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Awaitable, Callable

from shared.monitor_run_vocabulary import (
    RunHistoryStatus,
    is_measurable_run_history_row,
    normalize_phase_run_event,
    persist_phase_run_event,
    throughput_from_payload,
)

logger = logging.getLogger(__name__)

_TERMINAL_CONDUCTOR_STATUSES = frozenset(
    {
        RunHistoryStatus.BATCH_ROUND,
        RunHistoryStatus.DRAIN_FINISHED,
        RunHistoryStatus.PHASE_FINISHED,
    }
)


def conductor_history_payload(
    *,
    loops_processed: int = 0,
    scheduler_path: str,
    stats: dict[str, Any] | None = None,
    status: str | None = None,
    phase_name: str = "",
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> dict[str, Any]:
    """Build metadata via monitor SSOT (canonical iteration_index / rows_processed aliases)."""
    from datetime import timezone

    now = datetime.now(timezone.utc)
    event = normalize_phase_run_event(
        phase_name,
        loops_processed,
        started_at=started_at or now,
        finished_at=finished_at or now,
        scheduler_path=scheduler_path,
        run_history_status=status or RunHistoryStatus.BATCH_ROUND,
        allow_empty=status in _TERMINAL_CONDUCTOR_STATUSES if status else False,
        **(stats or {}),
    )
    return event.to_metadata()


def items_processed_from_stats(stats: dict[str, Any]) -> int:
    val = throughput_from_payload(stats, prefer_iteration=False)
    if val > 0:
        return val
    batch = stats.get("batch")
    if isinstance(batch, dict):
        total = 0
        for domain_stats in batch.values():
            if isinstance(domain_stats, dict):
                before = int(domain_stats.get("unlinked_before") or 0)
                after = int(domain_stats.get("unlinked_after") or 0)
                if before > after:
                    total += before - after
        if total:
            return total
    return 0


def persist_conductor_phase_run(
    phase_name: str,
    started_at: datetime,
    finished_at: datetime,
    *,
    success: bool = True,
    scheduler_path: str,
    loops_processed: int = 0,
    stats: dict[str, Any] | None = None,
    status: str | None = None,
) -> bool:
    """Persist conductor row using shared vocabulary; returns True when row was written."""
    status_str = status or RunHistoryStatus.BATCH_ROUND
    allow_empty = status_str in _TERMINAL_CONDUCTOR_STATUSES
    event = normalize_phase_run_event(
        phase_name,
        loops_processed,
        started_at=started_at,
        finished_at=finished_at,
        scheduler_path=scheduler_path,
        run_history_status=status_str,
        success=success,
        allow_empty=allow_empty,
        **(stats or {}),
    )
    meta = event.to_metadata()
    if is_measurable_run_history_row(meta, started_at=started_at, finished_at=finished_at):
        return persist_phase_run_event(event, allow_empty=allow_empty)
    # Instant markers (phase_started, drain_started) — traceability only, excluded from runs_1h.
    from shared.services.automation_run_history_writer import persist_automation_run_history

    persist_automation_run_history(
        phase_name,
        started_at,
        finished_at,
        success,
        metadata=meta,
    )
    return False


async def persist_conductor_phase_run_async(
    phase_name: str,
    started_at: datetime,
    finished_at: datetime,
    *,
    success: bool = True,
    scheduler_path: str,
    loops_processed: int = 0,
    stats: dict[str, Any] | None = None,
    status: str | None = None,
) -> bool:
    try:
        return await asyncio.to_thread(
            persist_conductor_phase_run,
            phase_name,
            started_at,
            finished_at,
            success=success,
            scheduler_path=scheduler_path,
            loops_processed=loops_processed,
            stats=stats,
            status=status,
        )
    except Exception as e:
        logger.debug("conductor run history %s: %s", phase_name, e)
        return False


def record_conductor_phase_heartbeat(
    phase_name: str,
    *,
    scheduler_path: str,
    items_processed: int = 0,
    detail: dict[str, Any] | None = None,
) -> None:
    try:
        from services.pipeline_phase_heartbeat_service import record_phase_heartbeat

        record_phase_heartbeat(
            phase_name,
            scheduler_path=scheduler_path,
            success=True,
            items_processed=items_processed,
            detail=detail or {},
        )
    except Exception:
        pass


async def run_conductor_phase_with_history(
    phase_name: str,
    runner: Callable[[], Awaitable[dict[str, Any]]],
    *,
    scheduler_path: str,
    record_start: bool = True,
) -> dict[str, Any]:
    from datetime import timezone

    started = datetime.now(timezone.utc)
    if record_start:
        await persist_conductor_phase_run_async(
            phase_name,
            started,
            started,
            scheduler_path=scheduler_path,
            loops_processed=0,
            status=RunHistoryStatus.PHASE_STARTED,
        )
        record_conductor_phase_heartbeat(
            phase_name,
            scheduler_path=scheduler_path,
            items_processed=0,
            detail={"status": RunHistoryStatus.PHASE_STARTED},
        )

    try:
        result = await runner()
        if not isinstance(result, dict):
            result = {"result": result}
    except Exception:
        finished = datetime.now(timezone.utc)
        await persist_conductor_phase_run_async(
            phase_name,
            started,
            finished,
            success=False,
            scheduler_path=scheduler_path,
            loops_processed=1,
            status=RunHistoryStatus.PHASE_FAILED,
        )
        raise

    finished = datetime.now(timezone.utc)
    processed = items_processed_from_stats(result)
    await persist_conductor_phase_run_async(
        phase_name,
        started,
        finished,
        scheduler_path=scheduler_path,
        loops_processed=1,
        stats=result,
        status=RunHistoryStatus.PHASE_FINISHED,
    )
    record_conductor_phase_heartbeat(
        phase_name,
        scheduler_path=scheduler_path,
        items_processed=processed,
        detail=result,
    )
    return result
