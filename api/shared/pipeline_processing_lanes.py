"""
Processing lanes (A→D) — scheduling SSOT for flat pipeline admission.

Documentation: ``docs/PIPELINE_PROCESSING_LANES.md``
"""

from __future__ import annotations

from api.config.runtime import env_bool, env_str

# Lane A — Spine SLA (today's news fully extracted)
LANE_A_PHASES: tuple[str, ...] = (
    "content_enrichment",
    "unified_intake_extraction",
    "spine_sql_tail",
    "document_processing",
    "context_sync",
)

# Lane B — Fresh structure (articles that cleared lane A)
LANE_B_PHASES: tuple[str, ...] = (
    "event_tracking",
    "mention_resolution",
    "entity_profile_build",
    "claim_extraction",
    "claims_to_facts",
    "extracted_claims_dedupe",
    "claim_subject_gap_refresh",
)

# Lane C — Incremental entity catalog sync (not whole-catalog mapping bursts)
LANE_C_PHASES: tuple[str, ...] = (
    "entity_profile_sync",
)

# Lane D — Debt & products (catch-up when lane A is stable)
LANE_D_PHASES: tuple[str, ...] = (
    "chronological_events_catchup",
    "event_deduplication",
    "story_enhancement",
    "research_paper_profiling",
    "claim_evidence_appraisal",
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
    "storyline_automation",
    "storyline_review_agent",
    "storyline_membership_review",
    "storyline_hygiene",
    "storyline_assembly",
    "topic_clustering",
    "content_refinement_queue",
    "episode_assembly_maintenance",
)

LANE_A_B_PRIORITY: tuple[str, ...] = LANE_A_PHASES + LANE_B_PHASES

FRESH_STRUCTURE_BAND_PHASES: frozenset[str] = frozenset(LANE_B_PHASES)

DEBT_PRODUCT_BAND_PHASES: frozenset[str] = frozenset((*LANE_C_PHASES, *LANE_D_PHASES))

STRUCTURE_BAND_PHASES: frozenset[str] = FRESH_STRUCTURE_BAND_PHASES | DEBT_PRODUCT_BAND_PHASES

# Ops phases that stay schedulable while lane A is hot.
_OPS_INTAKE_DEFER_EXEMPT: frozenset[str] = frozenset(
    {
        "health_check",
        "pending_db_flush",
        "rss_feed_health",
        "collection_cycle",
    }
)

# Lane A+B work may still run during intake-preprocess hot (spine + fresh structure).
_STRICT_INTAKE_DEFER_EXEMPT: frozenset[str] = frozenset(
    {
        *LANE_A_PHASES,
        *LANE_B_PHASES,
        *_OPS_INTAKE_DEFER_EXEMPT,
    }
)

# Legacy / catch-up: allow lane C+D drains while intake hot (pre–lane model behavior).
_RELAXED_INTAKE_DEFER_EXEMPT: frozenset[str] = frozenset(
    {
        *_STRICT_INTAKE_DEFER_EXEMPT,
        *LANE_C_PHASES,
        *LANE_D_PHASES,
        "storyline_hygiene",
    }
)


def intake_catchup_strict() -> bool:
    """When true (default), lane C+D do not compete with lane A while preprocess is hot."""
    return env_bool("INTAKE_CATCHUP_STRICT", True)


def intake_preprocess_defer_exempt_phases() -> frozenset[str]:
    return _STRICT_INTAKE_DEFER_EXEMPT if intake_catchup_strict() else _RELAXED_INTAKE_DEFER_EXEMPT


def lane_a_clear_threshold() -> int:
    try:
        from api.shared.pipeline_admission import mode_intake_clear

        return mode_intake_clear()
    except Exception:
        pass
    try:
        return max(1, int(env_str("INTAKE_PREPROCESS_CLEAR_THRESHOLD", "50")))
    except ValueError:
        return 50


def lane_a_pending(pending: dict[str, int] | None = None) -> int:
    p = pending or {}
    return sum(int(p.get(ph, 0) or 0) for ph in LANE_A_PHASES)


def lane_a_clear(pending: dict[str, int] | None = None) -> bool:
    return lane_a_pending(pending) <= lane_a_clear_threshold()


def fresh_structure_band_pending(pending: dict[str, int] | None = None) -> int:
    p = pending or {}
    return sum(int(p.get(ph, 0) or 0) for ph in FRESH_STRUCTURE_BAND_PHASES)


def debt_product_band_pending(pending: dict[str, int] | None = None) -> int:
    p = pending or {}
    return sum(int(p.get(ph, 0) or 0) for ph in DEBT_PRODUCT_BAND_PHASES)


def structure_band_pending(pending: dict[str, int] | None = None) -> int:
    return fresh_structure_band_pending(pending) + debt_product_band_pending(pending)


def structure_catchup_pending(pending: dict[str, int] | None = None) -> int:
    """Pending that should defer refinement — lane A while underwater; else fresh + debt."""
    p = pending or {}
    if not lane_a_clear(p):
        return lane_a_pending(p) + fresh_structure_band_pending(p)
    return fresh_structure_band_pending(p) + debt_product_band_pending(p)