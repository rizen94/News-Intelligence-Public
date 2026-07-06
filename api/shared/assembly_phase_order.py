"""
Post-spine assembly phase order — programmatic graph → editorial room loop.

Used by assembly conductor and automation suppression when ASSEMBLY_PIPELINE_MODE=ordered.
"""

from __future__ import annotations

from config.runtime import env_str

# Work-completion order after spine (link indexer runs inside spine_sql_tail).
POST_SPINE_PHASE_ORDER: tuple[str, ...] = (
    "graph_connection_distillation",
    "entity_profile_build",
    "event_tracking",
    "story_continuation",
    "storyline_assembly",
    "storyline_automation",
    "entity_organizer",
    "editorial_room_loop",
    "entity_dossier_compile",
)

# Phases retired from workload-driven scheduling (code remains for rollback / API).
POST_SPINE_RETIRED_PHASES: frozenset[str] = frozenset(
    {
        "proactive_detection",
        "storyline_discovery",
        "narrative_thread_build",
        "pattern_recognition",
        "pattern_matching",
        "relationship_extraction",
        "editorial_briefing_generation",
        "editorial_document_generation",
        "arc_report_generation",
        "daily_briefing_synthesis",
        "digest_generation",
        "storyline_synthesis",
        "rag_enhancement",
        "storyline_enrichment",
        "storyline_processing",
        "investigation_report_refresh",
        "story_enhancement",
        "event_coherence_review",
        "timeline_generation",
        "entity_position_tracker",
    }
)


def assembly_pipeline_mode() -> str:
    """ordered | shadow | legacy (workload-driven competition)."""
    raw = env_str("ASSEMBLY_PIPELINE_MODE", "ordered").strip().lower()
    if raw in ("ordered", "shadow", "legacy"):
        return raw
    return "ordered"


def assembly_pipeline_ordered_active() -> bool:
    return assembly_pipeline_mode() == "ordered"


def assembly_pipeline_shadow_active() -> bool:
    return assembly_pipeline_mode() == "shadow"


def editorial_room_loop_enabled() -> bool:
    if env_str("EDITORIAL_ROOM_LOOP_ENABLED", "true").lower() in ("0", "false", "no"):
        return False
    return True


def post_spine_scheduling_suppressed(phase_name: str) -> bool:
    """When assembly is not legacy, suppress retired full-scan / narrative phases."""
    if assembly_pipeline_mode() == "legacy":
        return False
    p = (phase_name or "").strip().lower().replace("-", "_")
    return p in POST_SPINE_RETIRED_PHASES


def assembly_phases_for_nightly_suffix() -> tuple[str, ...]:
    """Canonical post-spine tail for nightly sequential drain."""
    return POST_SPINE_PHASE_ORDER + ("mention_resolution", "entity_profile_sync")
