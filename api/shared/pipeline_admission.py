"""
Flat pipeline admission — mode + priority + single admit_phase.

Replaces nested pick_next_phases / residual / OOM special cases when
``PIPELINE_FLAT_SCHEDULER`` is enabled (default on).
"""

from __future__ import annotations

import logging
from typing import Any, Literal

logger = logging.getLogger(__name__)

SchedulerMode = Literal["pressure", "preprocess", "postprocess", "maintenance"]

# Light Widow work under RAM/DB pressure (no PopOS GPU enqueue on Widow).
PRESSURE_PRIORITY: tuple[str, ...] = (
    "pending_db_flush",
    "context_sync",
    "entity_profile_sync",
    "spine_sql_tail",
    "claims_to_facts",
    "event_tracking",
    "mention_resolution",
)

# Preprocess band order (collection appended separately when allowed).
PREPROCESS_PRIORITY: tuple[str, ...] = (
    "content_enrichment",
    "unified_intake_extraction",
    "spine_sql_tail",
    "document_processing",
    "context_sync",
    "mention_resolution",
    "entity_profile_build",
    "claim_extraction",
)

# Post-process / structure-first (Widow-local before remote assembly peers).
# Event matching rail (catchup → coref → continuation) before legacy chemistry stir.
POSTPROCESS_PRIORITY: tuple[str, ...] = (
    "mention_resolution",
    "entity_profile_build",
    "event_tracking",
    "chronological_events_catchup",
    "event_deduplication",
    "story_continuation",
    "editorial_research_pass",
    "editorial_narrative_pass",
    "editorial_reduction_pass",
    "graph_connection_distillation",
    "embedding_link_candidates",
    "collision_sampling",
    "stimulus_rag",
    "protein_harden",
    "storyline_automation",
    "storyline_review_agent",
    "storyline_membership_review",
    "storyline_assembly",
    "spine_sql_tail",
    "context_sync",
    "topic_clustering",
    "content_refinement_queue",
    "pending_db_flush",
)

# Maintenance fillers + residual structure when catchup drivers are quiet.
MAINTENANCE_PRIORITY: tuple[str, ...] = (
    "context_sync",
    "entity_profile_sync",
    "pending_db_flush",
    "mention_resolution",
    "entity_profile_build",
    "event_tracking",
    "chronological_events_catchup",
    "event_deduplication",
    "story_continuation",
    "editorial_research_pass",
    "editorial_narrative_pass",
    "editorial_reduction_pass",
    "graph_connection_distillation",
    "embedding_link_candidates",
    "collision_sampling",
    "stimulus_rag",
    "protein_harden",
    "graph_link_drift_review",
    "storyline_assembly",
    "topic_clustering",
    "storyline_automation",
    "storyline_review_agent",
    "storyline_membership_review",
    # Durable queued RAG/narrative jobs (auto-enqueue or UI) — not only postprocess mode.
    "content_refinement_queue",
    "rss_feed_health",
    "collection_cycle",
)

_MODE_BRANCH = {
    "pressure": "mode_pressure",
    "preprocess": "mode_preprocess",
    "postprocess": "mode_postprocess",
    "maintenance": "mode_maintenance",
}


def flat_scheduler_enabled() -> bool:
    """Kill-switch; default on so flat mode is the scheduling SSOT."""
    from config.runtime import env_str

    return env_str("PIPELINE_FLAT_SCHEDULER", "true").lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _controller_config() -> dict[str, Any]:
    try:
        from config.orchestrator_governance import get_orchestrator_governance_config

        raw = get_orchestrator_governance_config().get("pipeline_controller") or {}
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _mode_cfg() -> dict[str, Any]:
    cfg = _controller_config().get("modes")
    return cfg if isinstance(cfg, dict) else {}


def _mode_int(key: str, default: int, *, env: str | None = None) -> int:
    from config.runtime import env_str

    modes = _mode_cfg()
    if modes.get(key) is not None:
        try:
            return max(0, int(modes[key]))
        except (TypeError, ValueError):
            pass
    if env:
        try:
            return max(0, int(env_str(env, str(default))))
        except ValueError:
            pass
    return default


def mode_intake_clear() -> int:
    """Core preprocess pending above this → preprocess mode."""
    # Prefer modes.intake_clear; fall back to legacy intake_preprocess_clear_threshold.
    modes = _mode_cfg()
    if modes.get("intake_clear") is not None:
        return _mode_int("intake_clear", 50)
    cfg = _controller_config()
    if cfg.get("intake_preprocess_clear_threshold") is not None:
        try:
            return max(1, int(cfg["intake_preprocess_clear_threshold"]))
        except (TypeError, ValueError):
            pass
    if cfg.get("catchup_clear_threshold") is not None:
        try:
            return max(1, int(cfg["catchup_clear_threshold"]))
        except (TypeError, ValueError):
            pass
    return _mode_int("intake_clear", 50, env="INTAKE_PREPROCESS_CLEAR_THRESHOLD")


def mode_preprocess_stable() -> int:
    return _mode_int("preprocess_stable", 5, env="PREPROCESS_STABLE_THRESHOLD")


def mode_structure_hot() -> int:
    return _mode_int("structure_hot", 200, env="STRUCTURE_CATCHUP_REFINEMENT_DEFER_THRESHOLD")


def mode_residual_min() -> int:
    """Min pending for residual structure drains in maintenance mode."""
    return max(25, _mode_int("residual_min", 100))


# Phases whose maintenance-mode scheduling batches work up to ``mode_residual_min()``
# before running — to avoid waking expensive drains on every trickle. The final partial
# batch (0 < pending < residual_min) must still drain; see ``residual_tail_drain_due``.
MAINTENANCE_RESIDUAL_PHASES: frozenset[str] = frozenset(
    {
        "mention_resolution",
        "entity_profile_build",
        "event_tracking",
        "graph_connection_distillation",
        "embedding_link_candidates",
        "graph_link_drift_review",
        "storyline_assembly",
        "topic_clustering",
        "storyline_automation",
        "storyline_review_agent",
        "storyline_membership_review",
    }
)


def residual_tail_drain_sec() -> int:
    """Max time a sub-residual (partial) maintenance backlog may sit before the final
    partial batch runs anyway. Keeps trickle batching efficient while guaranteeing the
    tail below ``mode_residual_min()`` is never stranded (the last run that finishes the
    backlog is always allowed)."""
    return max(60, _mode_int("residual_tail_drain_sec", 900))


def residual_tail_drain_due(phase: str, automation: Any, *, now: Any = None) -> bool:
    """True when a residual phase holding a partial (< residual_min) backlog should drain
    anyway because it has no recent run within the tail-drain window. Never strands the
    final partial batch: if we can't establish a recent run, we allow the drain."""
    try:
        sched = (getattr(automation, "schedules", None) or {}).get(phase) or {}
    except Exception:
        return True
    last = sched.get("last_run")
    if last is None:
        return True
    from datetime import datetime, timezone

    if now is None:
        now = datetime.now(timezone.utc)
    window = max(int(sched.get("interval") or 0), residual_tail_drain_sec())
    try:
        return (now - last).total_seconds() >= window
    except Exception:
        return True


def mode_collection_downstream_max() -> int:
    return _mode_int("collection_downstream_max", 1200, env="COLLECTION_THROTTLE_PENDING_THRESHOLD")


def compute_mode(
    pending: dict[str, int],
    *,
    pressure: bool = False,
) -> SchedulerMode:
    """Pick exactly one scheduling mode for this replan."""
    from shared.pipeline_resource_policy import (
        intake_preprocess_pending,
        post_process_preferred_enabled,
        preprocess_stable_pending,
        structure_band_pending,
    )

    if pressure:
        return "pressure"

    if intake_preprocess_pending(pending) > mode_intake_clear():
        return "preprocess"

    if post_process_preferred_enabled():
        if (
            preprocess_stable_pending(pending) <= mode_preprocess_stable()
            and structure_band_pending(pending) > 0
        ):
            return "postprocess"

    return "maintenance"


def priority_list(mode: SchedulerMode) -> tuple[str, ...]:
    if mode == "pressure":
        return PRESSURE_PRIORITY
    if mode == "preprocess":
        return PREPROCESS_PRIORITY
    if mode == "postprocess":
        return POSTPROCESS_PRIORITY
    return MAINTENANCE_PRIORITY


def branch_label(mode: SchedulerMode) -> str:
    return _MODE_BRANCH.get(mode, f"mode_{mode}")


def _spine_sql_tail_should_run(pending: dict[str, int]) -> bool:
    enrich = int(pending.get("content_enrichment", 0) or 0)
    intake = int(pending.get("unified_intake_extraction", 0) or 0)
    claims = int(pending.get("claims_to_facts", 0) or 0)
    ctx = int(pending.get("context_sync", 0) or 0)
    if enrich > 0 or intake > 500:
        return False
    return claims > 0 or ctx > 0


def pending_ok(phase: str, pending: dict[str, int], *, mode: SchedulerMode) -> bool:
    """True when backlog (or composite) justifies scheduling this phase."""
    if phase == "spine_sql_tail":
        return _spine_sql_tail_should_run(pending)
    if phase == "rss_feed_health":
        return True
    if phase == "collection_cycle":
        return True  # further gated by collection_allowed in pick

    count = int(pending.get(phase, 0) or 0)
    if mode == "maintenance" and phase in MAINTENANCE_RESIDUAL_PHASES:
        return count >= mode_residual_min()
    return count > 0


def admit_phase(
    phase: str,
    *,
    pending: dict[str, int],
    mode: SchedulerMode,
    automation: Any,
    stall_holds: dict[str, int],
    ignore_remote_ownership: bool = False,
    popos_gpu_phases: frozenset[str] | None = None,
) -> str | None:
    """
    Return None if the phase may be desired, else a short deny reason.

    Host ordering and residual thresholds are mode/priority concerns — not here.
    """
    name = (phase or "").strip()
    if not name:
        return "empty_phase"

    if stall_holds.get(name, 0) > 0:
        return "stall_hold"

    try:
        from shared.remote_phase_worker import phase_owned_by_remote_worker

        if not ignore_remote_ownership and phase_owned_by_remote_worker(name):
            return "remote_owned"
    except Exception:
        pass

    try:
        from config.runtime import env_str
        from shared.process_memory import AUTOMATION_RSS_PAUSE_EXEMPT_PHASES, process_rss_mb

        raw_block = (env_str("AUTOMATION_BLOCK_PHASES", "") or "").strip()
        if raw_block and name in {x.strip() for x in raw_block.split(",") if x.strip()}:
            return "blocked"
        pause_mb = float(env_str("AUTOMATION_RSS_PAUSE_MB", "1800") or "1800")
        rss = process_rss_mb()
        if rss is not None and rss >= pause_mb and name not in AUTOMATION_RSS_PAUSE_EXEMPT_PHASES:
            return "rss_pause"
    except Exception:
        pass

    if name not in getattr(automation, "schedules", {}):
        return "no_schedule"
    schedule = automation.schedules[name]
    if not schedule.get("enabled", True):
        if not ignore_remote_ownership:
            return "disabled"
        try:
            from shared.remote_phase_worker import phase_owned_by_remote_worker

            if not phase_owned_by_remote_worker(name):
                return "disabled"
        except Exception:
            return "disabled"

    try:
        from services.backlog_metrics import SKIP_WHEN_EMPTY as _SKIP
    except Exception:
        _SKIP = frozenset(
            {
                "mention_resolution",
                "entity_profile_build",
                "event_tracking",
                "graph_connection_distillation",
                "storyline_assembly",
                "content_enrichment",
                "unified_intake_extraction",
                "context_sync",
                "claim_extraction",
            }
        )

    if name in _SKIP and int(pending.get(name, 0) or 0) <= 0:
        if name == "spine_sql_tail" and _spine_sql_tail_should_run(pending):
            pass
        elif name in ("rss_feed_health", "collection_cycle"):
            pass
        else:
            return "empty_backlog"

    try:
        from services.pipeline_schedule_service import automation_phase_allowed

        if not automation_phase_allowed(name, pending_count=int(pending.get(name, 0) or 0)):
            return "schedule_window"
    except Exception:
        pass

    try:
        from shared.assembly_phase_order import post_spine_scheduling_suppressed

        if post_spine_scheduling_suppressed(name):
            return "post_spine_suppressed"
    except Exception:
        pass

    try:
        from shared.pipeline_resource_policy import (
            entity_profile_build_allowed,
            intake_extraction_suppressed,
            intake_first_gpu_defer_threshold,
            intake_preprocess_hot,
            legacy_intake_extraction_phases,
            refinement_phase_allowed,
            unified_superseded_automation_phases,
        )
        from shared.pipeline_resource_policy import INTAKE_PREPROCESS_PHASES
        from shared.spine_phase_order import spine_pipeline_ordered_active

        if intake_extraction_suppressed() and name in legacy_intake_extraction_phases():
            return "legacy_intake_suppressed"
        if intake_extraction_suppressed() and name in unified_superseded_automation_phases():
            return "unified_superseded"

        # Spine-ordered: while preprocess hot, defer non-intake/non-structure-exempt phases.
        # MR/EPB stay admissible (structure co-schedule).
        _co_schedule = frozenset(
            {
                *INTAKE_PREPROCESS_PHASES,
                "health_check",
                "pending_db_flush",
                "rss_feed_health",
                "mention_resolution",
                "entity_profile_build",
            }
        )
        _gpu_defer = frozenset(
            {
                "storyline_assembly",
                "storyline_automation",
                "entity_dossier_compile",
            }
        )
        if spine_pipeline_ordered_active() and mode == "preprocess":
            if intake_preprocess_hot(pending) and name not in _co_schedule:
                return "preprocess_defer"
            intake = int(pending.get("unified_intake_extraction", 0) or 0)
            thresh = intake_first_gpu_defer_threshold()
            if thresh > 0 and intake >= thresh and name in _gpu_defer:
                return "uie_gpu_defer"

        if not refinement_phase_allowed(name, pending):
            return "refinement_deferred"
        if name == "entity_profile_build" and not entity_profile_build_allowed(pending):
            return "epb_not_allowed"
    except Exception:
        pass

    try:
        from config.runtime import env_str
        from shared.database.db_availability import is_automation_db_ready

        if env_str("AUTOMATION_PAUSE_WHEN_DB_DOWN", "true").lower() in ("1", "true", "yes"):
            if not is_automation_db_ready():
                return "db_down"
    except Exception:
        pass

    try:
        from services.nightly_ingest_window_service import in_nightly_pipeline_window_est

        nightly = in_nightly_pipeline_window_est()
    except Exception:
        nightly = False
    if name == "context_sync" and nightly:
        return "nightly_block"
    if name == "content_refinement_queue" and nightly:
        return "nightly_block"
    if name == "nightly_enrichment_context" and not nightly:
        return "nightly_only"

    # Pressure mode: never desire PopOS GPU phases onto Widow.
    if mode == "pressure" and popos_gpu_phases and name in popos_gpu_phases:
        return "pressure_no_gpu"

    return None


def _collection_allowed_flat(pending: dict[str, int], automation: Any, *, mode: SchedulerMode) -> bool:
    from datetime import datetime, timezone

    from config.runtime import env_str

    # Avoid importing services.automation_manager (pulls DB via services/__init__).
    try:
        from services.automation_manager import (
            _collection_throttle_pending_total,
            collection_cycle_has_pending_work,
        )
    except Exception:
        # Unit tests / import isolation: allow collection if schedule looks due.
        q_len = len(getattr(automation, "_pending_collection_queue", []) or [])
        if q_len > 0:
            return True
        if mode == "postprocess":
            return False
        return True

    q_len = len(getattr(automation, "_pending_collection_queue", []) or [])
    if not collection_cycle_has_pending_work(pending, pending_collection_queue_len=q_len):
        return False
    if mode == "postprocess":
        sched = automation.schedules.get("collection_cycle") or {}
        last = sched.get("last_run")
        if last is not None:
            interval = int(sched.get("interval") or 7200)
            age = (datetime.now(timezone.utc) - last).total_seconds()
            if age < interval:
                return False
    downstream, _br = _collection_throttle_pending_total(pending)
    if downstream > mode_collection_downstream_max():
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


def _rss_feed_health_due(automation: Any) -> bool:
    from datetime import datetime, timezone

    sched = automation.schedules.get("rss_feed_health") or {}
    if not sched.get("enabled"):
        return False
    last = sched.get("last_run")
    interval = int(sched.get("interval") or 604800)
    if last is None:
        return True
    return (datetime.now(timezone.utc) - last).total_seconds() >= interval


def pick_next_phases_flat(
    pending: dict[str, int],
    resources: Any,
    phase_health: dict[str, Any],
    automation: Any,
    *,
    stall_holds: dict[str, int],
    pressure: bool = False,
    wait_resources_critical: bool = False,
    popos_gpu_phases: frozenset[str] | None = None,
    catchup_phase_names: frozenset[str] | None = None,
    widow_assembly_fallback: bool = False,
) -> tuple[list[str], str]:
    """Mode → priority list → admit once → desired."""
    if wait_resources_critical:
        return [], "wait_resources_critical"

    mode = compute_mode(pending, pressure=pressure)
    branch = branch_label(mode)
    candidates = list(priority_list(mode))

    # Append remaining catchup peers with pending so the queue stays loaded.
    if mode in ("preprocess", "postprocess") and catchup_phase_names:
        extra = sorted(
            (
                ph
                for ph in catchup_phase_names
                if ph not in candidates
                and ph
                not in (
                    "collection_cycle",
                    "pending_db_flush",
                    "health_check",
                    "rss_feed_health",
                )
                and int(pending.get(ph, 0) or 0) > 0
            ),
            key=lambda p: -int(pending.get(p, 0) or 0),
        )
        candidates.extend(extra)

    if mode in ("postprocess", "maintenance") and int(pending.get("pending_db_flush", 0) or 0) > 0:
        if "pending_db_flush" not in candidates:
            candidates.append("pending_db_flush")

    if mode != "pressure" and "collection_cycle" not in candidates:
        candidates.append("collection_cycle")

    desired: list[str] = []
    for phase in candidates:
        if phase in desired:
            continue
        if not pending_ok(phase, pending, mode=mode):
            if phase == "rss_feed_health":
                if not _rss_feed_health_due(automation):
                    continue
            elif phase == "collection_cycle":
                pass  # collection has its own gate below
            elif (
                mode == "maintenance"
                and phase in MAINTENANCE_RESIDUAL_PHASES
                and int(pending.get(phase, 0) or 0) > 0
                and residual_tail_drain_due(phase, automation)
            ):
                # Tail-drain escape: the final partial batch (0 < pending < residual_min)
                # must still run so the backlog reaches zero. Batching held it below the
                # floor; once the tail-drain window elapses we admit the last run.
                pass
            else:
                continue
        if phase == "collection_cycle":
            if mode == "pressure":
                continue
            if not _collection_allowed_flat(pending, automation, mode=mode):
                continue
        if phase == "rss_feed_health" and not _rss_feed_health_due(automation):
            continue

        deny = admit_phase(
            phase,
            pending=pending,
            mode=mode,
            automation=automation,
            stall_holds=stall_holds,
            popos_gpu_phases=popos_gpu_phases,
        )
        if deny is not None:
            continue

        h = phase_health.get(phase) if phase_health else None
        if h is not None and getattr(h, "status", None) == "failing":
            continue

        desired.append(phase)

    # Residual assembly Widow fallback when remote-owned and PopOS stale.
    if (
        mode == "maintenance"
        and widow_assembly_fallback
        and "storyline_assembly" not in desired
        and int(pending.get("storyline_assembly", 0) or 0) >= mode_residual_min()
    ):
        desired.append("storyline_assembly")
        branch = "mode_maintenance_assembly_fallback"

    return desired, branch
