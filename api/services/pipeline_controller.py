"""
Unified pipeline controller — single scheduling brain for AutomationManager.

Replaces the 5s scheduler tick, spine/assembly conductor loops, and append-only enqueue.
Decision tree + queue reconcile + progress-based stall detection (no wall-clock task timeouts).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Maintenance-only phases (not catchup drivers).
_MAINTENANCE_PHASES = frozenset(
    {
        "health_check",
        "rss_feed_health",
        "cache_cleanup",
        "data_cleanup",
        "research_topic_refinement",
    }
)

# Long-running drain phases — dedupe when inflight >= cap.
LONG_DRAIN_PHASES = frozenset(
    {
        "collection_cycle",  # one ingest cycle at a time; drop stacked manual/governor copies
        "unified_intake_extraction",
        "claim_extraction",
        "entity_profile_build",
        "content_enrichment",
        "event_tracking",
        "entity_dossier_compile",
        "nightly_enrichment_context",
        "spine_sql_tail",
        "document_processing",
        "context_sync",
    }
)

_RESOURCE_CACHE_SECONDS = 2.0


def _controller_config() -> dict[str, Any]:
    try:
        from config.orchestrator_governance import get_orchestrator_governance_config

        raw = get_orchestrator_governance_config().get("pipeline_controller") or {}
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _cfg_int(key: str, default: int) -> int:
    try:
        val = _controller_config().get(key)
        if val is not None:
            return int(val)
    except (TypeError, ValueError):
        pass
    return default


def _cfg_float(key: str, default: float) -> float:
    try:
        val = _controller_config().get(key)
        if val is not None:
            return float(val)
    except (TypeError, ValueError):
        pass
    return default


def catchup_clear_threshold() -> int:
    return max(1, _cfg_int("catchup_clear_threshold", 50))


def prefetch_multiplier() -> int:
    return max(1, _cfg_int("prefetch_multiplier", 2))


def _default_max_concurrent_widow_gpu_drains() -> int:
    try:
        from config.runtime import env_str

        workers = max(1, int(env_str("AUTOMATION_MAX_CONCURRENT_TASKS", "4") or 4))
    except (TypeError, ValueError):
        workers = 4
    return 2 if workers >= 4 else 1


def max_concurrent_widow_gpu_drains() -> int:
    """Max PopOS-bound drain tasks on Widow workers (LLM on PopOS, process on Widow)."""
    cfg = _controller_config()
    raw = cfg.get("max_concurrent_widow_gpu_drains")
    if raw is not None:
        try:
            return max(1, int(raw))
        except (TypeError, ValueError):
            pass
    return _default_max_concurrent_widow_gpu_drains()


def effective_max_concurrent_widow_gpu_drains(automation: Any) -> int:
    total = max(1, int(getattr(automation, "max_concurrent_tasks", 4) or 4))
    return min(max_concurrent_widow_gpu_drains(), total)


def post_collection_kickoff_enabled() -> bool:
    raw = _controller_config().get("post_collection_kickoff_enabled")
    if raw is not None:
        return bool(raw)
    return True


def get_post_collection_kickoff_phases() -> list[str]:
    """Phases that typically follow RSS ingest (controller schedules via backlog counters)."""
    raw = _controller_config().get("post_collection_phases")
    if isinstance(raw, list) and raw:
        phases = [str(p).strip() for p in raw if str(p).strip()]
    else:
        phases = ["content_enrichment", "context_sync"]
    try:
        from shared.spine_phase_order import spine_pipeline_ordered_active

        if spine_pipeline_ordered_active():
            phases = ["content_enrichment"]
    except Exception:
        pass
    return phases


def popos_overflow_util_max_pct() -> float:
    return float(_cfg_int("popos_overflow_util_max_pct", 85))


def popos_overflow_temp_max_c() -> float:
    return float(_cfg_int("popos_overflow_temp_max_c", 82))


def widow_memory_pressure_pct() -> float:
    return _cfg_float("widow_memory_pressure_pct", 78.0)


def widow_memory_critical_pct() -> float:
    return _cfg_float("widow_memory_critical_pct", 92.0)


def widow_memory_pressure_headroom() -> float:
    return _cfg_float("widow_memory_pressure_headroom", 0.22)


# Phases that spike Widow process RSS — defer during memory pressure.
_WIDOW_RAM_HEAVY_PHASES = frozenset(
    {
        "collection_cycle",
        "content_enrichment",
        "document_processing",
        "nightly_enrichment_context",
        "ml_processing",
    }
)

# PopOS GPU phases preferred when Widow is under memory pressure (ordered).
_POPOS_OVERFLOW_PRIORITY: tuple[str, ...] = (
    "unified_intake_extraction",
    "claim_extraction",
    "entity_profile_build",
    "entity_dossier_compile",
    "fact_verification",
    "pattern_recognition",
    "storyline_discovery",
    "storyline_assembly",
    "event_extraction",
)

# While unified intake has pending work, do not co-enqueue these on OOM overflow.
_POPOS_OVERFLOW_DEFER_WHILE_INTAKE: frozenset[str] = frozenset(
    {
        "storyline_assembly",
        "storyline_discovery",
        "pattern_recognition",
        "entity_dossier_compile",
    }
)

# Residual assembly/event alone must not keep the full catchup enqueue path forever.
_CATCHUP_DRIVER_PHASES: frozenset[str] = frozenset(
    {
        "unified_intake_extraction",
        "content_enrichment",
        "context_sync",
        "claim_extraction",
        "entity_extraction",
        "event_extraction",
        "document_processing",
        "content_refinement_queue",
        "entity_profile_build",
        "ml_processing",
        "sentiment_analysis",
        "quality_scoring",
        "metadata_enrichment",
    }
)

# Lightweight Widow work safe during memory pressure (DB/SQL, no model load).
_LIGHT_WIDOW_DURING_PRESSURE: tuple[str, ...] = (
    "pending_db_flush",
    "health_check",
    "context_sync",
    "entity_profile_sync",
    "spine_sql_tail",
    "claims_to_facts",
    "event_tracking",
)


def stall_zero_progress_passes() -> int:
    return max(1, _cfg_int("stall_zero_progress_passes", 2))


def stall_backlog_unchanged_replans() -> int:
    return max(2, _cfg_int("stall_backlog_unchanged_replans", 3))


def failing_error_repeat_passes() -> int:
    return max(1, _cfg_int("failing_error_repeat_passes", 2))


def stall_hold_replans() -> int:
    return max(1, _cfg_int("stall_hold_replans", 8))


def unified_intake_defer_threshold() -> int:
    """Minimum unified_intake_extraction pending count to defer other GPU phases."""
    return max(1, _cfg_int("unified_intake_defer_threshold", 50))


def catchup_phases() -> frozenset[str]:
    from services.backlog_metrics import RAW_PENDING_COUNT_KEYS

    extra = frozenset({"spine_sql_tail"})
    skip = _MAINTENANCE_PHASES | frozenset({"pending_db_flush"})
    return (RAW_PENDING_COUNT_KEYS - skip) | extra


def is_catchup_active(pending: dict[str, int]) -> bool:
    from shared.pipeline_resource_policy import extract_bulk_pending_total

    if extract_bulk_pending_total(pending) > catchup_clear_threshold():
        return True
    for phase in _CATCHUP_DRIVER_PHASES:
        if int(pending.get(phase, 0) or 0) > 0:
            return True
    if _spine_sql_tail_should_run(pending):
        return True
    return False


def _spine_sql_tail_should_run(pending: dict[str, int]) -> bool:
    """True when SQL tail likely has work (composite — no single pending key)."""
    enrich = int(pending.get("content_enrichment", 0) or 0)
    intake = int(pending.get("unified_intake_extraction", 0) or 0)
    claims = int(pending.get("claims_to_facts", 0) or 0)
    ctx = int(pending.get("context_sync", 0) or 0)
    if enrich > 0 or intake > 500:
        return False
    return claims > 0 or ctx > 0


def _popos_gpu_phases() -> frozenset[str]:
    from shared.pipeline_resource_policy import Host, PHASE_POLICIES

    return frozenset(
        name
        for name, pol in PHASE_POLICIES.items()
        if pol.host in (Host.POPOS_GPU, Host.POPOS_HEAVY)
    )


def lane_pools_active(hosts: dict[str, Any] | None = None) -> bool:
    """Lane caps apply when dual-host routing can offload LLM to PopOS."""
    if hosts:
        routing = hosts.get("routing") or {}
        if routing.get("popos_available_for_overflow") is not None:
            return bool(routing.get("popos_available_for_overflow"))
    return popos_available_for_overflow(sample_host_resources())


def _widow_routine_phases() -> frozenset[str]:
    from shared.pipeline_resource_policy import Host, PHASE_POLICIES

    routine_hosts = {Host.WIDOW_CPU, Host.WIDOW_DB, Host.WIDOW_FETCH}
    return frozenset(
        name for name, pol in PHASE_POLICIES.items() if pol.host in routine_hosts
    )


def sample_host_resources(force: bool = False) -> Any:
    """Cached ResourceSnapshot from catchup_host_metrics."""
    now = time.monotonic()
    ctrl = getattr(sample_host_resources, "_cache", None)
    cache_at = getattr(sample_host_resources, "_cache_at", None)
    if (
        not force
        and ctrl is not None
        and cache_at is not None
        and (now - cache_at) < _RESOURCE_CACHE_SECONDS
    ):
        return ctrl
    try:
        from shared.adaptive_batch_policy import ensure_routing_context
        from shared.catchup_host_metrics import sample_resources

        ensure_routing_context()
        snap = sample_resources()
        sample_host_resources._cache = snap
        sample_host_resources._cache_at = now
        return snap
    except Exception as e:
        logger.debug("sample_host_resources: %s", e)
        return None


def popos_available_for_overflow(resources: Any) -> bool:
    from config.runtime import env_bool
    from shared.bulk_catchup_llm_routing import dual_lane_extraction_active

    if not dual_lane_extraction_active():
        return False
    if not env_bool("OLLAMA_DUAL_HOST_ROUTING_ENABLED", False):
        return False
    if resources is None:
        return False
    probe = str(getattr(resources, "gpu_probe_source", "") or "")
    if probe in ("unavailable", "error", "timeout"):
        return False
    util = getattr(resources, "gpu_util_percent", None)
    temp = getattr(resources, "gpu_temp_c", None)
    if util is not None and float(util) >= popos_overflow_util_max_pct():
        return False
    if temp is not None and float(temp) >= popos_overflow_temp_max_c():
        return False
    headroom = float(getattr(resources, "gpu_llm_headroom", 0) or 0)
    return headroom > 0.15


def _widow_memory_percent(resources: Any) -> float | None:
    if resources is None:
        return None
    raw = getattr(resources, "local_memory_percent", None)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def widow_memory_pressure(resources: Any) -> bool:
    """True when Widow host RAM is high enough to risk OOM in the API process."""
    pct = _widow_memory_percent(resources)
    if pct is not None and pct >= widow_memory_pressure_pct():
        return True
    if resources is not None:
        mem_headroom = float(getattr(resources, "local_memory_headroom", 0.5) or 0.5)
        if mem_headroom <= widow_memory_pressure_headroom():
            return True
    return False


def widow_memory_critical(resources: Any) -> bool:
    pct = _widow_memory_percent(resources)
    return pct is not None and pct >= widow_memory_critical_pct()


def widow_oom_popos_overflow_active(resources: Any, automation: Any) -> bool:
    """True when we should offload PopOS-eligible work instead of throttling."""
    if not popos_available_for_overflow(resources):
        return False
    if widow_memory_critical(resources):
        return True
    if widow_memory_pressure(resources):
        return True
    return not _widow_resources_ok(resources, automation)


def host_state_dict(resources: Any) -> dict[str, Any]:
    from shared.bulk_catchup_llm_routing import dual_lane_extraction_active

    widow: dict[str, Any] = {}
    popos: dict[str, Any] = {}
    if resources is not None:
        widow = {
            "memory_pct": getattr(resources, "local_memory_percent", None),
            "cpu_headroom": getattr(resources, "local_cpu_headroom", None),
            "db_headroom": getattr(resources, "db_headroom", None),
        }
        popos = {
            "reachable": str(getattr(resources, "gpu_probe_source", ""))
            not in ("unavailable", "error", "timeout"),
            "gpu_util_pct": getattr(resources, "gpu_util_percent", None),
            "vram_pct": getattr(resources, "gpu_vram_percent", None),
            "temp_c": getattr(resources, "gpu_temp_c", None),
            "headroom": getattr(resources, "gpu_llm_headroom", None),
            "probe_source": getattr(resources, "gpu_probe_source", None),
            "gpu_host": getattr(resources, "gpu_host", None),
        }
    return {
        "widow": {
            **widow,
            "memory_pressure": widow_memory_pressure(resources),
            "memory_critical": widow_memory_critical(resources),
        },
        "popos": popos,
        "routing": {
            "dual_lane_active": dual_lane_extraction_active(),
            "popos_available_for_overflow": popos_available_for_overflow(resources),
            "oom_popos_overflow_active": popos_available_for_overflow(resources)
            and (
                widow_memory_pressure(resources)
                or widow_memory_critical(resources)
            ),
        },
        "lane_pools": {
            "active": popos_available_for_overflow(resources),
            "max_popos_gpu_drains": max_concurrent_widow_gpu_drains(),
        },
    }


def _normalize_error(err: str | None) -> str:
    if not err:
        return ""
    return " ".join(str(err).strip().lower().split())[:120]


@dataclass
class PhaseHealth:
    phase: str
    status: str  # moving | slow | stalled | failing | unknown
    detail: str = ""


def _processed_count_from_row(row: dict[str, Any]) -> int:
    from shared.monitor_run_vocabulary import throughput_from_payload

    return throughput_from_payload(row, prefer_iteration=False)


def _activity_in_flight(activity_progress: dict[str, Any] | None) -> bool:
    """True when AutomationManager shows an active worker for this phase."""
    if not activity_progress:
        return False
    if int(activity_progress.get("running_instances") or 0) > 0:
        return True
    started = activity_progress.get("started_at")
    if isinstance(started, str) and started.strip():
        return True
    return activity_progress.get("task_name") is not None


def assess_phase_health(
    phase: str,
    pending: dict[str, int],
    pending_history: dict[str, list[int]],
    *,
    run_history_rows: list[dict[str, Any]] | None = None,
    activity_progress: dict[str, Any] | None = None,
) -> PhaseHealth:
    """Classify phase health from logs/backlog — count-based, not wall-clock."""
    pend = int(pending.get(phase, 0) or 0)
    hist = pending_history.get(phase) or []

    if activity_progress and _activity_in_flight(activity_progress):
        tp = activity_progress.get("total_processed")
        if tp is not None and int(tp) > 0:
            return PhaseHealth(phase, "moving", f"activity total_processed={tp}")
        rp = activity_progress.get("rows_processed")
        if rp is not None and int(rp) > 0:
            return PhaseHealth(phase, "moving", f"activity rows_processed={rp}")
        lp = activity_progress.get("iteration_index") or activity_progress.get("loops_processed")
        if lp is not None and int(lp) > 0:
            return PhaseHealth(phase, "slow", f"iteration={lp}")
        return PhaseHealth(phase, "slow", "drain in-flight")

    if len(hist) >= 2 and pend > 0:
        if all(h == pend for h in hist[-stall_backlog_unchanged_replans() :]):
            if run_history_rows:
                zero_runs = 0
                for row in run_history_rows[: stall_zero_progress_passes()]:
                    if _processed_count_from_row(row) <= 0:
                        zero_runs += 1
                if zero_runs >= stall_zero_progress_passes():
                    return PhaseHealth(phase, "stalled", "flat backlog + zero-progress passes")
            else:
                return PhaseHealth(phase, "stalled", "flat backlog snapshots")

    if run_history_rows:
        errors: list[str] = []
        for row in run_history_rows[: failing_error_repeat_passes() + 2]:
            if row.get("success") is False:
                errors.append(_normalize_error(row.get("error_message")))
        errors = [e for e in errors if e]
        if len(errors) >= failing_error_repeat_passes():
            if len(set(errors[: failing_error_repeat_passes()])) == 1:
                return PhaseHealth(phase, "failing", errors[0][:80])

        for row in run_history_rows[:3]:
            proc = _processed_count_from_row(row)
            if proc > 0:
                return PhaseHealth(phase, "moving", f"processed={proc}")

    if len(hist) >= 2 and pend > 0 and hist[-1] < hist[-2]:
        return PhaseHealth(phase, "moving", "backlog decreased")

    return PhaseHealth(phase, "unknown", "")


def _recent_run_history(phase: str, limit: int = 5) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        from shared.database.connection import get_ui_db_connection_context

        skip = ("drain_started", "phase_started")
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT success, error_message, metadata
                    FROM automation_run_history
                    WHERE phase_name = %s
                      AND COALESCE(metadata->>'status', '') NOT IN %s
                    ORDER BY finished_at DESC NULLS LAST
                    LIMIT %s
                    """,
                    (phase, skip, limit),
                )
                cols = [d[0] for d in cur.description]
                for row in cur.fetchall() or []:
                    d = dict(zip(cols, row))
                    meta = d.get("metadata") or {}
                    if isinstance(meta, dict):
                        for key in (
                            "round_processed",
                            "total_processed",
                            "items_processed",
                            "articles_processed",
                            "profiles_updated",
                            "processed",
                            "loops_processed",
                            "status",
                        ):
                            if key in meta:
                                d[key] = meta.get(key)
                    out.append(d)
    except Exception as e:
        logger.debug("_recent_run_history %s: %s", phase, e)
    return out


def _activity_progress_for_phase(phase: str) -> dict[str, Any] | None:
    try:
        from services.activity_feed_service import get_activity_feed

        snap = get_activity_feed().get_snapshot(recent_limit=5)
        for entry in snap.get("current") or []:
            if entry.get("task_name") == phase:
                return entry
    except Exception:
        pass
    return None


def assess_all_phase_health(
    pending: dict[str, int],
    pending_history: dict[str, list[int]],
    phases: frozenset[str] | None = None,
) -> dict[str, PhaseHealth]:
    check = phases or catchup_phases()
    result: dict[str, PhaseHealth] = {}
    for phase in check:
        if int(pending.get(phase, 0) or 0) <= 0 and phase != "spine_sql_tail":
            continue
        result[phase] = assess_phase_health(
            phase,
            pending,
            pending_history,
            run_history_rows=_recent_run_history(phase),
            activity_progress=_activity_progress_for_phase(phase),
        )
    return result


def _phase_eligible(
    phase: str,
    automation: Any,
    pending: dict[str, int],
    *,
    stall_holds: dict[str, int],
) -> bool:
    if stall_holds.get(phase, 0) > 0:
        return False
    if phase not in automation.schedules:
        return False
    schedule = automation.schedules[phase]
    if not schedule.get("enabled", True):
        return False

    from services.backlog_metrics import SKIP_WHEN_EMPTY

    if phase in SKIP_WHEN_EMPTY and int(pending.get(phase, 0) or 0) <= 0:
        if phase == "spine_sql_tail" and _spine_sql_tail_should_run(pending):
            pass
        else:
            return False

    try:
        from services.pipeline_schedule_service import automation_phase_allowed

        if not automation_phase_allowed(phase, pending_count=int(pending.get(phase, 0) or 0)):
            return False
    except Exception:
        pass

    try:
        from shared.assembly_phase_order import post_spine_scheduling_suppressed

        if post_spine_scheduling_suppressed(phase):
            return False
    except Exception:
        pass

    try:
        from shared.pipeline_resource_policy import (
            bulk_extract_compete_defer_phase,
            entity_profile_build_allowed,
            intake_extraction_suppressed,
            legacy_intake_extraction_phases,
            refinement_phase_allowed,
            unified_superseded_automation_phases,
        )

        if intake_extraction_suppressed() and phase in legacy_intake_extraction_phases():
            return False
        if intake_extraction_suppressed() and phase in unified_superseded_automation_phases():
            return False
        if bulk_extract_compete_defer_phase(phase, pending):
            return False
        if not refinement_phase_allowed(phase, pending):
            return False
        if phase == "entity_profile_build" and not entity_profile_build_allowed(pending):
            return False
    except Exception:
        pass

    try:
        from config.runtime import env_str
        from shared.database.db_availability import is_automation_db_ready

        if env_str("AUTOMATION_PAUSE_WHEN_DB_DOWN", "true").lower() in ("1", "true", "yes"):
            if not is_automation_db_ready():
                return False
    except Exception:
        pass

    try:
        from services.nightly_ingest_window_service import in_nightly_pipeline_window_est

        nightly = in_nightly_pipeline_window_est()
    except Exception:
        nightly = False
    if phase == "context_sync" and nightly:
        return False
    if phase == "content_refinement_queue" and nightly:
        return False
    if phase == "nightly_enrichment_context" and not nightly:
        return False

    return True


def _collection_allowed(pending: dict[str, int], automation: Any) -> bool:
    from config.runtime import env_str
    from services.automation_manager import (
        COLLECTION_THROTTLE_PENDING_THRESHOLD,
        _collection_throttle_pending_total,
        collection_cycle_has_pending_work,
    )

    q_len = len(getattr(automation, "_pending_collection_queue", []) or [])
    if not collection_cycle_has_pending_work(pending, pending_collection_queue_len=q_len):
        return False
    downstream, _br = _collection_throttle_pending_total(pending)
    if downstream > COLLECTION_THROTTLE_PENDING_THRESHOLD:
        return False
    skip_rss = env_str("AUTOMATION_SKIP_RSS_IN_COLLECTION_CYCLE", "").lower() in (
        "1",
        "true",
        "yes",
    )
    if skip_rss and q_len == 0:
        sched = automation.schedules.get("collection_cycle") or {}
        last = sched.get("last_run")
        if last is not None:
            interval = int(sched.get("interval") or 7200)
            age = (datetime.now(timezone.utc) - last).total_seconds()
            if age < interval * 0.5:
                return False
    return True


def _pick_widow_oom_popos_overflow(
    pending: dict[str, int],
    resources: Any,
    phase_health: dict[str, PhaseHealth],
    automation: Any,
    *,
    stall_holds: dict[str, int],
    catchup: bool,
) -> tuple[list[str], str]:
    """
    When Widow RAM is under pressure and PopOS is available, enqueue PopOS GPU phases
    plus lightweight Widow DB work — skip RSS/enrichment/collection that spike RSS.
    """
    desired: list[str] = []
    popos_phases = _popos_gpu_phases()
    branch = "widow_oom_popos_overflow"

    def _skip_health(phase: str) -> bool:
        h = phase_health.get(phase)
        return h is not None and h.status in ("stalled", "failing")

    def _add(phase: str) -> None:
        if phase in desired:
            return
        if phase in _WIDOW_RAM_HEAVY_PHASES:
            return
        if not _phase_eligible(phase, automation, pending, stall_holds=stall_holds):
            return
        if _skip_health(phase):
            return
        desired.append(phase)

    for phase in _POPOS_OVERFLOW_PRIORITY:
        if phase not in popos_phases:
            continue
        if int(pending.get(phase, 0) or 0) <= 0:
            continue
        intake_pending = int(pending.get("unified_intake_extraction", 0) or 0)
        if intake_pending > unified_intake_defer_threshold() and phase in _POPOS_OVERFLOW_DEFER_WHILE_INTAKE:
            continue
        _add(phase)

    for phase in popos_phases:
        if phase in desired or phase in _POPOS_OVERFLOW_PRIORITY:
            continue
        if int(pending.get(phase, 0) or 0) <= 0:
            continue
        intake_pending = int(pending.get("unified_intake_extraction", 0) or 0)
        if intake_pending > unified_intake_defer_threshold() and phase in _POPOS_OVERFLOW_DEFER_WHILE_INTAKE:
            continue
        _add(phase)

    for phase in _LIGHT_WIDOW_DURING_PRESSURE:
        if phase == "health_check":
            if not catchup and _phase_eligible(
                phase, automation, pending, stall_holds=stall_holds
            ):
                _add(phase)
            continue
        if phase == "spine_sql_tail":
            if _spine_sql_tail_should_run(pending):
                _add(phase)
            continue
        if int(pending.get(phase, 0) or 0) > 0:
            _add(phase)

    if not catchup:
        sched = automation.schedules.get("rss_feed_health") or {}
        if sched.get("enabled") and _phase_eligible(
            "rss_feed_health", automation, pending, stall_holds=stall_holds
        ):
            last = sched.get("last_run")
            interval = int(sched.get("interval") or 86400)
            if last is None or (datetime.now(timezone.utc) - last).total_seconds() >= interval:
                _add("rss_feed_health")
        if desired:
            return desired, branch
        return desired, branch

    asm_phase, _asm_meta = _pick_assembly_phase(pending)
    if asm_phase and asm_phase in popos_phases:
        intake_pending = int(pending.get("unified_intake_extraction", 0) or 0)
        if not (intake_pending > unified_intake_defer_threshold() and asm_phase in _POPOS_OVERFLOW_DEFER_WHILE_INTAKE):
            _add(asm_phase)

    return desired, branch


def _catchup_order_policy(*, popos_ok: bool, mem_pressure: bool) -> str:
    """
    Single catchup host-balance policy (SSOT for phase ordering).

    - popos_first: PopOS has headroom and Widow RAM is OK → GPU/PopOS phases before Widow DB/CPU.
    - widow_first: PopOS unavailable or Widow under pressure → Widow-local work before GPU drains.
    """
    if popos_ok and not mem_pressure:
        return "popos_first"
    return "widow_first"


def _catchup_phases_by_backlog(
    pending: dict[str, int],
    automation: Any,
    *,
    stall_holds: dict[str, int],
    skip: frozenset[str] | None = None,
    resources: Any | None = None,
) -> list[str]:
    """Phases with pending work, ordered by host-balance policy then backlog depth."""
    skip = skip or frozenset()
    popos = _popos_gpu_phases()
    cpu: list[tuple[str, int]] = []
    gpu: list[tuple[str, int]] = []

    for phase in catchup_phases():
        if phase in skip:
            continue
        if phase == "spine_sql_tail":
            if not _spine_sql_tail_should_run(pending):
                continue
            count = 1
        else:
            count = int(pending.get(phase, 0) or 0)
            if count <= 0:
                continue
        if not _phase_eligible(phase, automation, pending, stall_holds=stall_holds):
            continue
        (gpu if phase in popos else cpu).append((phase, count))

    cpu.sort(key=lambda x: (-x[1], x[0]))
    gpu.sort(key=lambda x: (-x[1], x[0]))
    popos_ok = popos_available_for_overflow(resources) if resources is not None else False
    mem_pressure = widow_memory_pressure(resources) if resources is not None else False
    if _catchup_order_policy(popos_ok=popos_ok, mem_pressure=mem_pressure) == "popos_first":
        return [p for p, _ in gpu] + [p for p, _ in cpu]
    return [p for p, _ in cpu] + [p for p, _ in gpu]


def max_concurrent_widow_cpu_drains(automation: Any) -> int:
    """Worker slots reserved for Widow DB/CPU/fetch drains when lane pools are active."""
    total = max(1, int(getattr(automation, "max_concurrent_tasks", 4) or 4))
    return max(1, total - effective_max_concurrent_widow_gpu_drains(automation))


def _host_lane_for_phase(phase: str) -> str:
    return "popos_gpu" if phase in _popos_gpu_phases() else "widow_local"


def host_lane_pipeline_depth(automation: Any, lane: str) -> int:
    """Running + scheduled depth for a host lane (PopOS GPU drain vs Widow-local)."""
    popos = _popos_gpu_phases()
    running = getattr(automation, "_running_tasks_by_phase", None) or {}
    queued = getattr(automation, "_scheduled_queue_depth_by_phase", None) or {}
    depth = 0
    for phase in set(running.keys()) | set(queued.keys()):
        if lane == "popos_gpu" and phase not in popos:
            continue
        if lane == "widow_local" and phase in popos:
            continue
        depth += int(running.get(phase, 0) or 0) + int(queued.get(phase, 0) or 0)
    return depth


def host_lane_at_cap(automation: Any, phase: str, *, hosts: dict[str, Any] | None = None) -> bool:
    """True when this phase's host lane cannot accept another scheduled drain."""
    if not lane_pools_active(hosts):
        return False
    lane = _host_lane_for_phase(phase)
    if lane == "popos_gpu":
        cap = effective_max_concurrent_widow_gpu_drains(automation)
    else:
        cap = max_concurrent_widow_cpu_drains(automation)
    return host_lane_pipeline_depth(automation, lane) >= cap


def _pick_assembly_phase(backlog: dict[str, int]) -> tuple[str | None, dict[str, Any]]:
    """SSOT: deferral + scoring live in assembly_conductor_service."""
    from services.assembly_conductor_service import _pick_assembly_phase as _asm_pick

    return _asm_pick(backlog)


def pick_next_phases(
    pending: dict[str, int],
    resources: Any,
    phase_health: dict[str, PhaseHealth],
    automation: Any,
    *,
    stall_holds: dict[str, int],
    catchup: bool,
) -> tuple[list[str], str]:
    """
    Explicit decision tree — returns ordered phase names to enqueue and branch label.
    """
    mem_critical = widow_memory_critical(resources)
    oom_overflow = widow_oom_popos_overflow_active(resources, automation)

    if mem_critical and not popos_available_for_overflow(resources):
        return [], "wait_resources_critical"

    if oom_overflow:
        desired, branch = _pick_widow_oom_popos_overflow(
            pending,
            resources,
            phase_health,
            automation,
            stall_holds=stall_holds,
            catchup=catchup,
        )
        if desired:
            logger.info(
                "PipelineController: Widow memory pressure — PopOS overflow "
                "(mem=%s%% branch=%s phases=%s)",
                _widow_memory_percent(resources),
                branch,
                desired[:6],
            )
            return desired, branch
        # Under memory pressure: never fall through to Widow RAM-heavy scheduling.
        if not _widow_resources_ok(resources, automation):
            return [], "wait_resources"
        return [], branch

    if not _widow_resources_ok(resources, automation):
        return [], "wait_resources"

    mem_pressure = widow_memory_pressure(resources)

    if not catchup:
        maint: list[str] = []
        if _phase_eligible("health_check", automation, pending, stall_holds=stall_holds):
            maint.append("health_check")
        for phase in ("context_sync", "entity_profile_sync", "pending_db_flush"):
            if int(pending.get(phase, 0) or 0) > 0 and _phase_eligible(
                phase, automation, pending, stall_holds=stall_holds
            ):
                maint.append(phase)
        if _collection_allowed(pending, automation) and not mem_pressure:
            if _phase_eligible("collection_cycle", automation, pending, stall_holds=stall_holds):
                maint.append("collection_cycle")
        sched = automation.schedules.get("rss_feed_health") or {}
        if sched.get("enabled") and _phase_eligible("rss_feed_health", automation, pending, stall_holds=stall_holds):
            last = sched.get("last_run")
            interval = int(sched.get("interval") or 86400)
            if last is None or (datetime.now(timezone.utc) - last).total_seconds() >= interval:
                maint.append("rss_feed_health")
        return maint, "maintenance"

    desired: list[str] = []

    def _skip_health(phase: str) -> bool:
        h = phase_health.get(phase)
        return h is not None and h.status in ("stalled", "failing")

    def _add(phase: str) -> None:
        if phase in desired:
            return
        if mem_pressure and phase in _WIDOW_RAM_HEAVY_PHASES:
            return
        if not _phase_eligible(phase, automation, pending, stall_holds=stall_holds):
            return
        if _skip_health(phase):
            return
        desired.append(phase)

    skip = frozenset(
        {
            "collection_cycle",
            "pending_db_flush",
            "health_check",
            "rss_feed_health",
        }
    )
    popos_ok = popos_available_for_overflow(resources)
    branch = f"catchup_{_catchup_order_policy(popos_ok=popos_ok, mem_pressure=mem_pressure)}"

    for phase in _catchup_phases_by_backlog(
        pending,
        automation,
        stall_holds=stall_holds,
        skip=skip,
        resources=resources,
    ):
        _add(phase)

    if _collection_allowed(pending, automation) and not mem_pressure:
        _add("collection_cycle")

    if int(pending.get("pending_db_flush", 0) or 0) > 0:
        _add("pending_db_flush")

    return desired, branch


def _widow_resources_ok(resources: Any, automation: Any) -> bool:
    mem_headroom = 0.5
    db_headroom = 0.2
    if resources is not None:
        mem_headroom = float(getattr(resources, "local_memory_headroom", 0.5) or 0.5)
        db_headroom = float(getattr(resources, "db_headroom", 0.5) or 0.5)
    try:
        from shared.database.connection import automation_db_pool_should_defer_phase

        if automation_db_pool_should_defer_phase("__controller__"):
            return db_headroom > 0.05
    except Exception:
        pass
    return mem_headroom > 0.08 or db_headroom > 0.05


@dataclass
class PipelineController:
    """Event-driven controller loop — replan on worker completion."""

    replan_event: asyncio.Event = field(default_factory=asyncio.Event)
    plan_generation: int = 0
    catchup_active: bool = False
    last_tree_branch: str = ""
    phase_health: dict[str, PhaseHealth] = field(default_factory=dict)
    stalled_phases: dict[str, str] = field(default_factory=dict)
    queue_actions_last_replan: list[str] = field(default_factory=list)
    hosts: dict[str, Any] = field(default_factory=dict)
    _stall_holds: dict[str, int] = field(default_factory=dict)
    _pending_history: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list))
    _running: bool = False
    _catchup_was_active: bool = False

    async def run(self, automation: Any) -> None:
        self._running = True
        automation.pipeline_controller = self
        logger.info("PipelineController started")
        self.replan_event.set()
        while self._running and automation.is_running:
            try:
                await asyncio.wait_for(self.replan_event.wait(), timeout=120.0)
            except asyncio.TimeoutError:
                pass
            self.replan_event.clear()
            try:
                await self._replan(automation)
            except Exception:
                logger.exception("PipelineController replan failed")
        logger.info("PipelineController stopped")

    def notify_worker_done(self) -> None:
        self.replan_event.set()

    def request_replan(self) -> None:
        self.replan_event.set()

    async def _replan(self, automation: Any) -> None:
        self.plan_generation += 1
        gen = self.plan_generation
        self.queue_actions_last_replan = []

        await automation.drain_phase_requests_to_queue()

        pending: dict[str, int] = {}
        try:
            from shared.pipeline_queue_counts import get_all_phase_queue_depths

            pending = get_all_phase_queue_depths()
        except Exception as e:
            logger.debug("get_all_phase_queue_depths: %s", e)

        for phase, count in pending.items():
            hist = self._pending_history[phase]
            hist.append(int(count or 0))
            if len(hist) > 10:
                del hist[:-10]

        resources = sample_host_resources(force=True)
        self.hosts = host_state_dict(resources)

        self.catchup_active = is_catchup_active(pending)
        if self.catchup_active and not self._catchup_was_active:
            logger.info("PipelineController: catchup mode ON")
        elif not self.catchup_active and self._catchup_was_active:
            logger.info("PipelineController: catchup mode OFF — maintenance only")
        self._catchup_was_active = self.catchup_active

        self.phase_health = assess_all_phase_health(pending, self._pending_history)
        self._update_stall_holds()

        desired, branch = pick_next_phases(
            pending,
            resources,
            self.phase_health,
            automation,
            stall_holds=self._stall_holds,
            catchup=self.catchup_active,
        )
        self.last_tree_branch = branch

        await automation.reconcile_and_enqueue(
            desired_phases=desired,
            plan_generation=gen,
            stall_holds=self._stall_holds,
            controller=self,
        )

        lp = self.hosts.get("lane_pools")
        if isinstance(lp, dict):
            lp = dict(lp)
            lp["popos_gpu_depth"] = host_lane_pipeline_depth(automation, "popos_gpu")
            lp["widow_local_depth"] = host_lane_pipeline_depth(automation, "widow_local")
            lp["max_popos_gpu_drains"] = effective_max_concurrent_widow_gpu_drains(automation)
            lp["max_widow_cpu_drains"] = max_concurrent_widow_cpu_drains(automation)
            self.hosts["lane_pools"] = lp

        if desired:
            logger.debug(
                "PipelineController replan gen=%s branch=%s desired=%s catchup=%s",
                gen,
                branch,
                desired[:8],
                self.catchup_active,
            )

    def _update_stall_holds(self) -> None:
        self.stalled_phases = {}
        for phase, health in self.phase_health.items():
            if health.status in ("stalled", "failing"):
                self.stalled_phases[phase] = health.detail
                self._stall_holds[phase] = stall_hold_replans()
                logger.info(
                    "PipelineController stall_yield:%s status=%s detail=%s",
                    phase,
                    health.status,
                    health.detail,
                )
        expired = [p for p, n in self._stall_holds.items() if n <= 0]
        for p in expired:
            del self._stall_holds[p]
        for p in list(self._stall_holds.keys()):
            self._stall_holds[p] = max(0, self._stall_holds[p] - 1)

    def get_state(self) -> dict[str, Any]:
        return {
            "catchup_active": self.catchup_active,
            "plan_generation": self.plan_generation,
            "last_tree_branch": self.last_tree_branch,
            "phase_health": {k: {"status": v.status, "detail": v.detail} for k, v in self.phase_health.items()},
            "stalled_phases": dict(self.stalled_phases),
            "queue_actions_last_replan": list(self.queue_actions_last_replan),
            "hosts": self.hosts,
            "stall_holds": dict(self._stall_holds),
        }


_controller_instance: PipelineController | None = None


def get_pipeline_controller() -> PipelineController | None:
    return _controller_instance


def set_pipeline_controller(ctrl: PipelineController | None) -> None:
    global _controller_instance
    _controller_instance = ctrl
