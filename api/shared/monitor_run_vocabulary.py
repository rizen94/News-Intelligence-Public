"""
Monitor run vocabulary — SSOT for phase runs, throughput, and run-history measurability.

See docs/monitor_alignment/CROSSWALK.md and docs/monitor_alignment/S2_persistence.md.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, TypedDict

logger = logging.getLogger(__name__)

MONITOR_SCHEMA_VERSION = "1.1"

# Merged from phase_batch_run_history, processing_progress, conductor_run_history, pipeline_controller.
THROUGHPUT_COUNT_KEYS: tuple[str, ...] = (
    "round_processed",
    "total_processed",
    "articles_processed",
    "processed",
    "llm_processed",
    "contexts_processed",
    "claims_inserted",
    "profiles_updated",
    "compiled",
    "chronicle_entries",
    "storylines_scanned",
    "articles_matched",
    "entity_profiles_built",
    "entity_profiles_enriched",
    "items_processed",
    "link_indexer_articles",
)

# Keys that count as iteration-level throughput (exclude cumulative-only for row count).
ITERATION_THROUGHPUT_KEYS: tuple[str, ...] = (
    "round_processed",
    "articles_processed",
    "processed",
    "contexts_processed",
    "claims_inserted",
    "profiles_updated",
    "compiled",
    "chronicle_entries",
    "storylines_scanned",
    "articles_matched",
    "entity_profiles_built",
    "entity_profiles_enriched",
    "items_processed",
)

# Chemistry-style connection phases (Monitor / operator chrome)
CHEMISTRY_PHASE_DISPLAY_LABELS: dict[str, str] = {
    "collision_sampling": "Collision sampling (loose bonds)",
    "stimulus_rag": "Stimulus RAG (evidence pull)",
    "protein_harden": "Protein harden (establish edges)",
    "embedding_link_candidates": "Embedding link candidates",
    "graph_connection_distillation": "Graph connection distillation",
}


class RunHistoryStatus(StrEnum):
    BATCH_ROUND = "batch_round"
    DRAIN_STARTED = "drain_started"
    DRAIN_FINISHED = "drain_finished"
    PHASE_STARTED = "phase_started"
    PHASE_FINISHED = "phase_finished"
    PHASE_FAILED = "phase_failed"


RUN_HISTORY_SKIP_STATUSES: frozenset[str] = frozenset(
    {
        RunHistoryStatus.DRAIN_STARTED,
        RunHistoryStatus.PHASE_STARTED,
    }
)

RUN_HISTORY_TERMINAL_STATUSES: frozenset[str] = frozenset(
    {
        RunHistoryStatus.BATCH_ROUND,
        RunHistoryStatus.DRAIN_FINISHED,
        RunHistoryStatus.PHASE_FINISHED,
    }
)

MEANINGFUL_DURATION_SEC = 1.0


class PhaseActivitySnapshot(TypedDict, total=False):
    """Known activity-feed fields (activity_feed_service accepts extra keys)."""

    phase_key: str
    task_name: str  # deprecated alias
    iteration_index: int
    loops_processed: int  # deprecated alias
    rows_processed: int
    total_processed: int
    message: str
    started_at: str
    running_instances: int


@dataclass
class PhaseRunEvent:
    phase_key: str
    iteration_index: int
    rows_processed: int
    rows_cumulative: int | None
    run_history_status: str
    scheduler_path: str
    started_at: datetime
    finished_at: datetime
    success: bool = True
    extra_metadata: dict[str, Any] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, Any]:
        meta: dict[str, Any] = {
            "batch": True,
            "status": self.run_history_status,
            "scheduler_path": self.scheduler_path,
            "loops_processed": self.iteration_index,
            "iteration_index": self.iteration_index,
        }
        if self.rows_cumulative is not None:
            meta["total_processed"] = self.rows_cumulative
        # Extra first, then pin iteration throughput so inflated action totals
        # in kwargs cannot overwrite rows_processed / round_processed.
        meta.update(self.extra_metadata)
        meta["round_processed"] = self.rows_processed
        meta["rows_processed"] = self.rows_processed
        return meta

    def activity_payload(self, *, message: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "phase_key": self.phase_key,
            "task_name": self.phase_key,
            "iteration_index": self.iteration_index,
            "loops_processed": self.iteration_index,
            "rows_processed": self.rows_processed,
            "total_processed": self.rows_cumulative,
        }
        if message is not None:
            payload["message"] = message
        return payload


def throughput_from_payload(payload: dict[str, Any] | None, *, prefer_iteration: bool = True) -> int:
    """Extract row throughput from metadata or stats dict."""
    if not payload:
        return 0
    keys = ITERATION_THROUGHPUT_KEYS if prefer_iteration else THROUGHPUT_COUNT_KEYS
    for key in keys:
        try:
            val = int(payload.get(key) or 0)
        except (TypeError, ValueError):
            continue
        if val > 0:
            return val
    if prefer_iteration:
        try:
            val = int(payload.get("total_processed") or 0)
            return val if val > 0 else 0
        except (TypeError, ValueError):
            pass
    return 0


def batch_stats_had_work(stats: dict[str, Any] | None) -> bool:
    return throughput_from_payload(stats, prefer_iteration=True) > 0


def is_measurable_run_history_row(
    metadata: dict[str, Any] | None,
    *,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    min_duration_sec: float = MEANINGFUL_DURATION_SEC,
) -> bool:
    """Same predicate as processing_progress runs_1h / runs_24h SQL."""
    meta = metadata or {}
    status = str(meta.get("status") or "").strip()
    if status in RUN_HISTORY_SKIP_STATUSES:
        return False
    if status in RUN_HISTORY_TERMINAL_STATUSES:
        return True
    if throughput_from_payload(meta) > 0:
        return True
    if started_at is not None and finished_at is not None and finished_at > started_at:
        try:
            dur = (finished_at - started_at).total_seconds()
            if dur >= min_duration_sec:
                return True
        except Exception:
            pass
    return False


def run_history_measurable_sql(*, min_dur_param: str = "%(min_dur)s") -> str:
    """SQL fragment for processing_progress — kept in sync with is_measurable_run_history_row."""
    terminal = ", ".join(f"'{s}'" for s in sorted(RUN_HISTORY_TERMINAL_STATUSES))
    skip = ", ".join(f"'{s}'" for s in sorted(RUN_HISTORY_SKIP_STATUSES))
    keys_sql = ", ".join(
        f"COALESCE((metadata->>'{k}')::bigint, 0)" for k in ITERATION_THROUGHPUT_KEYS[:8]
    )
    return f"""(
        COALESCE(metadata->>'status', '') NOT IN ({skip})
        AND (
            EXTRACT(EPOCH FROM (finished_at - started_at)) >= {min_dur_param}
            OR COALESCE(metadata->>'status', '') IN ({terminal})
            OR GREATEST({keys_sql}) > 0
        )
    )"""


def metadata_batch_throughput_sql(*, metadata_expr: str = "metadata") -> str:
    """SQL expression: first positive iteration throughput key.

    Must match ``throughput_from_payload(..., prefer_iteration=True)``. Using
    ``GREATEST`` inflated Monitor rows/run when metadata also carried action
    totals (e.g. membership dry-run demotions) under ``processed`` /
    ``items_processed`` while ``round_processed`` held the real batch size.
    """
    nullifs = [
        f"NULLIF(COALESCE(({metadata_expr}->>'{k}')::bigint, 0), 0)"
        for k in ITERATION_THROUGHPUT_KEYS
    ]
    nullifs.append(
        f"NULLIF(COALESCE(({metadata_expr}->>'total_processed')::bigint, 0), 0)"
    )
    return f"COALESCE({', '.join(nullifs)}, 0)"


def query_measured_rows_per_run_by_phase(cur, *, window_hours: int = 24) -> dict[str, tuple[int, str, int]]:
    """
    Average rows processed per batch run from automation_run_history (24h window).

    Returns phase_name -> (avg_rows, source, sample_count).
    """
    throughput = metadata_batch_throughput_sql(metadata_expr="metadata")
    terminal = ", ".join(f"'{s}'" for s in sorted({"drain_finished", "phase_finished"}))
    skip = ", ".join(f"'{s}'" for s in sorted(RUN_HISTORY_SKIP_STATUSES | {RunHistoryStatus.PHASE_FAILED}))
    measurable = run_history_measurable_sql(min_dur_param=str(MEANINGFUL_DURATION_SEC))
    try:
        cur.execute(
            f"""
            SELECT
                phase_name,
                COUNT(*)::int AS sample_count,
                COALESCE(
                    ROUND(AVG({throughput}))::int,
                    0
                ) AS avg_rows,
                COUNT(*) FILTER (
                    WHERE COALESCE(metadata->>'status', '') IN ({terminal})
                )::int AS terminal_count
            FROM automation_run_history
            WHERE finished_at >= NOW() - INTERVAL '{int(window_hours)} hours'
              AND success IS TRUE
              AND metadata IS NOT NULL
              AND (
                  COALESCE((metadata->>'batch')::boolean, false)
                  OR metadata->>'batch' = 'true'
              )
              AND COALESCE(metadata->>'status', '') NOT IN ({skip})
              AND {measurable}
              AND {throughput} > 0
            GROUP BY phase_name
            """
        )
        rows = cur.fetchall() or []
    except Exception as e:
        logger.debug("query_measured_rows_per_run_by_phase: %s", e)
        return {}

    out: dict[str, tuple[int, str, int]] = {}
    for raw_name, sample_count, avg_rows, terminal_count in rows:
        name = str(raw_name or "").strip()
        if not name:
            continue
        count = int(sample_count or 0)
        avg = max(1, int(avg_rows or 0))
        if int(terminal_count or 0) >= 1:
            source = "measured_24h_terminal"
        elif count >= 3:
            source = "measured_24h"
        else:
            source = "measured_24h_small_sample"
        out[name] = (avg, source, count)
    return out


def normalize_phase_run_event(
    phase_key: str,
    iteration_index: int,
    *,
    started_at: datetime,
    finished_at: datetime,
    scheduler_path: str = "automation_manager",
    run_history_status: str = RunHistoryStatus.BATCH_ROUND,
    success: bool = True,
    allow_empty: bool = False,
    **raw_stats: Any,
) -> PhaseRunEvent:
    rows = throughput_from_payload(raw_stats, prefer_iteration=True)
    if rows == 0 and allow_empty:
        rows = 0
    cumulative = raw_stats.get("total_processed") or raw_stats.get("rows_cumulative")
    try:
        rows_cumulative = int(cumulative) if cumulative is not None else None
    except (TypeError, ValueError):
        rows_cumulative = None
    extra = {
        k: v
        for k, v in raw_stats.items()
        if v is not None
        and not k.startswith("_")
        and isinstance(v, (int, float, str, bool))
        and k not in ("total_processed", "rows_cumulative")
    }
    return PhaseRunEvent(
        phase_key=(phase_key or "").strip(),
        iteration_index=max(0, int(iteration_index or 0)),
        rows_processed=rows,
        rows_cumulative=rows_cumulative,
        run_history_status=run_history_status,
        scheduler_path=scheduler_path,
        started_at=started_at,
        finished_at=finished_at,
        success=success,
        extra_metadata=extra,
    )


def format_activity_message(base_message: str, event: PhaseRunEvent) -> str:
    extra = event.extra_metadata or {}
    tier_suffix = ""
    try:
        fast = int(extra.get("fast_updated") or 0)
        full = int(extra.get("full_updated") or 0)
        if fast or full:
            tier_suffix = f", {fast} fast / {full} full"
    except (TypeError, ValueError):
        pass
    if event.rows_processed > 0:
        return f"{base_message} (round {event.iteration_index}, {event.rows_processed} processed{tier_suffix})"
    return f"{base_message} (round {event.iteration_index})"


def persist_phase_run_event(event: PhaseRunEvent, *, allow_empty: bool = False) -> bool:
    """Write measurable row to automation_run_history. Returns False if skipped."""
    if not event.phase_key:
        return False
    if event.rows_processed <= 0 and not allow_empty:
        if event.run_history_status == RunHistoryStatus.BATCH_ROUND:
            return False
    if not is_measurable_run_history_row(
        event.to_metadata(),
        started_at=event.started_at,
        finished_at=event.finished_at,
    ):
        return False
    from shared.services.automation_run_history_writer import persist_automation_run_history

    persist_automation_run_history(
        event.phase_key,
        event.started_at,
        event.finished_at,
        event.success,
        metadata=event.to_metadata(),
    )
    return True


async def emit_phase_run_event(
    event: PhaseRunEvent,
    *,
    activity_id: str,
    base_message: str,
    allow_empty_history: bool = False,
    invalidate_backlog_on_work: bool = True,
) -> bool:
    """
    SSOT write contract: activity feed always; history when measurable; backlog when work done.
    """
    message = format_activity_message(base_message, event)
    try:
        from services.activity_feed_service import get_activity_feed

        feed = get_activity_feed()
        feed.update_current_progress(
            activity_id,
            message=message,
            **event.activity_payload(),
        )
    except Exception as e:
        logger.debug("emit_phase_run_event activity: %s", e)

    persisted = False
    try:
        persisted = await asyncio.to_thread(
            persist_phase_run_event,
            event,
            allow_empty=allow_empty_history,
        )
    except Exception as e:
        logger.warning("emit_phase_run_event history %s: %s", event.phase_key, e)

    if invalidate_backlog_on_work and event.rows_processed > 0:
        try:
            from services.backlog_metrics import invalidate_backlog_metrics_cache

            invalidate_backlog_metrics_cache()
        except Exception:
            pass
        try:
            from services.monitor_backlog_snapshot_service import (
                maybe_refresh_monitor_backlog_snapshot_after_drain,
            )

            maybe_refresh_monitor_backlog_snapshot_after_drain()
        except Exception:
            pass

    return persisted
