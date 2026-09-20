"""
Pipeline conductor — single source for scheduler roles across AutomationManager,
OrchestratorCoordinator, and documented external timers (NRI).

Config: pipeline_conductor in orchestrator_governance.yaml with env overrides.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from config.runtime import env_str

# Phases with per-domain scope in governance config (mirrors automation_manager loops).
# Retired / conductor-owned phases are filtered dynamically in get_effective_processing_phases().
_DOMAIN_SCOPED_PHASES = frozenset(
    {
        "topic_clustering",
        "entity_enrichment",
        "cross_domain_synthesis",
    }
)

_STORYLINE_SCOPED_PHASES = frozenset(
    {
        "storyline_review_agent",
        "watchlist_alerts",
    }
)

# Infra / collection phases excluded from processing phase registry display.
_CONDUCTOR_EXCLUDED_INFRA_PHASES = frozenset(
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
    "claim_extraction",
    "claims_to_facts",
    "entity_profile_build",
    "entity_organizer",
    "graph_connection_distillation",
    "cross_domain_synthesis",
    "storyline_assembly",
    "event_tracking",
    "story_continuation",
    "entity_enrichment",
    "entity_dossier_compile",
    "storyline_automation",
    "storyline_review_agent",
    "event_deduplication",
    "mention_resolution",
    "content_refinement_queue",
    "content_enrichment",
    "document_processing",
    "watchlist_alerts",
    "fact_verification",
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
    "orchestrator_post_collection_kickoff_enabled": True,
    "orchestrator_collection_enabled": True,
    "post_collection_phases": ["content_enrichment", "context_sync"],
    "post_intake_beaker_enabled": True,
    "post_intake_beaker_phases": [
        "graph_connection_distillation",
        "embedding_link_candidates",
        "collision_sampling",
        "stimulus_rag",
        "protein_harden",
    ],
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

    return out


def automation_owns_processing() -> bool:
    """True when AutomationManager is the primary processing scheduler (default)."""
    return bool(get_conductor_config().get("automation_primary", True))


def orchestrator_post_collection_kickoff_enabled() -> bool:
    """True when RSS collection should trigger pipeline replan."""
    try:
        from config.orchestrator_governance import get_orchestrator_governance_config

        raw = (get_orchestrator_governance_config().get("pipeline_controller") or {}).get(
            "post_collection_kickoff_enabled"
        )
        if raw is not None:
            return bool(raw)
    except Exception:
        pass
    return bool(get_conductor_config().get("orchestrator_post_collection_kickoff_enabled", True))


def conductor_pipeline_modes() -> dict[str, str]:
    """Spine / assembly conductor modes for orchestrator and Monitor."""
    spine = "legacy"
    assembly = "legacy"
    try:
        from shared.spine_phase_order import spine_pipeline_mode

        spine = spine_pipeline_mode()
    except Exception:
        pass
    try:
        from shared.assembly_phase_order import assembly_pipeline_mode

        assembly = assembly_pipeline_mode()
    except Exception:
        pass
    return {"spine_pipeline_mode": spine, "assembly_pipeline_mode": assembly}


def phase_conductor_scheduling_suppressed(phase_name: str) -> bool:
    """
    True when PipelineController must not enqueue this phase from the orchestrator path.

    Post-spine retired phases are suppressed when assembly is not legacy.
    Scheduling loops in spine/assembly conductors were retired in v10.1 — PipelineController only.
    """
    p = (phase_name or "").strip().lower().replace("-", "_")
    if not p:
        return False
    try:
        from shared.assembly_phase_order import post_spine_scheduling_suppressed

        if post_spine_scheduling_suppressed(p):
            return True
    except Exception:
        pass
    try:
        from shared.pipeline_resource_policy import (
            intake_extraction_suppressed,
            legacy_intake_extraction_phases,
            unified_superseded_automation_phases,
        )

        if intake_extraction_suppressed() and p in legacy_intake_extraction_phases():
            return True
        if intake_extraction_suppressed() and p in unified_superseded_automation_phases():
            return True
    except Exception:
        pass
    return False


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
    Full processing phase registry (Monitor / orchestrator config display).

    Merges orchestrator_governance.yaml overrides with automation schedule phases.
    """
    yaml_phases = (_governance_config().get("processing") or {}).get("phases") or {}
    out: dict[str, dict[str, Any]] = {}
    for phase in _automation_pipeline_phases():
        if phase in _CONDUCTOR_EXCLUDED_INFRA_PHASES:
            continue
        if phase_conductor_scheduling_suppressed(phase):
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
            if not phase_conductor_scheduling_suppressed(phase):
                out[phase] = dict(spec)
    return out


def get_post_collection_kickoff_phases() -> list[str]:
    """Phases expected after RSS ingest — from pipeline_controller governance YAML."""
    phases: list[str]
    try:
        from config.orchestrator_governance import get_orchestrator_governance_config

        raw = (get_orchestrator_governance_config().get("pipeline_controller") or {}).get(
            "post_collection_phases"
        )
    except Exception:
        raw = None
    if not raw:
        raw = get_conductor_config().get("post_collection_phases")
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


def should_orchestrator_request_phase(
    phase_name: str,
    automation_status: dict[str, Any] | None,
    *,
    disabled_schedule_names: list[str] | None = None,
) -> bool:
    """Retired — PipelineController owns processing enqueue (v10.1+)."""
    return False


def get_documented_external_schedulers() -> list[dict[str, Any]]:
    """External schedulers documented in pipeline_conductor (not NI AutomationManager)."""
    schedulers = get_conductor_config().get("external_schedulers")
    if isinstance(schedulers, list):
        return [dict(s) for s in schedulers if isinstance(s, dict)]
    return list(_DEFAULT_CONDUCTOR["external_schedulers"])
