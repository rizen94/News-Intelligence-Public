"""
Hard-coded pipeline resource policy — host lane + batch defaults.

``Host.POPOS_GPU`` / ``POPOS_HEAVY`` mean **prefer PopOS execution** (Ollama on .99 and/or
the PopOS phase worker). They are **not** process placement by themselves — Widow
AutomationManager still runs a phase unless ``REMOTE_PHASE_WORKER_OWNED_PHASES`` disables it
and ``scripts/run_popos_phase_worker.py`` claims the work.

Design:
- **bulk** tier: intake path; UIE preferably on PopOS worker + local 5090 Ollama
- **refinement** tier: narrative/RAG/products — nightly window only unless bulk queue is clear
- **widow_db**: DB/HTTP only on Widow (orchestrator host)
- **widow_fetch**: trafilatura / RSS / document fetch on Widow

Steady-state unified intake LLM batch default is **6** articles per call (``UNIFIED_INTAKE_EXTRACTION_BATCH_SIZE``;
see ``config.runtime.unified_intake_extraction_batch_size()``). Raise ``UNIFIED_INTAKE_EXTRACTION_*``
on the **PopOS worker** env, not on the Widow API.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from config.runtime import env_bool, env_set, env_setdefault, env_str

logger = __import__("logging").getLogger(__name__)


class Host(str, Enum):
    POPOS_GPU = "popos_gpu"
    POPOS_HEAVY = "popos_heavy"  # 70B narrative finisher
    WIDOW_CPU = "widow_cpu"
    WIDOW_DB = "widow_db"
    WIDOW_FETCH = "widow_fetch"


class Tier(str, Enum):
    BULK = "bulk"
    REFINEMENT = "refinement"


@dataclass(frozen=True)
class PhasePolicy:
    host: Host
    tier: Tier
    execution_lane: str  # gpu | cpu for LLM caller
    resource_class: str  # gpu_heavy | db_heavy | cpu_light
    requires_llm: bool = False
    batched_llm: bool = False
    default_batch: int | None = None
    default_parallel: int | None = None
    run_budget_seconds: int = 900


# --- Phase registry (automation_manager task names) ---
PHASE_POLICIES: dict[str, PhasePolicy] = {
    # Tier 0 — ingest (Widow)
    "collection_cycle": PhasePolicy(Host.WIDOW_FETCH, Tier.BULK, "cpu", "db_heavy"),
    "content_enrichment": PhasePolicy(
        Host.WIDOW_FETCH, Tier.BULK, "cpu", "db_heavy", default_batch=60
    ),
    "document_processing": PhasePolicy(
        Host.WIDOW_FETCH, Tier.BULK, "cpu", "db_heavy", default_batch=10
    ),
    "rss_processing": PhasePolicy(Host.WIDOW_FETCH, Tier.BULK, "cpu", "cpu_light"),
    # Tier 1 — foundation bulk
    "context_sync": PhasePolicy(Host.WIDOW_DB, Tier.BULK, "cpu", "db_heavy", default_batch=100),
    "entity_profile_sync": PhasePolicy(Host.WIDOW_DB, Tier.BULK, "cpu", "db_heavy", default_batch=40),
    "metadata_enrichment": PhasePolicy(
        Host.WIDOW_CPU, Tier.BULK, "cpu", "cpu_light", requires_llm=True, default_batch=15
    ),
    "ml_processing": PhasePolicy(
        Host.POPOS_GPU,
        Tier.BULK,
        "gpu",
        "gpu_heavy",
        requires_llm=True,
        batched_llm=True,
        default_batch=50,
        default_parallel=4,
        run_budget_seconds=900,
    ),
    "entity_extraction": PhasePolicy(
        Host.POPOS_GPU,
        Tier.BULK,
        "gpu",
        "gpu_heavy",
        requires_llm=True,
        batched_llm=True,
        default_batch=40,
        default_parallel=6,
        run_budget_seconds=900,
    ),
    "unified_intake_extraction": PhasePolicy(
        Host.POPOS_GPU,
        Tier.BULK,
        "gpu",
        "gpu_heavy",
        requires_llm=True,
        batched_llm=True,
        default_batch=6,
        default_parallel=8,
        run_budget_seconds=900,
    ),
    "embeddings_worker": PhasePolicy(Host.WIDOW_CPU, Tier.BULK, "cpu", "db_heavy", default_batch=200),
    # Tier 2 — extraction bulk (PopOS GPU)
    "claim_extraction": PhasePolicy(
        Host.POPOS_GPU,
        Tier.BULK,
        "gpu",
        "gpu_heavy",
        requires_llm=True,
        batched_llm=True,
        default_batch=400,
        default_parallel=4,
        run_budget_seconds=900,
    ),
    "legislative_references": PhasePolicy(
        Host.WIDOW_CPU, Tier.BULK, "cpu", "cpu_light", default_batch=8
    ),
    "claims_to_facts": PhasePolicy(
        Host.WIDOW_DB, Tier.BULK, "cpu", "db_heavy", default_batch=200, run_budget_seconds=900
    ),
    "claim_evidence_appraisal": PhasePolicy(
        Host.POPOS_GPU,
        Tier.REFINEMENT,
        "gpu",
        "gpu_heavy",
        requires_llm=True,
        batched_llm=True,
        default_batch=8,
        default_parallel=2,
        run_budget_seconds=900,
    ),
    "claim_subject_gap_refresh": PhasePolicy(Host.WIDOW_DB, Tier.BULK, "cpu", "db_heavy"),
    "extracted_claims_dedupe": PhasePolicy(Host.WIDOW_DB, Tier.BULK, "cpu", "db_heavy"),
    "event_extraction": PhasePolicy(
        Host.POPOS_GPU,
        Tier.BULK,
        "gpu",
        "db_heavy",
        requires_llm=True,
        batched_llm=True,
        default_batch=30,
        default_parallel=3,
        run_budget_seconds=900,
    ),
    "event_tracking": PhasePolicy(Host.WIDOW_DB, Tier.BULK, "cpu", "db_heavy", default_batch=300),
    "topic_clustering": PhasePolicy(
        Host.POPOS_GPU,
        Tier.BULK,
        "gpu",
        "db_heavy",
        requires_llm=True,
        batched_llm=True,
        default_batch=20,
        default_parallel=4,
    ),
    "quality_scoring": PhasePolicy(
        Host.WIDOW_CPU,
        Tier.BULK,
        "cpu",
        "db_heavy",
        requires_llm=True,
        batched_llm=True,
        default_batch=50,
        default_parallel=4,
        run_budget_seconds=900,
    ),
    "sentiment_analysis": PhasePolicy(
        Host.POPOS_GPU,
        Tier.BULK,
        "gpu",
        "db_heavy",
        requires_llm=True,
        batched_llm=True,
        default_batch=100,
        default_parallel=4,
        run_budget_seconds=900,
    ),
    "fact_verification": PhasePolicy(
        Host.POPOS_GPU, Tier.BULK, "gpu", "gpu_heavy", requires_llm=True, default_batch=20
    ),
    "event_deduplication": PhasePolicy(Host.WIDOW_DB, Tier.BULK, "cpu", "db_heavy"),
    "story_continuation": PhasePolicy(Host.WIDOW_DB, Tier.BULK, "cpu", "db_heavy"),
  # Tier 3 — intelligence (bulk structure, defer heavy narrative)
    "entity_profile_build": PhasePolicy(
        # Widow local 8B: PopOS GPU frequently preempts profile batches (503 interactive),
        # which collapses throughput on the largest backlog phase.
        Host.WIDOW_CPU,
        Tier.BULK,
        "cpu",
        "gpu_heavy",
        requires_llm=True,
        default_batch=50,
        default_parallel=5,
        run_budget_seconds=900,
    ),
    "entity_organizer": PhasePolicy(Host.WIDOW_DB, Tier.BULK, "cpu", "db_heavy"),
    "graph_connection_distillation": PhasePolicy(
        Host.WIDOW_DB, Tier.BULK, "cpu", "db_heavy", default_batch=50
    ),
    "pattern_recognition": PhasePolicy(
        Host.POPOS_GPU, Tier.BULK, "gpu", "gpu_heavy", requires_llm=True
    ),
    "cross_domain_synthesis": PhasePolicy(
        Host.WIDOW_DB, Tier.BULK, "cpu", "db_heavy", default_batch=20
    ),
    "storyline_discovery": PhasePolicy(
        Host.POPOS_GPU, Tier.BULK, "gpu", "gpu_heavy", requires_llm=True, default_batch=50
    ),
    "proactive_detection": PhasePolicy(Host.WIDOW_DB, Tier.BULK, "cpu", "db_heavy", default_batch=100),
    "storyline_assembly": PhasePolicy(
        Host.POPOS_GPU, Tier.BULK, "gpu", "db_heavy", requires_llm=True, default_batch=20
    ),
    "event_coherence_review": PhasePolicy(
        Host.POPOS_GPU, Tier.BULK, "gpu", "gpu_heavy", requires_llm=True
    ),
    "entity_enrichment": PhasePolicy(Host.WIDOW_FETCH, Tier.BULK, "cpu", "cpu_light", default_batch=20),
    "investigation_report_refresh": PhasePolicy(
        Host.POPOS_GPU, Tier.REFINEMENT, "gpu", "gpu_heavy", requires_llm=True, default_batch=8
    ),
    "mention_resolution": PhasePolicy(
        Host.WIDOW_DB, Tier.BULK, "cpu", "db_heavy", default_batch=250, run_budget_seconds=1800
    ),
    # Refinement tier — end-of-pipeline only (nightly unless bulk clear)
    "story_enhancement": PhasePolicy(
        Host.POPOS_GPU, Tier.REFINEMENT, "gpu", "gpu_heavy", requires_llm=True
    ),
    "storyline_processing": PhasePolicy(
        Host.POPOS_GPU, Tier.REFINEMENT, "gpu", "gpu_heavy", requires_llm=True
    ),
    "rag_enhancement": PhasePolicy(
        Host.WIDOW_FETCH, Tier.REFINEMENT, "cpu", "cpu_light", default_batch=5
    ),
    "storyline_automation": PhasePolicy(
        Host.POPOS_GPU, Tier.REFINEMENT, "gpu", "gpu_heavy", requires_llm=True, default_batch=5
    ),
    "storyline_review_agent": PhasePolicy(
        Host.POPOS_GPU, Tier.REFINEMENT, "gpu", "gpu_heavy", requires_llm=True
    ),
    "storyline_membership_review": PhasePolicy(
        Host.WIDOW_DB, Tier.BULK, "cpu", "db_heavy", default_batch=100
    ),  # adaptive: min 100, uncapped (per-domain storyline pick + LLM mid-band)
    "storyline_hygiene": PhasePolicy(
        Host.WIDOW_DB, Tier.BULK, "cpu", "db_heavy", default_batch=25
    ),  # freeze→prune→near-dup merge; adaptive 10–60
    "embedding_link_candidates": PhasePolicy(
        Host.WIDOW_DB, Tier.BULK, "cpu", "db_heavy", default_batch=12
    ),
    "collision_sampling": PhasePolicy(
        Host.WIDOW_DB, Tier.BULK, "cpu", "db_heavy", default_batch=8
    ),
    "stimulus_rag": PhasePolicy(
        Host.WIDOW_FETCH, Tier.BULK, "cpu", "cpu_light", default_batch=3
    ),
    "protein_harden": PhasePolicy(
        Host.WIDOW_DB, Tier.BULK, "cpu", "db_heavy", default_batch=40
    ),
    "graph_link_drift_review": PhasePolicy(
        Host.WIDOW_DB, Tier.BULK, "cpu", "db_heavy", default_batch=40
    ),  # adaptive: 20–120 via adaptive_batch_policy
    "storyline_enrichment": PhasePolicy(
        Host.POPOS_HEAVY, Tier.REFINEMENT, "gpu", "gpu_heavy", requires_llm=True
    ),
    "entity_dossier_compile": PhasePolicy(
        Host.WIDOW_DB, Tier.BULK, "cpu", "db_heavy", default_batch=20
    ),  # fast compile Widow DB; narrative is separate refinement
    "entity_position_tracker": PhasePolicy(
        Host.POPOS_GPU, Tier.BULK, "gpu", "gpu_heavy", requires_llm=True
    ),
    "storyline_synthesis": PhasePolicy(
        Host.POPOS_HEAVY, Tier.REFINEMENT, "gpu", "gpu_heavy", requires_llm=True
    ),
    "daily_briefing_synthesis": PhasePolicy(
        Host.POPOS_HEAVY, Tier.REFINEMENT, "gpu", "gpu_heavy", requires_llm=True
    ),
    "digest_generation": PhasePolicy(
        Host.POPOS_GPU, Tier.REFINEMENT, "gpu", "gpu_heavy", requires_llm=True
    ),
    "narrative_thread_build": PhasePolicy(
        Host.POPOS_HEAVY, Tier.REFINEMENT, "gpu", "gpu_heavy", requires_llm=True
    ),
    "content_refinement_queue": PhasePolicy(
        Host.POPOS_HEAVY, Tier.REFINEMENT, "gpu", "gpu_heavy", requires_llm=True, default_batch=4
    ),
    "editorial_document_generation": PhasePolicy(
        Host.POPOS_HEAVY, Tier.REFINEMENT, "gpu", "gpu_heavy", requires_llm=True
    ),
    "editorial_briefing_generation": PhasePolicy(
        Host.POPOS_HEAVY, Tier.REFINEMENT, "gpu", "gpu_heavy", requires_llm=True
    ),
    "arc_report_generation": PhasePolicy(
        Host.POPOS_HEAVY, Tier.REFINEMENT, "gpu", "gpu_heavy", requires_llm=True
    ),
    "nightly_enrichment_context": PhasePolicy(
        Host.POPOS_HEAVY, Tier.REFINEMENT, "gpu", "gpu_heavy", requires_llm=True
    ),
    "watchlist_alerts": PhasePolicy(Host.WIDOW_CPU, Tier.BULK, "cpu", "db_heavy", requires_llm=True),
    "timeline_generation": PhasePolicy(
        Host.WIDOW_CPU, Tier.BULK, "cpu", "db_heavy", requires_llm=True, default_batch=12
    ),
    # v11 editorial modal drains — PopOS local Ollama (remote-owned when worker up).
    "editorial_research_pass": PhasePolicy(
        Host.POPOS_GPU,
        Tier.REFINEMENT,
        "gpu",
        "gpu_heavy",
        requires_llm=True,
        default_batch=5,
        run_budget_seconds=900,
    ),
    "editorial_narrative_pass": PhasePolicy(
        Host.POPOS_GPU,
        Tier.REFINEMENT,
        "gpu",
        "gpu_heavy",
        requires_llm=True,
        default_batch=5,
        run_budget_seconds=900,
    ),
    "editorial_reduction_pass": PhasePolicy(
        Host.POPOS_GPU,
        Tier.REFINEMENT,
        "gpu",
        "gpu_heavy",
        requires_llm=True,
        default_batch=5,
        run_budget_seconds=900,
    ),
    "chronological_events_catchup": PhasePolicy(
        Host.POPOS_GPU,
        Tier.BULK,
        "gpu",
        "gpu_heavy",
        requires_llm=True,
        default_batch=5,
        run_budget_seconds=600,
    ),
    # Maintenance
    "health_check": PhasePolicy(Host.WIDOW_DB, Tier.BULK, "cpu", "cpu_light"),
    "pending_db_flush": PhasePolicy(Host.WIDOW_DB, Tier.BULK, "cpu", "db_heavy"),
    "cache_cleanup": PhasePolicy(Host.WIDOW_DB, Tier.BULK, "cpu", "cpu_light"),
    "data_cleanup": PhasePolicy(Host.WIDOW_DB, Tier.BULK, "cpu", "db_heavy"),
    "macro_series_refresh": PhasePolicy(Host.WIDOW_FETCH, Tier.BULK, "cpu", "cpu_light"),
    "external_events_sync": PhasePolicy(Host.WIDOW_FETCH, Tier.BULK, "cpu", "cpu_light"),
    "sanctions_refresh": PhasePolicy(Host.WIDOW_FETCH, Tier.BULK, "cpu", "cpu_light"),
    "longitudinal_matview_refresh": PhasePolicy(Host.WIDOW_DB, Tier.BULK, "cpu", "db_heavy"),
    "pattern_matching": PhasePolicy(Host.WIDOW_DB, Tier.BULK, "cpu", "cpu_light"),
    "research_topic_refinement": PhasePolicy(
        Host.POPOS_GPU, Tier.REFINEMENT, "gpu", "gpu_heavy", requires_llm=True
    ),
}

_BULK_GATE_PHASES = frozenset(
    {
        "content_enrichment",
        "entity_extraction",
        "unified_intake_extraction",
        "event_extraction",
        "claim_extraction",
        "context_sync",
        "ml_processing",
    }
)

_LEGACY_INTAKE_EXTRACTION_PHASES = frozenset(
    {
        "entity_extraction",
        "event_extraction",
        "sentiment_analysis",
        "quality_scoring",
    }
)

# Scheduled phases largely superseded by unified_intake_extraction (still in codebase for rollback).
_UNIFIED_SUPERSEDED_AUTOMATION_PHASES = frozenset(
    {
        "ml_processing",
        "metadata_enrichment",
        "entity_extraction",
        "event_extraction",
        "sentiment_analysis",
        "quality_scoring",
    }
)

_EXTRACT_BACKLOG_PHASES = frozenset(
    {
        "entity_extraction",
        "event_extraction",
        "claim_extraction",
        "unified_intake_extraction",
    }
)

_POPOS_GPU_FALLBACK = "http://192.168.93.99:11434"


def get_phase_policy(phase_name: str) -> PhasePolicy | None:
    return PHASE_POLICIES.get(phase_name)


def phase_execution_lane(phase_name: str) -> str:
    p = get_phase_policy(phase_name)
    if p and p.requires_llm:
        return p.execution_lane
    return "cpu"


def phase_resource_class(phase_name: str) -> str:
    p = get_phase_policy(phase_name)
    if p:
        return p.resource_class
    return "cpu_light"


def cpu_structured_extraction_phases() -> frozenset[str]:
    """Phases pinned to Widow CPU (not PopOS GPU)."""
    return frozenset(
        name
        for name, p in PHASE_POLICIES.items()
        if p.requires_llm and p.execution_lane == "cpu" and p.host == Host.WIDOW_CPU
    )


def gpu_llm_phases() -> frozenset[str]:
    return frozenset(
        name for name, p in PHASE_POLICIES.items() if p.requires_llm and p.execution_lane == "gpu"
    )


def db_heavy_phases() -> frozenset[str]:
    return frozenset(
        name for name, p in PHASE_POLICIES.items() if p.resource_class == "db_heavy"
    )


def is_refinement_phase(phase_name: str) -> bool:
    p = get_phase_policy(phase_name)
    return p is not None and p.tier == Tier.REFINEMENT


def bulk_tier_pending_total(pending: dict[str, int] | None) -> int:
    p = pending or {}
    return sum(int(p.get(ph, 0) or 0) for ph in _BULK_GATE_PHASES)


def extract_bulk_pending_total(pending: dict[str, int] | None) -> int:
    p = pending or {}
    if intake_extraction_suppressed():
        return int(p.get("unified_intake_extraction", 0) or 0)
    return sum(int(p.get(ph, 0) or 0) for ph in _EXTRACT_BACKLOG_PHASES)


_BULK_EXTRACT_COMPETE_DEFER_PHASES = frozenset(
    {
        "topic_clustering",
        "timeline_generation",
        "cross_domain_synthesis",
        "pattern_recognition",
        "storyline_discovery",
        "storyline_assembly",
        "editorial_briefing_generation",
        "editorial_document_generation",
        "arc_report_generation",
        "storyline_synthesis",
        "daily_briefing_synthesis",
    }
)

# Spine-shaped intake / preprocess band (FIFO article order unchanged; phase priority).
# collection_cycle is last so downstream drains are preferred over flooding the inbox.
INTAKE_PREPROCESS_ORDER: tuple[str, ...] = (
    "content_enrichment",
    "unified_intake_extraction",
    "spine_sql_tail",
    "document_processing",
    "context_sync",
    "collection_cycle",
)
INTAKE_PREPROCESS_PHASES: frozenset[str] = frozenset(INTAKE_PREPROCESS_ORDER)

# Core queues that keep catchup in intake-first mode (sum vs clear threshold).
_INTAKE_PREPROCESS_CORE_PHASES: frozenset[str] = frozenset(
    {
        "content_enrichment",
        "unified_intake_extraction",
        "document_processing",
    }
)

# Narrow assembly/GPU peer defer while only UIE is hot (preprocess band otherwise clear).
_INTAKE_FIRST_GPU_DEFER_PHASES = frozenset(
    {
        "storyline_assembly",
        "storyline_automation",
        "entity_dossier_compile",
    }
)

# Never deferred by intake-preprocess gate (ops / drains that clear the spine,
# plus Widow-local structure drains that must not starve behind enrichment).
_INTAKE_PREPROCESS_DEFER_EXEMPT: frozenset[str] = frozenset(
    {
        *INTAKE_PREPROCESS_PHASES,
        "health_check",
        "pending_db_flush",
        "rss_feed_health",
        "mention_resolution",
        "entity_profile_build",
        "storyline_membership_review",
        "storyline_hygiene",
    }
)


def intake_preprocess_clear_threshold() -> int:
    """Pending sum on core preprocess phases above this → intake-first hard gate."""
    try:
        from shared.pipeline_admission import mode_intake_clear

        return mode_intake_clear()
    except Exception:
        pass
    try:
        from config.orchestrator_governance import get_orchestrator_governance_config

        cfg = get_orchestrator_governance_config().get("pipeline_controller") or {}
        if isinstance(cfg, dict):
            if cfg.get("intake_preprocess_clear_threshold") is not None:
                return max(1, int(cfg["intake_preprocess_clear_threshold"]))
            if cfg.get("catchup_clear_threshold") is not None:
                return max(1, int(cfg["catchup_clear_threshold"]))
    except Exception:
        pass
    try:
        return max(1, int(env_str("INTAKE_PREPROCESS_CLEAR_THRESHOLD", "50")))
    except ValueError:
        return 50


def intake_preprocess_pending(pending: dict[str, int] | None = None) -> int:
    """Sum of core spine preprocess queue depths (enrichment + UIE + documents)."""
    p = pending or {}
    return sum(int(p.get(ph, 0) or 0) for ph in _INTAKE_PREPROCESS_CORE_PHASES)


def intake_preprocess_hot(pending: dict[str, int] | None = None) -> bool:
    return intake_preprocess_pending(pending) > intake_preprocess_clear_threshold()


# Near-zero preprocess band → flip scheduling to post-process (structure) preferred.
# Includes claim_extraction + context_sync so "intake done" means ready for MR/EPB/GCD.
_PREPROCESS_STABLE_PHASES: frozenset[str] = frozenset(
    {
        "content_enrichment",
        "unified_intake_extraction",
        "document_processing",
        "claim_extraction",
        "context_sync",
    }
)


def preprocess_stable_threshold() -> int:
    """Max sum on preprocess-stable phases before post-process preferred can engage."""
    try:
        from shared.pipeline_admission import mode_preprocess_stable

        return mode_preprocess_stable()
    except Exception:
        pass
    try:
        return max(0, int(env_str("PREPROCESS_STABLE_THRESHOLD", "5")))
    except ValueError:
        return 5


def preprocess_stable_pending(pending: dict[str, int] | None = None) -> int:
    p = pending or {}
    return sum(int(p.get(ph, 0) or 0) for ph in _PREPROCESS_STABLE_PHASES)


def preprocess_stable(pending: dict[str, int] | None = None) -> bool:
    return preprocess_stable_pending(pending) <= preprocess_stable_threshold()


def post_process_preferred_enabled() -> bool:
    """Env kill-switch; default on so clear preprocess flips to structure drains."""
    return env_str("PIPELINE_POST_PROCESS_PREFERRED", "true").lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def intake_first_gpu_defer_threshold() -> int:
    try:
        from shared.pipeline_admission import mode_intake_clear

        return mode_intake_clear()
    except Exception:
        pass
    try:
        return max(0, int(env_str("INTAKE_FIRST_GPU_DEFER_THRESHOLD", "50")))
    except ValueError:
        return 50


def bulk_extract_compete_defer_phase(
    phase_name: str,
    pending: dict[str, int] | None = None,
) -> bool:
    """
    True when ``phase_name`` should not be scheduled because unified/claim extract
    backlog is high and this phase competes for workers or PopOS GPU.

    Spine-ordered path only (legacy extract>500 compete list removed).
    """
    p = pending or {}
    intake = int(p.get("unified_intake_extraction", 0) or 0)
    intake_thresh = intake_first_gpu_defer_threshold()

    try:
        from shared.spine_phase_order import spine_pipeline_ordered_active

        if not spine_pipeline_ordered_active():
            return False
    except Exception:
        return False

    # Hard gate: while core preprocess backlog is hot, defer all post-band work.
    if intake_preprocess_hot(p) and phase_name not in _INTAKE_PREPROCESS_DEFER_EXEMPT:
        return True
    # Prefer finishing unified intake before assembly/GPU peers burn PopOS slots.
    if (
        intake_thresh > 0
        and intake >= intake_thresh
        and phase_name in _INTAKE_FIRST_GPU_DEFER_PHASES
    ):
        return True
    return False


def legacy_intake_extraction_phases() -> frozenset[str]:
    return _LEGACY_INTAKE_EXTRACTION_PHASES


def unified_superseded_automation_phases() -> frozenset[str]:
    """Phases to skip scheduling when unified intake is active (overlap / worker contention)."""
    return _UNIFIED_SUPERSEDED_AUTOMATION_PHASES


def intake_extraction_suppressed() -> bool:
    """When true, automation schedules unified intake extract instead of legacy per-phase LLM."""
    from config.settings import legacy_intake_extraction_enabled, unified_intake_extraction_enabled

    if legacy_intake_extraction_enabled():
        return False
    return unified_intake_extraction_enabled()


def intake_phase_scheduled(phase_name: str) -> bool:
    """True when ``phase_name`` is the active intake extractor for Monitor / backlog counts."""
    phase = (phase_name or "").strip().lower().replace("-", "_")
    if phase == "unified_intake_extraction":
        return intake_extraction_suppressed()
    if phase in _LEGACY_INTAKE_EXTRACTION_PHASES:
        return not intake_extraction_suppressed()
    return True


def apply_intake_mode_pending_mask(counts: dict[str, int]) -> dict[str, int]:
    """
    Zero inactive intake phase counts so Monitor does not show unified backlog when
    legacy per-phase extract runs (and vice versa). ``extract_bulk_pending_total`` already
    picks the active mode; this keeps per-phase Monitor rows aligned with scheduling.
    Also zeros post-spine retired phases when assembly is not legacy.
    """
    out = dict(counts)
    if intake_extraction_suppressed():
        for phase in _LEGACY_INTAKE_EXTRACTION_PHASES:
            out[phase] = 0
        for phase in _UNIFIED_SUPERSEDED_AUTOMATION_PHASES:
            out[phase] = 0
    else:
        out["unified_intake_extraction"] = 0
    try:
        from shared.assembly_phase_order import (
            POST_SPINE_RETIRED_PHASES,
            assembly_pipeline_mode,
        )

        if assembly_pipeline_mode() != "legacy":
            for phase in POST_SPINE_RETIRED_PHASES:
                out[phase] = 0
    except Exception:
        pass
    return out


# Post-intake Band 1 — structure / new-material drains (before refinement filler).
STRUCTURE_BAND_PHASES: frozenset[str] = frozenset(
    {
        "mention_resolution",
        "entity_profile_build",
        "storyline_assembly",
        "storyline_automation",
        "storyline_review_agent",
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
    }
)


def structure_band_pending(pending: dict[str, int] | None = None) -> int:
    p = pending or {}
    return sum(int(p.get(ph, 0) or 0) for ph in STRUCTURE_BAND_PHASES)


def post_process_preferred(pending: dict[str, int] | None = None) -> bool:
    """True when preprocess is stable and structure-band backlog still needs churn."""
    if not post_process_preferred_enabled():
        return False
    return preprocess_stable(pending) and structure_band_pending(pending) > 0


# Pending sum used to decide when structure catchup is "hot" (defers refinement).
_STRUCTURE_CATCHUP_PENDING_PHASES: frozenset[str] = frozenset(
    {
        "mention_resolution",
        "entity_profile_build",
        "storyline_assembly",
        "storyline_automation",
        "storyline_review_agent",
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
    }
)

# Tier.REFINEMENT phases that still belong in the structure band (linking), not filler.
_STRUCTURE_BAND_REFINEMENT_EXEMPT: frozenset[str] = frozenset(
    {"storyline_automation", "storyline_review_agent"}
)

def structure_catchup_refinement_defer_threshold() -> int:
    """Defer Tier.REFINEMENT filler when structure pending sum is at/above this."""
    try:
        from shared.pipeline_admission import mode_structure_hot

        return mode_structure_hot()
    except Exception:
        pass
    try:
        return max(1, int(env_str("STRUCTURE_CATCHUP_REFINEMENT_DEFER_THRESHOLD", "200")))
    except ValueError:
        return 200


def structure_catchup_pending(pending: dict[str, int] | None = None) -> int:
    p = pending or {}
    return sum(int(p.get(ph, 0) or 0) for ph in _STRUCTURE_CATCHUP_PENDING_PHASES)


def structure_catchup_hot(pending: dict[str, int] | None = None) -> bool:
    return structure_catchup_pending(pending) >= structure_catchup_refinement_defer_threshold()


def structure_catchup_defers_refinement(
    phase_name: str,
    pending: dict[str, int] | None = None,
) -> bool:
    """True when refinement filler should wait for structure / new-material drains."""
    name = (phase_name or "").strip()
    if not name or name in _STRUCTURE_BAND_REFINEMENT_EXEMPT:
        return False
    if name in STRUCTURE_BAND_PHASES and not is_refinement_phase(name):
        return False
    if not is_refinement_phase(name):
        return False
    return structure_catchup_hot(pending)


def post_intake_work_band(phase_name: str) -> int:
    """1=structure/new-material, 2=bulk analysis peers, 3=refinement filler."""
    name = (phase_name or "").strip()
    if name in STRUCTURE_BAND_PHASES:
        return 1
    if is_refinement_phase(name):
        return 3
    return 2


def entity_profile_build_allowed(pending: dict[str, int] | None = None) -> bool:
    """Profile LLM build only when extract backlog is clear or nightly window."""
    try:
        from shared.spine_phase_order import spine_pipeline_ordered_active

        if spine_pipeline_ordered_active():
            return True
    except Exception:
        pass
    if env_str("ENTITY_PROFILE_BUILD_ANYTIME", "").lower() in ("1", "true", "yes"):
        return True
    try:
        from services.pipeline_schedule_service import popos_gpu_work_allowed

        if popos_gpu_work_allowed():
            return True
    except Exception:
        pass
    extract_left = extract_bulk_pending_total(pending)
    try:
        threshold = int(env_str("PIPELINE_REFINEMENT_BULK_CLEAR_THRESHOLD", "50"))
    except ValueError:
        threshold = 50
    return extract_left <= threshold


def refinement_phase_allowed(
    phase_name: str,
    pending: dict[str, int] | None = None,
) -> bool:
    """
    Refinement filler runs in nightly heavy window, when bulk intake is clear,
    and only when structure catchup is not hot (EPB / assembly / automation backlog).
    Override: PIPELINE_REFINEMENT_ANYTIME=true

    Durable ``content_refinement_queue`` jobs (UI / CONTENT_REFINEMENT_AUTO_ENQUEUE)
    are allowed whenever that queue has pending work — do not leave them blocked
    behind structure-band catchup forever.
    """
    if not is_refinement_phase(phase_name):
        return True
    if env_str("PIPELINE_REFINEMENT_ANYTIME", "").lower() in ("1", "true", "yes"):
        return True
    name = (phase_name or "").strip()
    if name == "content_refinement_queue":
        p = pending or {}
        if int(p.get("content_refinement_queue", 0) or 0) > 0:
            return True
    if phase_name == "entity_profile_build":
        try:
            from shared.spine_phase_order import spine_pipeline_ordered_active

            if spine_pipeline_ordered_active():
                return True
        except Exception:
            pass
    try:
        from services.pipeline_schedule_service import popos_gpu_work_allowed

        if popos_gpu_work_allowed():
            return True
    except Exception:
        pass
    # Between intakes: do not burn GPU/workers on narrative refinement while
    # structure / new-material drains still have meaningful backlog.
    if structure_catchup_defers_refinement(phase_name, pending):
        return False
    bulk_left = bulk_tier_pending_total(pending)
    try:
        threshold = int(env_str("PIPELINE_REFINEMENT_BULK_CLEAR_THRESHOLD", "50"))
    except ValueError:
        threshold = 50
    return bulk_left <= threshold


def story_enhancement_facts_only() -> bool:
    """During daytime bulk drain, process fact log only — no enrich/build LLM."""
    if env_str("STORY_ENHANCEMENT_FACTS_ONLY", "").lower() in ("0", "false", "no"):
        return False
    if env_str("STORY_ENHANCEMENT_FACTS_ONLY", "").lower() in ("1", "true", "yes"):
        return True
    try:
        from services.pipeline_schedule_service import popos_gpu_work_allowed

        return not popos_gpu_work_allowed()
    except Exception:
        return True


def _is_local_ollama_host(url: str, local: str) -> bool:
    """True when url points at this host's Ollama (localhost / 127.0.0.1 / OLLAMA_HOST)."""
    u = (url or "").strip().rstrip("/").lower()
    if not u:
        return True
    local_norm = local.rstrip("/").lower()
    return u in {
        local_norm,
        "http://127.0.0.1:11434",
        "http://localhost:11434",
    } or u.startswith(("http://127.0.0.1:", "http://localhost:"))


def _ensure_popos_gpu_host(pop: str, local: str) -> None:
    """When PopOS offload is enabled, never leave GPU lane on local Widow Ollama."""
    env_setdefault("AUTOMATION_USE_POPOS_GPU", "true")
    if not env_bool("AUTOMATION_USE_POPOS_GPU", True):
        return
    pop_norm = pop.rstrip("/")
    gpu = env_str("OLLAMA_GPU_HOST", "").strip()
    if _is_local_ollama_host(gpu, local):
        env_set("OLLAMA_GPU_HOST", pop_norm)
        env_setdefault("OLLAMA_POP_OS_HOST", pop_norm)
        logger.info("pipeline_resource_policy: OLLAMA_GPU_HOST -> %s (PopOS offload)", pop_norm)


def configure_pipeline_resources() -> None:
    """Apply hard-coded batch/parallel defaults and PopOS routing at process start.

    Widow does not run a local Ollama. All LLM HTTP targets PopOS (RTX 5090)
    unless this process is a PopOS phase worker (OLLAMA_HOST already local there).
    """
    pop = env_str("OLLAMA_POP_OS_HOST", "").strip() or _POPOS_GPU_FALLBACK
    local = env_str("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    # Widow must not target loopback Ollama (service is masked). Force PopOS.
    _loopback = local.lower().startswith(("http://127.0.0.1:", "http://localhost:"))
    if _loopback and pop:
        pop_norm = pop.rstrip("/")
        env_set("OLLAMA_HOST", pop_norm)
        env_set("OLLAMA_URL", pop_norm)
        env_set("OLLAMA_CPU_HOST", pop_norm)
        local = pop_norm
        logger.info(
            "pipeline_resource_policy: OLLAMA_HOST -> %s (Widow has no local Ollama)",
            pop_norm,
        )
    env_setdefault("OLLAMA_DUAL_HOST_ROUTING_ENABLED", "false")
    env_setdefault("OLLAMA_GPU_HOST", pop)
    env_setdefault("OLLAMA_CPU_HOST", local)
    _ensure_popos_gpu_host(pop, local)
    env_setdefault("OLLAMA_EXTRACTION_NUM_CTX", "8192")
    env_setdefault("AUTOMATION_USE_POPOS_GPU", "true")
    env_setdefault("AUTOMATION_DUAL_LANE", "false")
    # PopOS RTX 5090 is the sole Ollama host for Widow-orchestrated work.
    env_setdefault("AUTOMATION_GPU_PARALLEL", "2")
    env_setdefault("AUTOMATION_CPU_PARALLEL", "3")
    env_setdefault("OLLAMA_GPU_CONCURRENCY", "2")
    env_setdefault("AUTOMATION_FIXED_RESOURCE_POLICY", "true")
    env_setdefault("PIPELINE_REFINEMENT_BULK_CLEAR_THRESHOLD", "50")
    env_setdefault("STORY_ENHANCEMENT_FACTS_ONLY", "true")

    for name, policy in PHASE_POLICIES.items():
        if policy.default_batch is not None:
            key = f"{name.upper().replace('-', '_')}_BATCH_SIZE"
            env_setdefault(key, str(policy.default_batch))
        if policy.run_budget_seconds:
            env_setdefault(
                f"{name.upper().replace('-', '_')}_RUN_BUDGET_SECONDS",
                str(policy.run_budget_seconds),
            )

    env_setdefault("EVENT_EXTRACTION_BATCH_SIZE", "3")
    env_setdefault("ENTITY_EXTRACTION_BATCH_SIZE", "3")
    env_setdefault("ENTITY_EXTRACTION_ARTICLES_PER_DOMAIN", "40")
    env_setdefault("ENTITY_EXTRACTION_PARALLEL", "6")
    env_setdefault("EVENT_EXTRACTION_PARALLEL", "3")
    env_setdefault("EVENT_EXTRACTION_RUN_BUDGET_SECONDS", "0")
    env_setdefault("ENTITY_EXTRACTION_RUN_BUDGET_SECONDS", "0")
    env_setdefault("DOSSIER_CATCHUP_SKIP_NARRATIVE", "true")
    env_setdefault("UNIFIED_INTAKE_EXTRACTION_ENABLED", "true")
    env_setdefault("UNIFIED_INTAKE_LEGACY_AWARE_BACKLOG", "true")
    env_setdefault("UNIFIED_INTAKE_EXTRACTION_BATCH_SIZE", "6")
    env_setdefault("UNIFIED_INTAKE_EXTRACTION_PARALLEL", "8")
    env_setdefault("UNIFIED_INTAKE_EXTRACTION_RUN_BUDGET_SECONDS", "0")
    env_setdefault("GRAPH_CONNECTION_DISTILLATION_BATCH", "50")
    env_setdefault("ASSEMBLY_GRAPH_CONNECTION_DISTILLATION_CYCLE_BUDGET_SECONDS", "180")
    env_setdefault("FAST_NER_ENABLED", "true")
    env_setdefault("FAST_NER_BACKEND", "spacy")
    env_setdefault("ARTICLE_SIGNAL_FULL_MIN_QUALITY", "0.55")
    env_setdefault("INTAKE_FIRST_GPU_DEFER_THRESHOLD", "50")
    env_setdefault("PIPELINE_DRAIN_STALL_ROUNDS", "3")
    env_setdefault("AUTO_ENQUEUE_COMPREHENSIVE_RAG", "0")
    env_setdefault("STORYLINE_AUTO_ENQUEUE_NARRATIVE_FINISHER", "0")
    env_setdefault("CONTENT_REFINEMENT_API_ENQUEUE_ONLY", "true")
    # Prefer this flag to auto-enqueue comprehensive_rag (default off until ops validates).
    env_setdefault("CONTENT_REFINEMENT_AUTO_ENQUEUE", "false")
    env_setdefault("CONTENT_REFINEMENT_AUTO_ENQUEUE_MIN_ARTICLES", "3")
    env_setdefault("STORYLINE_ASSEMBLY_RUN_PROACTIVE", "false")
    env_setdefault("ASSEMBLY_PIPELINE_MODE", "ordered")
    env_setdefault("SPINE_PIPELINE_MODE", "ordered")
    env_setdefault("ARTICLE_SIGNAL_ENABLED", "true")
    env_setdefault("RSS_FEED_SILENCE_ENABLED", "true")
    env_setdefault("RSS_FEED_SILENCE_DRY_RUN", "false")
    env_setdefault("EDITORIAL_ROOM_LOOP_ENABLED", "true")
    env_setdefault("ENABLE_BROWSER_ENRICHMENT", "false")
    env_setdefault("ENABLE_WAYBACK_ENRICHMENT", "false")
    env_setdefault("ENABLE_ARCHIVETODAY_ENRICHMENT", "false")
    env_setdefault("ENTITY_STORE_FAST_PATH", "true")
    env_setdefault("RSS_INLINE_FULLTEXT_ENABLED", "false")
    env_setdefault("CONTENT_ENRICHMENT_FETCH_PARALLEL", "8")
    env_setdefault("CONTENT_ENRICHMENT_PER_HOST_LIMIT", "2")
    env_setdefault("PIPELINE_REPLAN_DEBOUNCE_SECONDS", "3")

    try:
        from shared.ollama_extraction_model_resolver import resolve_extraction_models_at_startup

        resolve_extraction_models_at_startup()
    except Exception as e:
        logger.warning("pipeline_resource_policy: extraction model resolve failed: %s", e)

    try:
        from shared.services.ollama_model_caller import reset_ollama_model_caller

        reset_ollama_model_caller()
    except Exception:
        pass

    logger.info(
        "pipeline_resource_policy: popos=%s gpu_host=%s extraction_model=%s bulk_phases=%s refinement_phases=%s",
        pop,
        env_str("OLLAMA_GPU_HOST", pop),
        env_str("OLLAMA_MODEL_EXTRACTION", ""),
        sum(1 for p in PHASE_POLICIES.values() if p.tier == Tier.BULK),
        sum(1 for p in PHASE_POLICIES.values() if p.tier == Tier.REFINEMENT),
    )
