"""
Phase constants and config extracted from automation_manager.py.

Contains scheduling constants, pipeline step ordering, time budgets, and env-based
configuration knobs.  Re-exported by services.automation.__init__ and kept in
automation_manager.py for backward compatibility.  New code should import directly
from this module when possible.
"""

from __future__ import annotations

import os

# Phases that stay continuously queued (never auto-evicted from queue).
BATCH_PHASES_CONTINUOUS = {
    "content_enrichment",
    "ml_processing",
    "entity_extraction",
    "sentiment_analysis",
    "quality_scoring",
    "storyline_processing",
    "rag_enhancement",
    "storyline_automation",
    "entity_profile_build",
    "timeline_generation",
    "topic_clustering",
    "event_extraction",
    "content_refinement_queue",
    # Severe backlog drains - without continuous requeue these starve behind claim_extraction
    "story_enhancement",
    "storyline_discovery",
    "storyline_assembly",
    # Scientific paper pathway - pick up as soon as CPU slots free (not interval flip)
    "research_paper_profiling",
    "claim_evidence_appraisal",
}

# When these phases have pending >= AUTOMATION_BACKLOG_SEVERE_THRESHOLD, claim_extraction
# yields workers (cap 1 + longer cooldown) so spine work can run.
SEVERE_BACKLOG_PEER_PHASES = frozenset(
    {
        "story_enhancement",
        "entity_profile_build",
        "metadata_enrichment",
        "entity_dossier_compile",
        "storyline_discovery",
        "storyline_assembly",
    }
)


# Estimated duration in seconds per phase (single place to tune).
PHASE_ESTIMATED_DURATION_SECONDS: dict[str, int] = {
    "rss_processing": 120,
    "ml_processing": 240,
    "topic_clustering": 400,  # observed ~396s avg when backlog; was 180
    "entity_extraction": 260,  # observed ~257s avg; was 120
    "quality_scoring": 90,
    "sentiment_analysis": 120,
    "storyline_processing": 300,
    "rag_enhancement": 600,
    "event_extraction": 300,
    "event_deduplication": 120,
    "story_continuation": 300,
    "timeline_generation": 300,
    "cache_cleanup": 60,
    "digest_generation": 180,
    "watchlist_alerts": 60,
    "data_cleanup": 300,
    "health_check": 10,
    "pending_db_flush": 30,
    "context_sync": 60,  # ~5-10s per 100 contexts (production batch)
    "entity_profile_sync": 225,  # observed ~223s avg; was 120
    "claim_extraction": 600,  # env CLAIM_EXTRACTION_BATCH_LIMIT x CLAIM_EXTRACTION_PARALLEL (LLM-bound)
    "legislative_references": 120,  # Congress.gov HTTP + rate-limit sleep per bill mention
    "claims_to_facts": 180,  # env CLAIMS_TO_FACTS_BATCH_LIMIT; resolver + INSERTs (DB-bound)
    "claim_subject_gap_refresh": 120,  # catalog upsert per active domain (DB-bound)
    "extracted_claims_dedupe": 180,  # batched DELETE; see EXTRACTED_CLAIMS_DEDUPE_* env
    "event_tracking": 200,  # observed ~196s avg; was 120
    "event_coherence_review": 180,
    "investigation_report_refresh": 300,
    "entity_profile_build": 600,
    "pattern_recognition": 120,
    "embeddings_worker": 600,
    "macro_series_refresh": 300,
    "external_events_sync": 240,
    "sanctions_refresh": 180,
    "quiver_collector": 300,  # Quiver Quant API -> congress/gov/lobby/insider tables
    "arc_report_generation": 900,
    "longitudinal_matview_refresh": 60,
    "storyline_automation": 180,
    "storyline_enrichment": 600,  # full-history pass: ~10 min
    "story_enhancement": 300,
    "entity_enrichment": 180,
    "pattern_matching": 90,
    "cross_domain_synthesis": 120,
    "entity_organizer": 600,  # observed can be 5-90 min under load; was 180
    "graph_connection_distillation": 90,  # pending proposals batch + DB merges / link inserts
    "entity_dossier_compile": 90,  # compile entity dossiers (no LLM), ~2-5s per dossier
    "entity_position_tracker": 300,  # LLM position extraction per entity, ~30-60s per entity
    "metadata_enrichment": 90,  # language/categories/sentiment/quality per domain batch
    "research_topic_refinement": 60,  # pick one topic, submit to finance orchestrator (idle-only)
    "editorial_document_generation": 300,  # LLM-generate/refine editorial_document on storylines
    "editorial_briefing_generation": 300,  # LLM-generate/refine editorial_briefing on tracked_events
    # Content enrichment, document pipeline, synthesis-related phases
    "content_enrichment": 120,  # trafilatura fetch per article, rate-limited
    "document_processing": 180,  # observed ~152s when small batch; was 600
    "research_paper_profiling": 300,  # LLM research axes per paper
    "claim_evidence_appraisal": 300,  # literature evidence grades -> subject memory
    "storyline_synthesis": 600,  # deep content synthesis per storyline
    "daily_briefing_synthesis": 300,  # breaking news synthesis per domain
    "storyline_discovery": 3600,  # Full-backlog discovery (capped) + embeddings + LLM per domain
    # v8: collect-then-analyze - single master task runs RSS + enrichment + docs
    "collection_cycle": 1800,  # 30 min; RSS + drain enrichment + doc collection + drain doc processing + pending queue
    "proactive_detection": 300,  # v8: emerging storylines per domain
    "storyline_assembly": 900,  # proactive + discovery + automation per domain
    "fact_verification": 120,  # v8: verify_recent_claims per domain
    "content_refinement_queue": 420,  # storyline RAG / timeline narrative / ~70B finisher (queued user jobs)
    "storyline_review_agent": 300,  # LLM review of pending article suggestions
    "nightly_enrichment_context": 21600,  # 02:00-07:00 local unified pipeline (NIGHTLY_PIPELINE_*); exits when idle
}


# Analysis pipeline - collect-then-analyze, single master task runs RSS + enrichment + docs.
ANALYSIS_PIPELINE_STEPS: tuple[tuple[str, ...], ...] = (
    # Step 0: Foundation
    (
        "nightly_enrichment_context",
        "context_sync",
        "entity_profile_sync",
        "ml_processing",
        "entity_extraction",
        "metadata_enrichment",
    ),
    # Step 1: Extraction (events elevated to foundational level)
    (
        "claim_extraction",
        "legislative_references",
        "claims_to_facts",
        "claim_subject_gap_refresh",
        "extracted_claims_dedupe",
        "event_extraction",  # Moved from Step 3 - events are foundational
        "event_tracking",
        "topic_clustering",
        "quality_scoring",
        "sentiment_analysis",
        "fact_verification",  # Moved from Step 2 - verify before synthesis
    ),
    # Step 2: Intelligence
    (
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
    ),
    # Step 3: Output (remaining time until next collection)
    (
        "storyline_processing",
        "rag_enhancement",
        "storyline_automation",
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
        "cache_cleanup",
        "data_cleanup",
    ),
)

STEP_TIME_BUDGETS: tuple[int | None, ...] = (
    1800,
    1200,
    1200,
    None,  # step 3 - no limit
)  # seconds; None = no limit


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    """Parse int env var with safe fallback and floor."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return max(minimum, int(raw))
    except (TypeError, ValueError):
        return default


# Cap concurrent Ollama/GPU tasks. Scale up when you have GPU/CPU headroom.
MAX_CONCURRENT_OLLAMA_TASKS = _env_int("MAX_CONCURRENT_OLLAMA_TASKS", 6)
AUTOMATION_MAX_CONCURRENT_TASKS = _env_int("AUTOMATION_MAX_CONCURRENT_TASKS", 12)
AUTOMATION_EXECUTOR_MAX_WORKERS = _env_int("AUTOMATION_EXECUTOR_MAX_WORKERS", 6)

# Seconds between scheduler ticks; min cooldown between re-enqueue of same phase when backlog exists.
WORKLOAD_MIN_COOLDOWN = max(1, int(os.environ.get("AUTOMATION_WORKLOAD_MIN_COOLDOWN_SECONDS", "10")))
AUTOMATION_SCHEDULER_TICK_SECONDS = max(1, int(os.environ.get("AUTOMATION_SCHEDULER_TICK_SECONDS", "5")))

# When true (default), skip dynamic_resource_service +/-1 scaling; floor max_concurrent_tasks with env below.
_AUTOMATION_DISABLE_DYNAMIC_TASK_SCALING = os.environ.get(
    "AUTOMATION_DISABLE_DYNAMIC_TASK_SCALING", "true"
).lower() in ("1", "true", "yes")

# Collection-cycle watchdog: 60 min after cycle starts, check if any phase should be added to the queue.
WATCHDOG_SECONDS = int(os.environ.get("COLLECTION_PHASE_WATCHDOG_SECONDS", "3600"))
