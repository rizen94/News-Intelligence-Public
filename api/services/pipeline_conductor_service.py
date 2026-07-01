"""
Pipeline conductor — single source for scheduler roles across AutomationManager,
OrchestratorCoordinator, and documented external timers (NRI).

Config: pipeline_conductor in orchestrator_governance.yaml with env overrides.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from config.runtime import env_str

# Phases orchestrator may nudge with per-domain scope (mirrors automation_manager loops).
_DOMAIN_SCOPED_PHASES = frozenset(
    {
        "topic_clustering",
        "ml_processing",
        "entity_extraction",
        "sentiment_analysis",
        "quality_scoring",
        "metadata_enrichment",
        "storyline_discovery",
        "proactive_detection",
        "storyline_assembly",
    }
)

_STORYLINE_SCOPED_PHASES = frozenset(
    {
        "storyline_automation",
        "story_continuation",
        "content_refinement_queue",
        "storyline_processing",
        "rag_enhancement",
        "storyline_synthesis",
    }
)

# Not nudged by ProcessingGovernor (collection/infra or owned elsewhere).
_GOVERNOR_EXCLUDED_PHASES = frozenset(
    {
        "collection_cycle",
        "health_check",
        "cache_cleanup",
        "data_cleanup",
        "pending_db_flush",
    }
)

# Fallback when automation_manager cannot be imported (tests / no DB).
_FALLBACK_PIPELINE_PHASES: tuple[str, ...] = (
    "nightly_enrichment_context",
    "context_sync",
    "entity_profile_sync",
    "ml_processing",
    "entity_extraction",
    "metadata_enrichment",
    "claim_extraction",
    "legislative_references",
    "claims_to_facts",
    "claim_subject_gap_refresh",
    "extracted_claims_dedupe",
    "event_extraction",
    "event_tracking",
    "topic_clustering",
    "quality_scoring",
    "sentiment_analysis",
    "fact_verification",
    "entity_profile_build",
    "entity_organizer",
    "graph_connection_distillation",
    "pattern_recognition",
    "cross_domain_synthesis",
    "storyline_discovery",
    "proactive_detection",
    "storyline_assembly",
    "event_coherence_review",
    "entity_enrichment",
    "story_enhancement",
    "pattern_matching",
    "research_topic_refinement",
    "investigation_report_refresh",
    "storyline_processing",
    "rag_enhancement",
    "storyline_automation",
    "storyline_review_agent",
    "storyline_enrichment",
    "story_continuation",
    "event_deduplication",
    "timeline_generation",
    "editorial_document_generation",
    "editorial_briefing_generation",
    "entity_dossier_compile",
    "entity_position_tracker",
    "storyline_synthesis",
    "daily_briefing_synthesis",
    "digest_generation",
    "narrative_thread_build",
    "watchlist_alerts",
    "content_refinement_queue",
    "content_enrichment",
    "document_processing",
    "mention_resolution",
)

_PHASE_INTERVAL_DEFAULTS: dict[str, int] = {
    "content_enrichment": 300,
    "context_sync": 900,
    "entity_profile_sync": 21600,
    "ml_processing": 300,
    "entity_extraction": 300,
    "mention_resolution": 300,
    "claim_extraction": 1800,
    "topic_clustering": 300,
    "storyline_automation": 300,
    "storyline_enrichment": 43200,
    "story_continuation": 600,
    "nightly_enrichment_context": 60,
    "document_processing": 600,
}

_DEFAULT_CONDUCTOR: dict[str, Any] = {
    "automation_primary": True,
    "orchestrator_processing_nudge_enabled": True,
    "orchestrator_post_collection_kickoff_enabled": True,
    "orchestrator_collection_enabled": True,
    "workload_driven_scheduling": True,
    "post_collection_phases": ["content_enrichment", "context_sync"],
    "external_schedulers": [
        {
            "name": "nri_mention_resolve",
            "host": "widow",
            "interval_seconds": 300,
            "budget_env": "NRI_MENTION_RESOLVE_BUDGET_SECONDS",
            "note": "CEM mention resolution — in-process via api/nri_core (mention_resolution phase)",
        },
    ],
}


def _env_bool(name: str, default: bool | None = None) -> bool | None:
    raw = env_str(name, "").strip()
    if not raw:
        return default
    return raw.lower() in ("1", "true", "yes")


def _governance_config() -> dict[str, Any]:
    try:
        from config.orchestrator_governance import get_orchestrator_governance_config

        return get_orchestrator_governance_config()
    except Exception:
        return {}


def get_conductor_config() -> dict[str, Any]:
    """Merged pipeline_conductor section with defaults and env overrides."""
    cfg = _governance_config()
    raw = cfg.get("pipeline_conductor")
    out = dict(_DEFAULT_CONDUCTOR)
    if isinstance(raw, dict):
        for k, v in raw.items():
            if v is not None:
                out[k] = v

    primary = _env_bool("PIPELINE_CONDUCTOR_AUTOMATION_PRIMARY")
    if primary is not None:
        out["automation_primary"] = primary

    nudge = _env_bool("PIPELINE_CONDUCTOR_ORCHESTRATOR_NUDGE")
    if nudge is not None:
        out["orchestrator_processing_nudge_enabled"] = nudge

    if not out.get("automation_primary", True):
        out["orchestrator_processing_nudge_enabled"] = True

    return out


def automation_owns_processing() -> bool:
    """True when AutomationManager is the primary processing scheduler (default)."""
    return bool(get_conductor_config().get("automation_primary", True))


def orchestrator_processing_nudge_enabled() -> bool:
    """True when OrchestratorCoordinator may request_phase via ProcessingGovernor."""
    cfg = get_conductor_config()
    if not cfg.get("automation_primary", True):
        return True
    return bool(cfg.get("orchestrator_processing_nudge_enabled", True))


def orchestrator_post_collection_kickoff_enabled() -> bool:
    """True when RSS collection should chain request_phase for downstream drains."""
    cfg = get_conductor_config()
    return bool(cfg.get("orchestrator_post_collection_kickoff_enabled", True))


def _automation_pipeline_phases() -> tuple[str, ...]:
    """Ordered pipeline phases from AutomationManager (no DB required for tuple itself)."""
    try:
        from services.automation_manager import ANALYSIS_PIPELINE_STEPS

        phases: list[str] = []
        seen: set[str] = set()
        for step in ANALYSIS_PIPELINE_STEPS:
            for phase in step:
                if phase not in seen:
                    seen.add(phase)
                    phases.append(phase)
        for extra in ("content_enrichment", "document_processing", "mention_resolution"):
            if extra not in seen:
                phases.append(extra)
        return tuple(phases)
    except Exception:
        return _FALLBACK_PIPELINE_PHASES


def get_effective_processing_phases() -> dict[str, dict[str, Any]]:
    """
    Full processing phase registry for ProcessingGovernor.

    Merges orchestrator_governance.yaml overrides with all ANALYSIS_PIPELINE_STEPS
    phases so the coordinator can nudge any automation schedule phase.
    """
    yaml_phases = (_governance_config().get("processing") or {}).get("phases") or {}
    out: dict[str, dict[str, Any]] = {}
    for phase in _automation_pipeline_phases():
        if phase in _GOVERNOR_EXCLUDED_PHASES:
            continue
        spec: dict[str, Any] = dict(yaml_phases.get(phase) or {}) if isinstance(
            yaml_phases.get(phase), dict
        ) else {}
        spec.setdefault("interval_seconds", _PHASE_INTERVAL_DEFAULTS.get(phase, 1200))
        if "scope" not in spec:
            if phase in _DOMAIN_SCOPED_PHASES:
                spec["scope"] = "domain"
            elif phase in _STORYLINE_SCOPED_PHASES:
                spec["scope"] = "storyline"
            else:
                spec["scope"] = None
        spec.setdefault("estimated_duration", 60)
        out[phase] = spec
    for phase, spec in yaml_phases.items():
        if phase not in out and isinstance(spec, dict):
            out[phase] = dict(spec)
    return out


def get_post_collection_kickoff_phases() -> list[str]:
    """Phases to request_phase immediately after orchestrator RSS ingest."""
    cfg = get_conductor_config()
    raw = cfg.get("post_collection_phases")
    if isinstance(raw, list) and raw:
        return [str(p).strip() for p in raw if str(p).strip()]
    return ["content_enrichment", "context_sync"]


def workload_driven_scheduling_enabled() -> bool:
    cfg = get_conductor_config()
    if cfg.get("workload_driven_scheduling") is not None:
        return bool(cfg["workload_driven_scheduling"])
    return bool(_governance_config().get("workload_driven_scheduling", True))


def _disabled_schedule_names(
    automation_status: dict[str, Any] | None,
    disabled_schedule_names: list[str] | None,
) -> set[str]:
    if disabled_schedule_names is not None:
        return {n.strip() for n in disabled_schedule_names if n and n.strip()}
    raw = env_str("AUTOMATION_DISABLED_SCHEDULES", "").strip()
    if raw:
        return {n.strip() for n in raw.split(",") if n.strip()}
    return set()


def _per_phase_cap(phase_name: str) -> int:
    """Mirror automation_manager per-phase cap for status-only checks."""
    try:
        from services.automation_manager import (
            AUTOMATION_PER_PHASE_CONCURRENT_CAP,
            _per_phase_concurrent_cap_overrides,
            _per_phase_concurrent_cap_phase_names,
        )

        overrides = _per_phase_concurrent_cap_overrides()
        if phase_name in overrides:
            return int(overrides[phase_name])
        if phase_name not in _per_phase_concurrent_cap_phase_names():
            return 0
        return int(AUTOMATION_PER_PHASE_CONCURRENT_CAP)
    except Exception:
        return int(env_str("AUTOMATION_PER_PHASE_CONCURRENT_CAP", "2") or 2)


def _phase_recently_ran(
    phase_name: str,
    automation_status: dict[str, Any],
    *,
    pending: int,
) -> bool:
    """True when phase ran within harmony cooldown (automation owns drain)."""
    schedules = automation_status.get("schedules") or {}
    sched = schedules.get(phase_name) if isinstance(schedules, dict) else None
    if not isinstance(sched, dict):
        return False
    last_run = sched.get("last_run")
    if not last_run:
        return False
    try:
        if isinstance(last_run, datetime):
            last_dt = last_run if last_run.tzinfo else last_run.replace(tzinfo=timezone.utc)
        else:
            last_run_s = str(last_run).replace("Z", "+00:00")
            last_dt = datetime.fromisoformat(last_run_s)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return False

    metrics = automation_status.get("metrics") or {}
    history = metrics.get("processing_history") or {}
    est = float(sched.get("estimated_duration", 60) or 60)
    try:
        from services.pipeline_orchestration_harmony import harmonized_workload_cooldown_seconds

        base = int(env_str("AUTOMATION_WORKLOAD_MIN_COOLDOWN_SECONDS", "10") or 10)
        running = int((automation_status.get("active_tasks_by_phase") or {}).get(phase_name, 0) or 0)
        cap = _per_phase_cap(phase_name)
        cooldown = harmonized_workload_cooldown_seconds(
            phase_name,
            base_cooldown=base,
            processing_history=history,
            estimated_duration=est,
            pending=pending,
            running_same_phase=running,
            per_phase_cap=cap,
        )
    except Exception:
        cooldown = 300

    elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds()
    return elapsed < cooldown


def should_orchestrator_request_phase(
    phase_name: str,
    automation_status: dict[str, Any] | None,
    *,
    disabled_schedule_names: list[str] | None = None,
) -> bool:
    """
    Whether OrchestratorCoordinator should call request_phase for this phase.

    Returns False when automation already owns the phase, nudge is disabled, or
    the phase is saturated / recently ran with pending backlog.
    """
    if not orchestrator_processing_nudge_enabled():
        return False

    if phase_name in _disabled_schedule_names(automation_status, disabled_schedule_names):
        return False

    st = automation_status or {}
    pending = int((st.get("pending_counts") or {}).get(phase_name, 0) or 0)
    active = int((st.get("active_tasks_by_phase") or {}).get(phase_name, 0) or 0)
    queued = int((st.get("queued_tasks_by_phase") or {}).get(phase_name, 0) or 0)

    # Workload-driven automation owns a phase only while it is running or queued.
    # Pending backlog alone must not block nudges — otherwise stuck phases never get request_phase.
    if workload_driven_scheduling_enabled() and pending > 0 and (active > 0 or queued > 0):
        return False

    if active > 0 or queued > 0:
        return False

    cap = _per_phase_cap(phase_name)
    if cap > 0 and active >= cap:
        return False

    if pending > 0 and (active > 0 or queued > 0) and _phase_recently_ran(
        phase_name, st, pending=pending
    ):
        return False

    return True


def effective_governor_interval_seconds(
    phase_name: str,
    base_interval: int,
    *,
    automation_pending: int,
    processing_history: dict[str, list[float]],
    estimated_duration: float,
) -> int:
    """
    Governor interval: harmony floor from measured duration, shortened when backlog is high.
    """
    from services.pipeline_orchestration_harmony import effective_schedule_interval_seconds

    interval = effective_schedule_interval_seconds(
        phase_name,
        int(base_interval),
        processing_history=processing_history,
        estimated_duration=estimated_duration,
    )
    pending = int(automation_pending or 0)
    if pending <= 0:
        return interval

    try:
        from services.backlog_metrics import BATCH_SIZE_PER_TASK

        batch = max(1, int(BATCH_SIZE_PER_TASK.get(phase_name, 30) or 30))
    except Exception:
        batch = 30

    if pending >= batch * 4:
        return max(60, int(interval * 0.5))
    if pending >= batch * 2:
        return max(60, int(interval * 0.7))
    return interval


def get_documented_external_schedulers() -> list[dict[str, Any]]:
    """External schedulers documented in pipeline_conductor (not NI AutomationManager)."""
    schedulers = get_conductor_config().get("external_schedulers")
    if isinstance(schedulers, list):
        return [dict(s) for s in schedulers if isinstance(s, dict)]
    return list(_DEFAULT_CONDUCTOR["external_schedulers"])
