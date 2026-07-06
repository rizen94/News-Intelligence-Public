"""Persist per-batch automation completions (Monitor runs_24h / throughput)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from shared.monitor_run_vocabulary import (
    RunHistoryStatus,
    batch_stats_had_work,
    normalize_phase_run_event,
    persist_phase_run_event,
    throughput_from_payload,
)

logger = logging.getLogger(__name__)

# Re-export SSOT symbols for backward compatibility.
__all__ = [
    "batch_stats_had_work",
    "phase_batch_metadata",
    "record_phase_batch_completion",
    "record_phase_batch_completion_async",
]


def phase_batch_metadata(
    *,
    scheduler_path: str = "automation_manager",
    status: str = "batch_round",
    loops_processed: int = 0,
    stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = throughput_from_payload(stats) if stats else 0
    meta: dict[str, Any] = {
        "batch": True,
        "status": status,
        "scheduler_path": scheduler_path,
        "loops_processed": loops_processed,
        "iteration_index": loops_processed,
        "rows_processed": rows,
    }
    if stats:
        for key, value in stats.items():
            if value is None or key.startswith("_"):
                continue
            if isinstance(value, (int, float, str, bool)):
                meta[key] = value
    return meta


def record_phase_batch_completion(
    phase_name: str,
    started_at: datetime,
    finished_at: datetime,
    *,
    stats: dict[str, Any] | None = None,
    scheduler_path: str = "automation_manager",
    status: str = RunHistoryStatus.BATCH_ROUND,
    loops_processed: int = 0,
    success: bool = True,
    allow_empty: bool = False,
) -> bool:
    """Insert one measurable automation_run_history row for a completed batch."""
    event = normalize_phase_run_event(
        phase_name,
        loops_processed,
        started_at=started_at,
        finished_at=finished_at,
        scheduler_path=scheduler_path,
        run_history_status=status,
        success=success,
        allow_empty=allow_empty,
        **(stats or {}),
    )
    return persist_phase_run_event(event, allow_empty=allow_empty)


async def record_phase_batch_completion_async(
    phase_name: str,
    started_at: datetime,
    finished_at: datetime,
    **kwargs: Any,
) -> bool:
    try:
        return await asyncio.to_thread(
            record_phase_batch_completion,
            phase_name,
            started_at,
            finished_at,
            **kwargs,
        )
    except Exception as e:
        logger.warning("phase batch history %s: %s", phase_name, e)
        return False
