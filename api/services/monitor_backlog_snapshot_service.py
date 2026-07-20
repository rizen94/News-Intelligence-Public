"""Precomputed Monitor backlog snapshot (refreshed on a schedule for fast page load)."""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

from config.runtime import env_str

logger = logging.getLogger(__name__)

_STATE_KEY = "monitor_backlog_snapshot"

_last_refresh_monotonic: float = 0.0
_last_drain_refresh_monotonic: float = 0.0
_refresh_lock = threading.Lock()
_refresh_inflight = False


def snapshot_interval_seconds() -> int:
    raw = env_str("MONITOR_BACKLOG_SNAPSHOT_INTERVAL_SECONDS", "900").strip()
    try:
        return max(60, int(raw))
    except ValueError:
        return 900


def drain_refresh_interval_seconds() -> int:
    """Min seconds between snapshot rebuilds triggered by phase drain completion."""
    raw = env_str("MONITOR_BACKLOG_SNAPSHOT_DRAIN_REFRESH_SECONDS", "60").strip()
    try:
        return max(15, int(raw))
    except ValueError:
        return 60


def refresh_monitor_backlog_snapshot(*, force: bool = False) -> dict[str, Any] | None:
    """Run heavy backlog_metrics queries once and persist to automation_state."""
    global _last_refresh_monotonic, _refresh_inflight
    interval = snapshot_interval_seconds()
    now_mono = time.monotonic()
    if not force and _last_refresh_monotonic and (now_mono - _last_refresh_monotonic) < interval:
        return read_monitor_backlog_snapshot(allow_stale=True)

    with _refresh_lock:
        if _refresh_inflight:
            # Another worker is already rebuilding (~60–90s); serve last snapshot.
            return read_monitor_backlog_snapshot(allow_stale=True)
        _refresh_inflight = True

    t0 = time.monotonic()
    try:
        from services.backlog_metrics import (
            get_all_backlog_counts,
            get_storyline_review_queue_pending,
            get_storyline_review_queue_pending_by_domain,
        )
        from shared.pipeline_queue_counts import get_all_phase_queue_depths

        pending = {k: int(v) for k, v in get_all_phase_queue_depths().items()}
        backlog = {k: int(v) for k, v in get_all_backlog_counts().items()}
        if not pending:
            prior = read_monitor_backlog_snapshot(allow_stale=True)
            prior_n = len((prior or {}).get("queue_depths") or (prior or {}).get("pending") or {})
            logger.warning(
                "monitor_backlog_snapshot refresh got 0 phases — not overwriting prior (%d phases)",
                prior_n,
            )
            return prior
        operator_metrics = {
            "storyline_review_queue_pending": get_storyline_review_queue_pending(),
            "storyline_review_queue_pending_by_domain": (
                get_storyline_review_queue_pending_by_domain()
            ),
        }
        work_queues: dict[str, Any] = {}
        try:
            from services.phase_work_queue_metrics import get_all_phase_work_queues

            work_queues = {
                k: dict(v) for k, v in get_all_phase_work_queues(pending).items()
            }
        except Exception as e:
            logger.warning("monitor_backlog_snapshot work_queues failed: %s", e)
        signal_lane_metrics: dict[str, int] = {}
        try:
            from services.phase_work_queue_metrics import get_signal_lane_counts_24h

            signal_lane_metrics = get_signal_lane_counts_24h()
        except Exception as e:
            logger.warning("monitor_backlog_snapshot signal_lane failed: %s", e)
        feed_health_metrics: dict[str, int] = {}
        try:
            from services.rss_feed_health_service import get_feed_health_monitor_counts

            feed_health_metrics = get_feed_health_monitor_counts()
        except Exception as e:
            logger.warning("monitor_backlog_snapshot feed_health failed: %s", e)
        spine_throughput: dict[str, Any] = {}
        assembly_throughput: dict[str, Any] = {}
        vault_work_queue: dict[str, Any] = {}
        intake_catchup_latency: dict[str, Any] = {}
        try:
            from services.spine_throughput_metrics import (
                get_spine_throughput_snapshot,
                sample_spine_latencies_from_db,
            )

            sample_spine_latencies_from_db(limit=100)
            spine_throughput = get_spine_throughput_snapshot()
        except Exception as e:
            logger.warning("monitor_backlog_snapshot spine_throughput failed: %s", e)
        try:
            from shared.intake_catchup_latency import (
                compute_intake_catchup_latency,
                record_intake_catchup_latency_sample,
            )

            intake_catchup_latency = compute_intake_catchup_latency(use_cache=False)
            record_intake_catchup_latency_sample(intake_catchup_latency)
        except Exception as e:
            logger.warning("monitor_backlog_snapshot intake_catchup_latency failed: %s", e)
        try:
            from services.assembly_throughput_metrics import get_assembly_throughput_snapshot

            assembly_throughput = get_assembly_throughput_snapshot()
        except Exception as e:
            logger.warning("monitor_backlog_snapshot assembly_throughput failed: %s", e)
        try:
            from services import vault_bridge_service as vault

            vault_work_queue = vault.read_cursors()
        except Exception as e:
            logger.warning("monitor_backlog_snapshot vault_work_queue failed: %s", e)
        refreshed_at = datetime.now(timezone.utc).isoformat()
        queue_audit: dict[str, Any] = {}
        try:
            from shared.queue_audit import build_queue_audit

            queue_audit = build_queue_audit(pending)
        except Exception as e:
            logger.warning("monitor_backlog_snapshot queue_audit failed: %s", e)
        unified_intake_breakdown: dict[str, int] | None = None
        try:
            from shared.pipeline_queue_counts import get_unified_intake_breakdown

            unified_intake_breakdown = dict(get_unified_intake_breakdown())
        except Exception as e:
            logger.warning("monitor_backlog_snapshot unified_intake_breakdown failed: %s", e)
        payload: dict[str, Any] = {
            "refreshed_at_utc": refreshed_at,
            "interval_seconds": interval,
            "queue_depths": pending,
            "scheduling_backlog": backlog,
            "pending": pending,
            "backlog": backlog,
            "operator_metrics": operator_metrics,
            "queue_audit": queue_audit,
            "unified_intake_breakdown": unified_intake_breakdown,
            "work_queues": work_queues,
            "signal_lane_metrics": signal_lane_metrics,
            "feed_health_metrics": feed_health_metrics,
            "spine_throughput": spine_throughput,
            "intake_catchup_latency": intake_catchup_latency,
            "assembly_throughput": assembly_throughput,
            "vault_work_queue": vault_work_queue,
            "intake_first_pass_sum": sum(
                int(v.get("intake_first_pass", 0) or 0) for v in work_queues.values()
            ),
            "intake_window_hours": work_queues.get(
                next(iter(work_queues), ""),
                {},
            ).get("intake_window_hours")
            if work_queues
            else None,
        }
        from shared.database.connection import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.automation_state (key, value, updated_at)
                    VALUES (%s, %s::jsonb, NOW())
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                    """,
                    (_STATE_KEY, json.dumps(payload)),
                )
            conn.commit()
        _last_refresh_monotonic = time.monotonic()
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "monitor_backlog_snapshot refreshed (%d phases, %dms)",
            len(pending),
            elapsed_ms,
        )
        try:
            _append_snapshot_history(payload, elapsed_ms=elapsed_ms, phase_count=len(pending))
        except Exception as hist_err:
            logger.debug("monitor_backlog_snapshot history: %s", hist_err)
        try:
            from domains.system_monitoring.routes.resource_dashboard import (
                soft_expire_processing_progress_fast_cache,
            )

            # Soft-expire (keep last phases) — hard invalidate caused perpetual warming banners.
            soft_expire_processing_progress_fast_cache()
        except Exception as inv_err:
            logger.debug("processing_progress fast cache soft-expire: %s", inv_err)
        return payload
    except Exception as e:
        logger.warning("refresh_monitor_backlog_snapshot failed: %s", e)
        return read_monitor_backlog_snapshot(allow_stale=True)
    finally:
        with _refresh_lock:
            _refresh_inflight = False


def read_monitor_backlog_snapshot(*, allow_stale: bool = False) -> dict[str, Any] | None:
    """Load snapshot from automation_state; None if missing or too old."""
    try:
        from shared.database.connection import get_ui_db_connection_context

        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT value, updated_at FROM public.automation_state WHERE key = %s",
                    (_STATE_KEY,),
                )
                row = cur.fetchone()
        if not row or not row[0]:
            return None
        raw = row[0]
        if isinstance(raw, str):
            data = json.loads(raw)
        elif isinstance(raw, dict):
            data = dict(raw)
        else:
            return None
        refreshed_at = data.get("refreshed_at_utc")
        if refreshed_at and not allow_stale:
            try:
                ts = datetime.fromisoformat(str(refreshed_at).replace("Z", "+00:00"))
                age = (datetime.now(timezone.utc) - ts).total_seconds()
                if age > snapshot_interval_seconds() * 1.5:
                    return None
            except Exception:
                pass
        return data
    except Exception as e:
        logger.debug("read_monitor_backlog_snapshot: %s", e)
        return None


def _append_snapshot_history(
    payload: dict[str, Any],
    *,
    elapsed_ms: int,
    phase_count: int,
) -> None:
    """Persist a history row for read-mostly trend / p95 analysis (Phase E)."""
    from shared.database.connection import get_db_connection_context

    queue_depths = payload.get("queue_depths") or payload.get("pending") or {}
    backlog_counts = payload.get("backlog") or payload.get("backlog_counts") or {}
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.monitor_backlog_snapshot_history (
                    refreshed_at, elapsed_ms, phase_count, queue_depths, backlog_counts, payload
                ) VALUES (NOW(), %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)
                """,
                (
                    elapsed_ms,
                    phase_count,
                    json.dumps(queue_depths),
                    json.dumps(backlog_counts),
                    json.dumps(
                        {
                            "refreshed_at_utc": payload.get("refreshed_at_utc"),
                            "operator_metrics": payload.get("operator_metrics"),
                        }
                    ),
                ),
            )
            # Retain ~14 days
            cur.execute(
                """
                DELETE FROM intelligence.monitor_backlog_snapshot_history
                WHERE refreshed_at < NOW() - INTERVAL '14 days'
                """
            )
        conn.commit()


def maybe_refresh_monitor_backlog_snapshot() -> None:
    """Called from health_check loop — refresh when interval elapsed."""
    interval = snapshot_interval_seconds()
    if _last_refresh_monotonic and (time.monotonic() - _last_refresh_monotonic) < interval:
        return
    refresh_monitor_backlog_snapshot(force=True)


def maybe_refresh_monitor_backlog_snapshot_after_drain() -> None:
    """After a queue-draining phase completes, refresh snapshot (throttled) so Monitor Total queue moves."""
    global _last_drain_refresh_monotonic
    interval = drain_refresh_interval_seconds()
    now_mono = time.monotonic()
    if _last_drain_refresh_monotonic and (now_mono - _last_drain_refresh_monotonic) < interval:
        return
    _last_drain_refresh_monotonic = now_mono
    refresh_monitor_backlog_snapshot(force=True)
