"""Centralized batch size constants, pending-count keys, and backlog thresholds.

All callers should import from this module or re-export through ``backlog_metrics``.
The canonical source is **this** file — never duplicate these values in a new module.

Key groups
----------
* ``BATCH_SIZE_PER_TASK`` – per-phase row-batch limits (used by Monitor / workload balancer)
* ``DEFAULT_BATCH_SUBTRACT`` – fallback batch size for unknown phases (env: BACKLOG_METRICS_DEFAULT_BATCH_SIZE)
* ``NO_BACKLOG_BATCH_SUBTRACT_PHASES`` – phases where backlog = pending (not row-batched)
* ``RAW_PENDING_COUNT_KEYS`` – keys fed into ``_get_raw_pending_counts``
* ``BACKLOG_HIGH_THRESHOLD`` / ``BACKLOG_MODE_INTERVAL`` / ``BACKLOG_ANY_INTERVAL`` – scheduler thresholds
"""

from __future__ import annotations

# ── Batch size per phase ──────────────────────────────────────────────────────
# How many items each task processes per run. Pending counts at or below this
# are normal throughput, not a backlog.  Anything above triggers backlog mode.
BATCH_SIZE_PER_TASK: dict[str, int] = {
    "content_enrichment": 60,
    "context_sync": 100,
    "event_tracking": 300,
    "claim_extraction": 50,
    "entity_profile_build": 25,  # v8
    "investigation_report_refresh": 8,
    "document_processing": 10,
    "content_refinement_queue": 4,
    # Unified nightly phase: enrichment + context_sync + refinement queue
    "nightly_enrichment_context": 0,
    # Per-run throughput (automation_manager batch limits × domain count where applicable)
    "metadata_enrichment": 15,  # order-of-magnitude per domain batch
    "ml_processing": 150,  # 50 × 3 schemas
    "entity_extraction": 60,  # 20 × 3
    "sentiment_analysis": 300,  # 100 × 3
    "quality_scoring": 150,  # 50 × 3
    "storyline_processing": 24,  # ~8 storylines worth of summary work per full pass
    "topic_clustering": 60,  # ~20 × 3 standard domains (approximates automation)
    "timeline_generation": 36,  # 12 × 3
    "storyline_discovery": 50,  # unlinked-in-newest-N proxy (see _count_storyline_discovery_pending)
    "proactive_detection": 1000,  # proactive candidate pool cap per domain
    "storyline_automation": 5,  # automation_manager LIMIT storylines per domain per tick
    "rag_enhancement": 9,  # few storylines enhanced per tick per domain
    "event_extraction": 90,  # 30 × 3
    "claims_to_facts": 10_000,  # overridden by get_claims_to_facts_batch_limit() when available
    "legislative_references": 8,  # articles scanned per domain per run (Congress.gov rate limits)
    "entity_profile_sync": 40,  # canonical rows mapped per domain batch (approx)
    "entity_enrichment": 20,  # run_enrichment_batch limit
    "entity_dossier_compile": 20,  # _run_scheduled_dossier_compiles max per run
    "story_enhancement": 50,  # fact_change_log + story_update_queue proxy per cycle
    "storyline_synthesis": 16,  # ~4 storylines × active domains per _execute_storyline_synthesis tick
    "graph_connection_distillation": 12,  # GRAPH_CONNECTION_DISTILLATION_BATCH proposals per run
    "pending_db_flush": 200,  # rough lines replayed per successful flush (order-of-magnitude)
    "extracted_claims_dedupe": 500,  # dedupe batch size order-of-magnitude
    "event_deduplication": 100,  # EventDeduplicationService.deduplicate_recent default
    "story_continuation": 90,  # ~30 events × active schemas
    "event_coherence_review": 5,  # LLM-heavy; few events per tick
    "research_paper_profiling": 2,  # trickle batch when pending ≫ threshold (see research_paper_profile_service)
    "claim_evidence_appraisal": 5,  # CLAIM_EVIDENCE_APPRAISAL_BATCH default
}

# ── Defaults / fallbacks ──────────────────────────────────────────────────────

DEFAULT_BATCH_SUBTRACT = int(
    __import__("os").environ.get("BACKLOG_METRICS_DEFAULT_BATCH_SIZE", "1"),
) or 1


# ── No-backlog phases (backlog == pending) ────────────────────────────────────

NO_BACKLOG_BATCH_SUBTRACT_PHASES = frozenset({"nightly_enrichment_context"})

# ── Pending-count keys (must match _get_raw_pending_counts) ───────────────────

RAW_PENDING_COUNT_KEYS: frozenset[str] = frozenset({
    "content_enrichment",
    "context_sync",
    "event_tracking",
    "claim_extraction",
    "entity_profile_build",
    "investigation_report_refresh",
    "document_processing",
    "pending_db_flush",
    "content_refinement_queue",
    "metadata_enrichment",
    "ml_processing",
    "entity_extraction",
    "sentiment_analysis",
    "quality_scoring",
    "storyline_processing",
    "topic_clustering",
    "timeline_generation",
    "storyline_discovery",
    "proactive_detection",
    "storyline_assembly",
    "rag_enhancement",
    "event_extraction",
    "storyline_automation",
    "claims_to_facts",
    "legislative_references",
    "entity_profile_sync",
    "entity_enrichment",
    "entity_dossier_compile",
    "story_enhancement",
    "storyline_synthesis",
    "graph_connection_distillation",
    "event_deduplication",
    "extracted_claims_dedupe",
    "story_continuation",
    "event_coherence_review",
})

# ── Backlog scheduler thresholds ──────────────────────────────────────────────

# When backlog exceeds this, use backlog-mode interval so we run more often
BACKLOG_HIGH_THRESHOLD = 200
# Effective min interval (seconds) when in backlog mode (high backlog)
BACKLOG_MODE_INTERVAL = 300
# When any backlog > 0, use this so we don't wait full interval between runs
BACKLOG_ANY_INTERVAL = 30
