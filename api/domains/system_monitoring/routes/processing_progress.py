"""
Processing progress payload for Monitor (dimension throughput, phase_dashboard, hourly ticks).

The HTTP route is registered on ``resource_dashboard.router`` as ``GET /processing_progress``
(same prefix as ``/backlog_status``) so the path is always mounted with the rest of system monitoring.
"""

from __future__ import annotations

import logging
import math
import time
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Literal

PendingMetricsSource = Literal["none", "live", "snapshot"]

from shared.database.connection import get_ui_db_connection as get_db_connection
from shared.domain_registry import get_schema_names_active, pipeline_url_schema_pairs
from shared.monitor_run_vocabulary import (
    MEANINGFUL_DURATION_SEC,
    MONITOR_SCHEMA_VERSION,
    RUN_HISTORY_SKIP_STATUSES,
    run_history_measurable_sql,
    throughput_from_payload,
)

logger = logging.getLogger(__name__)

# Keep aligned with resource_dashboard.BACKLOG_WORKLOAD_WINDOW_DAYS (docstring note only).
_BACKLOG_WORKLOAD_WINDOW_DAYS = 4

# Orchestrator-only phase: omit from Processing pulse (still runs on schedule; history remains in DB).
_PROCESSING_PROGRESS_EXCLUDED_PHASES = frozenset({"nightly_enrichment_context"})


def _processing_progress_excluded_phases() -> frozenset[str]:
    """Hide inactive intake modes and unified-superseded phases from Monitor pulse."""
    excluded = set(_PROCESSING_PROGRESS_EXCLUDED_PHASES)
    try:
        from shared.pipeline_resource_policy import (
            intake_extraction_suppressed,
            legacy_intake_extraction_phases,
            unified_superseded_automation_phases,
        )

        if intake_extraction_suppressed():
            excluded |= set(legacy_intake_extraction_phases())
            excluded |= set(unified_superseded_automation_phases())
        else:
            excluded.add("unified_intake_extraction")
    except Exception:
        pass
    return frozenset(excluded)


def _phase_scheduling_status(phase_name: str) -> str:
    """active | suppressed (intake mode) | retired (post-spine)."""
    name = (phase_name or "").strip()
    if not name:
        return "active"
    try:
        from shared.assembly_phase_order import post_spine_scheduling_suppressed

        if post_spine_scheduling_suppressed(name):
            return "retired"
    except Exception:
        pass
    try:
        from shared.pipeline_resource_policy import intake_phase_scheduled

        if not intake_phase_scheduled(name):
            return "suppressed"
    except Exception:
        pass
    return "active"


def _monitor_pulse_visible_phase(name: str) -> bool:
    """Monitor pulse table/ticks: hide retired post-spine phases (not scheduled)."""
    if not name or name in _processing_progress_excluded_phases():
        return False
    return _phase_scheduling_status(name) != "retired"


def _rollback_conn(conn) -> None:
    try:
        conn.rollback()
    except Exception:
        pass


def _unified_pending_count(
    phase_name: str,
    pending_m: dict[str, int],
    wq: dict[str, Any],
) -> int:
    """queue_depth from backlog_metrics kernel (work-queue breakdown is first_pass/retry only)."""
    _ = wq
    return int(pending_m.get(phase_name, 0) or 0)


def _norm_phase_name(raw: Any) -> str | None:
    """Stable string phase key for grouping and sorting; None if unusable."""
    if raw is None:
        return None
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8", errors="replace")
        except Exception:
            return None
    if not isinstance(raw, str):
        raw = str(raw)
    s = raw.strip()
    return s or None


_TERMINAL_BATCH_STATUSES = frozenset({"drain_finished", "phase_finished"})
_SKIP_BATCH_STATUSES = RUN_HISTORY_SKIP_STATUSES | frozenset({"phase_failed"})


def _measured_count_from_payload(payload: dict[str, Any]) -> int | None:
    # wave_processed is parallel batch slots, not articles cleared — ignore wave-only rows.
    if payload.get("wave") is not None and throughput_from_payload(payload) <= 0:
        return None
    n = throughput_from_payload(payload)
    return n if n > 0 else None


def _measured_batch_per_run_by_phase(
    rows: list[tuple[Any, Any]],
) -> dict[str, tuple[int, str]]:
    """Average rows processed per batch run from recent automation_run_history JSON payloads."""
    terminal_samples: dict[str, list[int]] = defaultdict(list)
    fallback_samples: dict[str, list[int]] = defaultdict(list)
    for raw_name, err in rows:
        norm = _norm_phase_name(raw_name)
        if not norm or not err:
            continue
        try:
            payload = json.loads(err)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(payload, dict) or not payload.get("batch"):
            continue
        status = str(payload.get("status") or "").strip().lower()
        if status in _SKIP_BATCH_STATUSES:
            continue
        n = _measured_count_from_payload(payload)
        if n is None:
            continue
        if status in _TERMINAL_BATCH_STATUSES:
            terminal_samples[norm].append(n)
        elif status in ("batch_round", "phase_finished") or payload.get("batch_round") is not None:
            fallback_samples[norm].append(n)
        elif status not in _SKIP_BATCH_STATUSES and status:
            fallback_samples[norm].append(n)

    out: dict[str, tuple[int, str]] = {}
    for phase in set(terminal_samples) | set(fallback_samples):
        vals = terminal_samples.get(phase) or fallback_samples[phase]
        avg = max(1, int(round(sum(vals) / len(vals))))
        source = (
            "measured_24h_terminal"
            if phase in terminal_samples and len(terminal_samples[phase]) >= 1
            else ("measured_24h" if len(vals) >= 3 else "measured_24h_small_sample")
        )
        out[phase] = (avg, source)

    return out


def _json_safe_float(value: Any, *, ndigits: int = 1) -> float | None:
    """Starlette JSONResponse uses allow_nan=False; drop NaN/Inf so encoding never raises."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    return round(f, ndigits)


def _build_dimension_throughput(cur) -> list[dict[str, Any]]:
    """Heavy cross-schema throughput counts (Monitor fast path skips this)."""
    from shared.monitor_dimension_metrics import apply_dimension_backlogs
    from shared.pipeline_queue_counts import get_all_phase_queue_depths

    queue_depths = get_all_phase_queue_depths()
    dimensions: list[dict[str, Any]] = []
    enriched_1h = enriched_24h = enriched_7d = 0
    for schema in get_pipeline_schema_names_active():
        try:
            cur.execute(
                f"""
                SELECT
                    COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '1 hour'),
                    COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '24 hours'),
                    COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '7 days')
                FROM {schema}.articles
                WHERE enrichment_status = 'enriched' AND url IS NOT NULL AND url != ''
                """
            )
            r = cur.fetchone()
            if r:
                enriched_1h += r[0] or 0
                enriched_24h += r[1] or 0
                enriched_7d += r[2] or 0
        except Exception:
            pass

    dimensions.append(
        {
            "id": "articles_enriched",
            "label": "Articles enriched",
            "backlog": 0,
            "last_1h": enriched_1h,
            "last_24h": enriched_24h,
            "last_7d": enriched_7d,
        }
    )

    context_backlog_breakdown: dict[str, int] = {}
    ctx_claim_1h = ctx_claim_24h = ctx_claim_7d = 0
    ctx_created_1h = ctx_created_24h = ctx_created_7d = 0
    try:
        try:
            from services.claim_extraction_service import get_context_claim_backlog_stats

            context_backlog_breakdown = get_context_claim_backlog_stats()
        except Exception:
            context_backlog_breakdown = {}
        cur.execute(
            """
            SELECT
                COUNT(DISTINCT context_id) FILTER (WHERE ec.created_at >= NOW() - INTERVAL '1 hour'),
                COUNT(DISTINCT context_id) FILTER (WHERE ec.created_at >= NOW() - INTERVAL '24 hours'),
                COUNT(DISTINCT context_id) FILTER (WHERE ec.created_at >= NOW() - INTERVAL '7 days')
            FROM intelligence.extracted_claims ec
            """
        )
        r = cur.fetchone()
        if r:
            ctx_claim_1h, ctx_claim_24h, ctx_claim_7d = (r[0] or 0), (r[1] or 0), (r[2] or 0)
        cur.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '1 hour'),
                COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '24 hours'),
                COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days')
            FROM intelligence.contexts
            """
        )
        r2 = cur.fetchone()
        if r2:
            ctx_created_1h, ctx_created_24h, ctx_created_7d = (
                r2[0] or 0,
                r2[1] or 0,
                r2[2] or 0,
            )
    except Exception:
        pass

    dimensions.append(
        {
            "id": "contexts_claimed",
            "label": "Contexts → claims (actionable queue)",
            "backlog": 0,
            "backlog_breakdown": context_backlog_breakdown or None,
            "backlog_note": (
                "backlog = queue_depth(claim_extraction); matches automation eligibility. "
                "backlog_breakdown.total_no_claims is terminal inventory, not work to do"
            ),
            "last_1h": ctx_claim_1h,
            "last_24h": ctx_claim_24h,
            "last_7d": ctx_claim_7d,
        }
    )
    dimensions.append(
        {
            "id": "contexts_created",
            "label": "Contexts created",
            "backlog": None,
            "last_1h": ctx_created_1h,
            "last_24h": ctx_created_24h,
            "last_7d": ctx_created_7d,
        }
    )

    ep_any_1h = ep_any_24h = ep_any_7d = 0
    try:
        cur.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '1 hour'),
                COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '24 hours'),
                COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '7 days')
            FROM intelligence.entity_profiles
            """
        )
        r = cur.fetchone()
        if r:
            ep_any_1h, ep_any_24h, ep_any_7d = (r[0] or 0), (r[1] or 0), (r[2] or 0)
    except Exception:
        pass

    dimensions.append(
        {
            "id": "entity_profiles_touched",
            "label": "Entity profiles updated",
            "backlog": 0,
            "last_1h": ep_any_1h,
            "last_24h": ep_any_24h,
            "last_7d": ep_any_7d,
        }
    )

    docs_1h = docs_24h = docs_7d = 0
    try:
        cur.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '1 hour'),
                COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '24 hours'),
                COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '7 days')
            FROM intelligence.processed_documents
            WHERE extracted_sections IS NOT NULL AND extracted_sections != '[]'::jsonb
            """
        )
        r = cur.fetchone()
        if r:
            docs_1h, docs_24h, docs_7d = (r[0] or 0), (r[1] or 0), (r[2] or 0)
    except Exception:
        pass

    dimensions.append(
        {
            "id": "documents_extracted",
            "label": "PDFs / documents extracted",
            "backlog": 0,
            "last_1h": docs_1h,
            "last_24h": docs_24h,
            "last_7d": docs_7d,
        }
    )

    syn_1h = syn_24h = syn_7d = 0
    for _dk, schema in pipeline_url_schema_pairs():
        try:
            cur.execute(
                f"""
                SELECT
                    COUNT(*) FILTER (WHERE synthesized_at >= NOW() - INTERVAL '1 hour'),
                    COUNT(*) FILTER (WHERE synthesized_at >= NOW() - INTERVAL '24 hours'),
                    COUNT(*) FILTER (WHERE synthesized_at >= NOW() - INTERVAL '7 days')
                FROM {schema}.storylines
                WHERE synthesized_at IS NOT NULL
                """
            )
            r = cur.fetchone()
            if r:
                syn_1h += r[0] or 0
                syn_24h += r[1] or 0
                syn_7d += r[2] or 0
        except Exception:
            pass

    dimensions.append(
        {
            "id": "storylines_synthesized",
            "label": "Storylines synthesized",
            "backlog": 0,
            "last_1h": syn_1h,
            "last_24h": syn_24h,
            "last_7d": syn_7d,
        }
    )
    return apply_dimension_backlogs(dimensions, queue_depths)


def compute_processing_progress_response(
    *,
    include_hourly_tick_rows: bool = False,
    include_pending_metrics: bool = False,
    include_dimension_throughput: bool = True,
    pending_metrics_source: PendingMetricsSource = "none",
) -> dict[str, Any]:
    """
    Build JSON for GET /api/system_monitoring/processing_progress.

    ``include_hourly_tick_rows``: when False (default), skip shipping up to thousands of
    hourly bucket rows; set ``hourly_phase_tick_bucket_count`` via a single COUNT query
    so the Monitor page stays light on JSON size and encoding time.

    ``include_pending_metrics``: when False, skip live ``backlog_metrics`` unless
    ``pending_metrics_source`` is ``snapshot`` (precomputed index in automation_state).

    ``pending_metrics_source``: ``none`` | ``live`` | ``snapshot``. ``snapshot`` reads
    ``monitor_backlog_snapshot`` refreshed every ~15 minutes for fast Monitor page load.

    See resource_dashboard route docstring / AGENTS.md for field meanings.
    """
    if include_pending_metrics:
        pending_metrics_source = "live"
    elif pending_metrics_source not in ("none", "live", "snapshot"):
        pending_metrics_source = "none"
    measured_batch_rows: list[tuple[Any, Any]] = []
    _build_started = time.monotonic()
    try:
        conn = get_db_connection()
    except Exception as e:
        logger.warning("processing_progress: database unavailable: %s", e)
        return {"success": False, "error": str(e)[:200], "data": None}

    now_iso = datetime.now(timezone.utc).isoformat()
    dimensions: list[dict[str, Any]] = []
    phases: list[dict[str, Any]] = []
    hourly_phase_ticks: list[dict[str, Any]] = []
    hourly_phase_tick_bucket_count: int | None = None

    try:
        cur = conn.cursor()
        try:
            cur.execute("SET LOCAL statement_timeout = '8s'")
        except Exception:
            _rollback_conn(conn)

        if include_dimension_throughput:
            try:
                dimensions = _build_dimension_throughput(cur)
            except Exception as e:
                logger.debug("processing_progress dimensions: %s", e)
                _rollback_conn(conn)

        try:
            min_dur = MEANINGFUL_DURATION_SEC
            measurable = run_history_measurable_sql()
            cur.execute(
                f"""
                SELECT phase_name,
                    COUNT(*) FILTER (
                        WHERE finished_at >= NOW() - INTERVAL '1 hour'
                          AND {measurable}
                    ) AS r1h,
                    COUNT(*) FILTER (
                        WHERE finished_at >= NOW() - INTERVAL '24 hours'
                          AND {measurable}
                    ) AS r24h,
                    COUNT(*) FILTER (
                        WHERE finished_at >= NOW() - INTERVAL '7 days'
                          AND {measurable}
                    ) AS r7d,
                    COUNT(*) FILTER (
                        WHERE finished_at >= NOW() - INTERVAL '24 hours'
                          AND success IS TRUE
                          AND {measurable}
                    ) AS s24h,
                    COUNT(*) FILTER (
                        WHERE finished_at >= NOW() - INTERVAL '24 hours'
                          AND success IS NOT TRUE
                          AND {measurable}
                    ) AS f24h,
                    COUNT(*) FILTER (
                        WHERE finished_at >= NOW() - INTERVAL '7 days'
                          AND success IS TRUE
                          AND {measurable}
                    ) AS s7d,
                    COUNT(*) FILTER (
                        WHERE finished_at >= NOW() - INTERVAL '7 days'
                          AND success IS NOT TRUE
                          AND {measurable}
                    ) AS f7d,
                    AVG(EXTRACT(EPOCH FROM (finished_at - started_at))) FILTER (
                        WHERE finished_at >= NOW() - INTERVAL '24 hours'
                          AND started_at IS NOT NULL
                          AND finished_at > started_at
                          AND {measurable}
                    ) AS avg_s
                FROM automation_run_history
                WHERE finished_at >= NOW() - INTERVAL '7 days'
                  AND NOT (phase_name = ANY(%(ex_phases)s))
                GROUP BY phase_name
                ORDER BY r7d DESC NULLS LAST, phase_name
                """,
                {"min_dur": min_dur, "ex_phases": list(_processing_progress_excluded_phases())},
            )
            for row in cur.fetchall() or []:
                (
                    name,
                    r1h,
                    r24h,
                    r7d,
                    s24h,
                    f24h,
                    s7d,
                    f7d,
                    avg_s,
                ) = row[0], row[1] or 0, row[2] or 0, row[3] or 0, row[4] or 0, row[5] or 0, row[6] or 0, row[7] or 0, row[8]
                pname = _norm_phase_name(name)
                if not pname:
                    continue
                r24i, r7di = int(r24h), int(r7d)
                s24i, f24i, s7i, f7i = int(s24h), int(f24h), int(s7d), int(f7d)
                # Tri-valued success: TRUE / FALSE / NULL — (IS TRUE) and (IS NOT TRUE) partition rows.
                if s24i + f24i != r24i:
                    logger.warning(
                        "processing_progress: 24h run count mismatch for %s: successes+failures=%s runs=%s",
                        pname,
                        s24i + f24i,
                        r24i,
                    )
                if s7i + f7i != r7di:
                    logger.warning(
                        "processing_progress: 7d run count mismatch for %s: successes+failures=%s runs=%s",
                        pname,
                        s7i + f7i,
                        r7di,
                    )
                # Sample proportion of completions marked success (not a binomial CI).
                pr24 = _json_safe_float(100.0 * s24i / r24i, ndigits=1) if r24i > 0 else None
                pr7 = _json_safe_float(100.0 * s7i / r7di, ndigits=1) if r7di > 0 else None
                phases.append(
                    {
                        "phase_name": pname,
                        "runs_1h": int(r1h),
                        "runs_24h": r24i,
                        "runs_7d": r7di,
                        "successes_24h": s24i,
                        "failures_24h": f24i,
                        "successes_7d": s7i,
                        "failures_7d": f7i,
                        "pass_rate_24h": pr24,
                        "pass_rate_7d": pr7,
                        "run_success_rate_24h": pr24,
                        "run_success_rate_7d": pr7,
                        "avg_duration_sec_24h": _json_safe_float(avg_s, ndigits=1),
                    }
                )
        except Exception as e:
            logger.debug("processing_progress phase summary: %s", e)
            _rollback_conn(conn)

        ex_phases = list(_processing_progress_excluded_phases())
        measurable = run_history_measurable_sql()
        tick_params = {
            "ex_phases": ex_phases,
            "min_dur": MEANINGFUL_DURATION_SEC,
        }
        try:
            if include_hourly_tick_rows:
                cur.execute(
                    f"""
                    SELECT date_trunc('hour', finished_at) AS hr,
                           phase_name,
                           COUNT(*) AS runs,
                           SUM(CASE WHEN success IS TRUE THEN 0 ELSE 1 END) AS fails
                    FROM automation_run_history
                    WHERE finished_at >= NOW() - INTERVAL '72 hours'
                      AND NOT (phase_name = ANY(%(ex_phases)s))
                      AND {measurable}
                    GROUP BY hr, phase_name
                    HAVING COUNT(*) > 0
                    ORDER BY hr ASC, phase_name ASC
                    LIMIT 4000
                    """,
                    tick_params,
                )
                for row in cur.fetchall() or []:
                    hr, pname, runs, fails = row[0], row[1], row[2] or 0, row[3] or 0
                    tick_phase = _norm_phase_name(pname)
                    if not tick_phase or not _monitor_pulse_visible_phase(tick_phase):
                        continue
                    hourly_phase_ticks.append(
                        {
                            "hour_utc": hr.isoformat()
                            if hasattr(hr, "isoformat")
                            else str(hr),
                            "phase_name": tick_phase,
                            "runs": int(runs),
                            "failures": int(fails),
                        }
                    )
                hourly_phase_tick_bucket_count = len(hourly_phase_ticks)
            else:
                cur.execute(
                    f"""
                    SELECT COUNT(*)::bigint FROM (
                        SELECT 1
                        FROM automation_run_history
                        WHERE finished_at >= NOW() - INTERVAL '72 hours'
                          AND NOT (phase_name = ANY(%(ex_phases)s))
                          AND {measurable}
                        GROUP BY date_trunc('hour', finished_at), phase_name
                        HAVING COUNT(*) > 0
                    ) subq
                    """,
                    tick_params,
                )
                rct = cur.fetchone()
                if rct and rct[0] is not None:
                    hourly_phase_tick_bucket_count = int(rct[0])
        except Exception as e:
            logger.debug("processing_progress hourly: %s", e)
            _rollback_conn(conn)

        measured_batch_rows: list[tuple[Any, Any]] = []
        try:
            cur.execute(
                """
                SELECT phase_name,
                       COALESCE(
                           CASE
                               WHEN metadata IS NOT NULL
                                    AND metadata::text LIKE '%%"batch":%%'
                               THEN metadata::text
                           END,
                           CASE
                               WHEN error_message IS NOT NULL
                                    AND error_message LIKE '%%"batch":%%'
                               THEN error_message
                           END
                       ) AS payload
                FROM automation_run_history
                WHERE finished_at >= NOW() - INTERVAL '24 hours'
                  AND success IS TRUE
                  AND (
                      (metadata IS NOT NULL AND metadata::text LIKE '%%"batch":%%')
                      OR (error_message IS NOT NULL AND error_message LIKE '%%"batch":%%')
                  )
                ORDER BY finished_at DESC
                LIMIT 500
                """
            )
            measured_batch_rows = list(cur.fetchall() or [])
        except Exception as e:
            logger.debug("processing_progress measured batch sample: %s", e)
            _rollback_conn(conn)

        cur.close()
        conn.close()
    except Exception as e:
        logger.warning("processing_progress: failed: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)[:200], "data": None}

    phase_by_name = {p["phase_name"]: p for p in phases if p.get("phase_name")}
    measured_batch_by_phase = _measured_batch_per_run_by_phase(measured_batch_rows)
    pending_m: dict[str, int] = {}
    backlog_m: dict[str, int] = {}
    pending_metrics_merge_error: str | None = None
    pending_metrics_as_of_utc: str | None = None
    snapshot_operator_metrics: dict[str, Any] = {}
    snapshot_signal_lane_metrics: dict[str, Any] = {}
    snapshot_feed_health_metrics: dict[str, Any] = {}
    snapshot_queue_audit: dict[str, Any] = {}
    snapshot_unified_intake_breakdown: dict[str, int] | None = None
    work_queues_m: dict[str, Any] = {}
    intake_window_hours: int | None = None
    pending_included = pending_metrics_source in ("live", "snapshot")

    def _fallback_batch(_: str) -> int:
        return 1

    get_batch = _fallback_batch
    try:
        from services.backlog_metrics import get_per_run_batch_size_for_phase

        get_batch = get_per_run_batch_size_for_phase
    except Exception as e:
        logger.debug("processing_progress batch size helper: %s", e)

    if pending_metrics_source == "live":
        try:
            from services.backlog_metrics import (
                get_all_backlog_counts,
                invalidate_backlog_metrics_cache,
            )
            from shared.pipeline_queue_counts import get_all_phase_queue_depths

            invalidate_backlog_metrics_cache()
            pending_m = {k: int(v) for k, v in get_all_phase_queue_depths().items()}
            backlog_m = {k: int(v) for k, v in get_all_backlog_counts().items()}
            pending_metrics_as_of_utc = now_iso
        except Exception as e:
            pending_metrics_merge_error = str(e)[:500]
            logger.warning(
                "processing_progress: backlog_metrics merge failed (pending_records will be zeros): %s",
                e,
            )
    elif pending_metrics_source == "snapshot":
        try:
            from services.monitor_backlog_snapshot_service import (
                read_monitor_backlog_snapshot,
                refresh_monitor_backlog_snapshot,
            )

            snap = read_monitor_backlog_snapshot(allow_stale=True)
            if not snap:
                snap = refresh_monitor_backlog_snapshot(force=True)
            if snap:
                pending_m = {
                    k: int(v)
                    for k, v in (
                        snap.get("queue_depths")
                        or snap.get("pending")
                        or {}
                    ).items()
                }
                backlog_m = {
                    k: int(v)
                    for k, v in (
                        snap.get("scheduling_backlog")
                        or snap.get("backlog")
                        or {}
                    ).items()
                }
                pending_metrics_as_of_utc = snap.get("refreshed_at_utc") or now_iso
                snapshot_operator_metrics = dict(snap.get("operator_metrics") or {})
                work_queues_m = dict(snap.get("work_queues") or {})
                snapshot_signal_lane_metrics = dict(snap.get("signal_lane_metrics") or {})
                snapshot_feed_health_metrics = dict(snap.get("feed_health_metrics") or {})
                snapshot_queue_audit = dict(snap.get("queue_audit") or {})
                raw_uib = snap.get("unified_intake_breakdown")
                if isinstance(raw_uib, dict):
                    snapshot_unified_intake_breakdown = {
                        k: int(v) for k, v in raw_uib.items()
                    }
                raw_intake = snap.get("intake_window_hours")
                if raw_intake is not None:
                    try:
                        intake_window_hours = int(raw_intake)
                    except (TypeError, ValueError):
                        intake_window_hours = None
            else:
                pending_metrics_merge_error = "monitor_backlog_snapshot unavailable"
        except Exception as e:
            pending_metrics_merge_error = str(e)[:500]
            logger.warning(
                "processing_progress: snapshot merge failed (pending_records will be zeros): %s",
                e,
            )

    if pending_metrics_source == "live" and not work_queues_m:
        try:
            from services.monitor_backlog_snapshot_service import read_monitor_backlog_snapshot

            snap_wq = read_monitor_backlog_snapshot(allow_stale=True)
            if snap_wq:
                work_queues_m = dict(snap_wq.get("work_queues") or {})
                if intake_window_hours is None and snap_wq.get("intake_window_hours") is not None:
                    intake_window_hours = int(snap_wq.get("intake_window_hours"))
        except Exception as e:
            logger.debug("processing_progress work_queues from snapshot: %s", e)

    def _phase_merge_sort_key(n: str) -> tuple:
        wq = work_queues_m.get(n) or {}
        first_pass = int(wq.get("first_pass", pending_m.get(n, 0)) or 0)
        return (
            -first_pass,
            -(pending_m.get(n, 0)),
            -(phase_by_name.get(n, {}).get("runs_7d", 0) or 0),
            n,
        )

    all_names = sorted(
        (
            (set(phase_by_name) | set(pending_m) | set(backlog_m))
            - _processing_progress_excluded_phases()
        ),
        key=_phase_merge_sort_key,
    )
    phase_dashboard: list[dict[str, Any]] = []
    for name in all_names:
        if not _monitor_pulse_visible_phase(name):
            continue
        row = dict(phase_by_name.get(name, {}))
        if not row:
            row = {
                "phase_name": name,
                "runs_1h": 0,
                "runs_24h": 0,
                "runs_7d": 0,
                "successes_24h": 0,
                "failures_24h": 0,
                "successes_7d": 0,
                "failures_7d": 0,
                "pass_rate_24h": None,
                "pass_rate_7d": None,
                "run_success_rate_24h": None,
                "run_success_rate_7d": None,
                "avg_duration_sec_24h": None,
            }
        row["phase_name"] = name
        row["phase_key"] = name
        wq = work_queues_m.get(name) or {}
        pend = _unified_pending_count(name, pending_m, wq)
        row["pending_records"] = pend
        row["queue_depth"] = pend
        row["scheduling_backlog"] = int(backlog_m.get(name, 0) or 0)
        row["scheduling_status"] = _phase_scheduling_status(name)
        try:
            from shared.pipeline_resource_policy import intake_phase_scheduled

            intake_inactive = not intake_phase_scheduled(name)
        except Exception:
            intake_inactive = False
        if intake_inactive:
            row["pending_first_pass"] = 0
            row["pending_retry"] = 0
            row["intake_first_pass"] = 0
            row["work_queue_metric_kind"] = "inactive_intake_mode"
        else:
            row["pending_first_pass"] = int(wq.get("first_pass", pend) or 0)
            row["pending_retry"] = int(wq.get("retry_pending", 0) or 0)
            row["intake_first_pass"] = int(wq.get("intake_first_pass", 0) or 0)
            row["work_queue_metric_kind"] = wq.get("metric_kind")
        if name in measured_batch_by_phase:
            bsize, bsource = measured_batch_by_phase[name]
            row["estimated_batch_per_run"] = bsize
            row["estimated_batch_per_run_source"] = bsource
        else:
            row["estimated_batch_per_run"] = int(get_batch(name))
            row["estimated_batch_per_run_source"] = "config_default"
        bsize = int(row["estimated_batch_per_run"])
        if pend <= 0:
            row["batches_to_drain"] = 0
            row["estimated_phase_runs"] = 0
        elif bsize > 0:
            est = int(math.ceil(pend / bsize))
            row["batches_to_drain"] = est
            row["estimated_phase_runs"] = est
        else:
            row["batches_to_drain"] = None
            row["estimated_phase_runs"] = None
        runs_24h = int(row.get("runs_24h") or 0)
        row["queue_stale"] = (
            row["scheduling_status"] == "active"
            and pend > bsize
            and bsize > 0
            and runs_24h == 0
        )
        from shared.pipeline_queue_vocabulary import add_queue_depth_aliases

        row = add_queue_depth_aliases(row)
        phase_dashboard.append(row)
        if name in ("unified_intake_extraction", "claim_extraction", "entity_extraction") or pend >= 500:
            try:
                from shared.monitor_pulse_debug import monitor_pulse_debug

                in_memory_runs = None
                try:
                    from services.automation_manager import get_automation_manager

                    st = get_automation_manager().get_status() or {}
                    in_memory_runs = (st.get("runs_last_60m_by_phase") or {}).get(name)
                except Exception:
                    pass
                monitor_pulse_debug(
                    "processing_progress.py:phase_dashboard_row",
                    "pulse_metrics_computed",
                    {
                        "phase": name,
                        "runs_1h_sql": row.get("runs_1h"),
                        "runs_24h": row.get("runs_24h"),
                        "runs_last_60m_in_memory": in_memory_runs,
                        "pending_records": pend,
                        "estimated_batch_per_run": bsize,
                        "estimated_batch_per_run_source": row.get("estimated_batch_per_run_source"),
                        "batches_to_drain": row.get("batches_to_drain"),
                        "pending_metrics_source": pending_metrics_source,
                        "pending_metrics_as_of_utc": pending_metrics_as_of_utc,
                    },
                    hypothesis_id="H2-H5",
                )
            except Exception:
                pass

    from shared.pipeline_queue_vocabulary import REPORTING_DEFINITIONS as QUEUE_VOCAB_DEFINITIONS

    reporting_definitions: dict[str, str] = {
        "monitor_schema_version": (
            f"Monitor reporting vocabulary version ({MONITOR_SCHEMA_VERSION}). "
            "Additive aliases: phase_key, queue_depth, estimated_phase_runs, run_success_rate_24h."
        ),
        "pass_rate_24h_7d": (
            "Percentage = 100 × (completions with success=TRUE) ÷ (all completions in window). "
            "SQL uses success IS NOT TRUE for non-success, so FALSE and NULL both count as non-success. "
            "Denominator is finished runs only (no censoring of in-flight work). "
            "This is a sample proportion, not a confidence interval."
        ),
        "pending_records": (
            "Estimated work remaining for this phase: backlog_metrics counts rows that match the same "
            "eligibility filters the automation phase uses (not raw table sizes). Phases with rotating "
            "batches (e.g. storyline_automation) still show total eligible items; estimated_batch_per_run "
            "reflects typical throughput per scheduler run."
        ),
        "pending_first_pass": (
            "Items never successfully cleared for this phase (no last_pass_at / never compiled / never "
            "linked / queue row never processed). Grows with new intake; shrinks as automation catches up."
        ),
        "pending_retry": (
            "Items that were attempted but still need another pass (failed_needs_retry or legacy false-clear "
            "outcomes). Subset of pending_records for pass-marker phases. For entity_dossier_compile, this "
            "column counts existing dossiers needing refresh because upstream data changed (or calendar stale "
            "when ENTITY_DOSSIER_STALE_DAYS > 0) — not failed compiles."
        ),
        "intake_first_pass": (
            "First-pass items created within the intake window (MONITOR_INTAKE_WINDOW_HOURS, default 72h). "
            "Tracks fresh RSS intake backlog separately from historical all-time first-pass debt."
        ),
        "estimated_batch_per_run": (
            "Rows consumed per run of the phase. Prefer measured_24h from recent batch "
            "automation_run_history payloads when available; otherwise config default from backlog_metrics."
        ),
        "runs_1h": (
            "Meaningful completions in the last hour (excludes instant drain_started/phase_started markers). "
            "Counts each completed batch round (metadata.status=batch_round) or drain/phase finish with rows processed."
        ),
        "batches_to_drain": (
            "Runs needed to clear the current queue: ceil(pending_records ÷ estimated_batch_per_run) "
            "when estimated_batch_per_run > 0; 0 if no pending; null if estimated_batch_per_run is 0 "
            "(no row-batch model for that phase). Values > 1 mean more than one run is needed to drain. "
            "Alias: estimated_phase_runs."
        ),
        "scheduling_status": (
            "active = orchestrator may enqueue; suppressed = inactive intake mode (unified vs legacy); "
            "retired = post-spine phase masked from scheduling (orphan backlog may still appear)."
        ),
        "queue_stale": (
            "True when active phase has pending work exceeding one batch but zero meaningful "
            "completions in the last 24h — likely scheduling starvation or recent API downtime."
        ),
        "avg_duration_sec_24h": (
            "Mean wall-clock seconds (finished_at − started_at) over 24h, excluding instant "
            "drain_started/phase_started markers and sub-second heartbeat rows."
        ),
        "runs_24h": (
            "Meaningful completions in 24h (excludes instant drain_started/phase_started markers). "
            "Per-batch rows (batch_round) count when rows were processed even if the outer scheduler task is still running."
        ),
        "dimension_throughput": (
            "Counts of rows updated or created in the stated intervals (SQL filters differ per dimension); "
            "not necessarily mutually exclusive across dimensions."
        ),
        "hourly_phase_ticks_failures": (
            "Per bucket, failures = completions where success is not TRUE (same rule as pass rate)."
        ),
        "storyline_review_queue_pending": (
            "Pending rows in public.storyline_article_suggestions awaiting operator approve/reject. "
            "Separate from storyline_automation pool depth (scheduler eligibility for suggest_only storylines)."
        ),
    }
    reporting_definitions.update(QUEUE_VOCAB_DEFINITIONS)

    operator_metrics: dict[str, Any] = {}
    if pending_metrics_source == "snapshot" and snapshot_operator_metrics:
        operator_metrics = snapshot_operator_metrics
    elif pending_metrics_source == "live":
        try:
            from services.backlog_metrics import (
                get_storyline_review_queue_pending,
                get_storyline_review_queue_pending_by_domain,
            )

            operator_metrics = {
                "storyline_review_queue_pending": get_storyline_review_queue_pending(),
                "storyline_review_queue_pending_by_domain": (
                    get_storyline_review_queue_pending_by_domain()
                ),
            }
        except Exception as e:
            logger.debug("processing_progress operator_metrics: %s", e)

    try:
        from shared.gpu_metrics import maybe_record_gpu_metric_sample

        maybe_record_gpu_metric_sample()
    except Exception:
        pass

    signal_lane_metrics: dict[str, int] = {}
    if pending_metrics_source == "snapshot" and snapshot_signal_lane_metrics:
        signal_lane_metrics = snapshot_signal_lane_metrics
    else:
        try:
            from services.phase_work_queue_metrics import get_signal_lane_counts_24h

            signal_lane_metrics = get_signal_lane_counts_24h()
        except Exception as e:
            logger.debug("processing_progress signal_lane_metrics: %s", e)

    feed_health_metrics: dict[str, int] = {}
    if pending_metrics_source == "snapshot" and snapshot_feed_health_metrics:
        feed_health_metrics = snapshot_feed_health_metrics
    else:
        try:
            from services.rss_feed_health_service import get_feed_health_monitor_counts

            feed_health_metrics = get_feed_health_monitor_counts()
        except Exception as e:
            logger.debug("processing_progress feed_health_metrics: %s", e)

    queue_audit: dict[str, Any] = {}
    unified_intake_breakdown: dict[str, int] | None = None
    if pending_included and pending_m:
        if snapshot_queue_audit:
            queue_audit = snapshot_queue_audit
        else:
            try:
                from shared.queue_audit import build_queue_audit

                queue_audit = build_queue_audit(pending_m)
            except Exception as e:
                logger.debug("processing_progress queue_audit: %s", e)
        if snapshot_unified_intake_breakdown is not None:
            unified_intake_breakdown = snapshot_unified_intake_breakdown
        else:
            try:
                from shared.pipeline_queue_counts import get_unified_intake_breakdown

                unified_intake_breakdown = dict(get_unified_intake_breakdown())
            except Exception as e:
                logger.debug("processing_progress unified_intake_breakdown: %s", e)

    try:
        from shared.monitor_pulse_debug import monitor_pulse_debug

        monitor_pulse_debug(
            "processing_progress.py:compute_processing_progress_response",
            "processing_progress_built",
            {
                "elapsed_ms": int((time.monotonic() - _build_started) * 1000),
                "include_dimension_throughput": include_dimension_throughput,
                "pending_metrics_source": pending_metrics_source,
                "phase_count": len(phase_dashboard),
            },
            hypothesis_id="H-slow-page",
            run_id="post-fix",
        )
    except Exception:
        pass

    return {
        "success": True,
        "data": {
            "generated_at_utc": now_iso,
            "workload_window_days_note": _BACKLOG_WORKLOAD_WINDOW_DAYS,
            "pending_metrics_included": pending_included,
            "pending_metrics_source": pending_metrics_source,
            "pending_metrics_as_of_utc": pending_metrics_as_of_utc,
            "pending_metrics_merge_error": pending_metrics_merge_error,
            "intake_window_hours": intake_window_hours,
            "intake_first_pass_sum": sum(
                int(wq.get("intake_first_pass", 0) or 0) for wq in work_queues_m.values()
            ),
            "signal_lane_metrics": signal_lane_metrics,
            "feed_health_metrics": feed_health_metrics,
            "operator_metrics": operator_metrics,
            "queue_audit": queue_audit,
            "unified_intake_breakdown": unified_intake_breakdown,
            "reporting_definitions": reporting_definitions,
            "monitor_schema_version": MONITOR_SCHEMA_VERSION,
            "dimension_throughput_included": include_dimension_throughput,
            "dimensions": dimensions,
            "phase_dashboard": phase_dashboard,
            "phases": phase_dashboard,
            "hourly_phase_ticks": hourly_phase_ticks,
            "hourly_phase_tick_bucket_count": hourly_phase_tick_bucket_count,
        },
    }
