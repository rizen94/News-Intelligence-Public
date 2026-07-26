"""
News Intelligence System v8.0 - Enterprise Automation Manager
Collect-then-analyze pipeline: collection_cycle, pipeline-ordered analysis (Foundation → Extraction → Intelligence → Output).

**Article batch order:** default **FIFO** (oldest rows first) via ``PIPELINE_ARTICLE_SELECTION_ORDER=fifo``.
Set ``lifo`` to restore newest-first selection. **Backfill:** ``PIPELINE_BACKFILL_MODE=true`` plus optional
``PIPELINE_BACKFILL_COLLECTION_RESUME_AT`` (or default 48h state file) pauses RSS + document discovery while
existing rows are processed.

Workload-driven scheduling: ``PipelineController`` enqueues phases when backlog counters show
pending work — not via cron, fixed intervals, or the retired 5s scheduler tick.

When ``AUTOMATION_QUEUE_SOFT_CAP`` > 0 and combined queue depth (scheduled + requested) reaches the cap,
new scheduled enqueues are skipped except phases in ``AUTOMATION_QUEUE_PAUSE_ALLOW``. Default **0** = disabled (no artificial queue-depth cap;
throughput is limited by ``AUTOMATION_MAX_CONCURRENT_TASKS``, ``MAX_CONCURRENT_OLLAMA_TASKS``, DB pools, and
PipelineController replan). Set a positive value only as a safety valve if the asyncio queue grows without bound.
**nightly_enrichment_context** is not allowlisted: one drain run is enough; it was previously allowlisted and
could stack hundreds of redundant queued sweeps while workers were busy.
**AUTOMATION_NIGHTLY_ENRICHMENT_MAX_QUEUED** caps scheduled+requested+running nightly tasks (default 1; 0=unlimited).
**AUTOMATION_MAX_SCHEDULED_DEPTH_PER_PHASE** caps scheduled asyncio-queue depth per phase (default 1; 0=unlimited) so workload-driven ticks cannot stack thousands of duplicate tasks; defer/retry bypass the cap.
With **CLAIM_EXTRACTION_DRAIN** (default on), **claim_extraction** also skips new scheduler/chain enqueues when running+queued depth already reaches the per-phase concurrent cap (``_should_skip_redundant_phase_request``), so context_sync completion cannot pile hundreds of duplicate tasks on ``_requested_task_queue``.
If a duplicate still reaches a worker under the cap, ``_discard_redundant_claim_extraction_when_at_cap`` completes it without re-queueing (per-phase defer used ``bypass_schedule_depth_cap`` and recycled the same backlog forever).
**AUTOMATION_PER_PHASE_CONCURRENT_CAP** caps how many workers may execute the same phase at once (default 2; 0=unlimited); **nightly_sequential_drain** bypasses; nightly window multiplies cap via **AUTOMATION_PER_PHASE_CONCURRENT_NIGHTLY_MULT** for catch-up when those phases are scheduled.
**AUTOMATION_DB_POOL_PRESSURE_GATE_ENABLED** (default true): while worker psycopg2 pool utilization ≥ **AUTOMATION_DB_WORKER_UTILIZATION_SKIP_THRESHOLD** (default 0.82), PipelineController may defer replans when the worker pool is hot. Manual Monitor phase requests still run (**requested_activity_id** bypasses deferral).

**Widow DB-adjacent sync (v10.1):** ``context_sync``, ``entity_profile_sync``, and ``pending_db_flush`` are scheduled by
``PipelineController`` when backlog counters show pending work — not via cron and not on fixed intervals when idle.
Do **not** list them in ``AUTOMATION_DISABLED_SCHEDULES``. Cron on Widow is only for idle-tx cleanup and weekly reconcile
(``infrastructure/widow-db-adjacent.cron``).
Widow only writes ``{domain}.articles``; there is no message queue. The **content_enrichment** scheduled task (plus the
enrichment loop inside ``collection_cycle``) drains pending rows from the DB so ingestion is not blocked when
``collection_cycle`` is throttled or skips RSS on the main host.
Dependency settle time after a phase completes is capped by AUTOMATION_DEPENDENCY_SETTLE_CAP_SEC (default 180s)
so long estimated_duration values (e.g. collection_cycle) do not block dependents such as storyline_discovery.

**Phase 2 spine-first (storyline audit):** demote ``proactive_detection``, standalone ``storyline_discovery``,
and ``narrative_thread_build`` via ``AUTOMATION_DISABLED_SCHEDULES``; scheduled bulk creation is
``storyline_assembly`` only. See ``docs/STORYLINE_CANONICAL_MODEL.md``.

Reader's guide:
  - For a **ordered map** of phases (v8 collect-then-analyze), start at
    ``docs/PIPELINE_AND_ORDER_OF_OPERATIONS.md``, then search this file for
    ``self.schedules`` (task name → interval, ``depends_on``, ``phase``).
  - Task execution branches on task name in the main scheduler loop (e.g.
    ``_execute_collection_cycle``); grep ``_execute_`` for implementations.
  - Governance overrides may come from ``api/config/orchestrator_governance.yaml``
    (analysis pipeline budgets, collection interval).
  - Scheduling semantics (``last_run``, lanes, parallel groups → queue): ``docs/AUTOMATION_MANAGER_SCHEDULING.md``.
"""

import asyncio
import itertools
import json
import logging
import os
import queue
import time
from pathlib import Path
from uuid import uuid4
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from psycopg2.extras import RealDictCursor

from shared.article_processing_gates import sql_ml_ready_and_content_bounds
from shared.pipeline_article_selection import (
    log_terminal_skip_stub_candidate,
    pipeline_article_selection_mode_report,
    pipeline_backfill_collection_should_pause,
    pipeline_backfill_status_line,
    sql_order_coalesce_pub_created,
    sql_order_created_at,
)
from shared.domain_registry import (
    get_pipeline_active_domain_keys,
    get_pipeline_schema_names_active,
    pipeline_url_schema_pairs,
    resolve_domain_schema,
    schema_to_primary_domain_key,
)


def _domains_for_phase(phase: str) -> list[str]:
    """Pipeline domains allowed to execute ``phase`` (corpus / research gate)."""
    from shared.domain_processing_mode import filter_domains_for_phase

    return filter_domains_for_phase(get_pipeline_active_domain_keys(), phase)


def _schemas_for_phase(phase: str) -> list[str]:
    """Schemas for domains allowed to execute ``phase``."""
    from shared.domain_processing_mode import domain_runs_phase

    return [
        sch
        for dk, sch in pipeline_url_schema_pairs()
        if domain_runs_phase(dk, phase)
    ]


# Configure logging
logger = logging.getLogger(__name__)

# Backlog-driven scheduling: skip empty cycles, run more often when backlog is high
try:
    from services.backlog_metrics import (
        BACKLOG_ANY_INTERVAL,
        BACKLOG_HIGH_THRESHOLD,
        BACKLOG_MODE_INTERVAL,
        SKIP_WHEN_EMPTY,
        get_all_backlog_counts,
        get_all_pending_counts,
    )
except ImportError:
    get_all_backlog_counts = None
    get_all_pending_counts = None
    SKIP_WHEN_EMPTY = frozenset()
    BACKLOG_HIGH_THRESHOLD = 200
    BACKLOG_MODE_INTERVAL = 300
    BACKLOG_ANY_INTERVAL = 30


# Persist each automation run to DB so "last 24h" is based on wall-clock time, not API restart
from shared.services.automation_run_history_writer import (
    persist_automation_run_history as _persist_automation_run,
)
from config.runtime import env_bool, env_float, env_int, env_pop, env_set, env_setdefault, env_str


# Legacy enrichment-backlog-first flag — removed in v8.1 (PipelineController owns sequencing).
_OLLAMA_AUTOMATION_PHASES_FULL = frozenset(
    {
        "topic_clustering",
        "ml_processing",
        "entity_extraction",
        "unified_intake_extraction",
        "sentiment_analysis",
        "storyline_processing",
        "rag_enhancement",
        "event_extraction",
        "event_deduplication",
        "story_continuation",
        "watchlist_alerts",
        "quality_scoring",
        "timeline_generation",
        "claim_extraction",
        "legislative_references",
        "event_tracking",
        "entity_profile_build",
        "entity_position_tracker",
        "editorial_document_generation",
        "editorial_briefing_generation",
        "story_enhancement",
        "content_refinement_queue",
        "nightly_enrichment_context",
        "storyline_synthesis",
        "storyline_review_agent",
        "storyline_membership_review",
        "embedding_link_candidates",
        "collision_sampling",
        "stimulus_rag",
        "protein_harden",
        "graph_link_drift_review",
        "daily_briefing_synthesis",
        "document_processing",
        "storyline_discovery",
        "proactive_detection",
        "storyline_assembly",
        "fact_verification",
        "narrative_thread_build",
        "event_coherence_review",
        "pattern_recognition",
        "investigation_report_refresh",
        "entity_enrichment",
        "storyline_enrichment",
    }
)


def _build_ollama_automation_phases() -> frozenset[str]:
    from shared.legacy_intake_rollback import legacy_intake_rollback_active
    from shared.pipeline_resource_policy import unified_superseded_automation_phases

    if legacy_intake_rollback_active():
        return _OLLAMA_AUTOMATION_PHASES_FULL
    return frozenset(_OLLAMA_AUTOMATION_PHASES_FULL - unified_superseded_automation_phases())


OLLAMA_AUTOMATION_PHASES = _build_ollama_automation_phases()
# Phases whose main LLM path uses Widow CPU (rate-limited HTTP / light models).
from shared.pipeline_resource_policy import cpu_structured_extraction_phases, db_heavy_phases as policy_db_heavy

STRUCTURED_LLM_CPU_LANE_PHASES = cpu_structured_extraction_phases()
# Default execution lane "gpu" for Ollama phases that are not structured-extraction-on-CPU above.
GPU_LANE_PHASES = frozenset(x for x in OLLAMA_AUTOMATION_PHASES if x not in STRUCTURED_LLM_CPU_LANE_PHASES)
DB_HEAVY_PHASES = policy_db_heavy()


def _env_bool(name: str, default: bool) -> bool:
    raw = env_str(name)
    if raw is None:
        return default
    return raw.lower() in ("1", "true", "yes", "on")


# Don't run collection_cycle when downstream pending exceeds this.
# Default sum: content_enrichment + context_sync + document_processing (minus COLLECTION_THROTTLE_EXCLUDE_PHASES).
# Optional: comma-separated phase names in COLLECTION_THROTTLE_EXTRA_PHASES (e.g. ml_processing,entity_extraction).
COLLECTION_THROTTLE_PENDING_THRESHOLD = int(
    env_str("COLLECTION_THROTTLE_PENDING_THRESHOLD", "1200")
)
_COLLECTION_THROTTLE_BASE = (
    "content_enrichment",
    "context_sync",
    "document_processing",
)


def _collection_throttle_pending_total(pending: dict[str, int] | None) -> tuple[int, dict[str, int]]:
    """Return (total, per-phase counts) used to gate collection_cycle when workload-driven."""
    p = pending or {}
    keys = list(_COLLECTION_THROTTLE_BASE)
    extra = env_str("COLLECTION_THROTTLE_EXTRA_PHASES", "").strip()
    if extra:
        for part in extra.split(","):
            k = part.strip()
            if k and k not in keys:
                keys.append(k)
    exclude_raw = env_str("COLLECTION_THROTTLE_EXCLUDE_PHASES", "document_processing")
    exclude = frozenset(x.strip() for x in exclude_raw.split(",") if x.strip())
    keys = [k for k in keys if k not in exclude]
    breakdown = {k: int(p.get(k, 0) or 0) for k in keys}
    return sum(breakdown.values()), breakdown


def collection_cycle_has_pending_work(
    pending_counts: dict[str, int] | None,
    *,
    pending_collection_queue_len: int = 0,
) -> bool:
    """
    True when collection_cycle has at least one sub-step with work.

    On hosts with AUTOMATION_SKIP_RSS_IN_COLLECTION_CYCLE, skip the whole cycle when
    enrichment, document processing, and the pending URL queue are all empty.
    """
    p = pending_counts or {}
    if int(p.get("content_enrichment") or 0) > 0:
        return True
    if int(p.get("document_processing") or 0) > 0:
        return True
    if int(pending_collection_queue_len or 0) > 0:
        return True
    try:
        from shared.pipeline_article_selection import pipeline_backfill_collection_should_pause

        if pipeline_backfill_collection_should_pause():
            return False
    except Exception:
        pass
    skip_rss = env_str("AUTOMATION_SKIP_RSS_IN_COLLECTION_CYCLE", "").lower() in (
        "1",
        "true",
        "yes",
    )
    if not skip_rss:
        return True
    return False


# When combined queue depth (main + requested) >= this, stop enqueueing scheduled work except allowlist.
# 0 = disabled (recommended). Use workers + Ollama semaphores + DB pool for real limits.
AUTOMATION_QUEUE_SOFT_CAP = env_int("AUTOMATION_QUEUE_SOFT_CAP", 0)
QUEUE_PAUSE_ALLOW_SCHEDULED = frozenset(
    x.strip()
    for x in env_str(
        "AUTOMATION_QUEUE_PAUSE_ALLOW",
        "collection_cycle,content_enrichment,health_check,pending_db_flush,content_refinement_queue",
    ).split(",")
    if x.strip()
)
# Max nightly_enrichment_context tasks at once: running + scheduled queue + requested queue.
# Each run is a full unified drain; default 1 avoids stacked sweeps and duplicate Monitor activity lines. 0 = no cap.
AUTOMATION_NIGHTLY_ENRICHMENT_MAX_QUEUED = int(
    env_str("AUTOMATION_NIGHTLY_ENRICHMENT_MAX_QUEUED", "1")
)
# Per-phase cap on scheduled Task objects waiting in the asyncio queue. Workload-driven scheduling
# otherwise enqueues another run every cooldown while DB pending remains, even if prior copies are
# still queued — Monitor "Queued" explodes and wastes memory. Defer/retry paths pass
# bypass_schedule_depth_cap so yield/nightly/GPU gates and retries never drop work. 0 = unlimited (legacy).
AUTOMATION_MAX_SCHEDULED_DEPTH_PER_PHASE = int(
    env_str("AUTOMATION_MAX_SCHEDULED_DEPTH_PER_PHASE", "1")
)
# Max automation workers executing the same phase at once (regular / daytime). Spreads load across
# phases instead of N workers all running claim_extraction (or other LLM-heavy work). Tasks with
# metadata nightly_sequential_drain bypass. During unified nightly window, cap is multiplied by
# AUTOMATION_PER_PHASE_CONCURRENT_NIGHTLY_MULT (scheduled phases are usually exclusive anyway).
# 0 = unlimited (legacy).
AUTOMATION_PER_PHASE_CONCURRENT_CAP = int(
    env_str("AUTOMATION_PER_PHASE_CONCURRENT_CAP", "2")
)
DEFAULT_AUTOMATION_PER_PHASE_CONCURRENT_CAP_PHASES = frozenset(
    {
        "collection_cycle",  # hard guard: one ingest cycle (RSS/docs/queue) at a time
        "claim_extraction",
        "claims_to_facts",
        "event_extraction",
        "entity_extraction",
        "entity_profile_build",
        "event_tracking",
        "topic_clustering",
        "sentiment_analysis",
        "rag_enhancement",
        "storyline_synthesis",
        "storyline_processing",
        "content_refinement_queue",
        # Previously uncapped (exec_cap=0): too many same-phase workers → worker DB pool exhaustion
        "timeline_generation",
        "event_deduplication",
        "watchlist_alerts",
        "story_continuation",
        "ml_processing",
        "research_topic_refinement",
        "narrative_thread_build",
        "storyline_automation",
        "storyline_review_agent",
        "storyline_membership_review",
        "storyline_hygiene",
        "embedding_link_candidates",
        "collision_sampling",
        "stimulus_rag",
        "protein_harden",
        "graph_link_drift_review",
        "content_enrichment",
        "proactive_detection",
        "fact_verification",
        "cross_domain_synthesis",
        "digest_generation",
        "entity_dossier_compile",
        "entity_position_tracker",
        "storyline_discovery",
        "editorial_document_generation",
        "editorial_briefing_generation",
        "storyline_enrichment",
        "pattern_matching",
        "data_cleanup",
        "cache_cleanup",
        "quality_scoring",
        # Wikidata lazy-mint: parallel drains double 429s and race the CEM watermark.
        "mention_resolution",
    }
)

# Built-in per-phase caps (env AUTOMATION_PER_PHASE_CONCURRENT_CAP_OVERRIDES merges on top).
# collection_cycle stays at 1 even when the global cap is higher — avoid parallel RSS/doc sweeps.
DEFAULT_AUTOMATION_PER_PHASE_CONCURRENT_CAP_OVERRIDES: dict[str, int] = {
    "collection_cycle": 1,
    "mention_resolution": 2,
}


def _per_phase_concurrent_cap_phase_names() -> frozenset[str]:
    raw = env_str("AUTOMATION_PER_PHASE_CONCURRENT_CAP_PHASES", "").strip()
    if raw:
        return frozenset(x.strip() for x in raw.split(",") if x.strip())
    return DEFAULT_AUTOMATION_PER_PHASE_CONCURRENT_CAP_PHASES


def _per_phase_concurrent_cap_overrides() -> dict[str, int]:
    """
    Optional per-phase caps: AUTOMATION_PER_PHASE_CONCURRENT_CAP_OVERRIDES=claim_extraction:1,claims_to_facts:2
    Values are max concurrent workers for that phase (clamped to max_concurrent_tasks at use site). 0 = unlimited.
    Built-in defaults (e.g. collection_cycle:1) apply unless overridden by env.
    """
    out = dict(DEFAULT_AUTOMATION_PER_PHASE_CONCURRENT_CAP_OVERRIDES)
    raw = env_str("AUTOMATION_PER_PHASE_CONCURRENT_CAP_OVERRIDES", "").strip()
    if not raw:
        return out
    for part in raw.split(","):
        part = part.strip()
        if ":" not in part:
            continue
        name, val = part.split(":", 1)
        name = name.strip()
        if not name:
            continue
        try:
            out[name] = int(val.strip())
        except ValueError:
            continue
    return out


def _per_phase_nightly_cap_mult_exclude() -> frozenset[str]:
    """
    Phases that do not multiply AUTOMATION_PER_PHASE_CONCURRENT_CAP by
    AUTOMATION_PER_PHASE_CONCURRENT_NIGHTLY_MULT during the unified nightly window.

    Default excludes claim_extraction so nightly catch-up does not spawn e.g. 8× huge LLM batches
    that stall for hours and stack the asyncio queue. collection_cycle stays at 1 (no parallel cycles).
    """
    raw = env_str("AUTOMATION_PER_PHASE_NIGHTLY_MULT_EXCLUDE", "").strip()
    if raw:
        return frozenset(x.strip() for x in raw.split(",") if x.strip())
    return frozenset({"claim_extraction", "collection_cycle"})


# Ollama tasks normally yield when a non-polling browser request hit the API recently; storyline
# deep analysis must still run or the UI shows "processing" forever while users read those pages.
_OLLAMA_YIELD_EXEMPT = frozenset(
    x.strip()
    for x in env_str(
        "OLLAMA_YIELD_EXEMPT_TASKS",
        "content_refinement_queue",
    ).split(",")
    if x.strip()
)

# Cap how long we wait after a dependency completes before a dependent may run. Without this,
# collection_cycle's large estimated_duration (~1800s) kept dependents (e.g. storyline_discovery)
# permanently ineligible while collection runs often.
AUTOMATION_DEPENDENCY_SETTLE_CAP_SEC = env_int("AUTOMATION_DEPENDENCY_SETTLE_CAP_SEC", 180)

# Phases that constitute "data load"; when none have run recently, downtime loop runs entity organizer
DATA_LOAD_PHASES = (
    "collection_cycle",
    "content_enrichment",
    "entity_extraction",
)  # v8: collection_cycle + standalone enrichment (Widow RSS) feed the pipeline
DOWNTIME_IDLE_SECONDS = 300  # Consider "downtime" if no data-load phase ran in last 5 min
DOWNTIME_ORGANIZER_SLEEP = 45  # Seconds between organizer cycles during downtime
DOWNTIME_POLL_SLEEP = 30  # Seconds to sleep when data load is active (before rechecking)

# v8: Pipeline-ordered analysis (run after each collection_cycle)
# Events moved to Step 1 (Extraction) — foundational entities should feed intelligence phases
# Fact verification moved to Step 1 — verification precedes intelligence synthesis
_ANALYSIS_PIPELINE_STEPS_FULL: tuple[tuple[str, ...], ...] = (
    # Step 0: Foundation
    (
        "nightly_enrichment_context",
        "context_sync",
        "entity_profile_sync",
        "ml_processing",
        "entity_extraction",
        "unified_intake_extraction",
        "metadata_enrichment",
    ),
    # Step 1: Extraction (events elevated to foundational level)
    (
        "claim_extraction",
        "legislative_references",
        "claims_to_facts",
        "claim_subject_gap_refresh",
        "extracted_claims_dedupe",
        "event_extraction",  # Moved from Step 3 — events are foundational
        "event_tracking",
        "topic_clustering",
        "quality_scoring",
        "sentiment_analysis",
        "fact_verification",  # Moved from Step 2 — verify before synthesis
    ),
    # Step 2: Structure + chemistry beaker (loose bonds → stimuli → harden)
    (
        "entity_organizer",
        "graph_connection_distillation",
        "embedding_link_candidates",
        "collision_sampling",
        "stimulus_rag",
        "protein_harden",
        "cross_domain_synthesis",
        "storyline_assembly",
        "event_tracking",
        "story_continuation",
        "entity_enrichment",
        "entity_dossier_compile",
    ),
    # Step 3: Minimal output (narrative products retired; vault = editorial room)
    (
        "storyline_automation",
        "storyline_review_agent",
        "storyline_membership_review",
        "storyline_hygiene",
        "graph_link_drift_review",
        "event_deduplication",
        "mention_resolution",
        "content_refinement_queue",
        "watchlist_alerts",
        "cache_cleanup",
        "data_cleanup",
    ),
)


def _build_analysis_pipeline_steps() -> tuple[tuple[str, ...], ...]:
    from shared.legacy_intake_rollback import legacy_intake_rollback_active
    from shared.pipeline_resource_policy import unified_superseded_automation_phases

    if legacy_intake_rollback_active():
        return _ANALYSIS_PIPELINE_STEPS_FULL
    skip = unified_superseded_automation_phases()
    return tuple(
        tuple(p for p in step if p not in skip)
        for step in _ANALYSIS_PIPELINE_STEPS_FULL
        if any(p not in skip for p in step)
    )


ANALYSIS_PIPELINE_STEPS = _build_analysis_pipeline_steps()

def _env_int(name: str, default: int, minimum: int = 1) -> int:
    """Parse int env var with safe fallback and floor."""
    raw = env_str(name)
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


class TaskStatus(Enum):
    """Task execution status"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class TaskPriority(Enum):
    """Task priority levels"""

    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4


@dataclass
class Task:
    """Task definition"""

    id: str
    name: str
    priority: TaskPriority
    status: TaskStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    retry_count: int = 0
    max_retries: int = 3
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _phase_max_retries(phase_name: str) -> int:
    try:
        from services.phase_retry_silence_service import max_retries_for_phase

        return max_retries_for_phase(phase_name)
    except Exception:
        return 3


# Estimated duration in seconds per phase (single place to tune)
PHASE_ESTIMATED_DURATION_SECONDS = {
    "rss_processing": 120,
    "ml_processing": 900,  # queue drain + background workers; was 240
    "topic_clustering": 400,  # observed ~396s avg when backlog; was 180
    "entity_extraction": 1800,  # GPU LLM batches; measured runs often 1–4h without drain budget
    "unified_intake_extraction": 3600,
    "spine_sql_tail": 300,
    "mention_resolution": 1800,
    "quality_scoring": 90,
    "sentiment_analysis": 900,  # inline LLM per article; drain budget default 900s
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
    "rss_feed_health": 120,
    "rolling_arc_refresh": 180,
    "pending_db_flush": 30,
    "context_sync": 60,  # ~5-10s per 100 contexts (production batch)
    "entity_profile_sync": 225,  # observed ~223s avg; was 120
    "claim_extraction": 600,  # env CLAIM_EXTRACTION_BATCH_LIMIT × CLAIM_EXTRACTION_PARALLEL (LLM-bound)
    "legislative_references": 120,  # Congress.gov HTTP + rate-limit sleep per bill mention
    "claims_to_facts": 180,  # env CLAIMS_TO_FACTS_BATCH_LIMIT; resolver + INSERTs (DB-bound)
    "claim_evidence_appraisal": 600,  # LLM paper appraisal; CLAIM_EVIDENCE_APPRAISAL_ENABLED
    "editorial_reduction_pass": 600,  # LLM package prune; EDITORIAL_REDUCTION_ENABLED
    "editorial_narrative_pass": 600,  # LLM package assembly; EDITORIAL_NARRATIVE_ENABLED
    "editorial_research_pass": 600,  # LLM research assembly; EDITORIAL_RESEARCH_ENABLED
    "chronological_events_catchup": 600,  # CE restore; CHRONOLOGICAL_EVENTS_CATCHUP_ENABLED
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
    "arc_report_generation": 900,
    "longitudinal_matview_refresh": 60,
    "storyline_automation": 180,
    "storyline_review_agent": 120,
    "storyline_membership_review": 180,
    "storyline_hygiene": 300,
    "embedding_link_candidates": 120,
    "collision_sampling": 60,
    "stimulus_rag": 180,
    "protein_harden": 120,
    "graph_link_drift_review": 90,
    "graph_link_drift_review": 120,
    "storyline_enrichment": 600,  # full-history pass: ~10 min
    "story_enhancement": 300,
    "entity_enrichment": 180,
    "pattern_matching": 90,
    "cross_domain_synthesis": 120,
    "entity_organizer": 600,  # observed can be 5–90 min under load; was 180
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
    "storyline_synthesis": 600,  # deep content synthesis per storyline
    "daily_briefing_synthesis": 300,  # breaking news synthesis per domain
    "storyline_discovery": 3600,  # Full-backlog discovery (capped) + embeddings + LLM per domain
    # v8: collect-then-analyze — single master task runs RSS + enrichment + docs
    "collection_cycle": 1800,  # 30 min; RSS + drain enrichment + doc collection + drain doc processing + pending queue
    "proactive_detection": 300,  # v8: emerging storylines per domain
    "storyline_assembly": 900,  # proactive + discovery + automation per domain
    "fact_verification": 120,  # v8: verify_recent_claims per domain
    "content_refinement_queue": 420,  # storyline RAG / timeline narrative / ~70B finisher (queued user jobs)
    "nightly_enrichment_context": 21600,  # 02:00–07:00 local unified pipeline (NIGHTLY_PIPELINE_*); exits when idle
}


class AutomationManager:
    """Enterprise-grade automation manager"""

    def __init__(self, db_config: dict[str, str]):
        self.db_config = db_config
        try:
            from shared.pipeline_resource_policy import configure_pipeline_resources

            configure_pipeline_resources()
        except Exception as e:
            logger.debug("pipeline resource policy: %s", e)
        self.is_running = False
        self.tasks: dict[str, Task] = {}
        self.executor = ThreadPoolExecutor(max_workers=AUTOMATION_EXECUTOR_MAX_WORKERS)
        self._executor = (
            self.executor
        )  # alias used by entity_dossier_compile, entity_position_tracker, fact_verification
        # PriorityQueue: lower TaskPriority.value dequeued first; tie-break FIFO via monotonic counter.
        self.task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._scheduled_task_queue_seq = itertools.count()
        # User/governor-requested tasks run before scheduled tasks so "Request phase" is not starved
        self._requested_task_queue: asyncio.Queue = asyncio.Queue()
        self.ollama_semaphore = asyncio.Semaphore(MAX_CONCURRENT_OLLAMA_TASKS)
        # One enrichment batch at a time (collection_cycle loop + standalone content_enrichment share DB rows).
        self._content_enrichment_lock = asyncio.Lock()
        self.workers: list[asyncio.Task] = []
        self._phase_worker_tasks: list[asyncio.Task] = []
        self._background_automation_tasks: list[asyncio.Task] = []
        self._worker_id_seq = 0
        # Thread-safe queue for coordinator-driven phase requests (run_phase from another thread)
        self._phase_request_queue = queue.Queue()
        # Optional: callable() -> finance orchestrator, set by main after app.state.finance_orchestrator exists
        self._get_finance_orchestrator = None
        self.health_check_interval = 30  # seconds
        try:
            self.task_timeout = max(
                60, env_int("AUTOMATION_TASK_WALL_TIMEOUT_SECONDS", 300)
            )
        except ValueError:
            self.task_timeout = 300
        self.max_concurrent_tasks = (
            AUTOMATION_MAX_CONCURRENT_TASKS
        )  # Phase workers; scale up when you have CPU/GPU headroom

        # v8: Pending collection queue — RAG/synthesis add URLs here; drained each collection_cycle
        self._pending_collection_queue: list[dict[str, Any]] = []

        # Monitor metrics for phase timeline:
        # - queued_tasks_by_phase: computed from in-memory asyncio queues
        # - running_tasks_by_phase: tracked while tasks are executing
        # - runs_last_60m_by_phase: recorded from completion timestamps
        self._running_tasks_by_phase: dict[str, int] = defaultdict(int)
        # Scheduled PriorityQueue has no per-phase qsize; we maintain counts for all phases (Monitor +
        # AUTOMATION_MAX_SCHEDULED_DEPTH_PER_PHASE).
        self._scheduled_queue_depth_by_phase: dict[str, int] = defaultdict(int)
        self._requested_queue_depth_by_phase: dict[str, int] = defaultdict(int)
        self._phase_run_times_last_60m: dict[str, deque[datetime]] = defaultdict(deque)
        self._running_tasks_by_lane: dict[str, int] = defaultdict(int)
        self._lane_run_times_last_60m: dict[str, deque[datetime]] = defaultdict(deque)
        self._measurable_runs_60m_sql_cache: dict[str, Any] = {"at": 0.0, "counts": {}}

        self.pipeline_controller = None

        # v8: Optional config from orchestrator_governance.yaml (collection_cycle interval)
        try:
            from config.orchestrator_governance import get_orchestrator_governance_config

            gov = get_orchestrator_governance_config()
            cc = gov.get("collection_cycle") or {}
        except Exception:
            cc = {}
        collection_interval = None
        if hasattr(os, "environ"):
            raw = env_str("COLLECTION_CYCLE_INTERVAL_SECONDS")
            if raw is not None:
                try:
                    collection_interval = int(raw)
                except ValueError:
                    pass
        if collection_interval is None:
            collection_interval = cc.get("interval_seconds", 7200)

        # Task schedules (cron-like) - Sequential processing with proper dependencies
        # v8: Collection runs as single collection_cycle every 2h; rss/enrichment/docs are sub-steps only
        self.schedules = {
            # PHASE 0: Collection cycle (v8) — RSS, enrichment drain, document collection, document processing drain, pending queue (interval from config/env)
            "collection_cycle": {
                "interval": collection_interval,
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.CRITICAL,
                "phase": 0,
                "depends_on": [],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["collection_cycle"],
            },
            # 02:00–07:00 local (NIGHTLY_PIPELINE_*): RSS kickoff → enrichment → context_sync → sequential drain → ~70B
            "nightly_enrichment_context": {
                "interval": 60,
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.HIGH,
                "phase": 0,
                "depends_on": [],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS[
                    "nightly_enrichment_context"
                ],
            },
            # PDF document processing (also runs inside collection_cycle); standalone so backlog drains between cycles
            "document_processing": {
                "interval": 600,  # 10 minutes - drain unprocessed PDFs (fetch + extract sections/entities)
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 0,
                "depends_on": [],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["document_processing"],
            },
            # Trafilatura full-text for RSS-short articles (all active domain schemas). Runs on its own schedule
            # so Widow/cron RSS rows are drained even when collection_cycle skips RSS or is throttled on backlog.
            "content_enrichment": {
                "interval": 300,  # 5 minutes when idle; workload-driven runs sooner when pending > 0
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.HIGH,
                "phase": 0,
                "depends_on": [],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["content_enrichment"],
            },
            "rss_feed_health": {
                "interval": 86400,  # nightly feed yield review + warn-then-auto silencing
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.LOW,
                "phase": 0,
                "depends_on": ["collection_cycle"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["rss_feed_health"],
            },
            "rolling_arc_refresh": {
                "interval": 86400,  # Phase B nightly rolling 12m arcs
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.LOW,
                "phase": 0,
                "depends_on": [],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["rolling_arc_refresh"],
            },
            # PHASE 1b: Context-centric sync (incremental: articles -> intelligence.contexts)
            "context_sync": {
                "interval": 900,  # 15 minutes - incremental sync, 100 contexts/batch, ~30-60s
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 1,
                "depends_on": ["collection_cycle", "content_enrichment"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["context_sync"],
            },
            # PHASE 1c: Entity profile sync (entity_canonical -> entity_profiles, old_entity_to_new)
            "entity_profile_sync": {
                "interval": 21600,  # 6 hours
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 1,
                "depends_on": [],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["entity_profile_sync"],
            },
            # PHASE 2a: Claim extraction (contexts -> extracted_claims; LLM rate limits)
            "claim_extraction": {
                "interval": 1800,  # 30 min fallback when idle; workload-driven when backlog > 0
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 2,
                "depends_on": ["context_sync"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["claim_extraction"],
            },
            # PHASE 2a.0: Federal bill citations → Congress.gov metadata/summaries/text pointers (politics/legal)
            "legislative_references": {
                "interval": 3600,  # 1 hour — rate limits; skips when backlog 0
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 2,
                "depends_on": ["context_sync"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["legislative_references"],
            },
            # PHASE 2a.1: Promote high-confidence claims to versioned_facts (activates story state chain)
            "claims_to_facts": {
                "interval": 3600,  # 1 hour - after claim_extraction has run
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 2,
                "depends_on": ["claim_extraction"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["claims_to_facts"],
            },
            # v11 corpus: evidence appraisal (feature-flagged; schedule enabled=False by default)
            "claim_evidence_appraisal": {
                "interval": 7200,
                "last_run": None,
                "enabled": False,
                "priority": TaskPriority.LOW,
                "phase": 2,
                "depends_on": ["claims_to_facts"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS[
                    "claim_evidence_appraisal"
                ],
            },
            # v11 Reduction modality: drain in_reduction packages (LLM prune → route back)
            "editorial_reduction_pass": {
                "interval": 1800,
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 3,
                "depends_on": ["editorial_narrative_pass", "editorial_research_pass"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS[
                    "editorial_reduction_pass"
                ],
            },
            # v11 Narrative modality: drain in_narrative packages (assemble → Reduction/Editor)
            "editorial_narrative_pass": {
                "interval": 1800,
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 3,
                "depends_on": ["story_continuation"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS[
                    "editorial_narrative_pass"
                ],
            },
            # v11 Research modality: drain in_research packages (spine + assemble → Reduction/Editor)
            "editorial_research_pass": {
                "interval": 1800,
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 3,
                "depends_on": ["story_continuation"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS[
                    "editorial_research_pass"
                ],
            },
            # PHASE 2a.2: Rebuild claim_subject_gap_catalog (operators + claims_to_facts ignore list)
            "claim_subject_gap_refresh": {
                "interval": 21600,  # 6 hours — DB snapshot only
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.LOW,
                "phase": 2,
                "depends_on": ["claims_to_facts"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS[
                    "claim_subject_gap_refresh"
                ],
            },
            # PHASE 2a.3: Remove duplicate extracted_claims (same context + normalized triple)
            "extracted_claims_dedupe": {
                "interval": 43200,  # 12 hours — bounded batches per run
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.LOW,
                "phase": 2,
                "depends_on": ["claim_extraction"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["extracted_claims_dedupe"],
            },
            # PHASE 2.3: Event tracking (contexts -> tracked_events; drain unlinked backlog)
            "event_tracking": {
                "interval": 900,  # 15 min - process more contexts per run when backlog is large
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 2,
                "depends_on": ["context_sync"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["event_tracking"],
            },
            # PHASE 3: Event coherence review (LLM verifies context-event fit; needs tracked_events)
            "event_coherence_review": {
                "interval": 7200,  # 2 hours
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.LOW,
                "phase": 3,
                "depends_on": ["event_tracking"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["event_coherence_review"],
            },
            # PHASE 2.4: Refresh investigation reports when events gain new context (after event_tracking)
            "investigation_report_refresh": {
                "interval": 7200,  # 2 hours
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.LOW,
                "phase": 2,
                "depends_on": ["event_tracking"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS[
                    "investigation_report_refresh"
                ],
            },
            # PHASE 2.5: Cross-domain synthesis (correlate events across active pipeline domains)
            "cross_domain_synthesis": {
                "interval": 1800,  # 30 minutes
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 2,
                "depends_on": ["event_tracking"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["cross_domain_synthesis"],
            },
            # PHASE 1.3: Entity profile builder (sections, relationships from contexts)
            "entity_profile_build": {
                "interval": 900,  # 15 minutes - run often, re-enqueue until profiles built
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 1,
                "depends_on": ["context_sync", "entity_profile_sync"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["entity_profile_build"],
            },
            # Longitudinal intelligence (Phases 1–4): nightly-heavy; yields to ingest
            # Hard-retired (no schedule): pattern_recognition — see retired_phase_registry
            "embeddings_worker": {
                "interval": 3600,
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.LOW,
                "phase": 2,
                "depends_on": ["content_enrichment"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["embeddings_worker"],
            },
            "macro_series_refresh": {
                "interval": 86400,
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.LOW,
                "phase": 2,
                "depends_on": [],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["macro_series_refresh"],
            },
            "external_events_sync": {
                "interval": 43200,
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.LOW,
                "phase": 2,
                "depends_on": [],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["external_events_sync"],
            },
            "sanctions_refresh": {
                "interval": 86400,
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.LOW,
                "phase": 2,
                "depends_on": [],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["sanctions_refresh"],
            },
            # Hard-retired (no schedule): arc_report_generation, longitudinal_matview_refresh
            # PHASE 2.6: Entity dossier compile (articles + storylines + relationships -> entity_dossiers)
            "entity_dossier_compile": {
                "interval": 3600,  # 1 hour - compile dossiers for entities missing or stale
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 2,
                "depends_on": ["entity_profile_sync"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["entity_dossier_compile"],
            },
            # PHASE 2: Entity position tracker (stances, votes, policy from articles -> entity_positions)
            "entity_position_tracker": {
                "interval": 7200,  # 2 hours
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 2,
                "depends_on": ["entity_profile_sync"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["entity_position_tracker"],
            },
            # Hard-retired (no schedule): metadata_enrichment — superseded by unified intake
            # Entity organizer: cleanup (merge/prune/cap) + relationship extraction; also runs in downtime loop
            "entity_organizer": {
                "interval": 600,  # 10 minutes - run after we have entities
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 2,
                "depends_on": ["entity_profile_sync"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["entity_organizer"],
            },
            "graph_connection_distillation": {
                "interval": 600,  # 10 minutes — drain merge/associate/hyperedge proposal queue
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 2,
                "depends_on": ["entity_organizer"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS[
                    "graph_connection_distillation"
                ],
            },
            "embedding_link_candidates": {
                "interval": 1800,
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 2,
                # After RSS intake chain (collection → enrich/UIE) — beaker stir
                "depends_on": ["collection_cycle", "unified_intake_extraction"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS[
                    "embedding_link_candidates"
                ],
            },
            "collision_sampling": {
                "interval": 1800,
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 2,
                "depends_on": ["collection_cycle", "unified_intake_extraction"],
                "estimated_duration": 60,
            },
            "stimulus_rag": {
                "interval": 900,
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 2,
                "depends_on": ["collision_sampling", "embedding_link_candidates"],
                "estimated_duration": 180,
            },
            "protein_harden": {
                "interval": 1200,
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 2,
                "depends_on": ["stimulus_rag", "graph_connection_distillation"],
                "estimated_duration": 120,
            },
            "graph_link_drift_review": {
                "interval": 3600,
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.LOW,
                "phase": 2,
                "depends_on": ["graph_connection_distillation"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS[
                    "graph_link_drift_review"
                ],
            },
            # Hard-retired (no schedule): ml_processing — superseded by unified intake
            # PHASE 5: Topic Clustering (Continuous iterative refinement)
            "topic_clustering": {
                "interval": 300,  # 5 minutes - run often, drain backlog
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.HIGH,
                "phase": 5,
                "depends_on": ["collection_cycle"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["topic_clustering"],
            },
            # Hard-retired (no schedule): entity_extraction — superseded by unified intake
            "unified_intake_extraction": {
                "interval": 300,
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 4,
                "depends_on": ["content_enrichment"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["unified_intake_extraction"],
                "parallel_group": "ml_entity_processing",
            },
            "spine_sql_tail": {
                "interval": 300,
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 4,
                "depends_on": ["unified_intake_extraction"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["spine_sql_tail"],
            },
            "mention_resolution": {
                "interval": 300,
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 4,
                "depends_on": ["unified_intake_extraction"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["mention_resolution"],
                "parallel_group": "ml_entity_processing",
            },
            # Hard-retired (no schedule): quality_scoring, sentiment_analysis — unified intake
            # PHASE 6: Storyline Discovery (AI auto-creates storylines from article clusters)
            "storyline_discovery": {
                "interval": 14400,  # 4 hours — discover new storylines from recent articles
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 6,
                "depends_on": ["collection_cycle"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["storyline_discovery"],
            },
            "proactive_detection": {
                "interval": 7200,  # 2 hours — emerging storylines (v8)
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 6,
                "depends_on": ["collection_cycle"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["proactive_detection"],
            },
            "storyline_assembly": {
                "interval": 1800,  # 30 min — detect + discover + link per domain
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.HIGH,
                "phase": 6,
                "depends_on": ["content_enrichment"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["storyline_assembly"],
            },
            "fact_verification": {
                "interval": 14400,  # 4 hours — verify recent claims (v8)
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 6,
                "depends_on": ["collection_cycle"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["fact_verification"],
            },
            # PHASE 7: Storyline Processing (summaries; continuous until empty)
            "storyline_processing": {
                "interval": 300,  # 5 minutes - run often, re-enqueue until empty
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.HIGH,
                "phase": 7,
                "depends_on": ["unified_intake_extraction"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["storyline_processing"],
            },
            # Scheduled batch + governor requests: match incoming articles to automation-enabled storylines
            "storyline_automation": {
                "interval": 300,  # 5 min: recent incoming → match to existing storylines
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 7,
                "depends_on": [],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["storyline_automation"],
            },
            "storyline_review_agent": {
                "interval": 300,
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 7,
                "depends_on": ["storyline_automation"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["storyline_review_agent"],
            },
            "storyline_membership_review": {
                "interval": 900,
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.LOW,
                "phase": 7,
                "depends_on": ["storyline_automation"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS[
                    "storyline_membership_review"
                ],
            },
            "storyline_hygiene": {
                "interval": 1800,  # 30m — freeze→prune→near-dup merge
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.LOW,
                "phase": 7,
                "depends_on": ["storyline_automation"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["storyline_hygiene"],
            },
            # v8: Enrich existing storylines/dossiers with full-history search (past articles/contexts)
            "storyline_enrichment": {
                "interval": 43200,  # 12 hours - full-history pass
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 7,
                "depends_on": ["storyline_automation"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["storyline_enrichment"],
            },
            # PHASE 8: RAG Enhancement (Every 30 minutes)
            "rag_enhancement": {
                "interval": 300,  # 5 minutes - run often, re-enqueue until storylines enhanced
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.HIGH,
                "phase": 8,
                "depends_on": ["storyline_processing"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["rag_enhancement"],
            },
            # Hard-retired (no schedule): event_extraction — superseded by unified intake
            # PHASE 9b: Event Deduplication (v5.0 — after unified intake events)
            "event_deduplication": {
                "interval": 600,  # 10 minutes
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 9,
                "depends_on": ["unified_intake_extraction", "chronological_events_catchup"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["event_deduplication"],
                "parallel_group": "event_processing",
            },
            # PHASE 9b2: Restore chronological_events for UIE-complete articles missing CE
            "chronological_events_catchup": {
                "interval": 1800,
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 9,
                "depends_on": ["unified_intake_extraction"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS[
                    "chronological_events_catchup"
                ],
            },
            # PHASE 9c: Story Continuation Matching (v5.0)
            "story_continuation": {
                "interval": 600,  # 10 minutes
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 9,
                "depends_on": ["event_deduplication"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["story_continuation"],
            },
            # PHASE 9d: Timeline Generation (continuous until empty)
            "timeline_generation": {
                "interval": 300,  # 5 minutes - run often, re-enqueue until empty
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 9,
                "depends_on": [],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["timeline_generation"],
            },
            # Phase 3 RAG: Entity enrichment (Wikipedia -> entity_profiles; LLM limits)
            "entity_enrichment": {
                "interval": 1800,  # 30 minutes - max 20 entities/run, 10s timeout/entity; skip if queue >1000
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 9,
                "depends_on": ["entity_profile_sync"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["entity_enrichment"],
            },
            # Phase 3 RAG: Full enhancement cycle (triggers + enrichment + profile build)
            "story_enhancement": {
                "interval": 300,  # 5 minutes - max 10 stories/run, 60s budget
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 9,
                "depends_on": [],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["story_enhancement"],
            },
            # User-requested storyline refinement (DB queue; no ad-hoc HTTP LLM)
            "content_refinement_queue": {
                "interval": 120,  # 2 min when idle; workload-driven when pending > 0
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 9,
                "depends_on": [],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["content_refinement_queue"],
            },
            # PHASE 10: Cache Cleanup (Every hour)
            "cache_cleanup": {
                "interval": 3600,  # 1 hour - Clean expired cache
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.LOW,
                "phase": 10,
                "depends_on": [],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["cache_cleanup"],
            },
            # Hard-retired (no schedule): editorial_document/briefing, digest_generation
            # Auto storyline synthesis (Wikipedia-style articles)
            "storyline_synthesis": {
                "interval": 3600,  # 60 minutes
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 10,
                "depends_on": ["storyline_processing"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["storyline_synthesis"],
            },
            # Hard-retired (no schedule): daily_briefing_synthesis
            # PHASE 12: Watchlist Alert Generation (v5.0)
            "watchlist_alerts": {
                "interval": 1200,  # 20 minutes - Relaxed from 15 min
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.LOW,
                "phase": 12,
                "depends_on": ["story_continuation"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["watchlist_alerts"],
            },
            # Phase 4 RAG: Watch patterns — match content, record pattern_matches, create watchlist alerts
            "pattern_matching": {
                "interval": 1800,  # 30 minutes
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.LOW,
                "phase": 12,
                "depends_on": [],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["pattern_matching"],
            },
            # IDLE-ONLY: Research topic refinement (finance) — run when no data load / higher-priority work
            "research_topic_refinement": {
                "interval": 3600,  # consider every hour when idle
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.LOW,
                "phase": 98,
                "depends_on": [],
                "idle_only": True,
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["research_topic_refinement"],
            },
            # PHASE 11: Narrative thread build + synthesis (cross-storyline narrative arcs)
            "narrative_thread_build": {
                "interval": 7200,  # 2 hours
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.LOW,
                "phase": 11,
                "depends_on": ["storyline_processing"],
                "estimated_duration": 120,
            },
            # MAINTENANCE: Data Cleanup (Daily)
            "data_cleanup": {
                "interval": 86400,  # 24 hours
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.LOW,
                "phase": 99,
                "depends_on": [],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["data_cleanup"],
            },
            # MONITORING: Health Check
            "health_check": {
                "interval": 120,  # 2 minutes - Relaxed from 1 min
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.CRITICAL,
                "phase": 0,
                "depends_on": [],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["health_check"],
            },
            # OUTAGE: Replay local spill file (automation_run_history) when DB was down
            "pending_db_flush": {
                "interval": 45,
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.CRITICAL,
                "phase": 0,
                "depends_on": [],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["pending_db_flush"],
            },
        }

        # Pristine dependency edges, captured before any suppression strips them,
        # so an auto-silenced phase can be re-wired when its silence lifts.
        self._pristine_depends_on: dict[str, list[str]] = {
            name: list(sched.get("depends_on") or []) for name, sched in self.schedules.items()
        }
        # Phases this manager disabled specifically because of auto-silence — the
        # only ones eligible for re-enable (never resurrect retired/superseded phases).
        self._auto_silence_disabled: set[str] = set()

        self._apply_automation_disabled_schedules()
        self._apply_legacy_intake_schedule_suppression()
        from shared.retired_phase_registry import apply_retired_schedule_suppression

        apply_retired_schedule_suppression(self.schedules)
        self._apply_entity_enrichment_schedule_dedupe()

        # Performance metrics
        self.metrics = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "avg_processing_time": 0,
            "system_uptime": 0,
            "last_health_check": None,
            "adaptive_timing": False,
            "processing_history": {},  # Track actual vs estimated durations (Monitor)
        }

        try:
            pr = pipeline_article_selection_mode_report()
            logger.info(
                "Pipeline article batch order: %s (ORDER BY created_at %s) — PIPELINE_ARTICLE_SELECTION_ORDER=%s",
                pr["label"],
                pr["sql_created_at"],
                pr["order_env"],
            )
            bfs = pipeline_backfill_status_line()
            if bfs:
                logger.warning("%s", bfs)
        except Exception:
            pass

    def get_disabled_schedule_names(self) -> list[str]:
        """Phases disabled via AUTOMATION_DISABLED_SCHEDULES, remote worker ownership, and auto-silence."""
        raw = env_str("AUTOMATION_DISABLED_SCHEDULES", "").strip()
        names = {x.strip() for x in raw.split(",") if x.strip()} if raw else set()
        try:
            from shared.remote_phase_worker import remote_owned_phases

            names |= set(remote_owned_phases())
        except Exception:
            pass
        try:
            from services.phase_retry_silence_service import list_auto_silenced_phases

            names |= list_auto_silenced_phases()
        except Exception:
            pass
        return sorted(names)

    def is_schedule_disabled(self, phase_name: str) -> bool:
        return phase_name.strip() in set(self.get_disabled_schedule_names())

    def _apply_automation_disabled_schedules(self) -> None:
        """
        Reconcile schedule enablement against the current disable set.

        Disables named schedules and strips them from depends_on so dependents still
        run (Widow cron / PopOS worker). Also re-enables phases whose *auto-silence*
        has since lifted — silence is a backoff, so it must not survive as a
        permanent disable until the next API restart. Safe to call repeatedly.
        """
        disabled = set(self.get_disabled_schedule_names())
        remote_owned: set[str] = set()
        try:
            from shared.remote_phase_worker import remote_owned_phases

            remote_owned = set(remote_owned_phases())
        except Exception:
            pass
        auto_silenced: set[str] = set()
        try:
            from services.phase_retry_silence_service import list_auto_silenced_phases

            auto_silenced = list_auto_silenced_phases()
        except Exception:
            pass

        self._reenable_lifted_silence_schedules(disabled)

        if not disabled:
            return
        for name in disabled:
            if name in self.schedules:
                was_enabled = bool(self.schedules[name].get("enabled", True))
                self.schedules[name]["enabled"] = False
                if name in remote_owned:
                    reason = "REMOTE_PHASE_WORKER_OWNED_PHASES"
                elif name in auto_silenced:
                    reason = "PHASE_AUTO_SILENCE"
                    self._auto_silence_disabled.add(name)
                else:
                    reason = "AUTOMATION_DISABLED_SCHEDULES"
                # Reconciler runs every controller cycle — only log real transitions.
                if was_enabled:
                    logger.info("Automation schedule %s disabled (%s)", name, reason)
            else:
                logger.warning("disabled schedule unknown phase %s", name)
        for sched_name, sched in self.schedules.items():
            deps = list(sched.get("depends_on") or [])
            if not deps:
                continue
            new_deps = [d for d in deps if d not in disabled]
            if new_deps != deps:
                sched["depends_on"] = new_deps
                logger.info(
                    "Automation: %s depends_on adjusted after disabled schedules: %s",
                    sched_name,
                    new_deps,
                )

    def _reenable_lifted_silence_schedules(self, disabled: set[str]) -> list[str]:
        """
        Re-enable phases that were disabled by auto-silence which has since lifted.

        Only phases this manager muted for PHASE_AUTO_SILENCE are eligible, so
        retired / superseded / remote-owned schedules are never resurrected.
        Dependency edges stripped when the phase was muted are restored from the
        pristine snapshot (skipping any edge that is still disabled).
        """
        eligible = {
            name
            for name in getattr(self, "_auto_silence_disabled", set())
            if name not in disabled and name in self.schedules
        }
        if not eligible:
            return []
        restored: list[str] = []
        for name in sorted(eligible):
            self.schedules[name]["enabled"] = True
            self.schedules[name]["last_run"] = None  # eligible on the next tick
            self._auto_silence_disabled.discard(name)
            restored.append(name)
            logger.info(
                "Automation schedule %s re-enabled (auto-silence lifted — retrying phase)",
                name,
            )
        pristine = getattr(self, "_pristine_depends_on", {}) or {}
        for sched_name, sched in self.schedules.items():
            original = pristine.get(sched_name)
            if not original:
                continue
            deps = list(sched.get("depends_on") or [])
            missing = [
                d for d in original if d in restored and d not in deps and d not in disabled
            ]
            if missing:
                sched["depends_on"] = [d for d in original if d not in disabled]
                logger.info(
                    "Automation: %s depends_on restored after silence lift: %s",
                    sched_name,
                    sched["depends_on"],
                )
        return restored

    def _apply_legacy_intake_schedule_suppression(self) -> None:
        """Disable legacy per-phase intake schedules superseded by unified_intake_extraction."""
        from shared.legacy_intake_rollback import legacy_intake_rollback_active
        from shared.pipeline_resource_policy import unified_superseded_automation_phases

        if legacy_intake_rollback_active():
            return
        disabled = unified_superseded_automation_phases()
        for name in disabled:
            if name in self.schedules:
                self.schedules[name]["enabled"] = False
                logger.info(
                    "Automation schedule %s disabled (superseded by unified_intake_extraction)",
                    name,
                )
        for sched_name, sched in self.schedules.items():
            deps = list(sched.get("depends_on") or [])
            new_deps = [d for d in deps if d not in disabled]
            if new_deps != deps:
                sched["depends_on"] = new_deps
                logger.debug(
                    "Automation: %s depends_on stripped legacy intake phases: %s",
                    sched_name,
                    new_deps,
                )

    def _apply_retired_phase_schedule_suppression(self) -> None:
        """Disable schedules for features.yaml retired phases (enabled:false with phase_name)."""
        from shared.retired_phase_registry import retired_automation_phases

        disabled = retired_automation_phases()
        if not disabled:
            return
        for name in disabled:
            if name in self.schedules and self.schedules[name].get("enabled", True):
                self.schedules[name]["enabled"] = False
                logger.info(
                    "Automation schedule %s disabled (features.yaml retired phase)",
                    name,
                )
        for sched_name, sched in self.schedules.items():
            deps = list(sched.get("depends_on") or [])
            new_deps = [d for d in deps if d not in disabled]
            if new_deps != deps:
                sched["depends_on"] = new_deps
                logger.debug(
                    "Automation: %s depends_on stripped retired phases: %s",
                    sched_name,
                    new_deps,
                )

    def _apply_entity_enrichment_schedule_dedupe(self) -> None:
        """story_enhancement orchestrator already runs entity enrichment batches."""
        se = self.schedules.get("story_enhancement") or {}
        ee = self.schedules.get("entity_enrichment")
        if ee and se.get("enabled", True):
            ee["enabled"] = False
            logger.info(
                "Automation schedule entity_enrichment disabled (owned by story_enhancement)"
            )
            for sched_name, sched in self.schedules.items():
                deps = list(sched.get("depends_on") or [])
                if "entity_enrichment" in deps:
                    sched["depends_on"] = [d for d in deps if d != "entity_enrichment"]
                    logger.debug(
                        "Automation: %s depends_on stripped entity_enrichment: %s",
                        sched_name,
                        sched["depends_on"],
                    )

    def _automation_queue_depth(self) -> int:
        """Approximate pending tasks in worker queues (scheduled + governor-requested)."""
        try:
            return int(self.task_queue.qsize()) + int(self._requested_task_queue.qsize())
        except Exception:
            return 0

    def _nightly_enrichment_in_flight_count(self) -> int:
        """Running + scheduled-queue + requested-queue nightly_enrichment_context tasks."""
        n = "nightly_enrichment_context"
        return (
            int(self._running_tasks_by_phase.get(n, 0) or 0)
            + int(self._scheduled_queue_depth_by_phase.get(n, 0) or 0)
            + int(self._requested_queue_depth_by_phase.get(n, 0) or 0)
        )

    def _phase_pipeline_inflight(self, phase_name: str) -> int:
        """Workers running this phase + tasks waiting in scheduled queue + governor-requested queue."""
        return (
            int(self._running_tasks_by_phase.get(phase_name, 0) or 0)
            + int(self._scheduled_queue_depth_by_phase.get(phase_name, 0) or 0)
            + int(self._requested_queue_depth_by_phase.get(phase_name, 0) or 0)
        )

    def _should_skip_redundant_phase_request(
        self, phase_name: str, *, allow_operator_bypass: bool = False
    ) -> bool:
        """
        Drop duplicate governor/chain requests when long-running drains already fill the pipeline.

        Without this, every context_sync completion chains request_phase(claim_extraction); each
        enqueue stacks on _requested_task_queue (832+) while a few workers hold long drains.
        Monitor/API triggers pass allow_operator_bypass when requested_activity_id is set.
        """
        if allow_operator_bypass:
            return False
        try:
            from services.pipeline_controller import LONG_DRAIN_PHASES

            if phase_name not in LONG_DRAIN_PHASES:
                return False
        except Exception:
            if phase_name != "claim_extraction":
                return False
        if phase_name == "claim_extraction":
            try:
                from services.claim_extraction_service import claim_extraction_drain_enabled

                if not claim_extraction_drain_enabled():
                    return False
            except Exception:
                return False
        cap = self._per_phase_scheduler_concurrent_cap(phase_name)
        if cap <= 0:
            cap = min(int(self.max_concurrent_tasks), 6)
        return self._phase_pipeline_inflight(phase_name) >= cap

    def _discard_redundant_drain_when_at_cap(self, task: Task, exec_cap: int) -> bool:
        """
        When the concurrent cap is already satisfied by other workers, duplicate long-drain tasks
        must not re-enter the asyncio queue. Otherwise copies accumulate while drains hold slots.
        """
        if exec_cap <= 0:
            return False
        if (task.metadata or {}).get("nightly_sequential_drain"):
            return False
        if (task.metadata or {}).get("requested_activity_id"):
            return False
        try:
            from services.pipeline_controller import LONG_DRAIN_PHASES

            if task.name not in LONG_DRAIN_PHASES:
                return False
        except Exception:
            if task.name != "claim_extraction":
                return False
        if task.name == "claim_extraction":
            try:
                from services.claim_extraction_service import claim_extraction_drain_enabled

                if not claim_extraction_drain_enabled():
                    return False
            except Exception:
                return False
        return int(self._running_tasks_by_phase.get(task.name, 0) or 0) >= exec_cap

    def _discard_redundant_claim_extraction_when_at_cap(self, task: Task, exec_cap: int) -> bool:
        """Backward-compatible alias."""
        return self._discard_redundant_drain_when_at_cap(task, exec_cap)

    def _can_enqueue_nightly_enrichment(self) -> bool:
        if AUTOMATION_NIGHTLY_ENRICHMENT_MAX_QUEUED <= 0:
            return True
        return self._nightly_enrichment_in_flight_count() < AUTOMATION_NIGHTLY_ENRICHMENT_MAX_QUEUED

    def _scheduled_queue_tuple(self, task: Task) -> tuple[int, int, Task]:
        """PriorityQueue entry: lower ``TaskPriority.value`` first, then FIFO."""
        p = (
            task.priority.value
            if isinstance(task.priority, TaskPriority)
            else int(task.priority)
        )
        return (p, next(self._scheduled_task_queue_seq), task)

    async def _enqueue_scheduled_task(
        self,
        task: Task,
        *,
        bypass_nightly_cap: bool = False,
        bypass_schedule_depth_cap: bool = False,
    ) -> bool:
        """
        Enqueue a scheduled task. Returns False if skipped (e.g. nightly cap).
        bypass_nightly_cap: set True for defer/retry re-enqueue of an in-flight task so work is not dropped.
        bypass_schedule_depth_cap: set True for defer/retry so yield/nightly/GPU gates never drop the task.
        """
        if (
            task.name == "nightly_enrichment_context"
            and not bypass_nightly_cap
            and not self._can_enqueue_nightly_enrichment()
        ):
            logger.debug(
                "Skip nightly_enrichment_context scheduled enqueue (in_flight=%s cap=%s)",
                self._nightly_enrichment_in_flight_count(),
                AUTOMATION_NIGHTLY_ENRICHMENT_MAX_QUEUED,
            )
            return False
        if (
            not bypass_schedule_depth_cap
            and AUTOMATION_MAX_SCHEDULED_DEPTH_PER_PHASE > 0
            and int(self._scheduled_queue_depth_by_phase.get(task.name, 0) or 0)
            >= AUTOMATION_MAX_SCHEDULED_DEPTH_PER_PHASE
        ):
            logger.debug(
                "Skip scheduled enqueue for %s (scheduled_depth=%s max=%s)",
                task.name,
                self._scheduled_queue_depth_by_phase.get(task.name, 0),
                AUTOMATION_MAX_SCHEDULED_DEPTH_PER_PHASE,
            )
            return False
        await self.task_queue.put(self._scheduled_queue_tuple(task))
        self._scheduled_queue_depth_by_phase[task.name] += 1
        return True

    def _enqueue_scheduled_task_nowait(
        self,
        task: Task,
        *,
        bypass_nightly_cap: bool = False,
        bypass_schedule_depth_cap: bool = False,
    ) -> bool:
        if (
            task.name == "nightly_enrichment_context"
            and not bypass_nightly_cap
            and not self._can_enqueue_nightly_enrichment()
        ):
            logger.debug(
                "Skip nightly_enrichment_context nowait enqueue (in_flight=%s cap=%s)",
                self._nightly_enrichment_in_flight_count(),
                AUTOMATION_NIGHTLY_ENRICHMENT_MAX_QUEUED,
            )
            return False
        if (
            not bypass_schedule_depth_cap
            and AUTOMATION_MAX_SCHEDULED_DEPTH_PER_PHASE > 0
            and int(self._scheduled_queue_depth_by_phase.get(task.name, 0) or 0)
            >= AUTOMATION_MAX_SCHEDULED_DEPTH_PER_PHASE
        ):
            logger.debug(
                "Skip nowait enqueue for %s (scheduled_depth=%s max=%s)",
                task.name,
                self._scheduled_queue_depth_by_phase.get(task.name, 0),
                AUTOMATION_MAX_SCHEDULED_DEPTH_PER_PHASE,
            )
            return False
        self.task_queue.put_nowait(self._scheduled_queue_tuple(task))
        self._scheduled_queue_depth_by_phase[task.name] += 1
        return True

    async def drain_phase_requests_to_queue(self) -> None:
        """Drain thread-safe phase requests (Monitor / orchestrator) into requested queue."""
        try:
            while True:
                item = self._phase_request_queue.get_nowait()
                force_nightly_unified_pipeline = False
                if isinstance(item, dict):
                    phase_name = item.get("phase")
                    domain = item.get("domain")
                    storyline_id = item.get("storyline_id")
                    requested_activity_id = item.get("requested_activity_id")
                    force_nightly_unified_pipeline = bool(
                        item.get("force_nightly_unified_pipeline")
                    )
                elif len(item) == 4:
                    phase_name, domain, storyline_id, requested_activity_id = item
                else:
                    phase_name, domain, storyline_id = item[0], item[1], item[2]
                    requested_activity_id = None
                if not phase_name or phase_name not in self.schedules:
                    continue
                if self._should_skip_redundant_phase_request(
                    phase_name,
                    allow_operator_bypass=bool(requested_activity_id),
                ):
                    continue
                schedule = self.schedules[phase_name]
                if not schedule.get("enabled", True):
                    continue
                task = Task(
                    id=f"{phase_name}_{int(datetime.now(timezone.utc).timestamp())}_req",
                    name=phase_name,
                    priority=TaskPriority.CRITICAL,
                    status=TaskStatus.PENDING,
                    created_at=datetime.now(timezone.utc),
                    max_retries=_phase_max_retries(phase_name),
                    metadata={
                        "domain": domain,
                        "storyline_id": storyline_id,
                        "requested_activity_id": requested_activity_id,
                        "force_nightly_unified_pipeline": force_nightly_unified_pipeline,
                        "operator_request": True,
                        "lane_default": self._phase_default_lane(phase_name),
                        "resource_class": self._phase_resource_class(phase_name),
                    },
                )
                await self._requested_task_queue.put(task)
                self._requested_queue_depth_by_phase[phase_name] += 1
                logger.info(
                    "Governor requested phase: %s (domain=%s, storyline_id=%s)",
                    phase_name,
                    domain,
                    storyline_id,
                )
        except queue.Empty:
            pass

    def _drain_priority_queue_tasks(self) -> list[Task]:
        tasks: list[Task] = []
        while True:
            try:
                item = self.task_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            t = item[2] if isinstance(item, tuple) and len(item) >= 3 else item
            if hasattr(t, "name"):
                tasks.append(t)
                self._scheduled_queue_depth_by_phase[t.name] = max(
                    0, int(self._scheduled_queue_depth_by_phase.get(t.name, 0) or 0) - 1
                )
        return tasks

    def _rebuild_priority_queue(self, tasks: list[Task]) -> None:
        for idx, task in enumerate(tasks):
            p = TaskPriority.CRITICAL.value if (task.metadata or {}).get("operator_request") else TaskPriority.NORMAL.value
            if isinstance(task.priority, TaskPriority):
                p = min(p, task.priority.value)
            self.task_queue.put_nowait((p, idx, task))
            self._scheduled_queue_depth_by_phase[task.name] += 1

    async def reconcile_and_enqueue(
        self,
        *,
        desired_phases: list[str],
        plan_generation: int,
        stall_holds: dict[str, int],
        controller: Any,
        pending: dict[str, int] | None = None,
    ) -> None:
        """Drop duplicates / stale plans, reorder, enqueue gaps to prefetch target."""
        from services.pipeline_controller import (
            host_lane_at_cap,
            prefetch_multiplier,
        )

        if pending is None:
            pending = {}
            try:
                from services.backlog_metrics import get_all_pending_counts

                pending = await asyncio.to_thread(get_all_pending_counts)
            except Exception:
                pending = {}
        else:
            pending = dict(pending)

        existing = self._drain_priority_queue_tasks()
        kept: list[Task] = []
        actions: list[str] = []
        phase_counts: dict[str, int] = defaultdict(int)
        controller_hosts = getattr(controller, "hosts", None) or {}

        for task in existing:
            meta = task.metadata or {}
            if meta.get("requested_activity_id") or meta.get("operator_request"):
                kept.append(task)
                phase_counts[task.name] += 1
                continue
            gen = meta.get("plan_generation")
            if gen is not None and int(gen) < plan_generation:
                actions.append(f"drop_stale:{task.name}")
                continue
            if stall_holds.get(task.name, 0) > 0:
                actions.append(f"drop_stall_hold:{task.name}")
                continue
            from shared.bulk_catchup_pause import bulk_catchup_pause_defers_phase

            if bulk_catchup_pause_defers_phase(task.name) and not meta.get("operator_request"):
                actions.append(f"drop_bulk_pause:{task.name}")
                continue
            if int(pending.get(task.name, 0) or 0) <= 0 and task.name != "spine_sql_tail":
                actions.append(f"drop_empty:{task.name}")
                continue
            cap = self._per_phase_scheduler_concurrent_cap(task.name)
            inflight = self._phase_pipeline_inflight(task.name)
            if cap > 0 and inflight >= cap:
                actions.append(f"drop_saturated:{task.name}")
                continue
            if host_lane_at_cap(self, task.name, hosts=controller_hosts):
                actions.append(f"drop_lane_cap:{task.name}")
                continue
            if AUTOMATION_MAX_SCHEDULED_DEPTH_PER_PHASE > 0:
                if phase_counts[task.name] >= AUTOMATION_MAX_SCHEDULED_DEPTH_PER_PHASE:
                    actions.append(f"drop_dup:{task.name}")
                    continue
            phase_counts[task.name] += 1
            meta["plan_generation"] = plan_generation
            task.metadata = meta
            kept.append(task)

        desired_set = []
        seen: set[str] = set()
        for phase in desired_phases:
            if phase in seen:
                continue
            seen.add(phase)
            desired_set.append(phase)

        # Reserve Widow-local structure slots so intake cannot consume the whole
        # prefetch budget while MR/EPB have actionable backlog.
        _widow_structure_reserve = ("mention_resolution", "entity_profile_build")
        reserved: list[str] = []
        for phase in _widow_structure_reserve:
            if phase in seen and int(pending.get(phase, 0) or 0) > 0:
                reserved.append(phase)
        enqueue_order = reserved + [p for p in desired_set if p not in reserved]

        ordered: list[Task] = []
        kept_by_phase: dict[str, list[Task]] = defaultdict(list)
        for t in kept:
            kept_by_phase[t.name].append(t)

        for phase in enqueue_order:
            ordered.extend(kept_by_phase.pop(phase, []))

        for phase, tasks in kept_by_phase.items():
            ordered.extend(tasks)

        self._rebuild_priority_queue(ordered)

        target = min(
            self.max_concurrent_tasks * prefetch_multiplier(),
            AUTOMATION_QUEUE_SOFT_CAP if AUTOMATION_QUEUE_SOFT_CAP > 0 else self.max_concurrent_tasks * prefetch_multiplier(),
        )
        if target <= 0:
            target = self.max_concurrent_tasks * prefetch_multiplier()

        # Heal ghost scheduled-depth counters when the asyncio queue is empty.
        # Superseded-task skips historically leaked depth and permanently blocked
        # AUTOMATION_MAX_SCHEDULED_DEPTH_PER_PHASE enqueues (queue_actions=[]).
        if self.task_queue.qsize() == 0:
            for _ph, _depth in list(self._scheduled_queue_depth_by_phase.items()):
                if int(_depth or 0) > 0:
                    actions.append(f"heal_sched_depth:{_ph}:{int(_depth)}")
                    self._scheduled_queue_depth_by_phase[_ph] = 0

        for phase in enqueue_order:
            if self._automation_queue_depth() >= target:
                break
            if stall_holds.get(phase, 0) > 0:
                actions.append(f"skip_stall:{phase}")
                continue
            if self._should_skip_redundant_phase_request(phase):
                actions.append(f"skip_redundant:{phase}")
                continue
            from shared.bulk_catchup_pause import bulk_catchup_pause_defers_phase

            if bulk_catchup_pause_defers_phase(phase):
                actions.append(f"drop_bulk_pause:{phase}")
                continue
            inflight = self._phase_pipeline_inflight(phase)
            cap = self._per_phase_scheduler_concurrent_cap(phase)
            if cap > 0 and inflight >= cap:
                actions.append(f"skip_cap:{phase}")
                continue
            if host_lane_at_cap(self, phase, hosts=controller_hosts):
                actions.append(f"skip_lane_cap:{phase}")
                continue
            if AUTOMATION_MAX_SCHEDULED_DEPTH_PER_PHASE > 0:
                queued = int(self._scheduled_queue_depth_by_phase.get(phase, 0) or 0)
                if queued >= AUTOMATION_MAX_SCHEDULED_DEPTH_PER_PHASE:
                    actions.append(f"skip_sched_depth:{phase}")
                    continue
            if phase not in self.schedules:
                actions.append(f"skip_no_schedule:{phase}")
                continue
            schedule = self.schedules[phase]
            task = Task(
                id=f"{phase}_{plan_generation}_{int(datetime.now(timezone.utc).timestamp())}",
                name=phase,
                priority=schedule.get("priority", TaskPriority.NORMAL),
                status=TaskStatus.PENDING,
                created_at=datetime.now(timezone.utc),
                max_retries=_phase_max_retries(phase),
                metadata={
                    "scheduled": True,
                    "controller": True,
                    "plan_generation": plan_generation,
                    "phase": schedule.get("phase", 0),
                    "lane_default": self._phase_default_lane(phase),
                    "resource_class": self._phase_resource_class(phase),
                },
            )
            if await self._enqueue_scheduled_task(task):
                actions.append(f"enqueue:{phase}")
                phase_counts[phase] += 1
            else:
                actions.append(f"enqueue_false:{phase}")

        controller.queue_actions_last_replan = actions

    def _scheduled_enqueue_paused(self) -> bool:
        """When True, skip adding new scheduled / chained / continuous tasks (allowlist still runs)."""
        if AUTOMATION_QUEUE_SOFT_CAP <= 0:
            return False
        return self._automation_queue_depth() >= AUTOMATION_QUEUE_SOFT_CAP

    def queue_collection_request(
        self, request_type: str = "url", url: str = "", source: str = ""
    ) -> None:
        """v8: Queue a URL or feed for the next collection cycle (e.g. from RAG/synthesis). Thread-safe append."""
        self._pending_collection_queue.append(
            {
                "type": request_type,
                "url": url,
                "source": source,
                "queued_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    def _load_pending_collection_queue(self) -> None:
        """v8: Load pending collection queue from DB (call on start)."""
        try:
            from shared.database.connection import get_db_connection_context

            with get_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT value FROM public.automation_state WHERE key = %s",
                        ("pending_collection_queue",),
                    )
                    row = cur.fetchone()
                if row and row[0] is not None and isinstance(row[0], list):
                    self._pending_collection_queue[:] = row[0]
                    logger.info(
                        "Loaded %s pending collection request(s) from DB",
                        len(self._pending_collection_queue),
                    )
        except Exception as e:
            logger.debug("Load pending_collection_queue: %s (table may not exist yet)", e)

    def persist_pending_collection_queue(self) -> None:
        """v8: Persist pending collection queue to DB (call on shutdown)."""
        try:
            from shared.database.connection import get_db_connection_context

            with get_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO public.automation_state (key, value, updated_at)
                        VALUES ('pending_collection_queue', %s::jsonb, NOW())
                        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                        """,
                        (
                            json.dumps(
                                [
                                    {
                                        k: v
                                        for k, v in req.items()
                                        if k in ("type", "url", "source", "queued_at")
                                    }
                                    for req in self._pending_collection_queue
                                ]
                            ),
                        ),
                    )
                conn.commit()
                if self._pending_collection_queue:
                    logger.info(
                        "Persisted %s pending collection request(s) to DB",
                        len(self._pending_collection_queue),
                    )
        except Exception as e:
            logger.debug("Persist pending_collection_queue: %s", e)

    async def _preflight_startup_health_check(self) -> None:
        """
        Before workers: confirm PostgreSQL is reachable via the **worker** pool (phases use it)
        and the **health** pool (standalone health_check). Retries a few times for transient startup.
        """
        if env_str("AUTOMATION_SKIP_STARTUP_PREFLIGHT", "").lower() in ("1", "true", "yes"):
            logger.warning(
                "AUTOMATION_SKIP_STARTUP_PREFLIGHT set — skipping startup DB preflight"
            )
            return

        from shared.database.connection import (
            get_db_connection_context,
            get_health_db_connection_context,
        )

        loop = asyncio.get_event_loop()
        try:
            attempts = max(1, env_int("AUTOMATION_STARTUP_HEALTH_CHECK_ATTEMPTS", 3))
        except ValueError:
            attempts = 3
        try:
            delay_sec = float(env_str("AUTOMATION_STARTUP_HEALTH_CHECK_DELAY_SEC", "2"))
        except ValueError:
            delay_sec = 2.0

        def _probe_both_pools() -> None:
            with get_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            with get_health_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()

        last_err: Exception | None = None
        for attempt in range(attempts):
            try:
                await loop.run_in_executor(None, _probe_both_pools)
                logger.info(
                    "Automation startup preflight: database OK (worker + health pools, attempt %s/%s)",
                    attempt + 1,
                    attempts,
                )
                return
            except Exception as e:
                last_err = e
                logger.warning(
                    "Automation startup preflight attempt %s/%s failed: %s",
                    attempt + 1,
                    attempts,
                    e,
                )
                if attempt + 1 < attempts:
                    await asyncio.sleep(delay_sec)

        raise RuntimeError(
            f"Automation startup preflight failed after {attempts} attempt(s): {last_err}"
        ) from last_err

    def _rebuild_automation_task_list(self) -> None:
        """``self.workers`` = phase dequeue workers + scheduler/health/metrics/organizer (for stop/cancel)."""
        self.workers = list(self._phase_worker_tasks) + list(self._background_automation_tasks)

    async def _sync_phase_worker_tasks(self) -> None:
        """
        Spawn or cancel asyncio workers so len(_phase_worker_tasks) == max_concurrent_tasks.
        Call after changing max_concurrent_tasks (dynamic allocation or scale up/down).
        """
        if not self.is_running:
            return
        target = max(1, int(self.max_concurrent_tasks))
        while len(self._phase_worker_tasks) < target:
            wid = f"worker-{self._worker_id_seq}"
            self._worker_id_seq += 1
            self._phase_worker_tasks.append(asyncio.create_task(self._worker(wid)))
        while len(self._phase_worker_tasks) > target:
            t = self._phase_worker_tasks.pop()
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
        self._rebuild_automation_task_list()

    async def start(self):
        """Start the automation manager"""
        logger.info("Starting Enterprise Automation Manager...")
        await self._preflight_startup_health_check()
        self._load_pending_collection_queue()
        self._phase_worker_tasks = []
        self._background_automation_tasks = []
        self.is_running = True

        await self._sync_phase_worker_tasks()

        from services.pipeline_controller import PipelineController, set_pipeline_controller

        controller = PipelineController()
        set_pipeline_controller(controller)
        controller_task = asyncio.create_task(controller.run(self))
        standalone_health = asyncio.create_task(self._standalone_health_check_loop())
        health_monitor = asyncio.create_task(self._health_monitor())
        metrics_collector = asyncio.create_task(self._metrics_collector())
        entity_organizer_loop = asyncio.create_task(self._entity_organizer_downtime_loop())
        self._background_automation_tasks = [
            controller_task,
            standalone_health,
            health_monitor,
            metrics_collector,
            entity_organizer_loop,
        ]
        self._rebuild_automation_task_list()

        logger.info(
            "Automation Manager started with PipelineController + %s phase dequeue workers",
            len(self._phase_worker_tasks),
        )

        # Keep the event loop running until shutdown (so worker/scheduler tasks keep running).
        # Without this, run_until_complete(automation.start()) returns and the thread exits.
        while self.is_running:
            await asyncio.sleep(1)

    async def stop(self):
        """Stop the automation manager gracefully"""
        logger.info("Stopping Automation Manager...")
        self.is_running = False

        # Cancel all workers
        for worker in self.workers:
            worker.cancel()

        # Wait for workers to finish
        await asyncio.gather(*self.workers, return_exceptions=True)

        self._phase_worker_tasks = []
        self._background_automation_tasks = []
        self.workers = []

        # Shutdown executor
        self.executor.shutdown(wait=True)

        logger.info("Automation Manager stopped")

    def request_phase(
        self,
        phase_name: str,
        domain: str | None = None,
        storyline_id: int | None = None,
        requested_activity_id: str | None = None,
        *,
        force_nightly_unified_pipeline: bool = False,
    ) -> None:
        """
        Request a phase to run (thread-safe). Call from coordinator or API.
        The scheduler will drain this queue and enqueue tasks with metadata.
        If requested_activity_id is set (e.g. from Monitor trigger), the worker
        will complete that activity when the task starts so Current activity shows the real task.

        For nightly_enrichment_context only: pass force_nightly_unified_pipeline=True to run
        run_nightly_unified_pipeline_drain even outside NIGHTLY_PIPELINE_* local hours (manual override).
        """
        try:
            self._phase_request_queue.put_nowait(
                {
                    "phase": phase_name,
                    "domain": domain,
                    "storyline_id": storyline_id,
                    "requested_activity_id": requested_activity_id,
                    "force_nightly_unified_pipeline": bool(force_nightly_unified_pipeline),
                }
            )
            ctrl = getattr(self, "pipeline_controller", None)
            if ctrl is not None:
                ctrl.request_replan()
        except Exception as e:
            logger.warning("AutomationManager request_phase failed: %s", e)

    def set_finance_orchestrator_getter(self, getter):
        """Set callable() -> finance orchestrator (used by research_topic_refinement when idle)."""
        self._get_finance_orchestrator = getter

    def get_phase_request_warning(self, phase_name: str) -> str | None:
        """
        If this phase is requested manually (e.g. from Monitor), check whether dependencies
        have run recently. Returns a warning string if running out of order may process
        incomplete data; returns None if OK.
        """
        if phase_name not in self.schedules:
            return None
        schedule = self.schedules[phase_name]
        depends_on = schedule.get("depends_on") or []
        if not depends_on:
            return None
        now = datetime.now(timezone.utc)
        unsatisfied = []
        for dep in depends_on:
            if dep not in self.schedules:
                continue
            dep_schedule = self.schedules[dep]
            if dep_schedule.get("last_run") is None:
                unsatisfied.append(f"{dep} (never run)")
                continue
            time_since = (now - dep_schedule["last_run"]).total_seconds()
            need = float(dep_schedule.get("estimated_duration", 60) or 60) * 0.5
            need = min(need, float(AUTOMATION_DEPENDENCY_SETTLE_CAP_SEC))
            if time_since < need:
                unsatisfied.append(f"{dep} (run {int(time_since)}s ago)")
        if not unsatisfied:
            return None
        return f"Dependencies may not be satisfied: {', '.join(unsatisfied)}. Task may process incomplete data."

    async def _worker(self, worker_id: str):
        """Worker process for task execution. Requests (governor/manual) run before scheduled tasks."""
        logger.info(f"Worker {worker_id} started")

        while self.is_running:
            task = None
            from_requested = False
            try:
                # Prefer user-requested tasks so "Request phase" is not starved by scheduled backlog
                try:
                    task = await asyncio.wait_for(self._requested_task_queue.get(), timeout=0.05)
                    from_requested = True
                except asyncio.TimeoutError:
                    _pq_item = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
                    task = _pq_item[2]

                if task:
                    meta = task.metadata or {}
                    ctrl = getattr(self, "pipeline_controller", None)
                    gen = meta.get("plan_generation")
                    if (
                        ctrl
                        and gen is not None
                        and not meta.get("requested_activity_id")
                        and not meta.get("operator_request")
                        and int(gen) < ctrl.plan_generation
                    ):
                        logger.debug(
                            "Skip superseded task %s (gen=%s < %s)",
                            task.name,
                            gen,
                            ctrl.plan_generation,
                        )
                        # Depth was bumped at enqueue; skipping must release it or
                        # reconcile permanently hits AUTOMATION_MAX_SCHEDULED_DEPTH.
                        if from_requested:
                            self._requested_queue_depth_by_phase[task.name] = max(
                                0,
                                int(self._requested_queue_depth_by_phase[task.name]) - 1,
                            )
                            self._requested_task_queue.task_done()
                        else:
                            self._scheduled_queue_depth_by_phase[task.name] = max(
                                0,
                                int(self._scheduled_queue_depth_by_phase[task.name]) - 1,
                            )
                            self.task_queue.task_done()
                        continue
                    if from_requested:
                        self._requested_queue_depth_by_phase[task.name] = max(
                            0,
                            int(self._requested_queue_depth_by_phase[task.name]) - 1,
                        )
                    elif not from_requested:
                        self._scheduled_queue_depth_by_phase[task.name] = max(
                            0,
                            int(self._scheduled_queue_depth_by_phase[task.name]) - 1,
                        )
                    await self._execute_task(task, worker_id)
                    if from_requested:
                        self._requested_task_queue.task_done()
                    else:
                        self.task_queue.task_done()

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                logger.info("Worker %s cancelled", worker_id)
                raise
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                await asyncio.sleep(1)

        logger.info(f"Worker {worker_id} stopped")

    @staticmethod
    def _phase_default_lane(phase_name: str) -> str:
        from shared.pipeline_resource_policy import get_phase_policy

        pol = get_phase_policy(phase_name)
        if pol and pol.requires_llm:
            return pol.execution_lane
        return "gpu" if phase_name in GPU_LANE_PHASES else "cpu"

    @staticmethod
    def _phase_resource_class(phase_name: str) -> str:
        from shared.pipeline_resource_policy import get_phase_policy, phase_resource_class

        if get_phase_policy(phase_name):
            return phase_resource_class(phase_name)
        if phase_name in GPU_LANE_PHASES:
            return "gpu_heavy"
        if phase_name in DB_HEAVY_PHASES:
            return "db_heavy"
        return "cpu_light"

    def _resolve_effective_lane(self, phase_name: str, resource_class: str) -> tuple[str, str]:
        """Lane policy from phase registry (PipelineController owns scheduling)."""
        return self._phase_default_lane(phase_name), "phase_policy"

    def _per_phase_scheduler_concurrent_cap(self, task_name: str) -> int:
        """Max workers that may run this phase at once (scheduler gate). 0 = unlimited."""
        overrides = _per_phase_concurrent_cap_overrides()
        if task_name in overrides:
            o = overrides[task_name]
            if o <= 0:
                return 0
            return min(self.max_concurrent_tasks, o)

        base = AUTOMATION_PER_PHASE_CONCURRENT_CAP
        if base <= 0:
            return 0
        if task_name not in _per_phase_concurrent_cap_phase_names():
            return 0
        try:
            from services.nightly_ingest_window_service import in_nightly_pipeline_window_est

            if in_nightly_pipeline_window_est():
                if task_name in _per_phase_nightly_cap_mult_exclude():
                    return min(self.max_concurrent_tasks, base)
                mult = env_int("AUTOMATION_PER_PHASE_CONCURRENT_NIGHTLY_MULT", 4)
                return min(self.max_concurrent_tasks, base * max(1, mult))
        except Exception:
            pass
        return min(self.max_concurrent_tasks, base)

    def _per_phase_execute_concurrent_cap(self, task: Task) -> int:
        """Cap at task start; nightly_sequential_drain is unlimited."""
        if (task.metadata or {}).get("nightly_sequential_drain"):
            return 0
        return self._per_phase_scheduler_concurrent_cap(task.name)

    def _update_processing_history(self, task_name: str, actual_duration: float):
        """Update processing history for adaptive timing"""
        if task_name not in self.metrics["processing_history"]:
            self.metrics["processing_history"][task_name] = []

        # Keep only last 10 runs
        history = self.metrics["processing_history"][task_name]
        history.append(actual_duration)
        if len(history) > 10:
            history.pop(0)

        self.metrics["processing_history"][task_name] = history

    def _get_input_volume_factor(self) -> float:
        """Calculate input volume factor based on recent article counts"""
        try:
            from shared.database.connection import get_db_connection_context

            recent_count = 0
            with get_db_connection_context() as conn:
                with conn.cursor() as cursor:
                    for schema in get_pipeline_schema_names_active():
                        cursor.execute(f"""
                            SELECT COUNT(*) FROM {schema}.articles
                            WHERE created_at > NOW() - INTERVAL '1 hour'
                        """)
                        recent_count += int(cursor.fetchone()[0] or 0)

            # Normalize to expected volume (100 articles per hour)
            expected_volume = 100
            volume_factor = max(0.5, min(2.0, recent_count / expected_volume))

            return volume_factor

        except Exception as e:
            logger.error(f"Error calculating input volume factor: {e}")
            return 1.0

    async def _execute_task(self, task: Task, worker_id: str):
        """Execute a task"""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)
        task.metadata = task.metadata or {}
        resource_class = task.metadata.get("resource_class") or self._phase_resource_class(task.name)
        task.metadata["resource_class"] = resource_class
        task.metadata["lane_default"] = task.metadata.get("lane_default") or self._phase_default_lane(
            task.name
        )
        effective_lane, lane_reason = self._resolve_effective_lane(task.name, resource_class)
        task.metadata["execution_lane"] = effective_lane
        task.metadata["lane_reason"] = lane_reason
        lane_token = None
        try:
            from shared.services.llm_service import push_llm_execution_lane

            lane_token = push_llm_execution_lane(effective_lane)
        except Exception:
            lane_token = None

        try:
            from shared.retired_phase_registry import is_hard_retired_schedule_phase

            if is_hard_retired_schedule_phase(task.name):
                logger.warning(
                    "Refusing hard-retired phase %s — not scheduled; "
                    "archived runners only via LEGACY_INTAKE_EXTRACTION_ENABLED / scripts",
                    task.name,
                )
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now(timezone.utc)
                task.metadata["retired_refuse"] = True
                return
        except Exception:
            pass

        try:
            from services.nightly_ingest_window_service import (
                in_nightly_enrichment_context_window_est,
                nightly_ingest_exclusive_automation_enabled,
                task_allowed_during_nightly_ingest_exclusive,
            )

            if (
                nightly_ingest_exclusive_automation_enabled()
                and in_nightly_enrichment_context_window_est()
                and not task_allowed_during_nightly_ingest_exclusive(task.name)
                and not (task.metadata or {}).get("nightly_sequential_drain")
            ):
                logger.debug("Nightly ingest exclusive window — deferring %s", task.name)
                task.status = TaskStatus.PENDING
                await self._enqueue_scheduled_task(
                    task,
                    bypass_nightly_cap=True,
                    bypass_schedule_depth_cap=True,
                )
                await asyncio.sleep(3)
                return
        except Exception as e:
            logger.debug("Nightly ingest exclusive gate: %s", e)

        # Reserve a per-phase slot before any await (e.g. ollama_semaphore); otherwise N workers can
        # all pass a naive "same_running >= cap" check then block on the semaphore and overrun the cap.
        per_phase_slot_held = False
        exec_cap = self._per_phase_execute_concurrent_cap(task)
        if exec_cap > 0:
            self._running_tasks_by_phase[task.name] += 1
            if int(self._running_tasks_by_phase[task.name] or 0) > exec_cap:
                self._running_tasks_by_phase[task.name] -= 1
                logger.debug(
                    "Per-phase concurrent cap — deferring %s (would exceed cap=%s)",
                    task.name,
                    exec_cap,
                )
                task.status = TaskStatus.PENDING
                task.started_at = None
                if self._discard_redundant_claim_extraction_when_at_cap(task, exec_cap):
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = datetime.now(timezone.utc)
                    logger.info(
                        "Discarded redundant %s (drain mode, cap=%s already satisfied; not re-queued)",
                        task.name,
                        exec_cap,
                    )
                    return
                await self._enqueue_scheduled_task(
                    task,
                    bypass_nightly_cap=True,
                    bypass_schedule_depth_cap=True,
                )
                await asyncio.sleep(1.5)
                return
            per_phase_slot_held = True

        def _release_per_phase_slot_if_held() -> None:
            nonlocal per_phase_slot_held
            if per_phase_slot_held:
                if self._running_tasks_by_phase.get(task.name, 0) > 0:
                    self._running_tasks_by_phase[task.name] -= 1
                per_phase_slot_held = False

        # Global process-RSS circuit breaker: one drain can grow from ~200MB to multi-GB
        # mid-run; never start non-exempt work once we are already over the pause floor.
        try:
            from shared.process_memory import process_rss_mb

            from config.runtime import env_str

            rss_now = process_rss_mb()
            pause_mb = float(env_str("AUTOMATION_RSS_PAUSE_MB", "1800") or "1800")
            from shared.process_memory import AUTOMATION_RSS_PAUSE_EXEMPT_PHASES

            _rss_exempt = AUTOMATION_RSS_PAUSE_EXEMPT_PHASES
            raw_block = (env_str("AUTOMATION_BLOCK_PHASES", "") or "").strip()
            _blocked = {x.strip() for x in raw_block.split(",") if x.strip()}
            if task.name in _blocked and not (task.metadata or {}).get(
                "nightly_sequential_drain"
            ):
                logger.warning(
                    "Deferring %s — listed in AUTOMATION_BLOCK_PHASES (UI memory protection)",
                    task.name,
                )
                _release_per_phase_slot_if_held()
                task.status = TaskStatus.PENDING
                await self._enqueue_scheduled_task(
                    task,
                    bypass_nightly_cap=True,
                    bypass_schedule_depth_cap=True,
                )
                await asyncio.sleep(30)
                return
            if (
                rss_now is not None
                and rss_now >= pause_mb
                and task.name not in _rss_exempt
                and not (task.metadata or {}).get("nightly_sequential_drain")
            ):
                logger.warning(
                    "Deferring %s — process RSS %.0f MB (pause gate %.0f)",
                    task.name,
                    rss_now,
                    pause_mb,
                )
                _release_per_phase_slot_if_held()
                task.status = TaskStatus.PENDING
                await self._enqueue_scheduled_task(
                    task,
                    bypass_nightly_cap=True,
                    bypass_schedule_depth_cap=True,
                )
                await asyncio.sleep(10)
                return
        except Exception:
            pass

        # Phases that call Ollama / shared LLM paths (or heavy GPU); yield to API + share ollama_semaphore.
        if task.name in OLLAMA_AUTOMATION_PHASES:
            try:
                from shared.services.api_request_tracker import should_yield_to_api

                if (
                    not (task.metadata or {}).get("nightly_sequential_drain")
                    and task.name not in _OLLAMA_YIELD_EXEMPT
                    and should_yield_to_api()
                ):
                    logger.debug(
                        f"Yielding to API — deferring {task.name} (web page load takes priority)"
                    )
                    _release_per_phase_slot_if_held()
                    task.status = TaskStatus.PENDING
                    await self._enqueue_scheduled_task(
                        task,
                        bypass_nightly_cap=True,
                        bypass_schedule_depth_cap=True,
                    )
                    await asyncio.sleep(5)  # Avoid tight loop — wait before worker picks next task
                    return
            except ImportError:
                pass
            # GPU temperature throttle: pause Ollama work if GPU is too hot
            try:
                from shared.gpu_metrics import (
                    GPU_THROTTLE_SLEEP_SECONDS,
                    should_throttle_ollama_for_lane,
                )

                effective_lane = (task.metadata or {}).get("execution_lane") or (
                    task.metadata or {}
                ).get("lane_default")
                if should_throttle_ollama_for_lane(effective_lane):
                    logger.warning(
                        "GPU temp high on %s lane — pausing Ollama task %s for %ss",
                        effective_lane or "gpu",
                        task.name,
                        GPU_THROTTLE_SLEEP_SECONDS,
                    )
                    await asyncio.sleep(GPU_THROTTLE_SLEEP_SECONDS)
                    if should_throttle_ollama_for_lane(effective_lane):
                        logger.warning("GPU still hot after pause — deferring %s", task.name)
                        _release_per_phase_slot_if_held()
                        task.status = TaskStatus.PENDING
                        await self._enqueue_scheduled_task(
                            task,
                            bypass_nightly_cap=True,
                            bypass_schedule_depth_cap=True,
                        )
                        return
            except ImportError:
                pass
            try:
                from services.content_refinement_queue_service import (
                    in_nightly_gpu_refinement_window_est,
                    nightly_gpu_refinement_exclusive_gpu_enabled,
                )

                if (
                    nightly_gpu_refinement_exclusive_gpu_enabled()
                    and in_nightly_gpu_refinement_window_est()
                    and not (task.metadata or {}).get("nightly_sequential_drain")
                ):
                    _nightly_ollama_allow = frozenset(
                        x.strip()
                        for x in env_str(
                            "NIGHTLY_GPU_REFINEMENT_OLLAMA_ALLOW",
                            "nightly_enrichment_context",
                        ).split(",")
                        if x.strip()
                    )
                    if task.name not in _nightly_ollama_allow:
                        logger.debug(
                            "Nightly GPU exclusive window — deferring Ollama task %s",
                            task.name,
                        )
                        _release_per_phase_slot_if_held()
                        task.status = TaskStatus.PENDING
                        await self._enqueue_scheduled_task(
                            task,
                            bypass_nightly_cap=True,
                            bypass_schedule_depth_cap=True,
                        )
                        await asyncio.sleep(5)
                        return
            except Exception as e:
                logger.debug("Nightly GPU exclusive Ollama gate: %s", e)
            await self.ollama_semaphore.acquire()

        logger.info(
            "Worker %s executing task: %s (lane=%s reason=%s class=%s)",
            worker_id,
            task.name,
            effective_lane,
            lane_reason,
            resource_class,
        )
        try:
            # Increment worker counters and register the activity-feed row INSIDE this try so
            # the finally below always reverts them. Previously these ran before the try, so a
            # cancellation in this window (replan/shutdown storm) leaked the per-phase counter
            # and left an orphaned "running" row that the monitor showed forever.
            if not per_phase_slot_held:
                self._running_tasks_by_phase[task.name] += 1
            self._running_tasks_by_lane[effective_lane] += 1
            try:
                from services.activity_feed_service import get_activity_feed

                feed = get_activity_feed()
                requested_id = (task.metadata or {}).get("requested_activity_id")
                if requested_id:
                    feed.complete(requested_id, success=True)
                message = self._activity_message(task)
                feed.add_current(
                    self._activity_feed_activity_id(task),
                    message,
                    task_name=task.name,
                    domain=task.metadata.get("domain"),
                    storyline_id=task.metadata.get("storyline_id"),
                    loops_processed=0,
                )
            except Exception as e:
                logger.debug("Activity feed add_current: %s", e)

            # Execute task based on type
            if task.name == "collection_cycle":
                await self._execute_collection_cycle(task)
            elif task.name == "document_processing":
                await self._execute_document_processing(task)
            elif task.name == "storyline_synthesis":
                await self._execute_storyline_synthesis(task)
            elif task.name == "daily_briefing_synthesis":
                await self._execute_daily_briefing_synthesis(task)
            elif task.name == "nightly_enrichment_context":
                await self._execute_nightly_enrichment_context(task)
            elif task.name == "content_enrichment":
                await self._execute_content_enrichment(task)
            elif task.name == "context_sync":
                await self._execute_context_sync(task)
            elif task.name == "entity_profile_sync":
                await self._execute_entity_profile_sync(task)
            elif task.name == "claim_extraction":
                await self._execute_claim_extraction(task)
            elif task.name == "legislative_references":
                await self._execute_legislative_references(task)
            elif task.name == "claims_to_facts":
                await self._execute_claims_to_facts(task)
            elif task.name == "claim_evidence_appraisal":
                await self._execute_claim_evidence_appraisal(task)
            elif task.name == "editorial_reduction_pass":
                await self._execute_editorial_reduction_pass(task)
            elif task.name == "editorial_narrative_pass":
                await self._execute_editorial_narrative_pass(task)
            elif task.name == "editorial_research_pass":
                await self._execute_editorial_research_pass(task)
            elif task.name == "claim_subject_gap_refresh":
                await self._execute_claim_subject_gap_refresh(task)
            elif task.name == "extracted_claims_dedupe":
                await self._execute_extracted_claims_dedupe(task)
            elif task.name == "event_tracking":
                await self._execute_event_tracking(task)
            elif task.name == "investigation_report_refresh":
                await self._execute_investigation_report_refresh(task)
            elif task.name == "cross_domain_synthesis":
                await self._execute_cross_domain_synthesis(task)
            elif task.name == "event_coherence_review":
                await self._execute_event_coherence_review(task)
            elif task.name == "entity_profile_build":
                await self._execute_entity_profile_build(task)
            elif task.name == "pattern_recognition":
                await self._execute_pattern_recognition(task)
            elif task.name == "embeddings_worker":
                await self._execute_embeddings_worker(task)
            elif task.name == "macro_series_refresh":
                await self._execute_macro_series_refresh(task)
            elif task.name == "external_events_sync":
                await self._execute_external_events_sync(task)
            elif task.name == "sanctions_refresh":
                await self._execute_sanctions_refresh(task)
            elif task.name == "arc_report_generation":
                await self._execute_arc_report_generation(task)
            elif task.name == "longitudinal_matview_refresh":
                await self._execute_longitudinal_matview_refresh(task)
            elif task.name == "entity_dossier_compile":
                await self._execute_entity_dossier_compile(task)
            elif task.name == "entity_position_tracker":
                await self._execute_entity_position_tracker(task)
            elif task.name == "metadata_enrichment":
                await self._execute_metadata_enrichment(task)
            elif task.name == "entity_organizer":
                await self._execute_entity_organizer(task)
            elif task.name == "graph_connection_distillation":
                await self._execute_graph_connection_distillation(task)
            elif task.name == "embedding_link_candidates":
                await self._execute_embedding_link_candidates(task)
            elif task.name == "collision_sampling":
                await self._execute_collision_sampling(task)
            elif task.name == "stimulus_rag":
                await self._execute_stimulus_rag(task)
            elif task.name == "protein_harden":
                await self._execute_protein_harden(task)
            elif task.name == "graph_link_drift_review":
                await self._execute_graph_link_drift_review(task)
            elif task.name == "digest_generation":
                await self._execute_digest_generation(task)
            elif task.name == "data_cleanup":
                await self._execute_data_cleanup(task)
            elif task.name == "health_check":
                await self._execute_health_check(task)
            elif task.name == "rss_feed_health":
                await self._execute_rss_feed_health(task)
            elif task.name == "rolling_arc_refresh":
                await self._execute_rolling_arc_refresh(task)
            elif task.name == "pending_db_flush":
                await self._execute_pending_db_flush(task)
            elif task.name == "rag_enhancement":
                await self._execute_rag_enhancement(task)
            elif task.name == "cache_cleanup":
                await self._execute_cache_cleanup(task)
            elif task.name == "ml_processing":
                await self._execute_ml_processing(task)
            elif task.name == "sentiment_analysis":
                await self._execute_sentiment_analysis(task)
            elif task.name == "storyline_processing":
                await self._execute_storyline_processing(task)
            elif task.name == "storyline_automation":
                await self._execute_storyline_automation(task)
            elif task.name == "storyline_review_agent":
                await self._execute_storyline_review_agent(task)
            elif task.name == "storyline_membership_review":
                await self._execute_storyline_membership_review(task)
            elif task.name == "storyline_hygiene":
                await self._execute_storyline_hygiene(task)
            elif task.name == "storyline_enrichment":
                await self._execute_storyline_enrichment(task)
            elif task.name == "entity_extraction":
                await self._execute_entity_extraction(task)
            elif task.name == "unified_intake_extraction":
                await self._execute_unified_intake_extraction(task)
            elif task.name == "spine_sql_tail":
                await self._execute_spine_sql_tail(task)
            elif task.name == "mention_resolution":
                await self._execute_mention_resolution(task)
            elif task.name == "quality_scoring":
                await self._execute_quality_scoring(task)
            elif task.name == "timeline_generation":
                await self._execute_timeline_generation(task)
            elif task.name == "topic_clustering":
                await self._execute_topic_clustering(task)
            elif task.name == "event_extraction":
                await self._execute_event_extraction_v5(task)
            elif task.name == "event_deduplication":
                await self._execute_event_deduplication_v5(task)
            elif task.name == "chronological_events_catchup":
                await self._execute_chronological_events_catchup(task)
            elif task.name == "story_continuation":
                await self._execute_story_continuation_v5(task)
            elif task.name == "watchlist_alerts":
                await self._execute_watchlist_alerts_v5(task)
            elif task.name == "story_enhancement":
                await self._execute_story_enhancement(task)
            elif task.name == "content_refinement_queue":
                await self._execute_content_refinement_queue(task)
            elif task.name == "entity_enrichment":
                await self._execute_entity_enrichment(task)
            elif task.name == "pattern_matching":
                await self._execute_pattern_matching(task)
            elif task.name == "research_topic_refinement":
                await self._execute_research_topic_refinement(task)
            elif task.name == "editorial_document_generation":
                await self._execute_editorial_document_generation(task)
            elif task.name == "editorial_briefing_generation":
                await self._execute_editorial_briefing_generation(task)
            elif task.name == "narrative_thread_build":
                await self._execute_narrative_thread_build(task)
            elif task.name == "storyline_discovery":
                await self._execute_storyline_discovery(task)
            elif task.name == "proactive_detection":
                await self._execute_proactive_detection(task)
            elif task.name == "storyline_assembly":
                await self._execute_storyline_assembly(task)
            elif task.name == "fact_verification":
                await self._execute_fact_verification(task)
            else:
                raise ValueError(f"Unknown task type: {task.name}")

            # Mark as completed
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc)
            self.metrics["tasks_completed"] += 1
            if task.name in self.schedules:
                self.schedules[task.name]["last_run"] = task.completed_at
            if not (task.metadata or {}).get("skip_automation_run_history"):
                _persist_automation_run(
                    task.name,
                    task.started_at,
                    task.completed_at,
                    True,
                    None,
                    metadata=task.metadata or {},
                )
            # Record completion for last-60m run counts (used by monitoring timeline).
            if not (task.metadata or {}).get("skip_automation_run_history"):
                try:
                    cutoff = datetime.now(timezone.utc) - timedelta(minutes=60)
                    dq = self._phase_run_times_last_60m[task.name]
                    dq.append(task.completed_at)
                    while dq and dq[0] < cutoff:
                        dq.popleft()
                    dq_lane = self._lane_run_times_last_60m[effective_lane]
                    dq_lane.append(task.completed_at)
                    while dq_lane and dq_lane[0] < cutoff:
                        dq_lane.popleft()
                except Exception:
                    pass

            processing_time = (task.completed_at - task.started_at).total_seconds()
            self._update_avg_processing_time(processing_time)
            self._update_processing_history(task.name, processing_time)
            logger.info(
                "Task %s completed in %.2fs (Phase %s)",
                task.name,
                processing_time,
                task.metadata.get("phase", 0),
            )

            try:
                from services.backlog_metrics import (
                    RAW_PENDING_COUNT_KEYS,
                    invalidate_backlog_metrics_cache_throttled,
                )

                if task.name in RAW_PENDING_COUNT_KEYS:
                    invalidate_backlog_metrics_cache_throttled(min_interval_seconds=30.0)
                    try:
                        from services.monitor_backlog_snapshot_service import (
                            maybe_refresh_monitor_backlog_snapshot_after_drain,
                        )

                        maybe_refresh_monitor_backlog_snapshot_after_drain()
                    except Exception:
                        pass
            except Exception:
                pass

        except Exception as e:
            # Handle task failure
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.retry_count += 1
            self.metrics["tasks_failed"] += 1
            finished_at = datetime.now(timezone.utc)
            if task.name in self.schedules:
                self.schedules[task.name]["last_run"] = finished_at
            _persist_automation_run(
                task.name,
                task.started_at,
                finished_at,
                False,
                str(e),
                metadata=task.metadata or {},
            )
            # Record failure for last-60m run counts (used by monitoring timeline).
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(minutes=60)
                dq = self._phase_run_times_last_60m[task.name]
                dq.append(finished_at)
                while dq and dq[0] < cutoff:
                    dq.popleft()
                dq_lane = self._lane_run_times_last_60m[effective_lane]
                dq_lane.append(finished_at)
                while dq_lane and dq_lane[0] < cutoff:
                    dq_lane.popleft()
            except Exception:
                pass

            logger.error(f"Task {task.name} failed: {e}")

            # Retry if under max retries (config-driven backoff per phase)
            try:
                from services.phase_retry_silence_service import (
                    backoff_seconds_for_retry,
                    max_retries_for_phase,
                )

                task.max_retries = max_retries_for_phase(task.name)
            except Exception:
                pass
            if task.retry_count < task.max_retries:
                task.status = TaskStatus.RETRYING
                try:
                    from services.phase_retry_silence_service import backoff_seconds_for_retry

                    delay = backoff_seconds_for_retry(task.name, task.retry_count)
                except Exception:
                    delay = min(60 * max(1, task.retry_count), 300)
                await asyncio.sleep(delay)
                await self._enqueue_scheduled_task(
                    task,
                    bypass_nightly_cap=True,
                    bypass_schedule_depth_cap=True,
                )
                logger.info(f"Retrying task {task.name} (attempt {task.retry_count + 1})")

        finally:
            # Keep per-phase worker counts in sync even when task fails.
            try:
                if self._running_tasks_by_phase.get(task.name, 0) > 0:
                    self._running_tasks_by_phase[task.name] -= 1
            except Exception:
                pass
            try:
                if self._running_tasks_by_lane.get(effective_lane, 0) > 0:
                    self._running_tasks_by_lane[effective_lane] -= 1
            except Exception:
                pass
            if task.name in OLLAMA_AUTOMATION_PHASES:
                self.ollama_semaphore.release()
            if lane_token is not None:
                try:
                    from shared.services.llm_service import pop_llm_execution_lane

                    pop_llm_execution_lane(lane_token)
                except Exception:
                    pass
            try:
                from services.activity_feed_service import get_activity_feed

                get_activity_feed().complete(
                    self._activity_feed_activity_id(task),
                    success=(task.status == TaskStatus.COMPLETED),
                    error_message=getattr(task, "error_message", None),
                )
            except Exception as e:
                logger.debug("Activity feed complete: %s", e)
            # Store task result
            self.tasks[task.id] = task
            ctrl = getattr(self, "pipeline_controller", None)
            if ctrl is not None:
                ctrl.notify_worker_done()

    _MONITOR_STABLE_ACTIVITY_PHASES = frozenset(
        {
            "nightly_enrichment_context",
            "collection_cycle",
            "unified_intake_extraction",
            "entity_profile_build",
            "storyline_assembly",
            "content_enrichment",
            "mention_resolution",
            "claim_extraction",
            "event_extraction_v5",
            "entity_extraction",
        }
    )
    # Drain phases skip the outer task-level history row; each batch completion is persisted separately.
    _BATCH_RUN_HISTORY_PHASES = frozenset(
        {
            "unified_intake_extraction",
            "entity_profile_build",
            "claim_extraction",
            "claims_to_facts",
            "content_enrichment",
            "document_processing",
            "spine_sql_tail",
            "storyline_membership_review",
            "storyline_hygiene",
            "story_continuation",
            "chronological_events_catchup",
        }
    )

    def _activity_feed_activity_id(self, task: Task) -> str:
        """
        Stable id for phases that should appear once in Monitor \"Current activity\".
        (Otherwise each Task UUID creates a separate row; nightly can enqueue up to MAX_QUEUED.)
        """
        if task.name in self._MONITOR_STABLE_ACTIVITY_PHASES:
            return f"phase:{task.name}"
        return task.id

    async def _record_phase_batch_loop(
        self,
        task: Task,
        *,
        loops_processed: int,
        **stats: Any,
    ) -> None:
        """Increment batch-loop counter for Monitor current activity (does not reset started_at)."""
        task.metadata = task.metadata or {}
        task.metadata["loops_processed"] = loops_processed
        task.metadata["iteration_index"] = loops_processed
        for key, value in stats.items():
            if value is not None:
                task.metadata[key] = value
        try:
            from shared.monitor_run_vocabulary import (
                RunHistoryStatus,
                emit_phase_run_event,
                normalize_phase_run_event,
            )
            from shared.services.phase_batch_run_history import batch_stats_had_work

            batch_finished = datetime.now(timezone.utc)
            batch_started = task.metadata.get("_batch_run_started_at")
            if batch_started is None:
                batch_started = task.started_at or batch_finished
            # claim_extraction: never persist empty batch_rounds. Historical spam (~160/hr on
            # Jul 15–16) came from allow_empty=True while PopOS cycled ~every 15–20s with a
            # probe/batch race that wrote contexts=0 rows into automation_run_history.
            allow_empty = task.name in self._BATCH_RUN_HISTORY_PHASES
            if task.name == "claim_extraction":
                _ctx = int(stats.get("contexts_processed") or 0)
                _cl = int(stats.get("claims_inserted") or 0)
                if _ctx <= 0 and _cl <= 0:
                    allow_empty = False
            should_emit_history = allow_empty or batch_stats_had_work(stats)
            event = normalize_phase_run_event(
                task.name,
                loops_processed,
                started_at=batch_started,
                finished_at=batch_finished,
                scheduler_path="automation_manager",
                run_history_status=RunHistoryStatus.BATCH_ROUND,
                allow_empty=allow_empty,
                **stats,
            )
            if should_emit_history:
                persisted = await emit_phase_run_event(
                    event,
                    activity_id=self._activity_feed_activity_id(task),
                    base_message=self._activity_message(task),
                    allow_empty_history=allow_empty,
                )
            else:
                from services.activity_feed_service import get_activity_feed
                from shared.monitor_run_vocabulary import format_activity_message

                feed = get_activity_feed()
                feed.update_current_progress(
                    self._activity_feed_activity_id(task),
                    message=format_activity_message(self._activity_message(task), event),
                    **event.activity_payload(),
                )
                persisted = False
            task.metadata["_batch_run_started_at"] = batch_finished
            try:
                from shared.monitor_run_vocabulary import is_measurable_run_history_row

                if persisted or is_measurable_run_history_row(
                    event.to_metadata(),
                    started_at=event.started_at,
                    finished_at=event.finished_at,
                ):
                    cutoff = datetime.now(timezone.utc) - timedelta(minutes=60)
                    dq = self._phase_run_times_last_60m[task.name]
                    dq.append(batch_finished)
                    while dq and dq[0] < cutoff:
                        dq.popleft()
                    self._measurable_runs_60m_sql_cache["at"] = 0.0
            except Exception:
                pass
        except Exception as e:
            logger.debug("Activity feed batch progress: %s", e)

    def _make_batch_progress_callback(self, task: Task):
        async def _on_batch(loops_processed: int, **stats: Any) -> None:
            await self._record_phase_batch_loop(task, loops_processed=loops_processed, **stats)

        return _on_batch

    @staticmethod
    def _stamp_monitor_batch_throughput(
        task: Task,
        *,
        round_processed: int,
        items_processed: int | None = None,
        **extra: Any,
    ) -> None:
        """Mark task metadata so Monitor measured rows/run can sample this run.

        ``query_measured_rows_per_run_by_phase`` requires ``batch=true`` and a
        positive iteration throughput key (prefer ``round_processed`` = batch budget).
        """
        if not isinstance(getattr(task, "metadata", None), dict):
            task.metadata = {}
        rp = max(0, int(round_processed or 0))
        task.metadata["batch"] = True
        task.metadata["round_processed"] = rp
        if items_processed is not None:
            task.metadata["items_processed"] = int(items_processed)
        for key, value in extra.items():
            if value is not None:
                task.metadata[key] = value

    def _activity_message(self, task: Task) -> str:
        """Human-readable one-line message for monitoring UI."""
        meta = task.metadata or {}
        domain = meta.get("domain")
        storyline_id = meta.get("storyline_id")
        name = task.name
        if name == "collection_cycle":
            return "Collection cycle (RSS, enrichment, documents, pending queue)"
        if name == "storyline_synthesis":
            return "Storyline synthesis (Wikipedia-style)"
        if name == "daily_briefing_synthesis":
            return "Daily briefing synthesis"
        if name == "context_sync":
            return f"Syncing articles to contexts ({domain or 'all domains'})"
        if name == "storyline_discovery":
            return "Discovering new storylines from article clusters"
        if name == "proactive_detection":
            return "Proactive detection (emerging storylines)"
        if name == "pending_db_flush":
            return "Flushing pending DB writes (local spill file → automation_run_history)"
        if name == "fact_verification":
            return "Fact verification (recent claims)"
        if name == "storyline_automation":
            if storyline_id and domain:
                return f"Storyline automation (storyline {storyline_id}, {domain})"
            return f"Storyline automation ({domain or 'all'})"
        if name == "storyline_enrichment":
            if storyline_id and domain:
                return f"Storyline enrichment / full history (storyline {storyline_id}, {domain})"
            return "Storyline enrichment (full-history, all domains)"
        if name == "entity_profile_sync":
            return f"Syncing entity profiles ({domain or 'all domains'})"
        if name == "entity_profile_build":
            return "Building entity profiles from contexts"
        if name == "entity_dossier_compile":
            return "Compiling entity dossiers (people/orgs)"
        if name == "entity_position_tracker":
            return "Extracting entity positions (stances/votes)"
        if name == "metadata_enrichment":
            return "Metadata enrichment (language, categories, quality)"
        if name == "claim_extraction":
            return "Extracting claims from contexts"
        if name == "legislative_references":
            return "Congress.gov bill snapshots (citations in articles)"
        if name == "event_tracking":
            return f"Tracking events ({domain or 'all'})"
        if name == "cross_domain_synthesis":
            return "Cross-domain synthesis"
        if name == "narrative_thread_build":
            return "Building narrative threads (cross-storyline arcs)"
        if name == "entity_organizer":
            return "Entity organizer (cleanup + relationships)"
        if name == "graph_connection_distillation":
            return "Graph connection distillation (proposal queue → merges / links)"
        if name == "entity_enrichment":
            return "Running entity enrichment"
        if name == "pattern_matching":
            return "Running watch pattern matching"
        if name == "story_enhancement":
            return "Running story enhancement cycle"
        if name == "topic_clustering":
            return "Topic clustering"
        if name == "ml_processing":
            return "ML processing (summaries, features)"
        if name == "entity_extraction":
            return "Entity extraction"
        if name == "unified_intake_extraction":
            return "Unified intake extraction (entities, events, claims, scoring)"
        if name == "event_extraction":
            return "Event extraction"
        if name == "story_continuation":
            return "Story continuation"
        if name == "watchlist_alerts":
            return "Generating watchlist alerts"
        if name == "data_cleanup":
            return "Data cleanup"
        if name == "health_check":
            return "Health check"
        if name == "rss_feed_health":
            return "RSS feed health review"
        if name == "rolling_arc_refresh":
            return "Rolling 12m arc refresh"
        if name == "nightly_enrichment_context":
            return "Nightly pipeline (enrichment → context sync → ~70B summaries)"
        if name == "cache_cleanup":
            return "Cache cleanup"
        if name == "digest_generation":
            return "Digest generation"
        # Generic fallback
        if domain:
            return f"{name.replace('_', ' ').title()} ({domain})"
        return name.replace("_", " ").title()

    async def _execute_rss_processing(self, task: Task):
        """Execute RSS processing: use domain feeds (collect_rss_feeds) for all active pipeline domains."""
        import asyncio

        from collectors.rss_collector import collect_rss_feeds

        try:
            loop = asyncio.get_event_loop()
            activity = await loop.run_in_executor(None, collect_rss_feeds)
            if activity > 0:
                logger.info(
                    "RSS processing: %s articles touched (new inserts + same-URL updates)",
                    activity,
                )
        except Exception as e:
            logger.warning(f"RSS processing failed: {e}")

    async def _execute_content_enrichment(self, task: Task):
        """Fetch full article text with trafilatura for articles with short content."""
        import asyncio

        task.metadata = task.metadata or {}
        try:
            from services.nightly_ingest_window_service import in_nightly_pipeline_window_est

            if in_nightly_pipeline_window_est() and not task.metadata.get(
                "nightly_sequential_drain"
            ):
                # Standalone CE no-ops overnight; nightly_enrichment_context owns the drain.
                # Skip outer history so Monitor Recent activity is not paired with a non-measurable
                # sub-1s empty row that leaves runs_1h unchanged.
                task.metadata["skip_automation_run_history"] = True
                try:
                    from services.activity_feed_service import get_activity_feed

                    get_activity_feed().update_current_progress(
                        self._activity_feed_activity_id(task),
                        message=(
                            "Content enrichment deferred "
                            "(nightly pipeline owns drain)"
                        ),
                    )
                except Exception:
                    pass
                logger.debug(
                    "Content enrichment: nightly pipeline window — handled by nightly_enrichment_context"
                )
                return
        except Exception:
            pass

        from shared.content_enrichment_drain import run_content_enrichment_batch

        # Batch row is the measurable runs_1h signal; skip empty outer task row.
        task.metadata["skip_automation_run_history"] = True
        try:
            default_bs = 60
            try:
                from shared.adaptive_batch_policy import resolve_adaptive_batch

                default_bs, _meta = resolve_adaptive_batch("content_enrichment", default_bs)
            except Exception:
                pass
            enrich_bs = max(1, int(default_bs))
            async with self._content_enrichment_lock:
                loop = asyncio.get_event_loop()
                # Queue-first claim → scoped enrich → finalize (U5)
                enriched = await loop.run_in_executor(
                    None, lambda bs=enrich_bs: run_content_enrichment_batch(batch_size=bs)
                )
            enriched_n = int(enriched or 0)
            # Always emit batch_round (allow_empty via _BATCH_RUN_HISTORY_PHASES) so idle /
            # fast completions still increment runs_1h — matching activity "ran Xm ago".
            await self._record_phase_batch_loop(
                task,
                loops_processed=1,
                round_processed=enriched_n,
                processed=enriched_n,
            )
        except Exception as e:
            logger.warning(f"Content enrichment failed: {e}")

    async def _execute_document_collection(self, task: Task):
        """Discover government and academic PDF documents (invoked from collection_cycle)."""
        import asyncio

        try:
            from services.document_collector_service import collect_documents

            loop = asyncio.get_event_loop()
            count = await loop.run_in_executor(None, lambda: collect_documents(max_per_source=15))
            if count > 0:
                logger.info(f"Document collection (v8): {count} new documents")
        except Exception as e:
            logger.warning(f"Document collection failed: {e}")

    async def _execute_document_processing(self, task: Task):
        """Process pending PDFs (download, extract text, sections, entities)."""
        import asyncio
        from datetime import datetime, timezone

        from shared.services.phase_batch_run_history import record_phase_batch_completion_async

        try:
            from shared.process_memory import process_rss_mb
            from services.backlog_metrics import get_backlog_count
            from services.document_processing_service import process_unprocessed_documents

            rss = process_rss_mb()
            pause_mb = float(
                __import__("config.runtime", fromlist=["env_str"]).env_str(
                    "AUTOMATION_RSS_PAUSE_MB", "1800"
                )
                or "1800"
            )
            if rss is not None and rss >= pause_mb:
                logger.warning(
                    "Skipping document_processing — process RSS %.0f MB (gate %.0f)",
                    rss,
                    pause_mb,
                )
                return

            # Adaptive batch ceiling; scale down when backlog is small or RSS memory is high
            backlog = get_backlog_count("document_processing") or 0
            try:
                from shared.adaptive_batch_policy import resolve_adaptive_batch

                limit, _meta = resolve_adaptive_batch("document_processing", 10)
            except Exception:
                limit = 10
            if backlog <= 10:
                limit = min(int(limit), 3)
            elif backlog <= 20:
                limit = min(int(limit), 6)
            if rss is not None and rss >= min(1200.0, pause_mb * 0.7):
                limit = min(int(limit), 1)
            started = datetime.now(timezone.utc)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda lim=int(limit): process_unprocessed_documents(limit=lim)
            )
            finished = datetime.now(timezone.utc)
            count = int(result.get("processed", 0) if isinstance(result, dict) else 0)
            if count > 0:
                await record_phase_batch_completion_async(
                    "document_processing",
                    started,
                    finished,
                    stats={"round_processed": count, "processed": count},
                )
                logger.info(f"Document processing (v8): {count} documents processed")
        except Exception as e:
            logger.warning(f"Document processing failed: {e}")

    async def _execute_collection_cycle(self, task: Task):
        """v8: Run collection sub-steps sequentially; drain enrichment and document processing; drain pending_collection_queue."""
        import asyncio

        asyncio.get_event_loop()
        dummy = Task(
            id=task.id + "_sub",
            name=task.name,
            priority=task.priority,
            status=TaskStatus.PENDING,
            created_at=task.created_at,
            metadata=task.metadata or {},
        )
        # 1. RSS fetch (optional: Widow / cron runs collect_rss_feeds; main GPU host skips duplicate RSS)
        backfill_pause = pipeline_backfill_collection_should_pause()
        if backfill_pause:
            sl = pipeline_backfill_status_line()
            if sl:
                logger.warning("Collection cycle: %s", sl)
        skip_rss = env_str("AUTOMATION_SKIP_RSS_IN_COLLECTION_CYCLE", "").lower() in (
            "1",
            "true",
            "yes",
        ) or backfill_pause
        if skip_rss:
            logger.info(
                "Collection cycle: skipping RSS (%s)",
                "PIPELINE_BACKFILL_MODE pause"
                if backfill_pause
                else "AUTOMATION_SKIP_RSS_IN_COLLECTION_CYCLE",
            )
        else:
            try:
                await self._execute_rss_processing(dummy)
            except Exception as e:
                logger.warning(f"Collection cycle RSS step failed: {e}")
            # Fresh intake invalidates stale stall evidence: give every auto-silenced
            # phase another chance. Anything still broken re-earns its silence via the
            # failing-streak threshold.
            try:
                from services.phase_retry_silence_service import lift_auto_silences

                lifted = await asyncio.to_thread(
                    lambda: lift_auto_silences(reason="rss_intake", force=True)
                )
                if lifted:
                    self._apply_automation_disabled_schedules()
                    logger.info("RSS intake lifted auto-silence for: %s", lifted)
            except Exception as e:
                logger.debug("collection_cycle silence lift: %s", e)
        # 2. Content enrichment — PipelineController schedules standalone content_enrichment
        try:
            from services.nightly_ingest_window_service import in_nightly_pipeline_window_est

            skip_enrich_nightly = in_nightly_pipeline_window_est()
        except Exception:
            skip_enrich_nightly = False
        if not skip_enrich_nightly:
            try:
                ctrl = getattr(self, "pipeline_controller", None)
                if ctrl is not None:
                    ctrl.request_replan()
            except Exception as e:
                logger.debug("collection_cycle post-RSS replan: %s", e)
        # Stir the beaker when intake preprocess is already clear (RSS done, backlog low).
        try:
            from shared.chemistry_beaker import kickoff_beaker_phases

            kickoff_beaker_phases(self, reason="collection_cycle_post_rss")
        except Exception as e:
            logger.debug("collection_cycle beaker kickoff: %s", e)
        # 3. Document collection (skip during backfill pause — avoid adding new external documents)
        if not backfill_pause:
            try:
                await self._execute_document_collection(dummy)
            except Exception as e:
                logger.warning(f"Collection cycle document collection failed: {e}")
        else:
            logger.info("Collection cycle: skipping document collection (PIPELINE_BACKFILL_MODE pause)")
        # 4. Document processing — loop until drained or cap
        loops_processed = 0
        max_doc_iters = 20
        for _ in range(max_doc_iters):
            if not get_all_pending_counts:
                break
            try:
                counts = get_all_pending_counts()
                if (counts.get("document_processing") or 0) == 0:
                    break
            except Exception:
                break
            try:
                await self._execute_document_processing(dummy)
                loops_processed += 1
                await self._record_phase_batch_loop(
                    task,
                    loops_processed=loops_processed,
                    step="document_processing",
                )
            except Exception as e:
                logger.warning(f"Collection cycle document processing failed: {e}")
                break
        # 5. Drain pending collection queue (URLs/feeds queued by RAG/synthesis)
        drained = 0
        if backfill_pause:
            qn = len(self._pending_collection_queue)
            if qn:
                logger.info(
                    "Collection cycle: deferring %s pending collection queue item(s) (backfill pause)",
                    qn,
                )
        while not backfill_pause and self._pending_collection_queue:
            req = self._pending_collection_queue.pop(0)
            drained += 1
            try:
                req_type = req.get("type") or "url"
                url = req.get("url") or ""
                source = req.get("source") or ""
                if req_type == "url" and url:
                    # Optional: add URL to document ingest or RSS; for now just log
                    logger.info(
                        "Collection cycle drained request: type=%s url=%s source=%s",
                        req_type,
                        url[:80],
                        source,
                    )
            except Exception as e:
                logger.debug("Pending collection item failed: %s", e)
        if drained:
            logger.info("Collection cycle drained %s pending collection request(s)", drained)

    async def _execute_storyline_synthesis(self, task: Task):
        from shared.retired_phase_dispatch import dispatch_retired_automation_phase

        await dispatch_retired_automation_phase(self, "storyline_synthesis", task)

    async def _execute_daily_briefing_synthesis(self, task: Task):
        """Fully retired — Briefings reads desk-promoted / RAG editorial fields."""
        logger.info(
            "daily_briefing_synthesis fully retired; use desk promote + content_refinement_queue"
        )
        return

    async def _execute_context_sync(self, task: Task):
        """Backfill: sync domain articles to intelligence.contexts (Phase 1.2 context-centric)."""
        try:
            from services.nightly_ingest_window_service import in_nightly_pipeline_window_est

            if in_nightly_pipeline_window_est() and not (task.metadata or {}).get(
                "nightly_sequential_drain"
            ):
                logger.debug(
                    "Context sync: nightly pipeline window — handled by nightly_enrichment_context"
                )
                return
        except Exception:
            pass
        try:
            from config.context_centric_config import is_context_centric_task_enabled

            if not is_context_centric_task_enabled("context_sync"):
                return
        except Exception:
            pass
        import asyncio

        from services.context_processor_service import sync_domain_articles_to_contexts

        try:
            from shared.adaptive_batch_policy import resolve_adaptive_batch

            sync_limit, _meta = resolve_adaptive_batch("context_sync", 100)
        except Exception:
            sync_limit = 100
        sync_limit = max(1, int(sync_limit))
        domains = _domains_for_phase("context_sync")
        total_all = 0

        for domain_key in domains:
            try:
                # Production: adaptive contexts/batch (default 100)
                total = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda d=domain_key, lim=sync_limit: sync_domain_articles_to_contexts(
                        d, limit=lim
                    ),
                )
                total_all += int(total or 0)
                if total > 0:
                    logger.info(f"Context sync {domain_key}: {total} contexts created")
            except Exception as e:
                logger.warning(f"Context sync {domain_key} failed: {e}")
        self._stamp_monitor_batch_throughput(
            task,
            round_processed=int(sync_limit) * max(1, len(domains)),
            items_processed=total_all,
            adaptive_batch=int(sync_limit),
            contexts_created=total_all,
        )

    async def _execute_entity_profile_sync(self, task: Task):
        """Sync entity_canonical -> entity_profiles + old_entity_to_new (Phase 1.3 context-centric)."""
        try:
            from config.context_centric_config import is_context_centric_task_enabled

            if not is_context_centric_task_enabled("entity_profile_sync"):
                return
        except Exception:
            pass
        import asyncio

        from services.entity_profile_sync_service import sync_domain_entity_profiles

        domains = _domains_for_phase("entity_profile_sync")
        total_all = 0
        for domain_key in domains:
            try:
                total = await asyncio.get_event_loop().run_in_executor(
                    None, lambda d=domain_key: sync_domain_entity_profiles(d)
                )
                total_all += int(total or 0)
                if total > 0:
                    logger.info(f"Entity profile sync {domain_key}: {total} new mappings")
            except Exception as e:
                logger.warning(f"Entity profile sync {domain_key} failed: {e}")
        per_domain = 40
        try:
            from services.backlog_metrics import BATCH_SIZE_PER_TASK

            per_domain = max(1, int(BATCH_SIZE_PER_TASK.get("entity_profile_sync", 40)))
        except Exception:
            pass
        self._stamp_monitor_batch_throughput(
            task,
            round_processed=int(per_domain) * max(1, len(domains)),
            items_processed=total_all,
            mappings_created=total_all,
        )

    async def _execute_claim_extraction(self, task: Task):
        """Extract claims (subject/predicate/object) from contexts without claims (Phase 2.1 context-centric)."""
        try:
            from config.context_centric_config import is_context_centric_task_enabled

            if not is_context_centric_task_enabled("claim_extraction"):
                return
        except Exception:
            pass
        from services.claim_extraction_service import (
            claim_extraction_drain_enabled,
            drain_claim_extraction_for_automation_task,
            run_claim_extraction_batch,
        )

        task.metadata = task.metadata or {}
        is_nightly_seq = bool(task.metadata.get("nightly_sequential_drain"))
        try:
            # Default: one automation task drains all pending contexts in a loop (CLAIM_EXTRACTION_DRAIN=true).
            # Keeps a single claim_extraction slot busy until idle so we do not stack many queued copies; other
            # workers and LLM lane semaphores handle sharing the GPU with other phases.
            # Nightly unified sequential drain: one batch per outer loop iteration so later phases get
            # time inside the 00:00–07:00 window (full drain can run 15m+ per call and starve the sweep).
            # Drain writes one automation_run_history row per batch; skip the task-level history row.
            run_limit = (task.metadata or {}).get("nightly_limit")
            nlim = int(run_limit) if run_limit else None
            use_drain = claim_extraction_drain_enabled() and not is_nightly_seq
            on_batch = self._make_batch_progress_callback(task)
            if use_drain:
                task.metadata["skip_automation_run_history"] = True

                async def _claim_batch_cb(batch_n: int, res) -> None:
                    await on_batch(
                        batch_n,
                        contexts_processed=res.contexts_processed,
                        claims_inserted=res.claims_inserted,
                    )

                total, batches = await drain_claim_extraction_for_automation_task(
                    nightly_limit=nlim,
                    on_batch_complete=_claim_batch_cb,
                )
                if total > 0:
                    logger.info(
                        "Claim extraction: %s claims inserted (%s batch(es) in one task)",
                        total,
                        batches,
                    )
            else:
                res = await run_claim_extraction_batch(limit=nlim)
                if res.contexts_processed > 0 or res.claims_inserted > 0:
                    await on_batch(
                        1,
                        contexts_processed=res.contexts_processed,
                        claims_inserted=res.claims_inserted,
                    )
                if res.claims_inserted > 0:
                    logger.info(
                        "Claim extraction: %s claims inserted",
                        res.claims_inserted,
                    )
        except Exception as e:
            logger.warning(f"Claim extraction failed: {e}")

    async def _execute_legislative_references(self, task: Task):
        """Detect bill citations in politics/legal articles; fetch Congress.gov bill/summary/text pointers."""
        try:
            from config.context_centric_config import is_context_centric_task_enabled

            if not is_context_centric_task_enabled("legislative_references"):
                return
        except Exception:
            pass
        try:
            from services.legislative_reference_service import run_legislative_reference_batch

            article_limit = 8
            try:
                from shared.adaptive_batch_policy import resolve_adaptive_batch

                article_limit, adaptive_meta = resolve_adaptive_batch(
                    "legislative_references", article_limit
                )
                if isinstance(task.metadata, dict):
                    task.metadata["adaptive_batch"] = article_limit
                    task.metadata["adaptive_batch_meta"] = adaptive_meta
            except Exception:
                pass
            stats = await asyncio.to_thread(
                run_legislative_reference_batch,
                article_limit_per_domain=article_limit,
            )
            if stats and not stats.get("skipped") and int(stats.get("articles_scanned") or 0) > 0:
                logger.info(
                    "Legislative references: scanned %s articles, %s snapshots (batch=%s)",
                    stats.get("articles_scanned"),
                    stats.get("references_upserted"),
                    article_limit,
                )
        except Exception as e:
            logger.warning("Legislative references failed: %s", e)

    async def _execute_claims_to_facts(self, task: Task):
        """Promote high-confidence extracted_claims to versioned_facts (activates story state chain)."""
        from datetime import datetime, timezone

        from services.claim_extraction_service import (
            claims_to_facts_drain_enabled,
            drain_claims_to_facts_for_automation_task,
            promote_claims_to_versioned_facts,
        )
        from shared.services.phase_batch_run_history import record_phase_batch_completion_async

        task.metadata = task.metadata or {}
        try:
            run_limit = task.metadata.get("nightly_limit")
            per_batch = int(run_limit) if run_limit else None
            is_nightly_seq = bool(task.metadata.get("nightly_sequential_drain"))

            # Daytime scheduled: optional multi-batch drain in one task (like claim_extraction).
            # Nightly sequential: one promote per run — outer NIGHTLY_SEQUENTIAL_PHASE_LOOP_CAPS repeats.
            if claims_to_facts_drain_enabled() and not is_nightly_seq:
                task.metadata["skip_automation_run_history"] = True
                total, batches = await drain_claims_to_facts_for_automation_task(
                    per_batch_limit=per_batch,
                )
                if total > 0:
                    logger.info(
                        "claims_to_facts drain: promoted=%s batches=%s",
                        total,
                        batches,
                    )
                return

            started = datetime.now(timezone.utc)
            stats = await asyncio.to_thread(
                promote_claims_to_versioned_facts,
                limit=per_batch,
            )
            finished = datetime.now(timezone.utc)
            if stats and int(stats.get("promoted") or 0) > 0:
                logger.info(
                    "claims_to_facts: promoted=%s candidates=%s",
                    stats.get("promoted"),
                    stats.get("candidates"),
                )
            try:
                await record_phase_batch_completion_async(
                    "claims_to_facts",
                    started,
                    finished,
                    stats={
                        "promoted": int((stats or {}).get("promoted") or 0),
                        "candidates": int((stats or {}).get("candidates") or 0),
                    },
                )
            except Exception:
                pass
        except Exception as e:
            logger.warning("claims_to_facts failed: %s", e)

    async def _execute_claim_evidence_appraisal(self, task: Task):
        """v11 corpus: grade paper findings with quote-required refusal contract."""
        from config.feature_registry import is_feature_enabled
        from services.claim_evidence_appraisal_service import (
            is_enabled,
            run_claim_evidence_appraisal_batch,
        )

        if not is_enabled() and not is_feature_enabled("claim_evidence_appraisal"):
            logger.debug("claim_evidence_appraisal skipped (feature disabled)")
            return
        try:
            limit = 8
            if isinstance(task.metadata, dict) and task.metadata.get("batch_limit"):
                limit = int(task.metadata["batch_limit"])
            stats = await asyncio.to_thread(
                run_claim_evidence_appraisal_batch,
                domain_key=None,
                limit=limit,
            )
            if stats and int(stats.get("appraised") or 0) > 0:
                logger.info("claim_evidence_appraisal: %s", stats)
        except Exception as e:
            logger.warning("claim_evidence_appraisal failed: %s", e)

    async def _execute_editorial_reduction_pass(self, task: Task):
        """v11 Reduction: prune in_reduction packages then route back to research/narrative."""
        from config.feature_registry import is_feature_enabled
        from services.editorial_package_reduction_service import (
            is_enabled,
            run_reduction_batch,
        )

        if not is_enabled():
            logger.debug("editorial_reduction_pass skipped (EDITORIAL_REDUCTION_ENABLED off)")
            return
        if not is_feature_enabled("editorial_reduction") and not is_enabled():
            return
        try:
            limit = 5
            if isinstance(task.metadata, dict) and task.metadata.get("batch_limit"):
                limit = int(task.metadata["batch_limit"])
            stats = await asyncio.to_thread(run_reduction_batch, limit=limit)
            if stats and int(stats.get("processed") or 0) > 0:
                logger.info("editorial_reduction_pass: %s", stats)
            try:
                from shared.pipeline_handoffs import after_editorial_reduction

                after_editorial_reduction(
                    self, processed=int((stats or {}).get("processed") or 0)
                )
            except Exception as e:
                logger.debug("editorial_reduction handoff: %s", e)
        except Exception as e:
            logger.warning("editorial_reduction_pass failed: %s", e)

    async def _execute_editorial_narrative_pass(self, task: Task):
        """v11 Narrative: assemble in_narrative packages then route to Reduction/Editor."""
        from services.editorial_package_narrative_service import (
            is_enabled,
            run_narrative_batch,
        )

        if not is_enabled():
            logger.debug("editorial_narrative_pass skipped (EDITORIAL_NARRATIVE_ENABLED off)")
            return
        try:
            limit = 5
            if isinstance(task.metadata, dict) and task.metadata.get("batch_limit"):
                limit = int(task.metadata["batch_limit"])
            stats = await asyncio.to_thread(run_narrative_batch, limit=limit)
            if stats and int(stats.get("processed") or 0) > 0:
                logger.info("editorial_narrative_pass: %s", stats)
            try:
                from shared.pipeline_handoffs import after_editorial_narrative

                after_editorial_narrative(
                    self, processed=int((stats or {}).get("processed") or 0)
                )
            except Exception as e:
                logger.debug("editorial_narrative handoff: %s", e)
        except Exception as e:
            logger.warning("editorial_narrative_pass failed: %s", e)

    async def _execute_editorial_research_pass(self, task: Task):
        """v11 Research: spine + assemble in_research packages then route to Reduction/Editor."""
        from services.editorial_package_research_service import (
            is_enabled,
            run_research_batch,
        )

        if not is_enabled():
            logger.debug("editorial_research_pass skipped (EDITORIAL_RESEARCH_ENABLED off)")
            return
        try:
            limit = 5
            if isinstance(task.metadata, dict) and task.metadata.get("batch_limit"):
                limit = int(task.metadata["batch_limit"])
            stats = await asyncio.to_thread(run_research_batch, limit=limit)
            if stats and int(stats.get("processed") or 0) > 0:
                logger.info("editorial_research_pass: %s", stats)
            try:
                from shared.pipeline_handoffs import after_editorial_research

                after_editorial_research(
                    self, processed=int((stats or {}).get("processed") or 0)
                )
            except Exception as e:
                logger.debug("editorial_research handoff: %s", e)
        except Exception as e:
            logger.warning("editorial_research_pass failed: %s", e)

    async def _execute_claim_subject_gap_refresh(self, task: Task):
        """Rebuild intelligence.claim_subject_gap_catalog (open subjects lacking profiles/canonicals)."""
        try:
            from config.context_centric_config import is_context_centric_task_enabled

            if not is_context_centric_task_enabled("claim_subject_gap_refresh"):
                return
        except Exception:
            pass
        try:
            from services.claim_subject_gap_service import refresh_claim_subject_gap_catalog

            out = await asyncio.to_thread(refresh_claim_subject_gap_catalog)
            if isinstance(out, dict) and out.get("success"):
                logger.info(
                    "Claim subject gap refresh: upserted=%s deleted_stale=%s",
                    out.get("rows_upserted"),
                    out.get("rows_deleted_stale"),
                )
        except Exception as e:
            logger.warning("Claim subject gap refresh failed: %s", e)

    async def _execute_extracted_claims_dedupe(self, task: Task):
        """Delete duplicate extracted_claims rows (same context + normalized triple)."""
        try:
            from config.context_centric_config import is_context_centric_task_enabled

            if not is_context_centric_task_enabled("extracted_claims_dedupe"):
                return
        except Exception:
            pass
        try:
            from services.extracted_claims_dedupe_service import run_dedupe_cycle

            out = await asyncio.to_thread(run_dedupe_cycle)
            if isinstance(out, dict) and int(out.get("deleted") or 0) > 0:
                logger.info(
                    "Extracted claims dedupe: deleted=%s remaining_dup_estimate=%s",
                    out.get("deleted"),
                    out.get("duplicates_after"),
                )
        except Exception as e:
            logger.warning("Extracted claims dedupe failed: %s", e)

    async def _execute_event_tracking(self, task: Task):
        """Populate tracked_events and event_chronicles from contexts (Phase 2.3 context-centric)."""
        from datetime import datetime, timezone

        from shared.services.phase_batch_run_history import record_phase_batch_completion_async

        try:
            from config.context_centric_config import is_context_centric_task_enabled

            if not is_context_centric_task_enabled("event_tracking"):
                return
        except Exception:
            pass
        try:
            from services.event_tracking_service import run_event_tracking_batch

            started = datetime.now(timezone.utc)
            try:
                from shared.adaptive_batch_policy import resolve_adaptive_batch

                batch_max = max(
                    25, min(300, env_int("EVENT_TRACKING_ASSEMBLY_BATCH_MAX", 300))
                )
                default_lim = max(
                    1,
                    min(
                        batch_max,
                        env_int("EVENT_TRACKING_ASSEMBLY_BATCH_LIMIT", 25),
                    ),
                )
                track_lim, _meta = resolve_adaptive_batch("event_tracking", default_lim)
                track_lim = max(1, min(batch_max, int(track_lim)))
            except Exception:
                track_lim = 300
            total = int(await run_event_tracking_batch(limit=track_lim) or 0)
            finished = datetime.now(timezone.utc)
            await record_phase_batch_completion_async(
                "event_tracking",
                started,
                finished,
                stats={
                    "chronicle_entries": total,
                    "round_processed": max(total, int(track_lim)),
                    "processed": total,
                    "batch_limit": int(track_lim),
                },
                allow_empty=True,
            )
            task.metadata = task.metadata or {}
            task.metadata["skip_automation_run_history"] = True
            if total > 0:
                logger.info(f"Event tracking: {total} chronicle entries added")
        except Exception as e:
            logger.warning(f"Event tracking failed: {e}")

    async def _execute_investigation_report_refresh(self, task: Task):
        from shared.retired_phase_dispatch import dispatch_retired_automation_phase

        await dispatch_retired_automation_phase(self, "investigation_report_refresh", task)

    async def _execute_cross_domain_synthesis(self, task: Task):
        """Run cross-domain correlation job (events spanning domains -> cross_domain_correlations)."""
        try:
            from services.cross_domain_service import run_cross_domain_synthesis

            result = run_cross_domain_synthesis(
                domains=None,
                time_window_days=90,
                correlation_threshold=0.5,
            )
            if result.get("correlations"):
                logger.info(
                    f"Cross-domain synthesis: {len(result['correlations'])} correlation(s) written"
                )
        except Exception as e:
            logger.warning(f"Cross-domain synthesis failed: {e}")

    async def _execute_event_coherence_review(self, task: Task):
        from shared.retired_phase_dispatch import dispatch_retired_automation_phase

        await dispatch_retired_automation_phase(self, "event_coherence_review", task)

    async def _execute_entity_profile_build(self, task: Task):
        """Build Wikipedia-style sections for entity_profiles from contexts (Phase 1.3)."""
        try:
            from config.context_centric_config import is_context_centric_task_enabled

            if not is_context_centric_task_enabled("entity_profile_build"):
                return
        except Exception:
            pass
        from services.entity_profile_builder_service import (
            drain_entity_profile_build,
            entity_profile_build_batch_limit,
            entity_profile_build_drain_enabled,
            run_profile_builder_batch,
        )

        task.metadata = task.metadata or {}
        is_nightly_seq = bool(task.metadata.get("nightly_sequential_drain"))
        task.metadata["skip_automation_run_history"] = True
        task.metadata.pop("_batch_run_started_at", None)
        on_batch = self._make_batch_progress_callback(task)
        limit = entity_profile_build_batch_limit()
        use_drain = entity_profile_build_drain_enabled() and not is_nightly_seq

        async def _on_profile_built(updated: int, processed_idx: int) -> None:
            await on_batch(
                processed_idx,
                profiles_updated=1,
                round_processed=1,
                total_processed=updated,
            )

        try:
            if use_drain:
                total_updated = 0

                async def _profile_batch_cb(batch_n: int, batch_stats) -> None:
                    nonlocal total_updated
                    total_updated += batch_stats.updated
                    await on_batch(
                        batch_n,
                        profiles_updated=batch_stats.updated,
                        round_processed=batch_stats.updated,
                        total_processed=total_updated,
                        fast_updated=batch_stats.fast_updated,
                        full_updated=batch_stats.full_updated,
                        contexts_used=batch_stats.contexts_used,
                    )

                stats = await drain_entity_profile_build(
                    batch_limit=limit,
                    on_batch_complete=_profile_batch_cb,
                )
                updated = int(stats.get("profiles_updated", 0) or 0)
            else:
                batch_result = await run_profile_builder_batch(
                    limit=limit,
                    on_profile_built=_on_profile_built,
                )
                updated = batch_result.updated
            task.metadata["items_processed"] = int(updated or 0)
            if updated <= 0:
                logger.debug("Entity profile build: no profiles updated this run")
        except Exception as e:
            logger.warning(f"Entity profile build failed: {e}")

    async def _execute_entity_dossier_compile(self, task: Task):
        """Compile entity dossiers (chronicle_data, relationships, positions) for entities missing or stale (Phase 2.6)."""
        from datetime import datetime, timezone

        from shared.services.phase_batch_run_history import record_phase_batch_completion_async

        try:
            from config.context_centric_config import is_context_centric_task_enabled

            if not is_context_centric_task_enabled("entity_dossier_compile"):
                return
        except Exception:
            pass
        import asyncio

        from services.dossier_compiler_service import _run_scheduled_dossier_compiles

        try:
            started = datetime.now(timezone.utc)
            loop = asyncio.get_event_loop()
            try:
                from services.assembly_conductor_service import _entity_dossier_compile_limit

                dossier_max = _entity_dossier_compile_limit()
            except Exception:
                dossier_max = max(1, min(100, env_int("ENTITY_DOSSIER_COMPILE_MAX", 20)))
            compiled = int(
                await loop.run_in_executor(
                    self._executor,
                    _run_scheduled_dossier_compiles,
                    dossier_max,
                    None,  # get_db_connection_fn -> use default
                    None,  # stale_days -> ENTITY_DOSSIER_STALE_DAYS / event-driven eligibility
                )
                or 0
            )
            finished = datetime.now(timezone.utc)
            if compiled > 0:
                await record_phase_batch_completion_async(
                    "entity_dossier_compile",
                    started,
                    finished,
                    stats={
                        "dossiers_compiled": compiled,
                        "round_processed": compiled,
                        "processed": compiled,
                    },
                )
                logger.info(f"Entity dossier compile: {compiled} dossiers compiled")
        except Exception as e:
            logger.warning(f"Entity dossier compile failed: {e}")

    async def _execute_entity_position_tracker(self, task: Task):
        from shared.retired_phase_dispatch import dispatch_retired_automation_phase

        await dispatch_retired_automation_phase(self, "entity_position_tracker", task)

    async def _execute_metadata_enrichment(self, task: Task):
        """Run metadata enrichment batch for domain articles (language, categories, sentiment, quality)."""
        from shared.legacy_intake_rollback import (
            legacy_intake_rollback_active,
            load_metadata_enrichment_service,
        )

        if not legacy_intake_rollback_active():
            logger.debug(
                "metadata_enrichment skipped (unified intake path; LEGACY_INTAKE_EXTRACTION_ENABLED for rollback)"
            )
            return
        try:
            mod = load_metadata_enrichment_service()
            try:
                from shared.adaptive_batch_policy import resolve_adaptive_batch

                meta_lim, _meta = resolve_adaptive_batch(
                    "metadata_enrichment",
                    max(1, min(200, env_int("METADATA_ENRICHMENT_LIMIT_PER_DOMAIN", 5))),
                )
            except Exception:
                meta_lim = max(
                    1,
                    min(200, env_int("METADATA_ENRICHMENT_LIMIT_PER_DOMAIN", 5)),
                )
            total = await mod.run_metadata_enrichment_batch_for_domains(
                limit_per_domain=max(1, int(meta_lim))
            )
            if total > 0:
                logger.info("Metadata enrichment: %d articles enriched", total)
        except Exception as e:
            logger.warning("Metadata enrichment failed: %s", e)

    async def _execute_story_enhancement(self, task: Task):
        """Story state triggers + entity enrich/build (enhancement orchestrator)."""
        from services.enhancement_orchestrator_service import run_enhancement_cycle
        from shared.services.phase_batch_run_history import record_phase_batch_completion_async

        task.metadata = task.metadata or {}
        started = datetime.now(timezone.utc)
        try:
            enrich_lim = 10
            build_lim = 10
            try:
                from shared.adaptive_batch_policy import resolve_adaptive_batch

                enrich_lim, enrich_meta = resolve_adaptive_batch("entity_enrichment", enrich_lim)
                build_lim, build_meta = resolve_adaptive_batch("entity_profile_build", build_lim)
                task.metadata["adaptive_batch"] = {
                    "entity_enrichment": int(enrich_lim),
                    "entity_profile_build": int(build_lim),
                }
                task.metadata["adaptive_batch_meta"] = {
                    "entity_enrichment": enrich_meta,
                    "entity_profile_build": build_meta,
                }
            except Exception:
                pass
            result = await run_enhancement_cycle(
                enrich_limit=max(1, int(enrich_lim)),
                build_limit=max(1, int(build_lim)),
            )
            finished = datetime.now(timezone.utc)
            built = int(result.get("entity_profiles_built") or 0)
            enriched = int(result.get("entity_profiles_enriched") or 0)
            fact_rows = int(result.get("fact_change_log_processed") or 0)
            queue_rows = int(result.get("story_update_queue_processed") or 0)
            if built > 0 or enriched > 0 or fact_rows > 0 or queue_rows > 0:
                await self._record_phase_batch_loop(
                    task,
                    loops_processed=1,
                    entity_profiles_built=built,
                    entity_profiles_enriched=enriched,
                    round_processed=built + enriched + fact_rows + queue_rows,
                    fact_change_log_processed=fact_rows,
                    story_update_queue_processed=queue_rows,
                )
                if built > 0:
                    await record_phase_batch_completion_async(
                        "entity_profile_build",
                        started,
                        finished,
                        stats={"profiles_updated": built, "round_processed": built},
                        scheduler_path="story_enhancement",
                    )
                task.metadata["skip_automation_run_history"] = True
        except Exception as e:
            logger.warning("Story enhancement failed: %s", e)

    async def _execute_content_refinement_queue(self, task: Task):
        """Drain intelligence.content_refinement_queue (storyline RAG, timeline narratives, ~70B finisher)."""
        from services.content_refinement_queue_service import (
            auto_enqueue_comprehensive_rag_for_automation,
            in_nightly_gpu_refinement_window_est,
            process_content_refinement_queue_batch,
        )

        if in_nightly_gpu_refinement_window_est():
            logger.debug(
                "Content refinement queue: nightly pipeline active — handled by nightly_enrichment_context"
            )
            return

        try:
            auto_enqueue_comprehensive_rag_for_automation()
            stats = await process_content_refinement_queue_batch()
            processed = int((stats or {}).get("processed") or 0)
            batch_limit = int((stats or {}).get("batch_limit") or processed or 4)
            self._stamp_monitor_batch_throughput(
                task,
                round_processed=max(processed, batch_limit),
                items_processed=processed,
                failed=int((stats or {}).get("failed") or 0),
                pending_before=int((stats or {}).get("pending_before") or 0),
                pending_after=int((stats or {}).get("pending_after") or 0),
            )
            logger.info(
                "Content refinement queue: pending_before=%s processed=%s failed=%s by_type=%s pending_after=%s",
                stats.get("pending_before"),
                stats.get("processed"),
                stats.get("failed"),
                stats.get("by_type"),
                stats.get("pending_after"),
            )
        except Exception as e:
            logger.warning("Content refinement queue failed: %s", e)

    async def _execute_nightly_enrichment_context(self, task: Task):
        """Nightly window: RSS kickoff → enrichment → context_sync → sequential phase drain → GPU refinement queue."""
        from services.nightly_ingest_window_service import (
            in_nightly_pipeline_window_est,
            run_nightly_unified_pipeline_drain,
        )

        force = bool((task.metadata or {}).get("force_nightly_unified_pipeline"))
        if not in_nightly_pipeline_window_est() and not force:
            return
        if force and not in_nightly_pipeline_window_est():
            logger.info(
                "nightly_enrichment_context: manual force — running unified pipeline outside local window"
            )

        try:
            stats = await run_nightly_unified_pipeline_drain(
                automation=self,
                force_outside_window=force,
            )
            if (
                stats.get("enrichment_articles", 0)
                or stats.get("contexts_created", 0)
                or stats.get("gpu_processed", 0)
                or stats.get("gpu_failed", 0)
                or stats.get("sequential_phase_runs", 0)
                or stats.get("kickoff_rss_activity", 0)
            ):
                logger.info(
                    "Nightly pipeline: cycles=%s enrich_batches=%s articles=%s sync_rounds=%s contexts=%s "
                    "seq_runs=%s kickoff_rss=%s gpu_batches=%s gpu_processed=%s gpu_failed=%s stopped=%s gpu_stopped=%s",
                    stats.get("outer_cycles"),
                    stats.get("enrichment_batches"),
                    stats.get("enrichment_articles"),
                    stats.get("context_sync_rounds"),
                    stats.get("contexts_created"),
                    stats.get("sequential_phase_runs"),
                    stats.get("kickoff_rss_activity"),
                    stats.get("gpu_batches"),
                    stats.get("gpu_processed"),
                    stats.get("gpu_failed"),
                    stats.get("stopped_reason"),
                    stats.get("gpu_stopped_reason"),
                )
            elif stats.get("outer_cycles", 0):
                logger.info(
                    "Nightly pipeline: cycles=%s enrich_batches=%s articles=%s sync_rounds=%s contexts=%s "
                    "seq_runs=%s kickoff_rss=%s gpu_batches=%s gpu_processed=%s gpu_failed=%s stopped=%s gpu_stopped=%s",
                    stats.get("outer_cycles"),
                    stats.get("enrichment_batches"),
                    stats.get("enrichment_articles"),
                    stats.get("context_sync_rounds"),
                    stats.get("contexts_created"),
                    stats.get("sequential_phase_runs"),
                    stats.get("kickoff_rss_activity"),
                    stats.get("gpu_batches"),
                    stats.get("gpu_processed"),
                    stats.get("gpu_failed"),
                    stats.get("stopped_reason"),
                    stats.get("gpu_stopped_reason"),
                )
        except Exception as e:
            logger.warning("Nightly unified pipeline failed: %s", e)

    async def run_nightly_sequential_phase(self, phase_name: str) -> dict[str, Any]:
        """Run one scheduler phase under nightly unified drain (bypasses yield / exclusive / chain noise)."""
        if phase_name not in self.schedules:
            logger.warning("Nightly sequential: unknown phase %s — skipping", phase_name)
            return {"skipped": True, "reason": "unknown_phase"}
        sched = self.schedules[phase_name]
        if not sched.get("enabled", True):
            logger.debug("Nightly sequential: phase %s disabled — skipping", phase_name)
            return {"skipped": True, "reason": "disabled"}
        nightly_meta: dict[str, Any] = {
            "nightly_sequential_drain": True,
            "scheduled": True,
            "phase": sched.get("phase", 0),
            "estimated_duration": sched.get("estimated_duration", 60),
        }
        # Prevent very large single runs from starving downstream nightly phases.
        if phase_name == "claim_extraction":
            try:
                nightly_meta["nightly_limit"] = max(
                    50,
                    env_int("NIGHTLY_CLAIM_EXTRACTION_BATCH_LIMIT", 250),
                )
            except ValueError:
                nightly_meta["nightly_limit"] = 250
        elif phase_name == "claims_to_facts":
            try:
                from services.claim_extraction_service import get_nightly_claims_to_facts_batch_limit

                nightly_meta["nightly_limit"] = int(get_nightly_claims_to_facts_batch_limit())
            except Exception:
                nightly_meta["nightly_limit"] = 10_000

        task = Task(
            id=f"nightly_seq_{phase_name}_{uuid4().hex[:10]}",
            name=phase_name,
            priority=sched.get("priority", TaskPriority.NORMAL),
            status=TaskStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            max_retries=_phase_max_retries(phase_name),
            metadata=nightly_meta,
        )
        await self._execute_task(task, "nightly_sequential_drain")
        return {"skipped": False}

    async def _execute_entity_enrichment(self, task: Task):
        """Phase 3 RAG: Run entity enrichment batch (Wikipedia -> entity_profiles + versioned_facts)."""
        from services.entity_enrichment_service import run_enrichment_batch

        try:
            # Production: adaptive entities per run (default 20); timeout 10s/entity; skip if queue >1000
            try:
                from shared.adaptive_batch_policy import resolve_adaptive_batch

                enrich_lim, _meta = resolve_adaptive_batch("entity_enrichment", 20)
            except Exception:
                enrich_lim = 20
            updated = run_enrichment_batch(limit=max(1, int(enrich_lim)))
            if updated > 0:
                logger.info(f"Entity enrichment: {updated} profiles enriched")
        except Exception as e:
            logger.warning(f"Entity enrichment failed: {e}")

    async def _execute_pattern_matching(self, task: Task):
        from shared.retired_phase_dispatch import dispatch_retired_automation_phase

        await dispatch_retired_automation_phase(self, "pattern_matching", task)

    async def _execute_research_topic_refinement(self, task: Task):
        """Idle-only: pick one finance research topic and submit a refinement (analysis) at low priority."""
        getter = getattr(self, "_get_finance_orchestrator", None)
        if not getter or not callable(getter):
            logger.debug("Research topic refinement: no finance orchestrator getter")
            return
        orch = getter()
        if not orch:
            logger.debug("Research topic refinement: finance orchestrator not available")
            return
        conn = await self._get_db_connection()
        if not conn:
            logger.warning("Research topic refinement: no DB connection")
            return
        try:
            from config.settings import finance_postgres_content_domain_key

            fin_schema = resolve_domain_schema(finance_postgres_content_domain_key())
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT EXISTS (
                      SELECT 1 FROM information_schema.tables
                      WHERE table_schema = %s AND table_name = 'research_topics'
                    )
                    """,
                    (fin_schema,),
                )
                if not cur.fetchone()[0]:
                    logger.debug("Research topic refinement: no research_topics in %s", fin_schema)
                    return
                cur.execute(
                    f"""
                    SELECT id, query, topic, date_range_start, date_range_end
                    FROM {fin_schema}.research_topics
                    ORDER BY last_refined_at NULLS FIRST, updated_at ASC
                    LIMIT 1
                    """
                )
                row = cur.fetchone()
            if not row:
                logger.debug("Research topic refinement: no topics to refine")
                return
            topic_id = row["id"]
            query = row["query"]
            topic = row["topic"] or "gold"
            start_date = str(row["date_range_start"]) if row.get("date_range_start") else None
            end_date = str(row["date_range_end"]) if row.get("date_range_end") else None
            from domains.finance.orchestrator_types import TaskPriority as FinTaskPriority
            from domains.finance.orchestrator_types import TaskType

            params = {"query": query, "topic": topic}
            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date
            task_id = orch.submit_task(
                TaskType.analysis,
                params,
                priority=FinTaskPriority.low,
                reason="Idle-time research topic refinement",
            )
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE {fin_schema}.research_topics
                    SET last_refined_task_id = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (task_id, topic_id),
                )
            conn.commit()
            logger.info(
                "Research topic refinement: topic_id=%s submitted as task_id=%s (low priority)",
                topic_id,
                task_id,
            )
        except Exception as e:
            logger.warning("Research topic refinement failed: %s", e)
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    async def _execute_entity_organizer(self, task: Task):
        """Run entity organizer: cleanup + relationship extraction + resolution (alias population + auto-merge + cross-domain linking)."""
        try:
            from services.entity_organizer_service import run_cycle

            relationship_limit = 100
            try:
                from shared.adaptive_batch_policy import resolve_adaptive_batch

                relationship_limit, adaptive_meta = resolve_adaptive_batch(
                    "entity_organizer", relationship_limit
                )
                if isinstance(task.metadata, dict):
                    task.metadata["adaptive_batch"] = relationship_limit
                    task.metadata["adaptive_batch_meta"] = adaptive_meta
            except Exception:
                pass
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                lambda: run_cycle(domain_key=None, relationship_limit=relationship_limit),
            )
            total_actions = result.get("cleanup", {}).get("total_actions", 0)
            rel = result.get("relationships_extracted", 0)
            if total_actions or rel:
                logger.info(
                    "Entity organizer: cleanup %s actions, %s relationship(s) extracted",
                    total_actions,
                    rel,
                )
            if result.get("errors"):
                logger.debug("Entity organizer errors: %s", result["errors"])
        except Exception as e:
            logger.warning("Entity organizer failed: %s", e)

        # Entity resolution: populate aliases from mentions, auto-merge near-duplicates, cross-domain linking
        try:
            from services.entity_resolution_service import run_resolution_batch

            loop = asyncio.get_event_loop()
            res_result = await loop.run_in_executor(
                self.executor,
                lambda: run_resolution_batch(
                    auto_merge_confidence=0.9, cross_domain_confidence=0.8
                ),
            )
            for domain_key, domain_res in res_result.get("domains", {}).items():
                aliases = domain_res.get("aliases", {})
                merges = domain_res.get("merges", {})
                if aliases.get("new_aliases", 0) or merges.get("merges_performed", 0):
                    logger.info(
                        "Entity resolution %s: %d aliases added, %d merges",
                        domain_key,
                        aliases.get("new_aliases", 0),
                        merges.get("merges_performed", 0),
                    )
            cross = res_result.get("cross_domain", {})
            if cross.get("relationships_created", 0):
                logger.info(
                    "Entity resolution cross-domain: %d relationships created",
                    cross.get("relationships_created", 0),
                )
        except Exception as e:
            logger.warning("Entity resolution batch failed: %s", e)

    async def _execute_graph_connection_distillation(self, task: Task):
        """Apply pending graph_connection_proposals (storyline merges, entity merges, M2M links)."""
        from datetime import datetime, timezone

        from shared.services.phase_batch_run_history import record_phase_batch_completion_async

        # Prefer batch history with throughput; skip empty task-shell rows that
        # falsely trip PipelineController zero-progress stall detection.
        task.metadata = task.metadata or {}
        task.metadata["skip_automation_run_history"] = True

        try:
            from services.graph_connection_processor_service import (
                process_graph_connection_proposals_batch,
            )

            started = datetime.now(timezone.utc)
            loop = asyncio.get_event_loop()
            stats = await loop.run_in_executor(
                self.executor,
                process_graph_connection_proposals_batch,
                None,
            )
            finished = datetime.now(timezone.utc)
            if stats and (
                stats.get("examined")
                or stats.get("storyline_merged")
                or stats.get("storyline_links")
                or stats.get("entity_merged")
                or stats.get("entity_links")
                or stats.get("topic_links")
                or stats.get("hyperedge_links")
                or stats.get("rejected")
                or stats.get("left_pending_editorial")
            ):
                logger.info("Graph connection distillation: %s", stats)
            processed = 0
            examined = 0
            batch_limit = 0
            if isinstance(stats, dict):
                examined = int(stats.get("examined") or 0)
                batch_limit = int(stats.get("batch_limit") or 0)
                processed = int(
                    stats.get("processed")
                    or sum(
                        int(stats.get(k) or 0)
                        for k in (
                            "storyline_merged",
                            "storyline_links",
                            "entity_merged",
                            "entity_links",
                            "topic_links",
                            "hyperedge_links",
                            "rejected",
                        )
                    )
                )
            # Prefer real work; fall back to configured batch_limit so empty
            # examined rounds remain measurable (throughput > 0).
            round_n = max(processed, examined, batch_limit, 1)
            await record_phase_batch_completion_async(
                "graph_connection_distillation",
                started,
                finished,
                stats={
                    "round_processed": round_n,
                    "processed": max(processed, examined),
                    "examined": examined,
                    "batch_limit": batch_limit,
                },
                allow_empty=True,
            )
            if stats and stats.get("errors"):
                logger.debug("Graph connection distillation errors: %s", stats["errors"])
        except Exception as e:
            logger.warning("Graph connection distillation failed: %s", e)

    def _is_data_load_active(self) -> bool:
        """True if any data-load phase (rss, content_enrichment, entity_extraction) ran recently."""
        now = datetime.now(timezone.utc)
        for phase in DATA_LOAD_PHASES:
            s = self.schedules.get(phase)
            if not s or s.get("last_run") is None:
                continue
            if (now - s["last_run"]).total_seconds() < DOWNTIME_IDLE_SECONDS:
                return True
        return False

    def _is_system_idle(self) -> bool:
        """True when no data-load phase ran recently — safe to run idle-only work (e.g. research topic refinement)."""
        return not self._is_data_load_active()

    def _get_rss_feeds_caught_up_status(self) -> dict:
        """Get current status of RSS feeds caught-up flags for monitoring."""
        try:
            conn = get_db_connection()
            if not conn:
                return {}
            
            cur = conn.cursor()
            
            # Get all active feeds with their caught-up status
            cur.execute("""
                SELECT 
                    id,
                    feed_name,
                    feed_url,
                    is_caught_up,
                    caught_up_since,
                    last_caught_up_check,
                    last_fetched_at,
                    is_active,
                    fetch_interval
                FROM rss_feeds 
                WHERE is_active = TRUE
                ORDER BY feed_name
            """)
            
            feeds = cur.fetchall()
            conn.close()
            
            feed_status = []
            for feed in feeds:
                feed_id, name, url, is_caught_up, caught_up_since, last_check, last_fetched, is_active, fetch_interval = feed
                
                # Calculate time since last caught up check
                time_since_check = None
                if last_check:
                    time_since_check = (datetime.now(timezone.utc) - last_check).total_seconds()
                
                # Calculate time since last fetch
                time_since_fetch = None
                if last_fetched:
                    time_since_fetch = (datetime.now(timezone.utc) - last_fetched).total_seconds()
                
                # Calculate next expected fetch time
                next_fetch_time = None
                if last_fetched and fetch_interval:
                    next_fetch_time = last_fetched + timedelta(seconds=fetch_interval)
                
                feed_status.append({
                    'id': feed_id,
                    'name': name,
                    'url': url,
                    'is_caught_up': is_caught_up,
                    'caught_up_since': caught_up_since,
                    'last_caught_up_check': last_check,
                    'last_fetched_at': last_fetched,
                    'is_active': is_active,
                    'fetch_interval': fetch_interval,
                    'time_since_check': time_since_check,
                    'time_since_fetch': time_since_fetch,
                    'next_fetch_time': next_fetch_time
                })
            
            return {
                'feeds': feed_status,
                'total_feeds': len(feeds),
                'caught_up_feeds': len([f for f in feeds if f[3]]),  # is_caught_up is at index 3
                'timestamp': datetime.now(timezone.utc)
            }
        except Exception as e:
            logger.error(f"Error getting RSS feeds caught-up status: {e}")
            return {}

    async def _entity_organizer_downtime_loop(self):
        """During downtime between data loads, loop: cleanup + relationship extraction (vectors between entities)."""
        logger.info("Entity organizer downtime loop started")
        while self.is_running:
            try:
                if self._is_data_load_active():
                    await asyncio.sleep(DOWNTIME_POLL_SLEEP)
                    continue
                from services.entity_organizer_service import run_cycle

                result = await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    lambda: run_cycle(domain_key=None, relationship_limit=50),
                )
                total_actions = result.get("cleanup", {}).get("total_actions", 0)
                rel = result.get("relationships_extracted", 0)
                if total_actions or rel:
                    logger.info(
                        "Entity organizer (downtime): cleanup %s actions, %s relationship(s)",
                        total_actions,
                        rel,
                    )
                await asyncio.sleep(DOWNTIME_ORGANIZER_SLEEP)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Entity organizer downtime loop: %s", e)
                await asyncio.sleep(DOWNTIME_ORGANIZER_SLEEP)
        logger.info("Entity organizer downtime loop stopped")

    async def _execute_pattern_recognition(self, task: Task):
        from shared.retired_phase_dispatch import dispatch_retired_automation_phase

        await dispatch_retired_automation_phase(self, "pattern_recognition", task)

    async def _execute_embeddings_worker(self, task: Task):
        """Chunk + embed articles into intelligence.embedding_chunks (nightly-friendly)."""
        import asyncio

        from services.embeddings_worker_service import run_embeddings_worker_batch
        from shared.intelligence_phase_gates import should_skip_automation_phase

        if should_skip_automation_phase("embeddings_worker"):
            logger.debug("Embeddings worker skipped (embedding_chunks empty; set EMBEDDINGS_WORKER_FORCE_BACKFILL=true to seed)")
            return

        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, run_embeddings_worker_batch
            )
            if result.get("embedded_articles"):
                logger.info("Embeddings worker: %s", result)
        except Exception as e:
            logger.warning("Embeddings worker failed: %s", e)

    async def _execute_macro_series_refresh(self, task: Task):
        import asyncio

        from services.gpr_epu_import_service import import_gpr_epu_from_config
        from services.macro_series_service import refresh_longitudinal_macro_series
        from services.trade_resources_import_service import run_trade_resources_import
        from services.vdem_freedomhouse_import_service import import_vdem_freedom_house_from_config

        try:
            fred = await asyncio.get_event_loop().run_in_executor(
                None, refresh_longitudinal_macro_series
            )
            csv_imp = await asyncio.get_event_loop().run_in_executor(
                None, import_gpr_epu_from_config
            )
            trade = await asyncio.get_event_loop().run_in_executor(
                None, run_trade_resources_import
            )
            legitimacy = await asyncio.get_event_loop().run_in_executor(
                None, import_vdem_freedom_house_from_config
            )
            logger.info(
                "Macro series refresh: fred=%s csv=%s trade=%s legitimacy=%s",
                fred,
                csv_imp,
                trade,
                legitimacy,
            )
        except Exception as e:
            logger.warning("Macro series refresh failed: %s", e)

    async def _execute_external_events_sync(self, task: Task):
        import asyncio

        from services.acled_client import run_acled_incremental_sync
        from services.ucdp_client import run_ucdp_backfill_batch

        try:
            acled = await asyncio.get_event_loop().run_in_executor(
                None, run_acled_incremental_sync
            )
            ucdp = await asyncio.get_event_loop().run_in_executor(
                None, run_ucdp_backfill_batch
            )
            logger.info("External events sync: acled=%s ucdp=%s", acled, ucdp)
        except Exception as e:
            logger.warning("External events sync failed: %s", e)

    async def _execute_sanctions_refresh(self, task: Task):
        import asyncio

        from services.sanctions_ingest_service import run_sanctions_refresh

        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, run_sanctions_refresh
            )
            logger.info("Sanctions refresh: %s", result)
        except Exception as e:
            logger.warning("Sanctions refresh failed: %s", e)

    async def _execute_arc_report_generation(self, task: Task):
        from shared.retired_phase_dispatch import dispatch_retired_automation_phase

        await dispatch_retired_automation_phase(self, "arc_report_generation", task)

    async def _execute_longitudinal_matview_refresh(self, task: Task):
        import asyncio

        from shared.database.connection import get_db_connection_context
        from shared.intelligence_phase_gates import should_skip_automation_phase

        if should_skip_automation_phase("longitudinal_matview_refresh"):
            logger.debug("Longitudinal matview refresh skipped (intelligence.arc_definitions empty)")
            return

        def _refresh():
            with get_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "REFRESH MATERIALIZED VIEW CONCURRENTLY intelligence.mv_arc_spine_events"
                    )
                    cur.execute(
                        "REFRESH MATERIALIZED VIEW CONCURRENTLY intelligence.mv_tension_heatmap_monthly"
                    )
                conn.commit()

        try:
            await asyncio.get_event_loop().run_in_executor(None, _refresh)
            logger.info("Longitudinal mat views refreshed")
        except Exception as e:
            logger.warning("Longitudinal matview refresh failed (run non-concurrent if first load): %s", e)
            def _refresh_non_concurrent():
                with get_db_connection_context() as conn:
                    with conn.cursor() as cur:
                        cur.execute("REFRESH MATERIALIZED VIEW intelligence.mv_arc_spine_events")
                        cur.execute(
                            "REFRESH MATERIALIZED VIEW intelligence.mv_tension_heatmap_monthly"
                        )
                    conn.commit()

            try:
                await asyncio.get_event_loop().run_in_executor(None, _refresh_non_concurrent)
            except Exception as e2:
                logger.warning("Longitudinal matview non-concurrent refresh failed: %s", e2)

    async def _execute_editorial_document_generation(self, task: Task):
        """Fully retired — storyline editorial_document via RAG refinement or desk promote."""
        logger.info(
            "editorial_document_generation fully retired; use content_refinement_queue or desk promote"
        )
        return

    async def _execute_editorial_briefing_generation(self, task: Task):
        """Fully retired — tracked_event narratives via desk promote / narrative_stack API."""
        logger.info(
            "editorial_briefing_generation fully retired; use desk promote or narrative_stack"
        )
        return

    async def _execute_narrative_thread_build(self, task: Task):
        from shared.retired_phase_dispatch import dispatch_retired_automation_phase

        await dispatch_retired_automation_phase(self, "narrative_thread_build", task)

    async def _execute_digest_generation(self, task: Task):
        """Fully retired — no digest batch synthesizer."""
        logger.info("digest_generation fully retired; Briefings uses /api/{domain}/report")
        return

    async def _execute_data_cleanup(self, task: Task):
        """Execute data cleanup task — articles + intelligence layer."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)

        try:
            deleted_count = 0
            conn = await self._get_db_connection()
            try:
                with conn.cursor() as cursor:
                    for schema in get_pipeline_schema_names_active():
                        cursor.execute(
                            f"""
                            DELETE FROM {schema}.articles
                            WHERE published_at < %s AND created_at < %s
                        """,
                            (cutoff_date, cutoff_date),
                        )
                        deleted_count += max(0, cursor.rowcount or 0)
                    conn.commit()
            finally:
                conn.close()
            logger.info(f"Data cleanup: deleted {deleted_count} old articles")
            if deleted_count > 0:
                try:
                    from services.intelligence_cleanup_controller import IntelligenceCleanupController

                    bridges = IntelligenceCleanupController().prune_stale_article_to_context_bridges()
                    if bridges:
                        logger.info(
                            "Data cleanup: pruned %s stale article_to_context bridge(s)",
                            bridges,
                        )
                except Exception as bridge_err:
                    logger.warning(f"Data cleanup (article bridges): {bridge_err}")
        except Exception as e:
            logger.warning(f"Data cleanup (articles): {e}")

        try:
            from services.intelligence_cleanup_controller import run_intelligence_cleanup

            result = await run_intelligence_cleanup()
            logger.info(f"Intelligence cleanup: {result.get('total_actions', 0)} actions taken")
        except Exception as e:
            logger.warning(f"Data cleanup (intelligence): {e}")

    async def _execute_pending_db_flush(self, task: Task):
        """Replay automation_run_history rows queued while DB was unreachable."""
        try:
            from shared.database.pending_db_writes import flush_pending_writes

            stats = flush_pending_writes()
            logger.info("pending_db_flush: %s", stats)
        except Exception as e:
            logger.warning("pending_db_flush failed: %s", e)

    async def _execute_rss_feed_health(self, task: Task):
        """Nightly RSS feed yield review — warn-then-auto silencing."""
        from services.rss_feed_health_service import run_feed_health_cycle

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, run_feed_health_cycle)
        logger.info("rss_feed_health cycle: %s", result)

    async def _execute_rolling_arc_refresh(self, task: Task):
        """Phase B: refresh rolling 12-month arcs + latent co-arc proposals."""
        from services.rolling_arc_service import refresh_default_rolling_arcs

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, refresh_default_rolling_arcs)
        logger.info("rolling_arc_refresh: %s", result)

    async def _execute_health_check(self, task: Task):
        """Execute health check task (manual ``request_phase`` only; scheduled runs use ``_standalone_health_check_loop``)."""
        from shared.database.connection import get_health_db_connection_context

        loop = asyncio.get_event_loop()

        def _probe_sync():
            with get_health_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()

        await loop.run_in_executor(None, _probe_sync)
        self.metrics["last_health_check"] = datetime.now(timezone.utc)
        logger.debug("Health check passed")

    async def _standalone_health_check_loop(self):
        """Periodic SELECT 1 on the **health** DB pool — not queued with other phases, does not use the worker pool."""
        from shared.database.connection import get_health_db_connection_context

        loop = asyncio.get_event_loop()

        def _probe_sync():
            with get_health_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()

        logger.info("Standalone health_check loop started (dedicated DB pool)")
        while self.is_running:
            sched = self.schedules.get("health_check") or {}
            if not sched.get("enabled", True):
                await asyncio.sleep(60)
                continue
            interval = max(15, int(sched.get("interval", 120)))
            started_at = datetime.now(timezone.utc)
            try:
                await loop.run_in_executor(None, _probe_sync)
                finished_at = datetime.now(timezone.utc)
                self.metrics["last_health_check"] = finished_at
                sched["last_run"] = finished_at
                _persist_automation_run(
                    "health_check", started_at, finished_at, True, None
                )
                try:
                    cutoff = datetime.now(timezone.utc) - timedelta(minutes=60)
                    dq = self._phase_run_times_last_60m["health_check"]
                    dq.append(finished_at)
                    while dq and dq[0] < cutoff:
                        dq.popleft()
                except Exception:
                    pass
                logger.debug("health_check (standalone): ok")
                try:
                    from services.monitor_backlog_snapshot_service import (
                        maybe_refresh_monitor_backlog_snapshot,
                    )

                    await loop.run_in_executor(None, maybe_refresh_monitor_backlog_snapshot)
                except Exception as snap_err:
                    logger.debug("monitor_backlog_snapshot refresh skipped: %s", snap_err)
            except Exception as e:
                finished_at = datetime.now(timezone.utc)
                sched["last_run"] = finished_at
                _persist_automation_run(
                    "health_check", started_at, finished_at, False, str(e)
                )
                try:
                    cutoff = datetime.now(timezone.utc) - timedelta(minutes=60)
                    dq = self._phase_run_times_last_60m["health_check"]
                    dq.append(finished_at)
                    while dq and dq[0] < cutoff:
                        dq.popleft()
                except Exception:
                    pass
                logger.error("health_check (standalone): %s", e)
            remaining = float(interval)
            while remaining > 0 and self.is_running:
                chunk = min(remaining, 5.0)
                await asyncio.sleep(chunk)
                remaining -= chunk
        logger.info("Standalone health_check loop stopped")

    async def _health_monitor(self):
        """Monitor system health"""
        logger.info("Health monitor started")

        while self.is_running:
            try:
                phase_alive = sum(
                    1 for t in self._phase_worker_tasks if not t.done()
                )
                if phase_alive < len(self._phase_worker_tasks):
                    logger.warning(
                        "Only %s/%s phase dequeue workers alive",
                        phase_alive,
                        len(self._phase_worker_tasks),
                    )

                # Check task queue size
                queue_size = self.task_queue.qsize()
                if queue_size > 100:
                    logger.warning(f"Task queue size: {queue_size}, consider scaling")

                # Check memory usage
                import psutil

                memory_percent = psutil.virtual_memory().percent
                if memory_percent > 80:
                    logger.warning(f"High memory usage: {memory_percent}%")

                await asyncio.sleep(self.health_check_interval)

            except Exception as e:
                logger.error(f"Health monitor error: {e}")
                await asyncio.sleep(self.health_check_interval)

        logger.info("Health monitor stopped")

    async def _metrics_collector(self):
        """Collect system metrics"""
        logger.info("Metrics collector started")

        while self.is_running:
            try:
                # Update system uptime
                self.metrics["system_uptime"] = time.time()

                # Log metrics every 5 minutes
                if int(time.time()) % 300 == 0:
                    logger.info(f"Metrics: {self.metrics}")

                await asyncio.sleep(60)

            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
                await asyncio.sleep(60)

        logger.info("Metrics collector stopped")

    def _update_avg_processing_time(self, new_time: float):
        """Update average processing time"""
        if self.metrics["avg_processing_time"] == 0:
            self.metrics["avg_processing_time"] = new_time
        else:
            # Exponential moving average
            alpha = 0.1
            self.metrics["avg_processing_time"] = (
                alpha * new_time + (1 - alpha) * self.metrics["avg_processing_time"]
            )

    async def _execute_rag_enhancement(self, task: Task):
        from services.rag_enhancement_runner import run_rag_enhancement_batch

        await run_rag_enhancement_batch()

    async def _execute_ml_processing(self, task: Task):
        """Queue articles for ML processing; drain multiple rounds within run budget."""
        from shared.legacy_intake_rollback import legacy_intake_rollback_active

        if not legacy_intake_rollback_active():
            logger.debug(
                "ml_processing skipped (unified intake path; LEGACY_INTAKE_EXTRACTION_ENABLED for rollback)"
            )
            return
        try:
            from modules.ml.background_processor import BackgroundMLProcessor

            from shared.pipeline_batch_drain import RunBudget, phase_run_budget_seconds

            ml_processor = BackgroundMLProcessor(self.db_config)
            processed_count = 0
            batch_rounds = 0
            try:
                from shared.adaptive_batch_policy import resolve_phase_batch_limit

                per_schema_limit = resolve_phase_batch_limit(
                    "ml_processing", 50, env_suffix="BATCH_LIMIT"
                )
            except Exception:
                from shared.pipeline_batch_drain import phase_batch_limit

                per_schema_limit = phase_batch_limit("ml_processing", 50, env_suffix="BATCH_LIMIT")
            budget = RunBudget(phase_run_budget_seconds("ml_processing", 900))

            ml_ready = sql_ml_ready_and_content_bounds()
            _ord = sql_order_created_at()

            while not budget.expired():
                round_queued = 0
                for schema in get_pipeline_schema_names_active():
                    conn = await self._get_db_connection()
                    try:
                        with conn.cursor() as cursor:
                            cursor.execute(f"""
                                SELECT id FROM {schema}.articles
                                WHERE ml_processed = FALSE
                                  AND ({ml_ready})
                                ORDER BY created_at {_ord}
                                LIMIT {per_schema_limit}
                            """)
                            articles = cursor.fetchall()
                    finally:
                        conn.close()

                    for (article_id,) in articles:
                        try:
                            ml_processor.queue_article_for_processing(
                                article_id, "full_analysis"
                            )
                            processed_count += 1
                            round_queued += 1
                        except Exception as e:
                            logger.error(
                                "Error processing article %s (%s): %s", article_id, schema, e
                            )

                if round_queued == 0:
                    break
                batch_rounds += 1

            logger.info(
                "ML processing completed: %s articles queued in %s round(s) (budget=%ss)",
                processed_count,
                batch_rounds,
                phase_run_budget_seconds("ml_processing", 900),
            )
        except Exception as e:
            if "ml_processed" in str(e) and (
                "does not exist" in str(e) or "UndefinedColumn" in str(e)
            ):
                logger.debug("ML processing skipped (column ml_processed not in schema): %s", e)
            else:
                raise

    async def _mark_article_phase_failure(
        self,
        *,
        schema: str,
        article_id: int,
        phase_name: str,
        error: Exception,
        default_max_attempts: int,
    ) -> None:
        """
        Track per-article phase failures in metadata and set terminal skip flags after N failures.
        This prevents wasteful re-queue loops on rows that consistently fail.
        """
        env_key = f"{phase_name.upper()}_MAX_FAILURES"
        try:
            max_failures = int(env_str(env_key, str(default_max_attempts)))
        except ValueError:
            max_failures = default_max_attempts
        max_failures = max(1, min(20, max_failures))

        fail_key = f"{phase_name}_failures"
        skip_key = f"{phase_name}_skip"
        last_err_key = f"{phase_name}_last_error"
        err_text = str(error)[:300]

        conn = await self._get_db_connection()
        if not conn:
            return
        terminal_skip = False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT metadata FROM {schema}.articles WHERE id = %s",
                    (article_id,),
                )
                row = cur.fetchone()
                if not row:
                    return
                md = row[0] or {}
                if isinstance(md, str):
                    try:
                        md = json.loads(md)
                    except Exception:
                        md = {}
                if not isinstance(md, dict):
                    md = {}
                p = md.get("pipeline_skip")
                if not isinstance(p, dict):
                    p = {}
                if bool(p.get(skip_key)):
                    return
                failures = int(p.get(fail_key, 0) or 0) + 1
                p[fail_key] = failures
                p[last_err_key] = err_text
                if failures >= max_failures:
                    p[skip_key] = True
                md["pipeline_skip"] = p
                terminal_skip = bool(p.get(skip_key))

                if phase_name == "event_extraction" and bool(p.get(skip_key)):
                    cur.execute(
                        f"""
                        UPDATE {schema}.articles
                        SET metadata = %s::jsonb,
                            timeline_processed = true,
                            timeline_events_generated = COALESCE(timeline_events_generated, 0),
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                        """,
                        (json.dumps(md), article_id),
                    )
                else:
                    cur.execute(
                        f"""
                        UPDATE {schema}.articles
                        SET metadata = %s::jsonb,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                        """,
                        (json.dumps(md), article_id),
                    )
            conn.commit()
            if terminal_skip:
                log_terminal_skip_stub_candidate(schema, article_id, phase_name)
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.debug(
                "mark_article_phase_failure failed schema=%s article_id=%s phase=%s: %s",
                schema,
                article_id,
                phase_name,
                e,
            )
        finally:
            conn.close()

    async def _execute_sentiment_analysis(self, task: Task):
        """Execute sentiment analysis; drain batches within run budget."""
        from shared.legacy_intake_rollback import legacy_intake_rollback_active

        if not legacy_intake_rollback_active():
            logger.debug("sentiment_analysis skipped (folded into unified intake)")
            return
        from shared.legacy_intake_rollback import load_ai_processing_service
        from shared.pipeline_batch_drain import RunBudget, phase_run_budget_seconds
        from shared.pipeline_pass_marker import phase_backlog_uses_pass_marker, record_article_phase_pass, sql_article_pass_null

        ai_service = load_ai_processing_service().get_ai_service()
        analyzed_count = 0
        batch_rounds = 0
        try:
            from shared.adaptive_batch_policy import resolve_phase_batch_limit

            per_schema_limit = resolve_phase_batch_limit(
                "sentiment_analysis", 100, env_suffix="BATCH_LIMIT"
            )
        except Exception:
            from shared.pipeline_batch_drain import phase_batch_limit

            per_schema_limit = phase_batch_limit(
                "sentiment_analysis", 100, env_suffix="BATCH_LIMIT"
            )
        budget = RunBudget(phase_run_budget_seconds("sentiment_analysis", 900))

        ml_ready = sql_ml_ready_and_content_bounds()
        pass_clause = ""
        if phase_backlog_uses_pass_marker("sentiment_analysis"):
            pass_clause = f" AND ({sql_article_pass_null('sentiment_analysis', 'a')}) "
        _ord = sql_order_created_at()

        while not budget.expired():
            round_analyzed = 0
            for schema in get_pipeline_schema_names_active():
                conn = await self._get_db_connection()
                try:
                    with conn.cursor() as cursor:
                        cursor.execute(f"""
                            SELECT a.id, a.content FROM {schema}.articles a
                            WHERE a.sentiment_score IS NULL
                              AND COALESCE((a.metadata #>> '{{pipeline_skip,sentiment_analysis_skip}}')::boolean, false) = false
                              AND ({ml_ready})
                              {pass_clause}
                            ORDER BY a.created_at {_ord}
                            LIMIT {per_schema_limit}
                        """)
                        articles = cursor.fetchall()
                finally:
                    conn.close()

                for article_id, content in articles:
                    try:
                        sentiment = await ai_service.analyze_sentiment(content)
                        if not isinstance(sentiment, dict):
                            continue
                        score = sentiment.get("score", 0)
                        label = sentiment.get("label", "")

                        write_conn = await self._get_db_connection()
                        try:
                            with write_conn.cursor() as write_cur:
                                write_cur.execute(
                                    f"""
                                    UPDATE {schema}.articles
                                    SET sentiment_score = %s,
                                        sentiment_label = COALESCE(%s, sentiment_label),
                                        updated_at = CURRENT_TIMESTAMP
                                    WHERE id = %s
                                """,
                                    (score, label or None, article_id),
                                )
                                write_conn.commit()
                            record_article_phase_pass(schema, article_id, "sentiment_analysis", "scored")
                            analyzed_count += 1
                            round_analyzed += 1
                        finally:
                            write_conn.close()
                    except Exception as e:
                        logger.error(
                            "Error analyzing sentiment for article %s (%s): %s", article_id, schema, e
                        )
                        await self._mark_article_phase_failure(
                            schema=schema,
                            article_id=article_id,
                            phase_name="sentiment_analysis",
                            error=e,
                            default_max_attempts=3,
                        )

            if round_analyzed == 0:
                break
            batch_rounds += 1

        logger.info(
            "Sentiment analysis completed: %s articles in %s round(s) (budget=%ss)",
            analyzed_count,
            batch_rounds,
            phase_run_budget_seconds("sentiment_analysis", 900),
        )

    async def _execute_storyline_processing(self, task: Task):
        from shared.retired_phase_dispatch import dispatch_retired_automation_phase

        await dispatch_retired_automation_phase(self, "storyline_processing", task)

    async def _execute_storyline_automation(self, task: Task):
        """Run RAG discovery for one storyline (from metadata) or all automation-enabled storylines."""
        from services.storyline_automation_service import StorylineAutomationService

        meta = task.metadata or {}
        storyline_id = meta.get("storyline_id")
        domain = meta.get("domain")
        if storyline_id and domain:
            try:
                svc = StorylineAutomationService(domain=domain)
                batch_started = datetime.now(timezone.utc)
                result = await svc.discover_articles_for_storyline(
                    storyline_id, force_refresh=False
                )
                count = len(result.get("articles", []))
                await self._record_phase_batch_loop(
                    task,
                    loops_processed=1,
                    storylines_scanned=1,
                    articles_matched=count,
                    round_processed=1,
                    domain=domain,
                    storyline_id=storyline_id,
                )
                task.metadata["skip_automation_run_history"] = True
                logger.info(
                    "Storyline automation: storyline_id=%s domain=%s discovered %s articles",
                    storyline_id,
                    domain,
                    count,
                )
            except Exception as e:
                logger.warning(
                    "Storyline automation failed for storyline_id=%s: %s", storyline_id, e
                )
        else:
            # Run for all automation-enabled storylines (each domain)
            batch_limit = 5
            try:
                batch_limit = max(
                    5,
                    env_int("STORYLINE_AUTOMATION_BATCH_PER_DOMAIN", 15),
                )
            except ValueError:
                pass
            try:
                from shared.adaptive_batch_policy import resolve_adaptive_batch

                batch_limit, _meta = resolve_adaptive_batch("storyline_automation", batch_limit)
                batch_limit = max(5, int(batch_limit))
            except Exception:
                pass
            for d in _domains_for_phase("storyline_automation"):
                # Optional operator pause (empty default — not a permanent domain policy).
                excluded_raw = env_str("STORYLINE_AUTOMATION_EXCLUDE_DOMAINS", "") or ""
                excluded = {x.strip() for x in excluded_raw.split(",") if x.strip()}
                if d in excluded:
                    logger.info(
                        "Storyline automation: skipping domain=%s (STORYLINE_AUTOMATION_EXCLUDE_DOMAINS)",
                        d,
                    )
                    continue
                domain_started = datetime.now(timezone.utc)
                scanned = 0
                matched = 0
                skipped_freq = 0
                skipped_backoff = 0
                try:
                    svc = StorylineAutomationService(domain=d)
                    conn = await self._get_db_connection()
                    schema = resolve_domain_schema(d)
                    try:
                        with conn.cursor() as cur:
                            # Due by frequency, and not inside zero-yield backoff window.
                            cur.execute(f"""
                                SELECT id FROM {schema}.storylines
                                WHERE automation_enabled = true
                                  AND (
                                    last_automation_run IS NULL
                                    OR last_automation_run
                                         <= NOW() - (COALESCE(automation_frequency_hours, 24) || ' hours')::interval
                                  )
                                  AND (
                                    NULLIF(quality_metrics->>'zero_yield_until', '') IS NULL
                                    OR (quality_metrics->>'zero_yield_until')::timestamptz <= NOW()
                                  )
                                ORDER BY last_automation_run ASC NULLS FIRST
                                LIMIT %s
                            """, (batch_limit,))
                            storyline_rows = cur.fetchall()
                    finally:
                        conn.close()
                    for row in storyline_rows:
                        scanned += 1
                        result = await svc.discover_articles_for_storyline(row[0], force_refresh=False)
                        if result.get("skipped_frequency"):
                            skipped_freq += 1
                        if result.get("skipped_zero_yield_backoff"):
                            skipped_backoff += 1
                        matched += len(result.get("articles") or [])
                    if scanned > 0:
                        await self._record_phase_batch_loop(
                            task,
                            loops_processed=scanned,
                            storylines_scanned=scanned,
                            articles_matched=matched,
                            round_processed=scanned,
                            domain=d,
                            skipped_frequency=skipped_freq,
                            skipped_zero_yield_backoff=skipped_backoff,
                        )
                        task.metadata["skip_automation_run_history"] = True
                except Exception as e:
                    logger.debug("Storyline automation batch %s: %s", d, e)
            if not (task.metadata or {}).get("skip_automation_run_history"):
                # Idle sweep (nothing due): still stamp budget so Monitor can measure.
                n_dom = len(_domains_for_phase("storyline_automation")) or 1
                self._stamp_monitor_batch_throughput(
                    task,
                    round_processed=int(batch_limit) * int(n_dom),
                    items_processed=0,
                    adaptive_batch=int(batch_limit),
                )
            logger.info("Storyline automation: batch run across domains completed")

    async def _execute_storyline_review_agent(self, task: Task):
        """LLM agent: approve/reject pending storyline_article_suggestions."""
        if env_str("STORYLINE_REVIEW_AGENT_ENABLED", "true").lower() not in ("1", "true", "yes"):
            return
        from services.storyline_review_agent_service import run_storyline_review_agent_all_domains

        batch_limit = 60
        adaptive_meta: dict = {}
        try:
            batch_limit = max(10, env_int("STORYLINE_REVIEW_BATCH_SIZE", 60))
        except ValueError:
            batch_limit = 60
        try:
            from shared.adaptive_batch_policy import resolve_adaptive_batch

            batch_limit, adaptive_meta = resolve_adaptive_batch(
                "storyline_review_agent", batch_limit
            )
            batch_limit = max(10, int(batch_limit))
            if isinstance(task.metadata, dict):
                task.metadata["adaptive_batch"] = batch_limit
                if adaptive_meta:
                    task.metadata["adaptive_batch_meta"] = adaptive_meta
        except Exception:
            adaptive_meta = {}

        try:
            result = await run_storyline_review_agent_all_domains(batch_limit=batch_limit)
            approved = int(result.get("approved", 0) or 0)
            rejected = int(result.get("rejected", 0) or 0)
            skipped = int(result.get("skipped", 0) or 0)
            errors = int(result.get("errors", 0) or 0)
            llm_calls = int(result.get("llm_calls", 0) or 0)
            parse_exhausted = int(result.get("parse_exhausted", 0) or 0)
            decided = approved + rejected
            if isinstance(task.metadata, dict):
                task.metadata["approved"] = approved
                task.metadata["rejected"] = rejected
                task.metadata["skipped"] = skipped
                task.metadata["errors"] = errors
                task.metadata["llm_calls"] = llm_calls
                task.metadata["parse_exhausted"] = parse_exhausted
                task.metadata["decided"] = decided
                # Throughput for Monitor ETA = decisions only (skips do not drain).
                task.metadata["items_processed"] = decided
            yield_info: dict = {}
            try:
                from shared.adaptive_batch_policy import (
                    apply_adaptive_batch_yield_gate,
                    record_adaptive_batch_yield,
                )

                yield_info = record_adaptive_batch_yield(
                    "storyline_review_agent",
                    approved=approved,
                    rejected=rejected,
                    skipped=skipped,
                    errors=errors,
                    batch_limit=batch_limit,
                )
                if isinstance(task.metadata, dict):
                    task.metadata["adaptive_batch_yield"] = yield_info
                # Apply yield gate now (hold/decrease only — no headroom double-step).
                post_batch, post_meta = apply_adaptive_batch_yield_gate(
                    "storyline_review_agent"
                )
                if isinstance(task.metadata, dict):
                    task.metadata["adaptive_batch_after"] = int(post_batch)
                    task.metadata["adaptive_batch_meta_after"] = post_meta
            except Exception:
                pass
            try:
                await self._record_phase_batch_loop(
                    task,
                    loops_processed=1,
                    items_processed=decided,
                    approved=approved,
                    rejected=rejected,
                    skipped=skipped,
                    parse_exhausted=parse_exhausted,
                    llm_calls=llm_calls,
                    round_processed=1 if decided > 0 else 0,
                )
                if isinstance(task.metadata, dict):
                    task.metadata["skip_automation_run_history"] = True
            except Exception:
                pass
            logger.info(
                "Storyline review agent: approved=%s rejected=%s llm_calls=%s skipped=%s "
                "parse_exhausted=%s errors=%s batch=%s decided=%s "
                "adaptive_action=%s yield_gate=%s decision_rate=%s batch_after=%s",
                approved,
                rejected,
                llm_calls,
                skipped,
                parse_exhausted,
                errors,
                batch_limit,
                decided,
                (adaptive_meta or {}).get("action"),
                (
                    (task.metadata or {}).get("adaptive_batch_meta_after") or {}
                ).get("yield_gate")
                or (adaptive_meta or {}).get("yield_gate"),
                (yield_info or {}).get("decision_rate"),
                (task.metadata or {}).get("adaptive_batch_after", batch_limit),
            )
        except Exception as e:
            logger.warning("Storyline review agent failed: %s", e)

    async def _execute_storyline_membership_review(self, task: Task):
        """Decouple off-topic storyline members; soft-deprioritize weak connections."""
        if env_str("STORYLINE_MEMBERSHIP_REVIEW_ENABLED", "true").lower() not in (
            "1",
            "true",
            "yes",
        ):
            return
        from services.storyline_membership_review_service import (
            run_storyline_membership_review_all_domains,
        )

        limit = 100
        try:
            limit = max(1, env_int("STORYLINE_MEMBERSHIP_REVIEW_MAX_STORYLINES", 100))
        except ValueError:
            limit = 100
        adaptive_meta: dict = {}
        try:
            from shared.adaptive_batch_policy import resolve_adaptive_batch

            limit, adaptive_meta = resolve_adaptive_batch(
                "storyline_membership_review", limit
            )
            limit = max(1, int(limit))
            if isinstance(task.metadata, dict):
                task.metadata["adaptive_batch"] = limit
                if adaptive_meta:
                    task.metadata["adaptive_batch_meta"] = adaptive_meta
        except Exception:
            adaptive_meta = {}
        dry_run = env_str("STORYLINE_MEMBERSHIP_REVIEW_DRY_RUN", "false").lower() in (
            "1",
            "true",
            "yes",
        )
        try:
            result = run_storyline_membership_review_all_domains(
                limit_per_domain=limit, dry_run=dry_run
            )
            totals = result.get("totals") or {}
            by_domain = result.get("by_domain") or {}
            storylines_scanned = 0
            if isinstance(by_domain, dict):
                for domain_res in by_domain.values():
                    if isinstance(domain_res, dict):
                        storylines_scanned += len(domain_res.get("storylines") or [])
            # Action totals (esp. dry-run demote/unlink candidates) are not batch
            # throughput — Monitor rows/run must track storylines scanned only.
            action_total = sum(int(totals.get(k, 0) or 0) for k in totals)
            if isinstance(task.metadata, dict):
                task.metadata.update(
                    {
                        "dry_run": dry_run,
                        "unlinked": int(totals.get("unlinked", 0) or 0),
                        "demoted": int(totals.get("demoted", 0) or 0),
                        "queued": int(totals.get("queued", 0) or 0),
                        "graph_quarantined": int(totals.get("graph_quarantined", 0) or 0),
                        "sei_demoted": int(totals.get("sei_demoted", 0) or 0),
                        "tracked_events_unlinked": int(
                            totals.get("tracked_events_unlinked", 0) or 0
                        ),
                        "action_totals_sum": action_total,
                        "storylines_scanned": storylines_scanned,
                        "items_processed": storylines_scanned,
                    }
                )
            logger.info(
                "Storyline membership review: dry_run=%s limit_per_domain=%s totals=%s scanned=%s",
                dry_run,
                limit,
                totals,
                storylines_scanned,
            )
            try:
                await self._record_phase_batch_loop(
                    task,
                    loops_processed=1,
                    round_processed=storylines_scanned,
                    items_processed=storylines_scanned,
                    storylines_scanned=storylines_scanned,
                )
            except Exception:
                pass
            try:
                from services.storyline_membership_llm_agent import run_membership_llm_midband

                llm_limit = 40
                try:
                    from shared.adaptive_batch_policy import resolve_adaptive_batch

                    llm_limit, _llm_meta = resolve_adaptive_batch(
                        "storyline_review_agent", llm_limit
                    )
                except Exception:
                    llm_limit = 40
                llm_stats = await run_membership_llm_midband(
                    batch_limit=llm_limit, dry_run=dry_run
                )
                if isinstance(task.metadata, dict):
                    task.metadata["membership_llm"] = llm_stats
                logger.info("Storyline membership LLM mid-band: %s", llm_stats)
            except Exception as llm_e:
                logger.debug("Storyline membership LLM: %s", llm_e)
        except Exception as e:
            logger.warning("Storyline membership review failed: %s", e)

    async def _execute_storyline_hygiene(self, task: Task):
        """Freeze → core prune → near-dup title merge (move-not-copy)."""
        if env_str("STORYLINE_HYGIENE_ENABLED", "true").lower() not in (
            "1",
            "true",
            "yes",
        ):
            return
        from services.storyline_hygiene_service import run_storyline_hygiene_all_domains

        limit = 25
        try:
            limit = max(1, env_int("STORYLINE_HYGIENE_MAX_STORYLINES", 25))
        except ValueError:
            limit = 25
        max_merges = 5
        try:
            max_merges = max(0, env_int("STORYLINE_HYGIENE_MAX_MERGES", 5))
        except ValueError:
            max_merges = 5
        adaptive_meta: dict = {}
        try:
            from shared.adaptive_batch_policy import resolve_adaptive_batch

            limit, adaptive_meta = resolve_adaptive_batch("storyline_hygiene", limit)
            limit = max(1, int(limit))
            if isinstance(task.metadata, dict):
                task.metadata["adaptive_batch"] = limit
                if adaptive_meta:
                    task.metadata["adaptive_batch_meta"] = adaptive_meta
        except Exception:
            adaptive_meta = {}
        dry_run = env_str("STORYLINE_HYGIENE_DRY_RUN", "false").lower() in (
            "1",
            "true",
            "yes",
        )
        try:
            result = run_storyline_hygiene_all_domains(
                limit_per_domain=limit,
                max_merges_per_domain=max_merges,
                dry_run=dry_run,
            )
            totals = result.get("totals") or {}
            if isinstance(task.metadata, dict):
                task.metadata.update(
                    {
                        "dry_run": dry_run,
                        "pruned": int(totals.get("pruned", 0) or 0),
                        "unlinked": int(totals.get("unlinked", 0) or 0),
                        "merged": int(totals.get("merged", 0) or 0),
                        "merge_skipped": int(totals.get("merge_skipped", 0) or 0),
                        "merge_candidates": int(totals.get("merge_candidates", 0) or 0),
                        "errors": int(totals.get("errors", 0) or 0),
                        "items_processed": int(totals.get("pruned", 0) or 0),
                    }
                )
            logger.info(
                "Storyline hygiene: dry_run=%s limit=%s merges=%s totals=%s",
                dry_run,
                limit,
                max_merges,
                totals,
            )
            try:
                await self._record_phase_batch_loop(
                    task,
                    loops_processed=1,
                    round_processed=int(totals.get("pruned", 0) or 0),
                    items_processed=int(totals.get("pruned", 0) or 0),
                )
            except Exception:
                pass
        except Exception as e:
            logger.warning("Storyline hygiene failed: %s", e)

    async def _execute_embedding_link_candidates(self, task: Task):
        from shared.chemistry_beaker import embedding_link_candidates_enabled

        if not embedding_link_candidates_enabled():
            task.metadata = task.metadata or {}
            task.metadata["skip_automation_run_history"] = True
            return
        from services.embedding_link_candidate_service import (
            run_embedding_link_candidates_for_domain,
        )

        limit = 12
        try:
            limit = max(1, env_int("EMBEDDING_LINK_MAX_STORYLINES", 12))
        except ValueError:
            limit = 12
        try:
            from shared.adaptive_batch_policy import resolve_adaptive_batch

            limit, adaptive_meta = resolve_adaptive_batch("embedding_link_candidates", limit)
            if isinstance(task.metadata, dict):
                task.metadata["adaptive_batch"] = limit
                task.metadata["adaptive_batch_meta"] = adaptive_meta
        except Exception:
            pass
        try:
            domains = _domains_for_phase("embedding_link_candidates")
            by_domain = {}
            totals = {"proposals": 0, "merges_enqueued": 0, "scanned": 0, "errors": 0}
            for dk in domains:
                res = run_embedding_link_candidates_for_domain(dk, limit=limit)
                by_domain[dk] = res
                for k in totals:
                    totals[k] += int(res.get(k, 0) or 0)
            result = {"by_domain": by_domain, "totals": totals}
            totals = result.get("totals") or {}
            # Monitor measured rows/run requires metadata.batch=true. Use
            # per-domain adaptive limit × active domains so AVG matches
            # configured_rows_per_run (per-domain adaptive phases).
            doms = len(domains) or 1
            if isinstance(task.metadata, dict):
                task.metadata.update(
                    {
                        "proposals": int(totals.get("proposals", 0) or 0),
                        "merges_enqueued": int(totals.get("merges_enqueued", 0) or 0),
                        "scanned": int(totals.get("scanned", 0) or 0),
                    }
                )
                self._stamp_monitor_batch_throughput(
                    task,
                    round_processed=int(limit) * int(doms),
                    items_processed=int(totals.get("proposals", 0) or 0),
                )
            logger.info("Embedding link candidates: totals=%s batch=%s", totals, limit)
        except Exception as e:
            logger.warning("Embedding link candidates failed: %s", e)

    async def _execute_collision_sampling(self, task: Task):
        from shared.chemistry_beaker import collision_sampling_enabled

        if not collision_sampling_enabled():
            task.metadata = task.metadata or {}
            task.metadata["skip_automation_run_history"] = True
            return
        from services.embedding_link_candidate_service import run_random_collision_sample

        pairs = 8
        try:
            pairs = max(1, env_int("COLLISION_SAMPLING_PAIRS", 8))
        except ValueError:
            pairs = 8
        try:
            from shared.adaptive_batch_policy import resolve_adaptive_batch

            pairs, adaptive_meta = resolve_adaptive_batch("collision_sampling", pairs)
            if isinstance(task.metadata, dict):
                task.metadata["adaptive_batch"] = pairs
                task.metadata["adaptive_batch_meta"] = adaptive_meta
        except Exception:
            pass
        try:
            domains = _domains_for_phase("collision_sampling")
            proposals = 0
            errors = 0
            for dk in domains:
                result = run_random_collision_sample(domain_key=dk, pairs=pairs)
                proposals += int((result or {}).get("proposals") or 0)
                errors += int((result or {}).get("errors") or 0)
            if isinstance(task.metadata, dict):
                # batch + round_processed=pairs so measured rows/run tracks adaptive
                # pair budget (not proposal count, which is often pairs × domains).
                self._stamp_monitor_batch_throughput(
                    task,
                    round_processed=int(pairs),
                    items_processed=proposals,
                    proposals=proposals,
                    errors=errors,
                )
            logger.info(
                "Collision sampling: proposals=%s errors=%s pairs=%s domains=%s",
                proposals,
                errors,
                pairs,
                len(domains),
            )
        except Exception as e:
            logger.warning("Collision sampling failed: %s", e)

    async def _execute_stimulus_rag(self, task: Task):
        from shared.chemistry_beaker import stimulus_rag_enabled

        if not stimulus_rag_enabled():
            task.metadata = task.metadata or {}
            task.metadata["skip_automation_run_history"] = True
            return
        from services.rag_evidence_pull_service import (
            drain_queued_evidence_pulls,
            screen_ai_arxiv_for_evidence_pull,
            screen_hypothesized_bonds_for_evidence_pull,
        )

        screen_limit = 20
        try:
            from shared.adaptive_batch_policy import resolve_adaptive_batch

            screen_limit, adaptive_meta = resolve_adaptive_batch("stimulus_rag", screen_limit)
            if isinstance(task.metadata, dict):
                task.metadata["adaptive_batch"] = screen_limit
                task.metadata["adaptive_batch_meta"] = adaptive_meta
        except Exception:
            pass
        bond_limit = screen_limit
        drain_limit = max(1, min(8, max(3, screen_limit // 7)))
        try:
            screened = screen_ai_arxiv_for_evidence_pull(limit=screen_limit)
            bond_screened = screen_hypothesized_bonds_for_evidence_pull(limit=bond_limit)
            drained = drain_queued_evidence_pulls(limit=drain_limit)
            if isinstance(task.metadata, dict):
                task.metadata["screened"] = screened
                task.metadata["bond_screened"] = bond_screened
                task.metadata["drained"] = drained
                items = (
                    int(drained.get("processed") or 0)
                    + int(screened.get("enqueued") or 0)
                    + int(bond_screened.get("enqueued") or 0)
                )
                self._stamp_monitor_batch_throughput(
                    task,
                    round_processed=int(screen_limit),
                    items_processed=items,
                )
            logger.info(
                "Stimulus RAG: screen=%s bonds=%s drain=%s (screen_lim=%s drain_lim=%s)",
                screened,
                bond_screened,
                drained,
                screen_limit,
                drain_limit,
            )
        except Exception as e:
            logger.warning("Stimulus RAG failed: %s", e)

    async def _execute_protein_harden(self, task: Task):
        from shared.chemistry_beaker import protein_harden_enabled

        if not protein_harden_enabled():
            task.metadata = task.metadata or {}
            task.metadata["skip_automation_run_history"] = True
            return
        from services.protein_harden_service import run_protein_harden

        limit = 40
        try:
            limit = max(1, env_int("PROTEIN_HARDEN_BATCH", 40))
        except ValueError:
            limit = 40
        try:
            from shared.adaptive_batch_policy import resolve_adaptive_batch

            limit, adaptive_meta = resolve_adaptive_batch("protein_harden", limit)
            if isinstance(task.metadata, dict):
                task.metadata["adaptive_batch"] = limit
                task.metadata["adaptive_batch_meta"] = adaptive_meta
        except Exception:
            pass
        try:
            result = run_protein_harden(limit=limit)
            if isinstance(task.metadata, dict):
                task.metadata.update(result)
                self._stamp_monitor_batch_throughput(
                    task,
                    round_processed=int(limit),
                    items_processed=int(result.get("promoted") or 0)
                    + int(result.get("refined") or 0),
                )
            logger.info("Protein harden: %s batch=%s", result, limit)
        except Exception as e:
            logger.warning("Protein harden failed: %s", e)

    async def _execute_graph_link_drift_review(self, task: Task):
        if env_str("GRAPH_LINK_DRIFT_REVIEW_ENABLED", "false").lower() not in (
            "1",
            "true",
            "yes",
        ):
            return
        from services.graph_link_drift_service import rescore_active_graph_links

        limit = 40
        try:
            limit = max(1, env_int("GRAPH_LINK_DRIFT_BATCH", 40))
        except ValueError:
            limit = 40
        adaptive_meta: dict = {}
        try:
            from shared.adaptive_batch_policy import resolve_adaptive_batch

            limit, adaptive_meta = resolve_adaptive_batch("graph_link_drift_review", limit)
            limit = max(1, int(limit))
            if isinstance(task.metadata, dict):
                task.metadata["adaptive_batch"] = limit
                if adaptive_meta:
                    task.metadata["adaptive_batch_meta"] = adaptive_meta
        except Exception:
            adaptive_meta = {}

        try:
            stats = rescore_active_graph_links(limit=limit)
            if isinstance(task.metadata, dict):
                task.metadata.update(stats)
                self._stamp_monitor_batch_throughput(
                    task,
                    # Prefer round_processed=limit so measured rows/run tracks adaptive
                    # batch size (examined/updated may be lower on short queues).
                    round_processed=int(limit),
                    items_processed=int(stats.get("updated", 0) or 0)
                    + int(stats.get("quarantined", 0) or 0),
                )
            logger.info(
                "Graph link drift review: limit=%s adaptive=%s stats=%s",
                limit,
                bool(adaptive_meta.get("adaptive")) if adaptive_meta else False,
                stats,
            )
        except Exception as e:
            logger.warning("Graph link drift review failed: %s", e)

    async def _execute_storyline_enrichment(self, task: Task):
        from shared.retired_phase_dispatch import dispatch_retired_automation_phase

        await dispatch_retired_automation_phase(self, "storyline_enrichment", task)

    async def _execute_storyline_discovery(self, task: Task):
        from shared.retired_phase_dispatch import dispatch_retired_automation_phase

        await dispatch_retired_automation_phase(self, "storyline_discovery", task)

    async def _execute_proactive_detection(self, task: Task):
        from shared.retired_phase_dispatch import dispatch_retired_automation_phase

        await dispatch_retired_automation_phase(self, "proactive_detection", task)

    async def _execute_storyline_assembly(self, task: Task):
        """Run proactive detection + discovery + automation for one domain or all pipeline domains."""
        from services.storyline_assembly_service import (
            run_storyline_assembly_for_domain,
        )
        from shared.domain_processing_mode import domain_runs_phase

        meta = task.metadata or {}
        domain = meta.get("domain")
        task.metadata = task.metadata or {}
        try:
            if domain:
                if not domain_runs_phase(domain, "storyline_assembly"):
                    logger.debug(
                        "Storyline assembly skipped corpus domain=%s", domain
                    )
                    return
                result = await run_storyline_assembly_for_domain(domain)
                task.metadata["skip_automation_run_history"] = True
                logger.info(
                    "Storyline assembly [%s]: unlinked %s → %s steps=%s",
                    domain,
                    result.get("unlinked_before"),
                    result.get("unlinked_after"),
                    list((result.get("steps") or {}).keys()),
                )
            else:
                from services.storyline_assembly_service import (
                    domains_needing_assembly,
                    count_unlinked_articles,
                )

                allowed = set(_domains_for_phase("storyline_assembly"))
                domains = [dk for dk in domains_needing_assembly() if dk in allowed]
                if domains:
                    domains = sorted(
                        domains,
                        key=lambda dk: count_unlinked_articles(dk),
                        reverse=True,
                    )
                for dk in domains:
                    res = await run_storyline_assembly_for_domain(dk)
                    if res.get("unlinked_before", 0) != res.get("unlinked_after", 0):
                        logger.info(
                            "Storyline assembly [%s]: unlinked %s → %s",
                            dk,
                            res.get("unlinked_before"),
                            res.get("unlinked_after"),
                        )
                task.metadata["skip_automation_run_history"] = True
        except Exception as e:
            logger.warning("Storyline assembly failed: %s", e)

    async def _execute_fact_verification(self, task: Task):
        """v8: Verify recent claims per domain (governance-weighted corroboration, Wikipedia + internal checks; results returned to logs/API, not persisted on claim rows)."""
        try:
            from services.fact_verification_service import verify_recent_claims

            loop = asyncio.get_event_loop()
            try:
                from shared.adaptive_batch_policy import resolve_adaptive_batch

                fv_limit, _meta = resolve_adaptive_batch("fact_verification", 20)
            except Exception:
                fv_limit = 20
            fv_limit = max(1, int(fv_limit))
            for domain in _domains_for_phase("fact_verification"):
                try:
                    result = await loop.run_in_executor(
                        self._executor,
                        lambda d=domain, lim=fv_limit: verify_recent_claims(
                            d, hours=72, limit=lim
                        ),
                    )
                    if result.get("success") and result.get("claims_verified", 0) > 0:
                        logger.info(
                            "Fact verification [%s]: %s claims verified",
                            domain,
                            result["claims_verified"],
                        )
                        try:
                            from services.versioned_facts_lifecycle_service import (
                                writeback_verification_batch,
                            )

                            wb = writeback_verification_batch(
                                result.get("results") or []
                            )
                            if wb.get("facts_updated"):
                                logger.info(
                                    "Fact verification writeback [%s]: %s versioned_facts updated",
                                    domain,
                                    wb["facts_updated"],
                                )
                        except Exception as wb_err:
                            logger.debug(
                                "Fact verification writeback skipped [%s]: %s",
                                domain,
                                wb_err,
                            )
                except Exception as e:
                    logger.debug("Fact verification failed for %s: %s", domain, e)
        except Exception as e:
            logger.warning("Fact verification task failed: %s", e)

    async def _execute_spine_sql_tail(self, task: Task) -> None:
        """SQL-only spine tail: claims_to_facts, profile links, link indexer, event markers."""
        from shared.pipeline_batch_drain import phase_run_budget_seconds
        from services.spine_sql_tail_service import run_spine_sql_tail_drain

        task.metadata = task.metadata or {}
        task.metadata["skip_automation_run_history"] = True
        result = await run_spine_sql_tail_drain(
            budget_seconds=phase_run_budget_seconds("spine_sql_tail", 300),
        )
        processed = int(
            result.get("claims_to_facts", 0)
            + result.get("profile_links", 0)
            + result.get("link_indexer_articles", 0)
            + result.get("event_context_markers", 0)
        )
        if processed > 0 or int(result.get("rounds") or 0) > 0:
            await self._record_phase_batch_loop(
                task,
                loops_processed=max(1, int(result.get("rounds") or 0)),
                processed=processed,
                round_processed=processed,
            )
        task.metadata["items_processed"] = processed
        logger.info("spine_sql_tail drain: processed=%s rounds=%s", processed, result.get("rounds"))

    async def _execute_unified_intake_extraction(self, task: Task):
        """Single batched LLM pass: entities, claims, events, sentiment, quality."""
        from shared.pipeline_batch_drain import phase_run_budget_seconds
        from shared.unified_intake_extraction_runner import run_unified_intake_extraction_batch_drain

        async def _on_fail(schema: str, article_id: int, error: Exception) -> None:
            await self._mark_article_phase_failure(
                schema=schema,
                article_id=article_id,
                phase_name="unified_intake_extraction",
                error=error,
                default_max_attempts=3,
            )

        task.metadata = task.metadata or {}
        task.metadata["skip_automation_run_history"] = True
        task.metadata.pop("_batch_run_started_at", None)
        on_batch = self._make_batch_progress_callback(task)

        async def _unified_batch_cb(batch_n: int, stats: dict) -> None:
            await on_batch(batch_n, **stats)

        async def _unified_wave_cb(wave_idx: int, stats: dict) -> None:
            processed = int(stats.get("round_processed") or 0)
            if processed <= 0:
                return
            await on_batch(
                int(stats.get("batch_round") or wave_idx),
                round_processed=processed,
                total_processed=int(stats.get("total_processed") or processed),
                backfill_count=int(stats.get("backfill_count") or 0),
            )

        per_domain = None
        try:
            from shared.adaptive_batch_policy import resolve_phase_batch_limit

            per_domain = resolve_phase_batch_limit("unified_intake_extraction", 40)
        except Exception:
            pass

        result = await run_unified_intake_extraction_batch_drain(
            budget_seconds=phase_run_budget_seconds("unified_intake_extraction", 0),
            articles_per_domain=per_domain,
            on_article_failure=_on_fail,
            on_batch_complete=_unified_batch_cb,
            on_wave_complete=_unified_wave_cb,
        )
        processed = int(result.get("articles_processed") or 0)
        logger.info(
            "Unified intake extraction: %s articles in %s batch round(s)",
            processed,
            result.get("batch_rounds", 0),
        )
        # Critical path: CE restore (if needed) → event coreference before chemistry stir.
        try:
            from shared.pipeline_handoffs import after_unified_intake

            after_unified_intake(self, articles_processed=processed)
        except Exception as e:
            logger.debug("unified_intake event-rail handoff: %s", e)
        # Legacy chemistry beaker — secondary; gated by CHEMISTRY_BEAKER_ENABLED.
        try:
            from shared.chemistry_beaker import kickoff_beaker_phases

            kickoff_beaker_phases(self, reason="unified_intake_batch_complete")
        except Exception as e:
            logger.debug("unified_intake beaker kickoff: %s", e)

    async def _execute_entity_extraction(self, task: Task):
        """Batched entity extraction on PopOS GPU (with Widow CPU overflow when dual-lane)."""
        from shared.legacy_intake_rollback import (
            legacy_intake_rollback_active,
            load_entity_extraction_runner,
        )

        if not legacy_intake_rollback_active():
            logger.debug(
                "entity_extraction skipped (unified intake path; LEGACY_INTAKE_EXTRACTION_ENABLED for rollback)"
            )
            return

        run_entity_extraction_batch_drain = load_entity_extraction_runner().run_entity_extraction_batch_drain

        async def _on_fail(schema: str, article_id: int, error: Exception) -> None:
            await self._mark_article_phase_failure(
                schema=schema,
                article_id=article_id,
                phase_name="entity_extraction",
                error=error,
                default_max_attempts=3,
            )

        result = await run_entity_extraction_batch_drain(on_article_failure=_on_fail)
        extracted_count = int(result.get("articles_processed") or 0)
        logger.info(
            "Entity extraction completed: %s articles in %s batch round(s)",
            extracted_count,
            result.get("batch_rounds", 0),
        )

        if extracted_count > 0 and env_str("ENTITY_EXTRACTION_POST_SYNC", "").lower() in (
            "1",
            "true",
            "yes",
        ):
            try:
                post_lim = env_int("ENTITY_EXTRACTION_POST_MENTION_LIMIT", 1500)
            except ValueError:
                post_lim = 1500
            from services.context_processor_service import backfill_context_entity_mentions_for_domain
            from services.entity_profile_sync_service import sync_domain_entity_profiles
            from shared.domain_registry import pipeline_url_schema_pairs

            for domain_key, _schema_name in pipeline_url_schema_pairs():
                try:
                    sync_domain_entity_profiles(domain_key)
                except Exception as e:
                    logger.debug("entity_extraction post-sync profiles %s: %s", domain_key, e)
                try:
                    backfill_context_entity_mentions_for_domain(domain_key, limit=max(50, post_lim))
                except Exception as e:
                    logger.debug("entity_extraction post-sync mentions %s: %s", domain_key, e)

    async def _execute_mention_resolution(self, task: Task):
        from services.automation.executor import execute_mention_resolution

        await execute_mention_resolution(task)

    async def _execute_event_extraction_v5(self, task: Task):
        """v5.0 — batched event extraction with PopOS GPU routing when enabled."""
        from shared.legacy_intake_rollback import (
            legacy_intake_rollback_active,
            load_event_extraction_runner,
        )

        if not legacy_intake_rollback_active():
            logger.debug(
                "event_extraction skipped (unified intake path; LEGACY_INTAKE_EXTRACTION_ENABLED for rollback)"
            )
            return
        try:
            run_event_extraction_batch_drain = load_event_extraction_runner().run_event_extraction_batch_drain

            async def _on_fail(schema: str, article_id: int, error: Exception) -> None:
                await self._mark_article_phase_failure(
                    schema=schema,
                    article_id=article_id,
                    phase_name="event_extraction",
                    error=error,
                    default_max_attempts=2,
                )

            result = await run_event_extraction_batch_drain(on_article_failure=_on_fail)
            logger.info(
                "v5 event extraction completed: %s events from %s articles (%s rounds)",
                result.get("events_saved", 0),
                result.get("articles_processed", 0),
                result.get("batch_rounds", 0),
            )
        except Exception as e:
            if (
                "timeline_processed" in str(e) or "chronological_events" in str(e)
            ) and "does not exist" in str(e):
                logger.debug("Event extraction skipped (schema not migrated): %s", e)
            else:
                raise

    async def _execute_event_deduplication_v5(self, task: Task):
        """v5.0 -- Deduplicate / coreference events. Skips cleanly if chronological_events is missing."""
        try:
            from services.event_coreference_service import coreference_recent

            conn = await self._get_db_connection()
            try:
                dedupe_limit = 100
                try:
                    from shared.adaptive_batch_policy import resolve_adaptive_batch

                    dedupe_limit, adaptive_meta = resolve_adaptive_batch(
                        "event_deduplication", dedupe_limit
                    )
                    if isinstance(task.metadata, dict):
                        task.metadata["adaptive_batch"] = dedupe_limit
                        task.metadata["adaptive_batch_meta"] = adaptive_meta
                except Exception:
                    pass
                stats = await coreference_recent(conn, limit=dedupe_limit)
                if isinstance(task.metadata, dict):
                    task.metadata["dedup_stats"] = {
                        k: stats.get(k, 0)
                        for k in (
                            "checked",
                            "merged",
                            "hard_merges",
                            "soft_links",
                            "chains_collapsed",
                            "soft_pruned",
                        )
                    }
                logger.info(
                    "v5 event deduplication completed: "
                    "checked=%s, merged=%s, hard_merges=%s, soft_links=%s, "
                    "chains_collapsed=%s, soft_pruned=%s (batch=%s)",
                    stats.get("checked", 0),
                    stats.get("merged", 0),
                    stats.get("hard_merges", 0),
                    stats.get("soft_links", 0),
                    stats.get("chains_collapsed", 0),
                    stats.get("soft_pruned", 0),
                    dedupe_limit,
                )
                try:
                    from shared.pipeline_handoffs import after_event_deduplication

                    after_event_deduplication(
                        self,
                        merged=int(stats.get("merged") or 0),
                        soft_links=int(stats.get("soft_links") or 0),
                        hard_merges=int(stats.get("hard_merges") or 0),
                    )
                except Exception as e:
                    logger.debug("event_deduplication handoff: %s", e)
            finally:
                conn.close()
        except Exception as e:
            if "chronological_events" in str(e) and "does not exist" in str(e):
                logger.debug(
                    "Event deduplication skipped (chronological_events not migrated): %s", e
                )
            else:
                logger.error(f"Event deduplication failed: {e}", exc_info=True)
                raise

    async def _execute_chronological_events_catchup(self, task: Task):
        """Re-extract chronological_events for UIE-complete articles with zero CE rows."""
        from services.chronological_events_catchup_service import (
            is_enabled,
            run_catchup_batch_sync,
        )

        if not is_enabled():
            logger.debug(
                "chronological_events_catchup skipped (CHRONOLOGICAL_EVENTS_CATCHUP_ENABLED off)"
            )
            return
        try:
            limit = 5
            if isinstance(task.metadata, dict) and task.metadata.get("batch_limit"):
                limit = int(task.metadata["batch_limit"])
            stats = await asyncio.to_thread(run_catchup_batch_sync, limit=limit)
            if stats and int(stats.get("processed") or 0) > 0:
                logger.info("chronological_events_catchup: %s", stats)
            await self._record_phase_batch_loop(
                task,
                loops_processed=1,
                round_processed=int(stats.get("processed") or 0),
                items_processed=int(stats.get("saved_total") or 0),
            )
            try:
                from shared.pipeline_handoffs import after_chronological_events_catchup

                after_chronological_events_catchup(
                    self, saved_total=int((stats or {}).get("saved_total") or 0)
                )
            except Exception as e:
                logger.debug("chronological_events_catchup handoff: %s", e)
        except Exception as e:
            logger.warning("chronological_events_catchup failed: %s", e)

    async def _execute_story_continuation_v5(self, task: Task):
        """v5.0 -- Match events to existing storylines and manage lifecycle states. Runs per domain (storylines/story_entity_index are per-schema)."""
        from services.pipeline_phase_heartbeat_service import record_phase_heartbeat
        from services.story_continuation_service import StoryContinuationService

        conn = await self._get_db_connection()
        if not conn:
            logger.warning("Story continuation: no DB connection")
            return
        try:
            total = {"checked": 0, "linked": 0, "flagged": 0}
            cont_limit = 30
            try:
                from shared.adaptive_batch_policy import resolve_adaptive_batch

                cont_limit, adaptive_meta = resolve_adaptive_batch("story_continuation", cont_limit)
                if isinstance(task.metadata, dict):
                    task.metadata["adaptive_batch"] = cont_limit
                    task.metadata["adaptive_batch_meta"] = adaptive_meta
            except Exception:
                pass
            for schema in _schemas_for_phase("story_continuation"):
                try:
                    svc = StoryContinuationService(conn, schema=schema)
                    stats = await svc.process_recent_events(limit=cont_limit)
                    svc.update_lifecycle_states()
                    total["checked"] += stats["checked"]
                    total["linked"] += stats["linked"]
                    total["flagged"] += stats["flagged"]
                    if stats["checked"] or stats["linked"] or stats["flagged"]:
                        logger.debug(
                            "Story continuation [%s]: checked=%s linked=%s flagged=%s",
                            schema,
                            stats["checked"],
                            stats["linked"],
                            stats["flagged"],
                        )
                except Exception as e:
                    logger.warning("Story continuation failed for schema %s: %s", schema, e)
            logger.info(
                f"v5 story continuation completed: "
                f"checked={total['checked']}, linked={total['linked']}, flagged={total['flagged']}"
            )
            await self._record_phase_batch_loop(
                task,
                loops_processed=1,
                round_processed=total["checked"],
                items_processed=total["linked"] + total["flagged"],
            )
            try:
                from shared.pipeline_handoffs import after_story_continuation

                after_story_continuation(self, linked=int(total.get("linked") or 0))
            except Exception as e:
                logger.debug("story_continuation handoff: %s", e)
            try:
                record_phase_heartbeat(
                    "story_continuation",
                    scheduler_path="automation",
                    success=True,
                    items_processed=total["checked"],
                    detail={
                        "status": "complete",
                        "linked": total["linked"],
                        "flagged": total["flagged"],
                        "checked": total["checked"],
                    },
                )
            except Exception as hb_err:
                logger.debug("story_continuation heartbeat: %s", hb_err)
        finally:
            conn.close()

    async def _execute_watchlist_alerts_v5(self, task: Task):
        """v5.0 -- Generate alerts for watched storylines."""
        from services.watchlist_service import WatchlistService

        conn = await self._get_db_connection()
        try:
            svc = WatchlistService(conn)
            reactivation = svc.generate_reactivation_alerts()
            new_events = svc.generate_new_event_alerts()

            logger.info(f"v5 watchlist alerts: {reactivation} reactivation, {new_events} new-event")
        except Exception as e:
            if "does not exist" in str(e) or "relation" in str(e).lower():
                logger.debug(
                    "Watchlist alerts skipped (watchlist/chronological_events not migrated): %s", e
                )
            else:
                logger.warning("Watchlist alerts failed: %s", e)
        finally:
            conn.close()

    async def _execute_quality_scoring(self, task: Task):
        """Execute quality scoring task"""
        from shared.legacy_intake_rollback import legacy_intake_rollback_active

        if not legacy_intake_rollback_active():
            logger.debug("quality_scoring skipped (folded into unified intake)")
            return
        from shared.legacy_intake_rollback import load_ai_processing_service

        ai_service = load_ai_processing_service().get_ai_service()
        scored_count = 0

        ml_ready = sql_ml_ready_and_content_bounds()
        _ord = sql_order_created_at()
        try:
            from shared.adaptive_batch_policy import resolve_adaptive_batch

            qs_limit, _meta = resolve_adaptive_batch("quality_scoring", 50)
        except Exception:
            qs_limit = 50
        qs_limit = max(1, int(qs_limit))
        for schema in get_pipeline_schema_names_active():
            # Fetch candidates quickly, then close transaction before awaited LLM work.
            conn = await self._get_db_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"""
                        SELECT id, content, title FROM {schema}.articles
                        WHERE quality_score IS NULL
                          AND COALESCE((metadata #>> '{{pipeline_skip,quality_scoring_skip}}')::boolean, false) = false
                          AND ({ml_ready})
                        ORDER BY created_at {_ord}
                        LIMIT %s
                    """,
                        (qs_limit,),
                    )
                    articles = cursor.fetchall()
            finally:
                conn.close()

            for article_id, content, title in articles:
                try:
                    quality = await ai_service.score_article_quality(content, title)
                    if not isinstance(quality, dict):
                        continue
                    write_conn = await self._get_db_connection()
                    try:
                        with write_conn.cursor() as write_cur:
                            write_cur.execute(
                                f"""
                                UPDATE {schema}.articles
                                SET quality_score = %s, updated_at = CURRENT_TIMESTAMP
                                WHERE id = %s
                            """,
                                (quality.get("score", 0), article_id),
                            )
                            write_conn.commit()
                        scored_count += 1
                    finally:
                        write_conn.close()
                except Exception as e:
                    logger.error(
                        "Error scoring quality for article %s (%s): %s", article_id, schema, e
                    )
                    await self._mark_article_phase_failure(
                        schema=schema,
                        article_id=article_id,
                        phase_name="quality_scoring",
                        error=e,
                        default_max_attempts=3,
                    )

        logger.info(f"Quality scoring completed: {scored_count} articles scored")

    async def _execute_timeline_generation(self, task: Task):
        from shared.retired_phase_dispatch import dispatch_retired_automation_phase

        await dispatch_retired_automation_phase(self, "timeline_generation", task)

    async def _execute_cache_cleanup(self, task: Task):
        """Execute cache cleanup task"""
        from services.smart_cache_service import get_cache_service

        cache_service = get_cache_service()

        try:
            # Clear expired cache entries
            cleared_count = await cache_service.clear_expired_cache()
            logger.info(f"Cache cleanup completed: {cleared_count} expired entries cleared")

        except Exception as e:
            logger.error(f"Error during cache cleanup: {e}")

    async def _execute_topic_clustering(self, task: Task):
        """Execute topic clustering — bounded SQL selection + parallel batch processing."""
        try:
            logger.info(
                "Starting topic clustering (parallel batch, topic_clusters SSOT)"
            )

            from config.settings import (
                topic_clustering_backlog_uses_pass_marker,
                topic_clustering_batch_size,
                topic_clustering_concurrency,
                topic_clustering_graduation_confidence,
                topic_clustering_iterative_refinement_enabled,
            )
            from domains.content_analysis.services.topic_clustering_service import (
                TopicClusteringService,
                process_articles_batch,
            )
            from shared.database.connection import get_db_config, get_db_connection
            from shared.domain_registry import (
                first_active_domain_key,
                pipeline_url_schema_pairs,
                resolve_domain_schema,
            )

            domains = [
                {"domain_key": dk, "schema_name": schema}
                for dk, schema in pipeline_url_schema_pairs()
            ]
            if not domains:
                fb = first_active_domain_key()
                logger.warning("No active domains found, defaulting to %s", fb)
                domains = [{"domain_key": fb, "schema_name": resolve_domain_schema(fb)}]

            CONFIDENCE_THRESHOLD = float(topic_clustering_graduation_confidence())
            TC_USE_PASS_MARKER = topic_clustering_backlog_uses_pass_marker()
            TC_ITERATIVE = topic_clustering_iterative_refinement_enabled()
            BATCH_SIZE = topic_clustering_batch_size()
            CONCURRENCY = topic_clustering_concurrency()

            db_config = get_db_config()
            total_processed = 0
            total_fast_lane = 0
            total_llm = 0

            for domain_info in domains:
                domain_key = domain_info["domain_key"]
                schema_name = domain_info.get("schema_name", domain_key.replace("-", "_"))

                logger.info("Topic clustering domain=%s schema=%s", domain_key, schema_name)

                topic_service = TopicClusteringService(db_config, domain=domain_key)
                topic_service.schema = schema_name

                conn = get_db_connection()
                try:
                    with conn.cursor() as cursor:
                        article_ids = TopicClusteringService.select_pending_article_ids(
                            cursor,
                            schema_name,
                            batch_size=BATCH_SIZE,
                            use_pass_marker=TC_USE_PASS_MARKER,
                            iterative=TC_ITERATIVE,
                            confidence_threshold=CONFIDENCE_THRESHOLD,
                        )
                finally:
                    conn.close()

                if not article_ids:
                    logger.info("No pending topic clustering articles in %s", domain_key)
                    continue

                logger.info(
                    "Selected %s articles (batch=%s concurrency=%s)",
                    len(article_ids),
                    BATCH_SIZE,
                    CONCURRENCY,
                )

                batch_result = await process_articles_batch(
                    topic_service,
                    article_ids,
                    concurrency=CONCURRENCY,
                )

                logger.info(
                    "  %s: processed=%s failed=%s fast_lane=%s llm=%s assigned=%s created=%s",
                    domain_key,
                    batch_result.processed,
                    batch_result.failed,
                    batch_result.fast_lane_hits,
                    batch_result.llm_extractions,
                    batch_result.topics_assigned,
                    batch_result.topics_created,
                )

                total_processed += batch_result.processed
                total_fast_lane += batch_result.fast_lane_hits
                total_llm += batch_result.llm_extractions

            logger.info(
                "Topic clustering cycle done: processed=%s fast_lane=%s llm=%s",
                total_processed,
                total_fast_lane,
                total_llm,
            )

        except Exception as e:
            logger.error(f"Error during topic clustering: {e}", exc_info=True)

    async def _get_db_connection(self):
        """Get database connection from shared pool. Runs in executor to avoid blocking the event loop."""
        from shared.database.connection import get_db_connection

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, get_db_connection)

    def _sql_measurable_runs_last_60m_by_phase(self) -> dict[str, int]:
        """DB-backed runs_1h counts — same predicate as processing_progress (survives API restart)."""
        import time

        now = time.monotonic()
        cached = self._measurable_runs_60m_sql_cache
        if now - float(cached.get("at") or 0) < 60.0 and isinstance(cached.get("counts"), dict):
            return cached["counts"]
        counts: dict[str, int] = {}
        try:
            from shared.database.connection import get_ui_db_connection_context
            from shared.monitor_run_vocabulary import MEANINGFUL_DURATION_SEC, run_history_measurable_sql

            measurable = run_history_measurable_sql()
            with get_ui_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT phase_name, COUNT(*)::int
                        FROM automation_run_history
                        WHERE finished_at >= NOW() - INTERVAL '1 hour'
                          AND {measurable}
                        GROUP BY phase_name
                        """,
                        {"min_dur": MEANINGFUL_DURATION_SEC},
                    )
                    for name, cnt in cur.fetchall() or []:
                        if name:
                            counts[str(name)] = int(cnt or 0)
        except Exception as e:
            logger.debug("sql measurable runs 60m: %s", e)
            prev = cached.get("counts")
            return prev if isinstance(prev, dict) else {}
        self._measurable_runs_60m_sql_cache = {"at": now, "counts": counts}
        return counts

    def _merged_runs_last_60m_by_phase(self) -> dict[str, int]:
        """max(in-memory live counter, SQL measurable) — aligned with processing_progress runs_1h."""
        in_mem = {k: len(dq) for k, dq in self._phase_run_times_last_60m.items() if dq}
        sql = self._sql_measurable_runs_last_60m_by_phase()
        merged = dict(sql)
        for phase, count in in_mem.items():
            merged[phase] = max(int(merged.get(phase, 0)), int(count))
        return merged

    def get_status(self, *, include_pending: bool = True) -> dict[str, Any]:
        """Get automation status.

        ``include_pending=False`` skips live backlog SQL (use for Monitor HTTP) so the
        UI DB/worker pools are not blocked for 30–200s on every 15s poll.
        """
        phase_active = (
            sum(1 for t in self._phase_worker_tasks if not t.done())
            if self._phase_worker_tasks
            else 0
        )
        out = {
            "is_running": self.is_running,
            "active_workers": phase_active,
            "phase_workers_configured": len(self._phase_worker_tasks),
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "automation_background_tasks_active": (
                sum(1 for t in self._background_automation_tasks if not t.done())
                if self._background_automation_tasks
                else 0
            ),
            "queue_size": self.task_queue.qsize(),
            "requested_queue_size": self._requested_task_queue.qsize(),
            "combined_queue_depth": self._automation_queue_depth(),
            "queue_soft_cap": AUTOMATION_QUEUE_SOFT_CAP,
            "scheduled_enqueue_paused": self._scheduled_enqueue_paused(),
            "nightly_enrichment_in_flight": self._nightly_enrichment_in_flight_count(),
            "nightly_enrichment_max_queued": AUTOMATION_NIGHTLY_ENRICHMENT_MAX_QUEUED,
            "metrics": self.metrics,
            "schedules": self.schedules,
            "recent_tasks": list(self.tasks.values())[-10:],  # Last 10 tasks
        }
        ctrl = getattr(self, "pipeline_controller", None)
        if ctrl is not None:
            out["controller_state"] = ctrl.get_state()
            out["controller_state"]["queue_depth"] = self._automation_queue_depth()
        else:
            out["controller_state"] = None
        # Per-phase queue/run metrics
        # - queued_tasks_by_phase: tasks currently enqueued (not yet executing)
        # - active_tasks_by_phase: tasks currently executing (workers)
        # - runs_last_60m_by_phase: how many phase runs completed in the last 60 minutes
        try:
            from collections import Counter

            queued_counter = Counter()
            queued_lane_counter = Counter()
            for q in (self.task_queue, self._requested_task_queue):
                try:
                    internal = getattr(q, "_queue", None)
                    if internal is not None:
                        for item in list(internal):
                            t = item[2] if isinstance(item, tuple) and len(item) >= 3 else item
                            if hasattr(t, "name"):
                                queued_counter.update([t.name])
                                lane = (
                                    ((getattr(t, "metadata", None) or {}).get("execution_lane"))
                                    or ((getattr(t, "metadata", None) or {}).get("lane_default"))
                                    or self._phase_default_lane(t.name)
                                )
                                queued_lane_counter.update([lane])
                except Exception:
                    pass
            out["queued_tasks_by_phase"] = dict(queued_counter)
            out["queued_tasks_by_lane"] = dict(queued_lane_counter)
        except Exception:
            out["queued_tasks_by_phase"] = {}
            out["queued_tasks_by_lane"] = {}
        try:
            out["active_tasks_by_phase"] = {
                k: v for k, v in self._running_tasks_by_phase.items() if v > 0
            }
        except Exception:
            out["active_tasks_by_phase"] = {}
        try:
            out["runs_last_60m_by_phase"] = self._merged_runs_last_60m_by_phase()
        except Exception:
            out["runs_last_60m_by_phase"] = {}
        try:
            out["active_tasks_by_lane"] = {
                k: v for k, v in self._running_tasks_by_lane.items() if v > 0
            }
        except Exception:
            out["active_tasks_by_lane"] = {}
        try:
            out["runs_last_60m_by_lane"] = {
                k: len(dq) for k, dq in self._lane_run_times_last_60m.items()
            }
        except Exception:
            out["runs_last_60m_by_lane"] = {}
        if include_pending:
            if get_all_backlog_counts:
                try:
                    out["backlog_counts"] = get_all_backlog_counts()
                except Exception:
                    pass
            if get_all_pending_counts:
                try:
                    out["pending_counts"] = get_all_pending_counts()
                except Exception:
                    pass
        else:
            # Prefer precomputed Monitor snapshot — never block HTTP on live COUNTs.
            try:
                from services.monitor_backlog_snapshot_service import (
                    read_monitor_backlog_snapshot,
                )

                snap = read_monitor_backlog_snapshot(allow_stale=True) or {}
                out["pending_counts"] = dict(
                    snap.get("queue_depths") or snap.get("pending") or {}
                )
                out["backlog_counts"] = dict(
                    snap.get("scheduling_backlog") or snap.get("backlog") or {}
                )
                out["pending_source"] = "monitor_backlog_snapshot"
            except Exception:
                out["pending_counts"] = {}
                out["backlog_counts"] = {}
                out["pending_source"] = "unavailable"
        try:
            from services.document_pipeline_metrics import get_document_pipeline_metrics

            out["document_pipeline"] = get_document_pipeline_metrics()
        except Exception:
            out["document_pipeline"] = {"error": "unavailable"}
        try:
            from shared.database.connection import get_db_pool_snapshot

            out["db_pools"] = get_db_pool_snapshot()
        except Exception:
            out["db_pools"] = {"error": "unavailable"}
        try:
            ctrl = getattr(self, "pipeline_controller", None)
            out["pipeline_controller"] = ctrl.get_state() if ctrl is not None else {"active": False}
        except Exception:
            out["pipeline_controller"] = {"error": "unavailable"}
        try:
            from shared.services.llm_service import llm_service as _ls

            out["llm_routing"] = {
                "dual_host_enabled": bool(_ls.dual_host_enabled),
                "cpu_base_url": _ls.ollama_cpu_host,
                "gpu_base_url": _ls.ollama_gpu_host,
            }
        except Exception as e:
            out["llm_routing"] = {"error": str(e)}
        try:
            from shared.pipeline_queue_vocabulary import add_automation_status_aliases

            out = add_automation_status_aliases(out)
        except Exception:
            pass
        return out

    def get_metrics(self) -> dict[str, Any]:
        """Get detailed metrics"""
        return {
            "performance": self.metrics,
            "task_distribution": {
                status.value: len([t for t in self.tasks.values() if t.status == status])
                for status in TaskStatus
            },
            "system_health": {
                "uptime": self.metrics["system_uptime"],
                "last_health_check": self.metrics["last_health_check"],
                "active_workers": (
                    sum(1 for t in self._phase_worker_tasks if not t.done())
                    if self._phase_worker_tasks
                    else 0
                ),
            },
        }

    def get_orchestrator_snapshot(self, *, include_pending: bool = True) -> dict[str, Any]:
        """Lightweight status for OrchestratorCoordinator (avoids full get_status DB work)."""
        from collections import Counter

        queued_counter: Counter[str] = Counter()
        for q in (self.task_queue, self._requested_task_queue):
            try:
                internal = getattr(q, "_queue", None)
                if internal is not None:
                    for item in list(internal):
                        t = item[2] if isinstance(item, tuple) and len(item) >= 3 else item
                        if hasattr(t, "name"):
                            queued_counter.update([t.name])
            except Exception:
                pass
        pending: dict[str, int] = {}
        if include_pending:
            try:
                from services.backlog_metrics import get_all_pending_counts

                pending = get_all_pending_counts()
            except Exception:
                pass
        snapshot: dict[str, Any] = {
            "pending_counts": pending,
            "active_tasks_by_phase": {
                k: int(v)
                for k, v in self._running_tasks_by_phase.items()
                if int(v or 0) > 0
            },
            "queued_tasks_by_phase": dict(queued_counter),
            "schedules": {
                name: {
                    "last_run": sched.get("last_run"),
                    "estimated_duration": sched.get("estimated_duration", 60),
                }
                for name, sched in self.schedules.items()
            },
            "metrics": {
                "processing_history": (self.metrics.get("processing_history") or {}),
            },
        }
        try:
            from services.pipeline_conductor_service import conductor_pipeline_modes

            snapshot["pipeline_conductor"] = conductor_pipeline_modes()
        except Exception:
            pass
        return snapshot


# Global instance
automation_manager = None


def get_automation_manager() -> AutomationManager:
    """Return the process-wide automation manager.

    When the API starts normally, ``main.py`` assigns this to the same instance as
    ``app.state.automation``. If nothing has set the module global yet, a new
    **unstarted** manager may be created (legacy callers) — prefer ``request.app.state.automation``
    in routes when available.
    """
    global automation_manager
    if automation_manager is None:
        from config.database import get_db_config

        db_config = get_db_config()
        automation_manager = AutomationManager(db_config)
    return automation_manager
