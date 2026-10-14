"""
Ordered spine pipeline phases — enrich → fused intake → SQL tail.

Used by spine conductor, nightly drain prefix, and bulk catch-up.
"""

from __future__ import annotations

from config.runtime import env_str

# Work-completion order for article spine (4h SLA).
SPINE_PHASE_ORDER: tuple[str, ...] = (
    "content_enrichment",
    "unified_intake_extraction",
    "spine_sql_tail",
)

# Composite tail step (not a legacy automation schedule name).
SPINE_SQL_TAIL_PHASE = "spine_sql_tail"

# Phases superseded by fused intake for articles that cleared unified pass.
FUSED_SPINE_SUPERSEDED_PHASES: frozenset[str] = frozenset(
    {
        "entity_extraction",
        "event_extraction",
        "sentiment_analysis",
        "quality_scoring",
        "ml_processing",
        "metadata_enrichment",
    }
)

# claim_extraction only for gap-fill when fusion did not mark context.
FUSED_CLAIM_GAP_PHASE = "claim_extraction"


def spine_pipeline_mode() -> str:
    """ordered | shadow | legacy (workload-driven)."""
    raw = env_str("SPINE_PIPELINE_MODE", "ordered").strip().lower()
    if raw in ("ordered", "shadow", "legacy"):
        return raw
    return "ordered"


def spine_pipeline_ordered_active() -> bool:
    return spine_pipeline_mode() == "ordered"


def spine_pipeline_shadow_active() -> bool:
    return spine_pipeline_mode() == "shadow"


def intake_fusion_enabled() -> bool:
    if env_str("INTAKE_FUSION_ENABLED", "true").lower() in ("0", "false", "no"):
        return False
    from config.settings import unified_intake_extraction_enabled

    return unified_intake_extraction_enabled()


def fusion_any_of_dependencies(task_name: str) -> tuple[str, ...] | None:
    """
    When intake fusion is active, some dependents need ANY upstream (not ALL).
    Returns alternative dependency names or None for normal ALL-of logic.
    """
    if not intake_fusion_enabled():
        return None
    task = (task_name or "").strip().lower().replace("-", "_")
    if task == "claims_to_facts":
        return ("unified_intake_extraction", "claim_extraction", "spine_sql_tail")
    if task in ("extracted_claims_dedupe", "claim_subject_gap_refresh"):
        return ("claims_to_facts", "unified_intake_extraction")
    if task == "entity_profile_sync":
        return ("unified_intake_extraction", "context_sync", "spine_sql_tail")
    return None


def fused_claim_extraction_gap_fill_only() -> bool:
    """Steady-state: claim_extraction schedules only for contexts fusion missed."""
    return intake_fusion_enabled()


def spine_phases_for_nightly_prefix() -> tuple[str, ...]:
    """Replace legacy entity/ml prefix in nightly sequential drain."""
    base: tuple[str, ...] = SPINE_PHASE_ORDER + (
        "claim_extraction",
        "claims_to_facts",
        "event_tracking",
        "topic_clustering",
        "entity_profile_sync",
    )
    try:
        from shared.assembly_phase_order import assembly_pipeline_ordered_active

        if assembly_pipeline_ordered_active():
            return base
    except Exception:
        pass
    return base + ("entity_profile_build",)
