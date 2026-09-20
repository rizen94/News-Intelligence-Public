"""
Post-spine assembly phase order — programmatic graph → editorial rails (v12).

Used by assembly conductor and automation suppression when ASSEMBLY_PIPELINE_MODE=ordered.
"""

from __future__ import annotations

from config.runtime import env_str

# Work-completion order after spine (link indexer runs inside spine_sql_tail).
# entity_organizer (T1 ambiguous enqueue) before distillation so pending stays
# for editorial T2 instead of being drained in a prior tick with an empty feed.
# Event rail: CE restore → coref → continuation before storyline assembly / editorial.
# v12: evidence expand before reduction; storyline_automation + room_loop retired.
POST_SPINE_PHASE_ORDER: tuple[str, ...] = (
    "entity_organizer",
    "graph_connection_distillation",
    "entity_profile_build",
    "event_tracking",
    "chronological_events_catchup",
    "event_deduplication",
    "story_continuation",
    "storyline_assembly",
    "editorial_research_pass",
    "editorial_narrative_pass",
    "editorial_evidence_expand_pass",
    "editorial_reduction_pass",
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
        # rag_enhancement unretired: targeted top-N hot storylines (refinement / nightly)
        "storyline_enrichment",
        "storyline_processing",
        "investigation_report_refresh",
        "story_enhancement",
        "event_coherence_review",
        "timeline_generation",
        "entity_position_tracker",
        # v12 cutover — bag absorb + room loop out of ordered schedule
        "storyline_automation",
        "editorial_room_loop",
    }
)

# Briefing batch synthesizers — fully retired (desk promote + content_refinement_queue / RAG).
# Suppressed even when ASSEMBLY_PIPELINE_MODE=legacy; executors are hard no-ops.
FULLY_RETIRED_BRIEFING_PHASES: frozenset[str] = frozenset(
    {
        "editorial_document_generation",
        "editorial_briefing_generation",
        "daily_briefing_synthesis",
        "digest_generation",
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
    """v12 default off — room loop retired from POST_SPINE."""
    if env_str("EDITORIAL_ROOM_LOOP_ENABLED", "false").lower() in ("1", "true", "yes", "on"):
        return True
    return False


def _norm_phase(phase_name: str) -> str:
    return (phase_name or "").strip().lower().replace("-", "_")


def is_fully_retired_briefing_phase(phase_name: str) -> bool:
    return _norm_phase(phase_name) in FULLY_RETIRED_BRIEFING_PHASES


def post_spine_scheduling_suppressed(phase_name: str) -> bool:
    """When assembly is not legacy, suppress retired full-scan / narrative phases.

    Fully retired briefing phases are always suppressed (including legacy mode).
    """
    p = _norm_phase(phase_name)
    if p in FULLY_RETIRED_BRIEFING_PHASES:
        return True
    if assembly_pipeline_mode() == "legacy":
        return False
    return p in POST_SPINE_RETIRED_PHASES

def assembly_phases_for_nightly_suffix() -> tuple[str, ...]:
    """Canonical post-spine tail for nightly sequential drain."""
    return POST_SPINE_PHASE_ORDER + ("mention_resolution", "entity_profile_sync")
