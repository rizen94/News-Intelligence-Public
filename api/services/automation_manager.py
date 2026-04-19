"""
News Intelligence System v8.0 - Enterprise Automation Manager
Collect-then-analyze pipeline: collection_cycle, pipeline-ordered analysis (Foundation → Extraction → Intelligence → Output).

**Article batch order:** default **FIFO** (oldest rows first) via ``PIPELINE_ARTICLE_SELECTION_ORDER=fifo``.
Set ``lifo`` to restore newest-first selection. **Backfill:** ``PIPELINE_BACKFILL_MODE=true`` plus optional
``PIPELINE_BACKFILL_COLLECTION_RESUME_AT`` (or default 48h state file) pauses RSS + document discovery while
existing rows are processed.

Workload-driven scheduling (USE_WORKLOAD_DRIVEN_ORDER=True): the scheduler checks every process every tick.
Order and run eligibility are determined by current workload, not fixed intervals. When a phase has pending
work it is eligible every WORKLOAD_MIN_COOLDOWN seconds; when idle, intervals apply. Collection is throttled
when downstream backlog (enrichment + context_sync + document_processing) exceeds
COLLECTION_THROTTLE_PENDING_THRESHOLD so the sequence collection → processing → synthesis completes before
adding more RSS. No process is left behind because of fast RSS; phases with no work are skipped or deprioritized.

When ``AUTOMATION_QUEUE_SOFT_CAP`` > 0 and combined queue depth (scheduled + requested) reaches the cap,
new scheduled enqueues, continuous batch re-queues, and dependency-chain ``request_phase`` calls are skipped
except phases in ``AUTOMATION_QUEUE_PAUSE_ALLOW``. Default **0** = disabled (no artificial queue-depth cap;
throughput is limited by ``AUTOMATION_MAX_CONCURRENT_TASKS``, ``MAX_CONCURRENT_OLLAMA_TASKS``, DB pools, and
cooldowns). Set a positive value only as a safety valve if the asyncio queue grows without bound.
**nightly_enrichment_context** is not allowlisted: one drain run is enough; it was previously allowlisted and
could stack hundreds of redundant queued sweeps while workers were busy.
**AUTOMATION_NIGHTLY_ENRICHMENT_MAX_QUEUED** caps scheduled+requested+running nightly tasks (default 1; 0=unlimited).
**AUTOMATION_MAX_SCHEDULED_DEPTH_PER_PHASE** caps scheduled asyncio-queue depth per phase (default 1; 0=unlimited) so workload-driven ticks cannot stack thousands of duplicate tasks; defer/retry bypass the cap.
With **CLAIM_EXTRACTION_DRAIN** (default on), **claim_extraction** also skips new scheduler/chain enqueues when running+queued depth already reaches the per-phase concurrent cap (``_should_skip_redundant_phase_request``), so context_sync completion cannot pile hundreds of duplicate tasks on ``_requested_task_queue``.
If a duplicate still reaches a worker under the cap, ``_discard_redundant_claim_extraction_when_at_cap`` completes it without re-queueing (per-phase defer used ``bypass_schedule_depth_cap`` and recycled the same backlog forever).
**AUTOMATION_PER_PHASE_CONCURRENT_CAP** caps how many workers may execute the same phase at once (default 2; 0=unlimited); **nightly_sequential_drain** bypasses; nightly window multiplies cap via **AUTOMATION_PER_PHASE_CONCURRENT_NIGHTLY_MULT** for catch-up when those phases are scheduled.
**AUTOMATION_DB_POOL_PRESSURE_GATE_ENABLED** (default true): while worker psycopg2 pool utilization ≥ **AUTOMATION_DB_WORKER_UTILIZATION_SKIP_THRESHOLD** (default 0.82), defer *new* scheduled enqueues and continuous batch re-queues except **AUTOMATION_DB_POOL_GATE_EXEMPT_PHASES** (default: health_check, pending_db_flush). Manual Monitor phase requests still run (**requested_activity_id** bypasses request_phase deferral).

**Offload to Widow (DB host):** set ``AUTOMATION_SKIP_RSS_IN_COLLECTION_CYCLE=true`` on the GPU/main API host when
RSS runs on Widow; set ``AUTOMATION_DISABLED_SCHEDULES=context_sync,entity_profile_sync,pending_db_flush`` (comma-separated)
for phases moved to ``api/scripts/run_widow_db_adjacent.py`` cron — dependents' ``depends_on`` lists are adjusted automatically.
Widow only writes ``{domain}.articles``; there is no message queue. The **content_enrichment** scheduled task (plus the
enrichment loop inside ``collection_cycle``) drains pending rows from the DB so ingestion is not blocked when
``collection_cycle`` is throttled or skips RSS on the main host.
Dependency settle time after a phase completes is capped by AUTOMATION_DEPENDENCY_SETTLE_CAP_SEC (default 180s)
so long estimated_duration values (e.g. collection_cycle) do not block dependents such as storyline_discovery.

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
from uuid import uuid4
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
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


# Legacy enrichment-backlog-first flag — removed in v8.1.
# The pipeline cycle now handles sequencing; no need for per-backlog gating.
ENRICHMENT_BACKLOG_FIRST_ENABLED = False
ENRICHMENT_BACKLOG_FIRST_WHITELIST = frozenset()

# Phases that process batches; re-enqueue when pending work remains (v8: capped per analysis window)
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
}
# Default when governance YAML omits key: 0 = unlimited (see __init__ for env override).
MAX_REQUEUE_PER_WINDOW = 0

# Phases that enter the Ollama yield / GPU throttle / semaphore path in ``_execute_task``.
OLLAMA_AUTOMATION_PHASES = frozenset(
    {
        "topic_clustering",
        "ml_processing",
        "entity_extraction",
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
        "daily_briefing_synthesis",
        "document_processing",
        "storyline_discovery",
        "proactive_detection",
        "fact_verification",
        "narrative_thread_build",
        "event_coherence_review",
        "pattern_recognition",
        "investigation_report_refresh",
        "entity_enrichment",
        "storyline_enrichment",
    }
)
# Phases whose main LLM path uses ``OllamaModelCaller`` with ``STRUCTURED_EXTRACTION`` → ``_call_ollama(..., execution_lane="cpu")``.
# They are excluded from ``GPU_LANE_PHASES`` so automation ``ContextVar`` lane, dynamic router defaults, and Monitor
# match the CPU host + CPU semaphore (see ``shared/services/ollama_model_caller.py``).
STRUCTURED_LLM_CPU_LANE_PHASES = frozenset(
    {
        "claim_extraction",
        "entity_extraction",
        "event_extraction",
    }
)
# Default execution lane "gpu" for Ollama phases that are not structured-extraction-on-CPU above.
GPU_LANE_PHASES = frozenset(x for x in OLLAMA_AUTOMATION_PHASES if x not in STRUCTURED_LLM_CPU_LANE_PHASES)
DB_HEAVY_PHASES = frozenset(
    {
        "context_sync",
        "entity_profile_sync",
        "claims_to_facts",
        "claim_subject_gap_refresh",
        "extracted_claims_dedupe",
        "pending_db_flush",
        "entity_organizer",
        "graph_connection_distillation",
        "collection_cycle",
        "content_enrichment",
        # Churn-heavy automation phases (worker pool + LLM); used for router cooldowns / resource class
        "timeline_generation",
        "event_deduplication",
        "event_extraction",
        "watchlist_alerts",
        "story_continuation",
        "ml_processing",
        "topic_clustering",
        "sentiment_analysis",
        "entity_extraction",
        "quality_scoring",
    }
)


def _automation_db_pool_pressure_gate_enabled() -> bool:
    """When True, defer new scheduled work if worker psycopg2 pool utilization is above threshold."""
    return os.getenv("AUTOMATION_DB_POOL_PRESSURE_GATE_ENABLED", "true").lower() in (
        "1",
        "true",
        "yes",
    )


def _db_pool_gate_exempt_phases() -> frozenset[str]:
    """Phases that may still schedule when the worker pool is hot (liveness + spill replay)."""
    base = frozenset({"health_check", "pending_db_flush"})
    raw = os.environ.get("AUTOMATION_DB_POOL_GATE_EXEMPT_PHASES", "").strip()
    if not raw:
        return base
    return base | frozenset(x.strip() for x in raw.split(",") if x.strip())


def automation_db_pool_should_defer_phase(phase_name: str) -> bool:
    """
    Return True if this phase should not be *newly* scheduled while worker DB pool is under pressure.

    Does not apply to tasks already queued. Manual Monitor requests (requested_activity_id) bypass
    in request_phase. Defer/retry paths that re-queue the same Task use the same enqueue APIs but
    typically run when pressure drops; exempt phases always pass.
    """
    if phase_name in _db_pool_gate_exempt_phases():
        return False
    if not _automation_db_pool_pressure_gate_enabled():
        return False
    try:
        from shared.database.connection import get_db_pool_snapshot

        snap = get_db_pool_snapshot()
        w = float((snap.get("worker") or {}).get("utilization") or 0.0)
    except Exception:
        return False
    try:
        thr = float(os.getenv("AUTOMATION_DB_WORKER_UTILIZATION_SKIP_THRESHOLD", "0.82"))
    except ValueError:
        thr = 0.82
    return w >= thr


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.lower() in ("1", "true", "yes", "on")


AUTOMATION_DYNAMIC_RESOURCE_ROUTING_ENABLED = _env_bool(
    "AUTOMATION_DYNAMIC_RESOURCE_ROUTING_ENABLED", True
)
# Dynamic router gateway thresholds (headroom values are 0..1).
ROUTER_GPU_SATURATED_HEADROOM = float(
    os.environ.get("AUTOMATION_ROUTER_GPU_SATURATED_HEADROOM", "0.15")
)
ROUTER_GPU_EXTRA_HEADROOM = float(
    os.environ.get("AUTOMATION_ROUTER_GPU_EXTRA_HEADROOM", "0.55")
)
ROUTER_CPU_HOT_HEADROOM = float(os.environ.get("AUTOMATION_ROUTER_CPU_HOT_HEADROOM", "0.20"))
ROUTER_CPU_EXTRA_HEADROOM = float(
    os.environ.get("AUTOMATION_ROUTER_CPU_EXTRA_HEADROOM", "0.55")
)
ROUTER_DB_PRESSURE_HEADROOM = float(
    os.environ.get("AUTOMATION_ROUTER_DB_PRESSURE_HEADROOM", "0.20")
)
ROUTER_DB_EXTRA_HEADROOM = float(os.environ.get("AUTOMATION_ROUTER_DB_EXTRA_HEADROOM", "0.65"))
# Cooldown multipliers (resource-router). Lower = less artificial backoff when "hot".
ROUTER_MULT_DB_PRESSURE = float(os.environ.get("AUTOMATION_ROUTER_COOLDOWN_MULT_DB_PRESSURE", "2.0"))
ROUTER_MULT_GPU_SATURATED = float(
    os.environ.get("AUTOMATION_ROUTER_COOLDOWN_MULT_GPU_SATURATED", "1.5")
)
ROUTER_MULT_CPU_HOT = float(os.environ.get("AUTOMATION_ROUTER_COOLDOWN_MULT_CPU_HOT", "1.3"))
ROUTER_MULT_HEADROOM_BONUS = float(
    os.environ.get("AUTOMATION_ROUTER_COOLDOWN_MULT_HEADROOM", "0.85")
)

# Workload-driven scheduling: WORKLOAD_MIN_COOLDOWN set after AUTOMATION_MAX_CONCURRENT_TASKS (see below).
# Don't run collection_cycle when downstream pending exceeds this.
# Default sum: content_enrichment + context_sync + document_processing (minus COLLECTION_THROTTLE_EXCLUDE_PHASES).
# Optional: comma-separated phase names in COLLECTION_THROTTLE_EXTRA_PHASES (e.g. ml_processing,entity_extraction).
COLLECTION_THROTTLE_PENDING_THRESHOLD = int(
    os.environ.get("COLLECTION_THROTTLE_PENDING_THRESHOLD", "1200")
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
    extra = os.environ.get("COLLECTION_THROTTLE_EXTRA_PHASES", "").strip()
    if extra:
        for part in extra.split(","):
            k = part.strip()
            if k and k not in keys:
                keys.append(k)
    exclude_raw = os.environ.get("COLLECTION_THROTTLE_EXCLUDE_PHASES", "document_processing")
    exclude = frozenset(x.strip() for x in exclude_raw.split(",") if x.strip())
    keys = [k for k in keys if k not in exclude]
    breakdown = {k: int(p.get(k, 0) or 0) for k in keys}
    return sum(breakdown.values()), breakdown
# When True, scheduler ignores analysis-window step lock; workload + pipeline order determine what runs.
USE_WORKLOAD_DRIVEN_ORDER = True

# When combined queue depth (main + requested) >= this, stop enqueueing scheduled work except allowlist.
# 0 = disabled (recommended). Use workers + Ollama semaphores + DB pool for real limits.
AUTOMATION_QUEUE_SOFT_CAP = int(os.environ.get("AUTOMATION_QUEUE_SOFT_CAP", "0"))
QUEUE_PAUSE_ALLOW_SCHEDULED = frozenset(
    x.strip()
    for x in os.environ.get(
        "AUTOMATION_QUEUE_PAUSE_ALLOW",
        "collection_cycle,content_enrichment,health_check,pending_db_flush,content_refinement_queue",
    ).split(",")
    if x.strip()
)
# Max nightly_enrichment_context tasks at once: running + scheduled queue + requested queue.
# Each run is a full unified drain; default 1 avoids stacked sweeps and duplicate Monitor activity lines. 0 = no cap.
AUTOMATION_NIGHTLY_ENRICHMENT_MAX_QUEUED = int(
    os.environ.get("AUTOMATION_NIGHTLY_ENRICHMENT_MAX_QUEUED", "1")
)
# Per-phase cap on scheduled Task objects waiting in the asyncio queue. Workload-driven scheduling
# otherwise enqueues another run every cooldown while DB pending remains, even if prior copies are
# still queued — Monitor "Queued" explodes and wastes memory. Defer/retry paths pass
# bypass_schedule_depth_cap so yield/nightly/GPU gates and retries never drop work. 0 = unlimited (legacy).
AUTOMATION_MAX_SCHEDULED_DEPTH_PER_PHASE = int(
    os.environ.get("AUTOMATION_MAX_SCHEDULED_DEPTH_PER_PHASE", "1")
)
# Max automation workers executing the same phase at once (regular / daytime). Spreads load across
# phases instead of N workers all running claim_extraction (or other LLM-heavy work). Tasks with
# metadata nightly_sequential_drain bypass. During unified nightly window, cap is multiplied by
# AUTOMATION_PER_PHASE_CONCURRENT_NIGHTLY_MULT (scheduled phases are usually exclusive anyway).
# 0 = unlimited (legacy).
AUTOMATION_PER_PHASE_CONCURRENT_CAP = int(
    os.environ.get("AUTOMATION_PER_PHASE_CONCURRENT_CAP", "2")
)
DEFAULT_AUTOMATION_PER_PHASE_CONCURRENT_CAP_PHASES = frozenset(
    {
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
    }
)


def _per_phase_concurrent_cap_phase_names() -> frozenset[str]:
    raw = os.environ.get("AUTOMATION_PER_PHASE_CONCURRENT_CAP_PHASES", "").strip()
    if raw:
        return frozenset(x.strip() for x in raw.split(",") if x.strip())
    return DEFAULT_AUTOMATION_PER_PHASE_CONCURRENT_CAP_PHASES


def _per_phase_concurrent_cap_overrides() -> dict[str, int]:
    """
    Optional per-phase caps: AUTOMATION_PER_PHASE_CONCURRENT_CAP_OVERRIDES=claim_extraction:1,claims_to_facts:2
    Values are max concurrent workers for that phase (clamped to max_concurrent_tasks at use site). 0 = unlimited.
    """
    raw = os.environ.get("AUTOMATION_PER_PHASE_CONCURRENT_CAP_OVERRIDES", "").strip()
    if not raw:
        return {}
    out: dict[str, int] = {}
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
    that stall for hours and stack the asyncio queue.
    """
    raw = os.environ.get("AUTOMATION_PER_PHASE_NIGHTLY_MULT_EXCLUDE", "").strip()
    if raw:
        return frozenset(x.strip() for x in raw.split(",") if x.strip())
    return frozenset({"claim_extraction"})


# Ollama tasks normally yield when a non-polling browser request hit the API recently; storyline
# deep analysis must still run or the UI shows "processing" forever while users read those pages.
_OLLAMA_YIELD_EXEMPT = frozenset(
    x.strip()
    for x in os.environ.get(
        "OLLAMA_YIELD_EXEMPT_TASKS",
        "content_refinement_queue",
    ).split(",")
    if x.strip()
)

# Cap how long we wait after a dependency completes before a dependent may run. Without this,
# collection_cycle's large estimated_duration (~1800s) kept dependents (e.g. storyline_discovery)
# permanently ineligible while collection runs often.
AUTOMATION_DEPENDENCY_SETTLE_CAP_SEC = int(
    os.environ.get("AUTOMATION_DEPENDENCY_SETTLE_CAP_SEC", "180")
)

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
    # Step 1: Extraction
    (
        "claim_extraction",
        "legislative_references",
        "claims_to_facts",
        "claim_subject_gap_refresh",
        "extracted_claims_dedupe",
        "event_tracking",
        "topic_clustering",
        "quality_scoring",
        "sentiment_analysis",
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
        "fact_verification",
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
        "event_extraction",
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
    None,
)  # seconds; None = no limit (step 3)

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
MAX_CONCURRENT_OLLAMA_TASKS = _env_int("MAX_CONCURRENT_OLLAMA_TASKS", 12)
AUTOMATION_MAX_CONCURRENT_TASKS = _env_int("AUTOMATION_MAX_CONCURRENT_TASKS", 12)
AUTOMATION_EXECUTOR_MAX_WORKERS = _env_int("AUTOMATION_EXECUTOR_MAX_WORKERS", 6)

# Seconds between scheduler ticks; min cooldown between re-enqueue of same phase when backlog exists.
WORKLOAD_MIN_COOLDOWN = max(1, int(os.environ.get("AUTOMATION_WORKLOAD_MIN_COOLDOWN_SECONDS", "10")))
AUTOMATION_SCHEDULER_TICK_SECONDS = max(1, int(os.environ.get("AUTOMATION_SCHEDULER_TICK_SECONDS", "5")))
# When true (default), skip dynamic_resource_service ±1 scaling; floor max_concurrent_tasks with env below.
_AUTOMATION_DISABLE_DYNAMIC_TASK_SCALING = os.environ.get(
    "AUTOMATION_DISABLE_DYNAMIC_TASK_SCALING", "true"
).lower() in ("1", "true", "yes")

# Collection-cycle watchdog: 60 min after cycle starts, check if any phase should be added to the queue.
WATCHDOG_SECONDS = int(os.environ.get("COLLECTION_PHASE_WATCHDOG_SECONDS", "3600"))


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
    metadata: dict[str, Any] = None


# Estimated duration in seconds per phase (single place to tune)
PHASE_ESTIMATED_DURATION_SECONDS = {
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
    "claim_extraction": 600,  # env CLAIM_EXTRACTION_BATCH_LIMIT × CLAIM_EXTRACTION_PARALLEL (LLM-bound)
    "legislative_references": 120,  # Congress.gov HTTP + rate-limit sleep per bill mention
    "claims_to_facts": 180,  # env CLAIMS_TO_FACTS_BATCH_LIMIT; resolver + INSERTs (DB-bound)
    "claim_subject_gap_refresh": 120,  # catalog upsert per active domain (DB-bound)
    "extracted_claims_dedupe": 180,  # batched DELETE; see EXTRACTED_CLAIMS_DEDUPE_* env
    "event_tracking": 200,  # observed ~196s avg; was 120
    "event_coherence_review": 180,
    "investigation_report_refresh": 300,
    "entity_profile_build": 600,
    "pattern_recognition": 120,
    "storyline_automation": 180,
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
    "fact_verification": 120,  # v8: verify_recent_claims per domain
    "content_refinement_queue": 420,  # storyline RAG / timeline narrative / ~70B finisher (queued user jobs)
    "nightly_enrichment_context": 21600,  # 02:00–07:00 local unified pipeline (NIGHTLY_PIPELINE_*); exits when idle
}


class AutomationManager:
    """Enterprise-grade automation manager"""

    def __init__(self, db_config: dict[str, str]):
        self.db_config = db_config
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
        self.task_timeout = 300  # 5 minutes
        self.max_concurrent_tasks = (
            AUTOMATION_MAX_CONCURRENT_TASKS
        )  # Phase workers; scale up when you have CPU/GPU headroom

        # Dynamic resource allocation
        self.dynamic_resource_service = None
        self.resource_allocation = None

        # v8: Pending collection queue — RAG/synthesis add URLs here; drained each collection_cycle
        self._pending_collection_queue: list[dict[str, Any]] = []
        # v8: Pipeline-ordered analysis state (set when collection_cycle completes, cleared when next collection starts)
        self._analysis_window_start: datetime | None = None
        self._active_step: int = 0
        self._step_started_at: datetime | None = None
        # v8: Re-enqueue count per task in current analysis window (reset when window starts)
        self._requeue_counts: dict[str, int] = {}

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
        self._resource_headroom: dict[str, Any] = {}

        # Collection-cycle watchdog: when current cycle started; per-phase last completion (for "has it run since start?")
        self._collection_cycle_started_at: datetime | None = None
        self._last_completed_at_by_phase: dict[str, datetime] = {}

        # v8: Optional config from orchestrator_governance.yaml (analysis_pipeline, collection_cycle)
        try:
            from config.orchestrator_governance import get_orchestrator_governance_config

            gov = get_orchestrator_governance_config()
            ap = gov.get("analysis_pipeline") or {}
            cc = gov.get("collection_cycle") or {}
        except Exception:
            ap, cc = {}, {}
        budgets = ap.get("step_budgets_seconds")
        self._step_time_budgets: tuple[int | None, ...] = (
            tuple(budgets) if budgets else STEP_TIME_BUDGETS
        )
        _env_mrq = os.environ.get("AUTOMATION_MAX_REQUEUE_PER_WINDOW", "").strip()
        if _env_mrq != "":
            try:
                self._max_requeue_per_window = max(0, int(_env_mrq))
            except ValueError:
                self._max_requeue_per_window = max(
                    0, int(ap.get("max_requeue_per_window", MAX_REQUEUE_PER_WINDOW))
                )
        else:
            self._max_requeue_per_window = max(
                0, int(ap.get("max_requeue_per_window", MAX_REQUEUE_PER_WINDOW))
            )
        collection_interval = None
        if hasattr(os, "environ"):
            raw = os.environ.get("COLLECTION_CYCLE_INTERVAL_SECONDS")
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
                "interval": 1800,  # 30 minutes - max 50 contexts/run, ~1-2 min, cost-controlled
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
            # PHASE 2.5: Cross-domain synthesis (correlate events across politics/finance/science-tech)
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
            # PHASE 2.2: Pattern recognition (network, temporal, behavioral, event)
            "pattern_recognition": {
                "interval": 7200,  # 2 hours
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 2,
                "depends_on": ["context_sync", "entity_profile_sync"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["pattern_recognition"],
            },
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
            # Metadata enrichment (language, categories, sentiment, quality) for domain articles
            "metadata_enrichment": {
                "interval": 900,  # 15 minutes
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 2,
                "depends_on": ["collection_cycle"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["metadata_enrichment"],
            },
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
            # PHASE 3: ML Processing (Runs frequently on processed articles)
            "ml_processing": {
                "interval": 300,  # 5 minutes - run often, re-enqueue until empty
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.HIGH,
                "phase": 3,
                "depends_on": ["collection_cycle"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["ml_processing"],
            },
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
            # PHASE 4: Parallel ML & Entity Processing (Runs frequently)
            "entity_extraction": {
                "interval": 300,  # 5 minutes - run often, re-enqueue until empty
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 4,
                "depends_on": ["collection_cycle"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["entity_extraction"],
                "parallel_group": "ml_entity_processing",  # Can run in parallel with ML
            },
            # PHASE 4: Parallel ML & Entity Processing (Runs frequently)
            "quality_scoring": {
                "interval": 300,  # 5 minutes - run often
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 4,
                "depends_on": ["collection_cycle"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["quality_scoring"],
                "parallel_group": "ml_entity_processing",  # Can run in parallel with ML
            },
            # PHASE 4: Parallel ML & Entity Processing (Runs frequently)
            "sentiment_analysis": {
                "interval": 300,  # 5 minutes - run often, re-enqueue until empty
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 4,
                "depends_on": ["collection_cycle"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["sentiment_analysis"],
                "parallel_group": "ml_entity_processing",  # Can run in parallel with ML
            },
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
                "depends_on": ["ml_processing", "sentiment_analysis"],
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
            # PHASE 9a: Event Extraction (v5.0 - runs after entity extraction)
            "event_extraction": {
                "interval": 300,  # 5 minutes - run often, re-enqueue until empty
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 9,
                "depends_on": ["entity_extraction"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["event_extraction"],
                "parallel_group": "event_processing",
            },
            # PHASE 9b: Event Deduplication (v5.0 - runs after event extraction)
            "event_deduplication": {
                "interval": 600,  # 10 minutes
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 9,
                "depends_on": ["event_extraction"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["event_deduplication"],
                "parallel_group": "event_processing",
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
                "depends_on": ["rag_enhancement"],
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
            # PHASE 10.5: Editorial document generation — build/refine storyline editorial_document (see editorial_briefing_generation for events)
            "editorial_document_generation": {
                "interval": 1800,  # 30 minutes
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 10,
                "depends_on": ["storyline_processing"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS[
                    "editorial_document_generation"
                ],
            },
            "editorial_briefing_generation": {
                "interval": 1800,  # 30 minutes
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 10,
                "depends_on": ["event_tracking"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS[
                    "editorial_briefing_generation"
                ],
            },
            # PHASE 11: Digest Generation (Every hour)
            "digest_generation": {
                "interval": 3600,  # 1 hour
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.NORMAL,
                "phase": 11,
                "depends_on": ["editorial_document_generation"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["digest_generation"],
            },
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
            # Auto daily briefing synthesis (breaking news)
            "daily_briefing_synthesis": {
                "interval": 14400,  # 4 hours
                "last_run": None,
                "enabled": True,
                "priority": TaskPriority.LOW,
                "phase": 11,
                "depends_on": ["storyline_synthesis"],
                "estimated_duration": PHASE_ESTIMATED_DURATION_SECONDS["daily_briefing_synthesis"],
            },
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
                "depends_on": ["storyline_processing", "editorial_document_generation"],
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

        self._apply_automation_disabled_schedules()

        # Performance metrics
        self.metrics = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "avg_processing_time": 0,
            "system_uptime": 0,
            "last_health_check": None,
            "adaptive_timing": True,
            "load_factor": 1.0,  # Multiplier for intervals based on load
            "processing_history": {},  # Track actual vs estimated durations
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

    def _apply_automation_disabled_schedules(self) -> None:
        """Disable named schedules and strip them from depends_on so dependents still run (Widow cron offload)."""
        raw = os.environ.get("AUTOMATION_DISABLED_SCHEDULES", "").strip()
        if not raw:
            return
        disabled = {x.strip() for x in raw.split(",") if x.strip()}
        for name in disabled:
            if name in self.schedules:
                self.schedules[name]["enabled"] = False
                logger.info(
                    "Automation schedule %s disabled (AUTOMATION_DISABLED_SCHEDULES)",
                    name,
                )
            else:
                logger.warning("AUTOMATION_DISABLED_SCHEDULES: unknown phase %s", name)
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
        if phase_name != "claim_extraction":
            return False
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

    def _discard_redundant_claim_extraction_when_at_cap(self, task: Task, exec_cap: int) -> bool:
        """
        When the concurrent cap is already satisfied by other workers, a duplicate claim_extraction
        task must not re-enter the asyncio queue (bypass_schedule_depth_cap). Otherwise thousands of
        copies accumulate while a few long drain runs hold the slots.
        """
        if task.name != "claim_extraction" or exec_cap <= 0:
            return False
        if (task.metadata or {}).get("nightly_sequential_drain"):
            return False
        if (task.metadata or {}).get("requested_activity_id"):
            return False
        try:
            from services.claim_extraction_service import claim_extraction_drain_enabled

            if not claim_extraction_drain_enabled():
                return False
        except Exception:
            return False
        # After the failed slot attempt we reverted our +1; count is workers already executing.
        return int(self._running_tasks_by_phase.get(task.name, 0) or 0) >= exec_cap

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
            conn = self._get_db_connection_sync()
            if not conn:
                return
            try:
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
            finally:
                conn.close()
        except Exception as e:
            logger.debug("Load pending_collection_queue: %s (table may not exist yet)", e)

    def _get_db_connection_sync(self):
        """Synchronous DB connection for use from sync code (e.g. load/save queue)."""
        from shared.database.connection import get_db_connection

        return get_db_connection()

    def persist_pending_collection_queue(self) -> None:
        """v8: Persist pending collection queue to DB (call on shutdown)."""
        try:
            conn = self._get_db_connection_sync()
            if not conn:
                return
            try:
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
            finally:
                conn.close()
        except Exception as e:
            logger.debug("Persist pending_collection_queue: %s", e)

    async def _preflight_startup_health_check(self) -> None:
        """
        Before workers: confirm PostgreSQL is reachable via the **worker** pool (phases use it)
        and the **health** pool (standalone health_check). Retries a few times for transient startup.
        """
        if os.getenv("AUTOMATION_SKIP_STARTUP_PREFLIGHT", "").lower() in ("1", "true", "yes"):
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
            attempts = max(1, int(os.getenv("AUTOMATION_STARTUP_HEALTH_CHECK_ATTEMPTS", "3")))
        except ValueError:
            attempts = 3
        try:
            delay_sec = float(os.getenv("AUTOMATION_STARTUP_HEALTH_CHECK_DELAY_SEC", "2"))
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

        scheduler = asyncio.create_task(self._scheduler())
        standalone_health = asyncio.create_task(self._standalone_health_check_loop())
        health_monitor = asyncio.create_task(self._health_monitor())
        metrics_collector = asyncio.create_task(self._metrics_collector())
        entity_organizer_loop = asyncio.create_task(self._entity_organizer_downtime_loop())
        self._background_automation_tasks = [
            scheduler,
            standalone_health,
            health_monitor,
            metrics_collector,
            entity_organizer_loop,
        ]
        self._rebuild_automation_task_list()

        logger.info(
            "Automation Manager started with %s phase dequeue workers (+ background tasks)",
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
            need = dep_schedule.get("estimated_duration", 60) * max(
                0.5, self.metrics.get("load_factor", 1.0)
            )
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
        return "gpu" if phase_name in GPU_LANE_PHASES else "cpu"

    @staticmethod
    def _phase_resource_class(phase_name: str) -> str:
        if phase_name in GPU_LANE_PHASES:
            return "gpu_heavy"
        if phase_name in DB_HEAVY_PHASES:
            return "db_heavy"
        return "cpu_light"

    def _resource_headroom_snapshot(self) -> dict[str, Any]:
        """
        Compute CPU/GPU/DB headroom in [0,1] for dynamic routing/cooldowns.
        1.0 means plenty of room, 0.0 means saturated.
        """
        cpu_percent = None
        gpu_percent = None
        try:
            import psutil

            cpu_percent = float(psutil.cpu_percent(interval=0.0))
        except Exception:
            cpu_percent = None
        try:
            from shared.gpu_metrics import get_gpu_metrics

            gpu_percent = get_gpu_metrics().get("gpu_utilization_percent")
            if gpu_percent is not None:
                gpu_percent = float(gpu_percent)
        except Exception:
            gpu_percent = None
        db_snapshot = {}
        worker_util = 0.0
        try:
            from shared.database.connection import get_db_pool_snapshot

            db_snapshot = get_db_pool_snapshot()
            worker_util = float((db_snapshot.get("worker") or {}).get("utilization") or 0.0)
        except Exception:
            db_snapshot = {}
            worker_util = 0.0

        cpu_headroom = max(0.0, min(1.0, 1.0 - ((cpu_percent or 0.0) / 100.0)))
        gpu_headroom = (
            max(0.0, min(1.0, 1.0 - (gpu_percent / 100.0)))
            if gpu_percent is not None
            else 0.5
        )
        db_headroom = max(0.0, min(1.0, 1.0 - worker_util))
        return {
            "cpu_percent": cpu_percent,
            "gpu_percent": gpu_percent,
            "db_pool": db_snapshot,
            "cpu_headroom": round(cpu_headroom, 3),
            "gpu_headroom": round(gpu_headroom, 3),
            "db_headroom": round(db_headroom, 3),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _resolve_effective_lane(self, phase_name: str, resource_class: str) -> tuple[str, str]:
        """
        Lane policy: phase default + guarded dynamic adjustment by current headroom.
        Returns (lane, reason).
        """
        default_lane = self._phase_default_lane(phase_name)
        if not AUTOMATION_DYNAMIC_RESOURCE_ROUTING_ENABLED:
            return default_lane, "static_phase_policy"

        hr = self._resource_headroom or {}
        cpu_h = float(hr.get("cpu_headroom") or 0.0)
        gpu_h = float(hr.get("gpu_headroom") or 0.0)
        db_h = float(hr.get("db_headroom") or 0.0)

        if (
            default_lane == "gpu"
            and gpu_h < ROUTER_GPU_SATURATED_HEADROOM
            and cpu_h > ROUTER_CPU_HOT_HEADROOM
            and resource_class != "gpu_heavy"
        ):
            return "cpu", "dynamic_gpu_saturated_cpu_available"
        if (
            default_lane == "cpu"
            and resource_class == "cpu_light"
            and gpu_h > ROUTER_GPU_EXTRA_HEADROOM
            and cpu_h < ROUTER_CPU_HOT_HEADROOM
        ):
            return "gpu", "dynamic_cpu_hot_gpu_available"
        if resource_class == "db_heavy" and db_h < ROUTER_DB_PRESSURE_HEADROOM:
            return "cpu", "db_pressure_cpu_lane_only"
        return default_lane, "phase_default"

    def _dynamic_cooldown_multiplier(self, resource_class: str) -> tuple[float, str]:
        if not AUTOMATION_DYNAMIC_RESOURCE_ROUTING_ENABLED:
            return 1.0, "static"
        hr = self._resource_headroom or {}
        cpu_h = float(hr.get("cpu_headroom") or 0.0)
        gpu_h = float(hr.get("gpu_headroom") or 0.0)
        db_h = float(hr.get("db_headroom") or 0.0)
        if resource_class == "db_heavy":
            if db_h < ROUTER_DB_PRESSURE_HEADROOM:
                return ROUTER_MULT_DB_PRESSURE, "db_pool_pressure"
            if db_h > ROUTER_DB_EXTRA_HEADROOM:
                return ROUTER_MULT_HEADROOM_BONUS, "db_pool_headroom"
            return 1.0, "db_balanced"
        if resource_class == "gpu_heavy":
            if gpu_h < ROUTER_GPU_SATURATED_HEADROOM:
                return ROUTER_MULT_GPU_SATURATED, "gpu_saturated"
            if gpu_h > ROUTER_GPU_EXTRA_HEADROOM:
                return ROUTER_MULT_HEADROOM_BONUS, "gpu_headroom"
            return 1.0, "gpu_balanced"
        if cpu_h < ROUTER_CPU_HOT_HEADROOM:
            return ROUTER_MULT_CPU_HOT, "cpu_hot"
        if cpu_h > ROUTER_CPU_EXTRA_HEADROOM:
            return ROUTER_MULT_HEADROOM_BONUS, "cpu_headroom"
        return 1.0, "cpu_balanced"

    def _bootstrap_initial_tasks(self):
        """Queue key phases immediately on startup so work starts without waiting for first interval."""
        now = datetime.now(timezone.utc)
        # Phases that should run once as soon as we start (no deps, or bootstrap allows)
        for task_name in ("collection_cycle",):
            schedule = self.schedules.get(task_name)
            if not schedule or not schedule.get("enabled", True):
                continue
            if schedule.get("last_run") is not None:
                continue
            task = Task(
                id=f"{task_name}_bootstrap_{int(now.timestamp())}",
                name=task_name,
                priority=schedule.get("priority", TaskPriority.NORMAL),
                status=TaskStatus.PENDING,
                created_at=now,
                metadata={
                    "scheduled": True,
                    "phase": schedule.get("phase", 0),
                    "bootstrap": True,
                    "lane_default": self._phase_default_lane(task_name),
                    "resource_class": self._phase_resource_class(task_name),
                },
            )
            try:
                if self._enqueue_scheduled_task_nowait(task):
                    schedule["last_run"] = now
                    logger.info("Startup: queued %s so processing begins immediately", task_name)
            except asyncio.QueueFull:
                logger.warning("Startup: task queue full, skipped bootstrap %s", task_name)

    async def _scheduler(self):
        """Task scheduler with dependency management"""
        logger.info("Scheduler started")
        # Kick off work immediately on startup (don't wait for first 5s tick)
        self._bootstrap_initial_tasks()

        while self.is_running:
            try:
                current_time = datetime.now(timezone.utc)
                backlog_counts: dict[str, int] = {}
                self._pending_counts: dict[str, int] = {}
                if get_all_backlog_counts:
                    try:
                        backlog_counts = get_all_backlog_counts()
                    except Exception as e:
                        logger.debug("Backlog counts unavailable: %s", e)
                if get_all_pending_counts:
                    try:
                        self._pending_counts = get_all_pending_counts()
                    except Exception as e:
                        logger.debug("Pending counts unavailable: %s", e)
                self._resource_headroom = self._resource_headroom_snapshot()

                try:
                    from services.content_refinement_queue_service import (
                        maybe_auto_enqueue_comprehensive_rag_from_scheduler,
                    )

                    maybe_auto_enqueue_comprehensive_rag_from_scheduler()
                except Exception as e:
                    logger.debug("scheduler auto_enqueue comprehensive_rag: %s", e)

                # Drain coordinator-driven phase requests (thread-safe); respect enrichment-backlog-first
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
                        if phase_name not in self.schedules:
                            logger.debug("request_phase: unknown phase %s, skipping", phase_name)
                            continue
                        schedule = self.schedules[phase_name]
                        if not schedule.get("enabled", True):
                            logger.debug(
                                "request_phase: phase %s is disabled, skipping", phase_name
                            )
                            continue
                        if (
                            ENRICHMENT_BACKLOG_FIRST_ENABLED
                            and backlog_counts.get("content_enrichment", 0) > 0
                            and phase_name not in ENRICHMENT_BACKLOG_FIRST_WHITELIST
                        ):
                            logger.info(
                                "request_phase: skipping %s (enrichment backlog first, %s articles pending)",
                                phase_name,
                                backlog_counts.get("content_enrichment", 0),
                            )
                            continue
                        if (
                            phase_name == "nightly_enrichment_context"
                            and not self._can_enqueue_nightly_enrichment()
                        ):
                            logger.info(
                                "request_phase: skipping nightly_enrichment_context (in_flight=%s cap=%s)",
                                self._nightly_enrichment_in_flight_count(),
                                AUTOMATION_NIGHTLY_ENRICHMENT_MAX_QUEUED,
                            )
                            continue
                        if self._should_skip_redundant_phase_request(
                            phase_name,
                            allow_operator_bypass=bool(requested_activity_id),
                        ):
                            logger.debug(
                                "request_phase: skipping %s (drain pipeline saturated, inflight=%s)",
                                phase_name,
                                self._phase_pipeline_inflight(phase_name),
                            )
                            continue
                        if automation_db_pool_should_defer_phase(phase_name) and not (
                            requested_activity_id
                        ):
                            logger.debug(
                                "request_phase: defer %s (DB worker pool pressure)",
                                phase_name,
                            )
                            continue
                        task = Task(
                            id=f"{phase_name}_{int(datetime.now(timezone.utc).timestamp())}",
                            name=phase_name,
                            priority=schedule.get("priority", TaskPriority.NORMAL),
                            status=TaskStatus.PENDING,
                            created_at=datetime.now(timezone.utc),
                            metadata={
                                "domain": domain,
                                "storyline_id": storyline_id,
                                "requested_activity_id": requested_activity_id,
                                "force_nightly_unified_pipeline": force_nightly_unified_pipeline,
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

                # Sort tasks by phase for proper sequencing
                sorted_tasks = sorted(self.schedules.items(), key=lambda x: x[1].get("phase", 0))

                # Group tasks by phase and parallel groups
                phase_groups = {}
                for task_name, schedule in sorted_tasks:
                    if not schedule["enabled"]:
                        continue

                    phase = schedule.get("phase", 0)
                    parallel_group = schedule.get("parallel_group")

                    if parallel_group:
                        # Add to parallel group
                        if phase not in phase_groups:
                            phase_groups[phase] = {"parallel_groups": {}, "sequential_tasks": []}
                        if "parallel_groups" not in phase_groups[phase]:
                            phase_groups[phase]["parallel_groups"] = {}
                        if parallel_group not in phase_groups[phase]["parallel_groups"]:
                            phase_groups[phase]["parallel_groups"][parallel_group] = []
                        phase_groups[phase]["parallel_groups"][parallel_group].append(
                            (task_name, schedule)
                        )
                    else:
                        # Sequential task
                        if phase not in phase_groups:
                            phase_groups[phase] = {"parallel_groups": {}, "sequential_tasks": []}
                        phase_groups[phase]["sequential_tasks"].append((task_name, schedule))

                # Update resource allocation periodically
                if current_time.second % 60 == 0:  # Every minute
                    await self._update_resource_allocation()

                if not _AUTOMATION_DISABLE_DYNAMIC_TASK_SCALING:
                    if await self._should_scale_down():
                        logger.warning("High system load detected - scaling down processing")
                        self.max_concurrent_tasks = max(1, self.max_concurrent_tasks - 1)
                        await self._sync_phase_worker_tasks()
                    elif await self._should_scale_up():
                        logger.info("Low system load detected - scaling up processing")
                        cap = max(12, int(AUTOMATION_MAX_CONCURRENT_TASKS))
                        self.max_concurrent_tasks = min(cap, self.max_concurrent_tasks + 1)
                        await self._sync_phase_worker_tasks()

                # Parallel groups: enqueue each eligible phase through the same queue as sequential work
                # (avoids blocking the scheduler coroutine on asyncio.gather of long-running phases).
                for phase in sorted(phase_groups.keys()):
                    phase_data = phase_groups[phase]
                    for parallel_group, group_tasks in phase_data["parallel_groups"].items():
                        if not self._should_run_parallel_group(
                            parallel_group, group_tasks, current_time, backlog_counts
                        ):
                            continue
                        for task_name, schedule in group_tasks:
                            if self._should_run_task(
                                task_name, schedule, current_time, backlog_counts
                            ):
                                await self._create_and_queue_task(
                                    task_name, schedule, current_time
                                )

                # Sequential tasks: collect all runnable across phases, then queue by work-driven priority.
                # Select processes intelligently: effective priority (boost when backlog high), then most work first, then phase order.
                all_runnable: list[tuple[str, dict[str, Any]]] = []
                for phase in sorted(phase_groups.keys()):
                    phase_data = phase_groups[phase]
                    runnable = [
                        (task_name, schedule)
                        for task_name, schedule in phase_data["sequential_tasks"]
                        if self._should_run_task(task_name, schedule, current_time, backlog_counts)
                    ]
                    all_runnable.extend(runnable)

                def _work_driven_sort_key(item):
                    task_name, schedule = item
                    p = schedule.get(
                        "priority", TaskPriority.NORMAL
                    ).value  # lower = higher priority
                    backlog = backlog_counts.get(task_name, 0)
                    resource_class = self._phase_resource_class(task_name)
                    lane, _ = self._resolve_effective_lane(task_name, resource_class)
                    if (
                        ENRICHMENT_BACKLOG_FIRST_ENABLED
                        and task_name == "content_enrichment"
                        and backlog > 0
                    ):
                        p = TaskPriority.CRITICAL.value
                    elif backlog > BACKLOG_HIGH_THRESHOLD:
                        # Boost priority by one level when this task has a lot of work (prioritize work that needs doing)
                        p = max(TaskPriority.CRITICAL.value, p - 1)
                    # Prefer queueing tasks that fit current free resources.
                    if AUTOMATION_DYNAMIC_RESOURCE_ROUTING_ENABLED:
                        hr = self._resource_headroom or {}
                        if (
                            lane == "gpu"
                            and float(hr.get("gpu_headroom") or 0.0) > ROUTER_GPU_EXTRA_HEADROOM
                        ):
                            p = max(TaskPriority.CRITICAL.value, p - 1)
                        if (
                            lane == "cpu"
                            and float(hr.get("cpu_headroom") or 0.0) > ROUTER_CPU_EXTRA_HEADROOM
                        ):
                            p = max(TaskPriority.CRITICAL.value, p - 1)
                    phase = schedule.get("phase", 0)
                    # Sort: higher priority first (lower p), then more backlog first (-backlog), then earlier phase
                    return (p, -backlog, phase)

                for task_name, schedule in sorted(all_runnable, key=_work_driven_sort_key):
                    await self._create_and_queue_task(task_name, schedule, current_time)

                await asyncio.sleep(float(AUTOMATION_SCHEDULER_TICK_SECONDS))

            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(float(AUTOMATION_SCHEDULER_TICK_SECONDS))

        logger.info("Scheduler stopped")

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
                mult = int(os.environ.get("AUTOMATION_PER_PHASE_CONCURRENT_NIGHTLY_MULT", "4"))
                return min(self.max_concurrent_tasks, base * max(1, mult))
        except Exception:
            pass
        return min(self.max_concurrent_tasks, base)

    def _per_phase_execute_concurrent_cap(self, task: Task) -> int:
        """Cap at task start; nightly_sequential_drain is unlimited."""
        if (task.metadata or {}).get("nightly_sequential_drain"):
            return 0
        return self._per_phase_scheduler_concurrent_cap(task.name)

    def _should_run_parallel_group(
        self,
        parallel_group: str,
        tasks: list[tuple[str, dict]],
        current_time: datetime,
        backlog_counts: dict[str, int] | None = None,
    ) -> bool:
        """Check if parallel group should run"""
        if not tasks:
            return False
        backlog_counts = backlog_counts or {}
        for task_name, schedule in tasks:
            if self._should_run_task(task_name, schedule, current_time, backlog_counts):
                return True
        return False

    def _should_run_task(
        self,
        task_name: str,
        schedule: dict[str, Any],
        current_time: datetime,
        backlog_counts: dict[str, int] | None = None,
    ) -> bool:
        """Check if individual task should run.

        Two separate concepts:
        - **pending**: raw count of items waiting (even 1).  Used for SKIP_WHEN_EMPTY
          so tasks with any work still run on their normal interval.
        - **backlog**: pending minus one batch size.  Only positive when there is more
          work than a single run can handle.  Used to shorten the interval so the
          scheduler drains the excess faster.

        v8: When in analysis window (after collection_cycle), only tasks in the current
        pipeline step are allowed; step advances when time budget expires.
        """
        # v8: Pipeline-agnostic tasks always use normal logic (e.g. document_processing drains PDF backlog)
        if task_name in ("collection_cycle", "health_check", "document_processing", "content_enrichment"):
            pass
        elif not USE_WORKLOAD_DRIVEN_ORDER and self._analysis_window_start is not None:
            # Legacy: only run tasks in current pipeline step when step budget is enforced
            if (
                self._active_step < len(self._step_time_budgets)
                and self._step_started_at is not None
            ):
                budget = self._step_time_budgets[self._active_step]
                if (
                    budget is not None
                    and (current_time - self._step_started_at).total_seconds() >= budget
                ):
                    self._active_step = min(self._active_step + 1, len(ANALYSIS_PIPELINE_STEPS) - 1)
                    self._step_started_at = current_time
            if self._active_step < len(ANALYSIS_PIPELINE_STEPS):
                if task_name not in ANALYSIS_PIPELINE_STEPS[self._active_step]:
                    return False
        elif USE_WORKLOAD_DRIVEN_ORDER and self._analysis_window_start is not None:
            # Advance step for reporting only; do not gate tasks — workload order decides
            if (
                self._active_step < len(self._step_time_budgets)
                and self._step_started_at is not None
            ):
                budget = self._step_time_budgets[self._active_step]
                if (
                    budget is not None
                    and (current_time - self._step_started_at).total_seconds() >= budget
                ):
                    self._active_step = min(self._active_step + 1, len(ANALYSIS_PIPELINE_STEPS) - 1)
                    self._step_started_at = current_time

        if not self._check_dependencies(task_name, schedule):
            return False

        # When PostgreSQL is down, do not schedule new phases (avoids LLM/CPU waste). Flush runs when DB is back.
        try:
            if os.getenv("AUTOMATION_PAUSE_WHEN_DB_DOWN", "true").lower() in ("1", "true", "yes"):
                from shared.database.db_availability import is_automation_db_ready

                if not is_automation_db_ready():
                    return False
        except Exception:
            pass

        # Workload-driven: don't run collection_cycle when downstream backlog is high — complete
        # collection → processing → synthesis sequence before adding more RSS.
        if USE_WORKLOAD_DRIVEN_ORDER and task_name == "collection_cycle":
            pc = self._pending_counts if hasattr(self, "_pending_counts") else {}
            downstream, throttle_br = _collection_throttle_pending_total(pc)
            if downstream > COLLECTION_THROTTLE_PENDING_THRESHOLD:
                logger.debug(
                    "collection_cycle throttled: pending_total=%s threshold=%s breakdown=%s",
                    downstream,
                    COLLECTION_THROTTLE_PENDING_THRESHOLD,
                    throttle_br,
                )
                return False

        if schedule.get("idle_only") and not self._is_system_idle():
            return False

        # Nightly unified pipeline [NIGHTLY_PIPELINE_START, END): nightly_enrichment_context owns the long drain;
        # NIGHTLY_PIPELINE_EXCLUSIVE (default on) blocks other scheduled phases until 07:00 local.
        try:
            from services.nightly_ingest_window_service import in_nightly_pipeline_window_est

            _nightly_pipe = in_nightly_pipeline_window_est()
        except Exception:
            _nightly_pipe = False
        if task_name == "context_sync" and _nightly_pipe:
            return False
        if task_name == "content_refinement_queue" and _nightly_pipe:
            return False
        if task_name == "nightly_enrichment_context" and not _nightly_pipe:
            return False

        # During the unified nightly window, only run the long drain + essentials unless disabled.
        if _nightly_pipe:
            raw_exc = os.environ.get("NIGHTLY_PIPELINE_EXCLUSIVE", "1").lower()
            if raw_exc in ("1", "true", "yes"):
                allowed = frozenset(
                    x.strip()
                    for x in os.environ.get(
                        "NIGHTLY_PIPELINE_ALLOWED_SCHEDULED_PHASES",
                        "nightly_enrichment_context,health_check,pending_db_flush",
                    ).split(",")
                    if x.strip()
                )
                if task_name not in allowed:
                    return False

        backlog_counts = backlog_counts or {}
        if (
            ENRICHMENT_BACKLOG_FIRST_ENABLED
            and backlog_counts.get("content_enrichment", 0) > 0
            and task_name not in ENRICHMENT_BACKLOG_FIRST_WHITELIST
        ):
            return False

        backlog = backlog_counts.get(task_name, 0)

        # SKIP_WHEN_EMPTY: skip when no work (so we don't run empty cycles).
        pending = (
            self._pending_counts.get(task_name, 0) if hasattr(self, "_pending_counts") else backlog
        )
        if task_name in SKIP_WHEN_EMPTY and pending == 0:
            return False

        has_work = pending > 0 or backlog > 0

        # Avoid N workers all executing the same LLM-heavy phase while others sit idle.
        ppc = self._per_phase_scheduler_concurrent_cap(task_name)
        if ppc > 0:
            running_same = int(self._running_tasks_by_phase.get(task_name, 0) or 0)
            if running_same >= ppc:
                return False

        # Workload-driven: when there is work, eligibility is based on cooldown + deps only (no interval).
        # Each tick we check every process; if it has work and deps are satisfied, we add it to the candidate
        # list; sort order (priority, -backlog, phase) then decides what gets queued first.
        if USE_WORKLOAD_DRIVEN_ORDER and has_work:
            time_since = (
                (current_time - schedule["last_run"]).total_seconds()
                if schedule.get("last_run")
                else 9999
            )
            cooldown_sec = WORKLOAD_MIN_COOLDOWN
            resource_class = self._phase_resource_class(task_name)
            try:
                from services.backlog_metrics import BATCH_SIZE_PER_TASK
                from services.workload_balancer import (
                    effective_workload_cooldown_seconds,
                    workload_balancer_enabled,
                    workload_balancer_phase_names,
                )

                if workload_balancer_enabled() and task_name in workload_balancer_phase_names():
                    _bs = BATCH_SIZE_PER_TASK.get(task_name, 30)
                    cooldown_sec = effective_workload_cooldown_seconds(
                        task_name,
                        pending,
                        base_cooldown=WORKLOAD_MIN_COOLDOWN,
                        batch_size=int(_bs),
                    )
            except Exception:
                pass
            mult, _ = self._dynamic_cooldown_multiplier(resource_class)
            cooldown_sec = max(3, int(round(float(cooldown_sec) * float(mult))))
            if time_since >= cooldown_sec and self._are_dependencies_satisfied(
                task_name, schedule, current_time
            ):
                if automation_db_pool_should_defer_phase(task_name):
                    return False
                return True
            return False

        # No work (or legacy mode): use interval so we don't run e.g. collection_cycle every tick when idle.
        base_interval = schedule["interval"]
        adaptive_interval = self._calculate_adaptive_interval(task_name, base_interval)
        if backlog > BACKLOG_HIGH_THRESHOLD:
            effective_interval = min(adaptive_interval, BACKLOG_MODE_INTERVAL)
        elif backlog > 0:
            effective_interval = min(adaptive_interval, BACKLOG_ANY_INTERVAL)
        else:
            effective_interval = adaptive_interval

        if (
            schedule["last_run"] is None
            or (current_time - schedule["last_run"]).total_seconds() >= effective_interval
        ):
            if self._are_dependencies_satisfied(task_name, schedule, current_time):
                if automation_db_pool_should_defer_phase(task_name):
                    return False
                return True
        return False

    async def _create_and_queue_task(
        self, task_name: str, schedule: dict[str, Any], current_time: datetime
    ):
        """Create and queue a task"""
        if task_name == "health_check":
            return
        if self._should_skip_redundant_phase_request(task_name):
            return
        if self._scheduled_enqueue_paused() and task_name not in QUEUE_PAUSE_ALLOW_SCHEDULED:
            logger.info(
                "Queue soft cap: skipping scheduled enqueue for %s (depth=%s cap=%s)",
                task_name,
                self._automation_queue_depth(),
                AUTOMATION_QUEUE_SOFT_CAP,
            )
            return
        if automation_db_pool_should_defer_phase(task_name):
            logger.debug(
                "DB worker pool pressure — skip scheduled create/queue for %s",
                task_name,
            )
            return
        # Create task
        task = Task(
            id=f"{task_name}_{int(current_time.timestamp())}",
            name=task_name,
            priority=schedule["priority"],
            status=TaskStatus.PENDING,
            created_at=current_time,
            metadata={
                "scheduled": True,
                "phase": schedule.get("phase", 0),
                "estimated_duration": schedule.get("estimated_duration", 60),
                "lane_default": self._phase_default_lane(task_name),
                "resource_class": self._phase_resource_class(task_name),
            },
        )

        # Add to queue (do not advance last_run if nightly cap or queue cap skipped enqueue)
        if await self._enqueue_scheduled_task(task):
            schedule["last_run"] = current_time
            logger.info(f"Scheduled task: {task_name} (Phase {schedule.get('phase', 0)})")

    def _check_dependencies(self, task_name: str, schedule: dict[str, Any]) -> bool:
        """Check if task has dependencies"""
        depends_on = schedule.get("depends_on", [])
        return len(depends_on) == 0 or all(
            dep_task in self.schedules and self.schedules[dep_task]["enabled"]
            for dep_task in depends_on
        )

    def _are_dependencies_satisfied(
        self, task_name: str, schedule: dict[str, Any], current_time: datetime
    ) -> bool:
        """Check if all dependencies have been satisfied recently.
        When this task has never run, treat 'dependency never run' as satisfied so we queue
        both (phase order ensures the dependency runs first); otherwise nothing would ever
        call the dependent.
        """
        depends_on = schedule.get("depends_on", [])
        this_never_run = schedule.get("last_run") is None

        for dep_task in depends_on:
            if dep_task not in self.schedules:
                continue

            dep_schedule = self.schedules[dep_task]
            dep_never_run = dep_schedule["last_run"] is None

            # Bootstrap: if both this task and the dependency have never run, allow queuing
            # so the scheduler queues both; phase order queues the dependency first.
            if this_never_run and dep_never_run:
                continue

            if dep_never_run:
                return False

            # Require a short settle window after dependency completed (DB / pipeline visibility).
            # Cap by AUTOMATION_DEPENDENCY_SETTLE_CAP_SEC so long phases (e.g. collection_cycle ~30m
            # estimated) do not block dependents indefinitely while collection runs often.
            time_since_dep = (current_time - dep_schedule["last_run"]).total_seconds()
            dep_duration = dep_schedule.get("estimated_duration", 60)
            adjusted_duration = dep_duration * self.metrics["load_factor"]
            settle = min(max(adjusted_duration, 15.0), float(AUTOMATION_DEPENDENCY_SETTLE_CAP_SEC))
            if time_since_dep < settle:
                return False

        return True

    def _get_dynamic_resource_service(self):
        """Get dynamic resource service instance"""
        if self.dynamic_resource_service is None:
            from services.dynamic_resource_service import get_dynamic_resource_service

            self.dynamic_resource_service = get_dynamic_resource_service()
        return self.dynamic_resource_service

    async def _update_resource_allocation(self):
        """Update resource allocation based on current system load"""
        try:
            resource_service = self._get_dynamic_resource_service()
            self.resource_allocation = await resource_service.allocate_resources_dynamically()

            # Never shrink below configured automation floor (env AUTOMATION_MAX_CONCURRENT_TASKS).
            allocated = int(self.resource_allocation.max_parallel_tasks)
            self.max_concurrent_tasks = max(allocated, int(AUTOMATION_MAX_CONCURRENT_TASKS))

            logger.info(
                f"Resource allocation updated: {self.max_concurrent_tasks} max parallel tasks "
                f"(floor={AUTOMATION_MAX_CONCURRENT_TASKS}, allocated={allocated})"
            )
            if self.is_running:
                await self._sync_phase_worker_tasks()

        except Exception as e:
            logger.error(f"Error updating resource allocation: {e}")

    async def _should_scale_down(self) -> bool:
        """Check if system should scale down due to high load"""
        try:
            resource_service = self._get_dynamic_resource_service()
            return await resource_service.should_scale_down()
        except Exception as e:
            logger.error(f"Error checking scale down conditions: {e}")
            return False

    async def _should_scale_up(self) -> bool:
        """Check if system should scale up due to low load"""
        try:
            resource_service = self._get_dynamic_resource_service()
            return await resource_service.should_scale_up()
        except Exception as e:
            logger.error(f"Error checking scale up conditions: {e}")
            return False

    def _calculate_adaptive_interval(self, task_name: str, base_interval: int) -> int:
        """Calculate adaptive interval based on processing load and history"""
        if not self.metrics["adaptive_timing"]:
            return base_interval

        # Get processing history for this task
        history = self.metrics["processing_history"].get(task_name, [])
        if len(history) < 3:  # Need at least 3 data points
            return base_interval

        # Calculate average processing time vs estimated
        recent_times = history[-5:]  # Last 5 runs
        avg_actual = sum(recent_times) / len(recent_times)
        estimated = self.schedules[task_name].get("estimated_duration", 60)

        # Calculate load factor
        load_ratio = avg_actual / estimated if estimated > 0 else 1.0

        # Adjust interval based on load
        if load_ratio > 1.5:  # Processing taking 50% longer than estimated
            self.metrics["load_factor"] = min(2.0, self.metrics["load_factor"] * 1.1)
        elif load_ratio < 0.8:  # Processing faster than estimated
            self.metrics["load_factor"] = max(0.5, self.metrics["load_factor"] * 0.95)

        # Apply load factor to interval
        adjusted_interval = int(base_interval * self.metrics["load_factor"])

        # Ensure minimum interval (at least 2x estimated duration)
        min_interval = max(60, estimated * 2)
        # Cap at 1.5x base so we don't slow down too much during full-time runs
        max_interval = int(base_interval * 1.5)
        return min(max(adjusted_interval, min_interval), max_interval)

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
            conn = self._get_db_connection_sync()
            if not conn:
                return 1.0
            try:
                with conn.cursor() as cursor:
                    recent_count = 0
                    for schema in get_pipeline_schema_names_active():
                        cursor.execute(f"""
                            SELECT COUNT(*) FROM {schema}.articles
                            WHERE created_at > NOW() - INTERVAL '1 hour'
                        """)
                        recent_count += int(cursor.fetchone()[0] or 0)
            finally:
                conn.close()

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
                    get_gpu_metrics,
                    should_throttle_ollama,
                )

                if should_throttle_ollama():
                    metrics = get_gpu_metrics()
                    temp = metrics.get("gpu_temperature_c")
                    logger.warning(
                        "GPU temp %s C >= 82 C — pausing Ollama task %s for %ss to cool",
                        temp,
                        task.name,
                        GPU_THROTTLE_SLEEP_SECONDS,
                    )
                    await asyncio.sleep(GPU_THROTTLE_SLEEP_SECONDS)
                    if should_throttle_ollama():
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
                        for x in os.environ.get(
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
            )
        except Exception as e:
            logger.debug("Activity feed add_current: %s", e)

        try:
            # Execute task based on type
            if task.name == "collection_cycle":
                self._collection_cycle_started_at = task.started_at
                asyncio.create_task(self._run_collection_watchdog(task.started_at))
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
            elif task.name == "digest_generation":
                await self._execute_digest_generation(task)
            elif task.name == "data_cleanup":
                await self._execute_data_cleanup(task)
            elif task.name == "health_check":
                await self._execute_health_check(task)
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
            elif task.name == "storyline_enrichment":
                await self._execute_storyline_enrichment(task)
            elif task.name == "entity_extraction":
                await self._execute_entity_extraction(task)
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
            self._last_completed_at_by_phase[task.name] = task.completed_at
            if not (task.metadata or {}).get("skip_automation_run_history"):
                _persist_automation_run(
                    task.name,
                    task.started_at,
                    task.completed_at,
                    True,
                    None,
                )
            # Record completion for last-60m run counts (used by monitoring timeline).
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

            # v8: When collection_cycle completes, enter analysis pipeline (step 0) and reset re-enqueue counts
            if task.name == "collection_cycle":
                self._analysis_window_start = task.completed_at
                self._active_step = 0
                self._step_started_at = task.completed_at
                self._requeue_counts = {}

            # Calculate processing time
            processing_time = (task.completed_at - task.started_at).total_seconds()
            self._update_avg_processing_time(processing_time)

            # Update processing history for adaptive timing
            self._update_processing_history(task.name, processing_time)

            logger.info(
                f"Task {task.name} completed in {processing_time:.2f}s (Phase {task.metadata.get('phase', 0)})"
            )

            # Continuous iteration: when work remains, queue next run (v8: capped per analysis window)
            if task.name in BATCH_PHASES_CONTINUOUS and not (task.metadata or {}).get(
                "nightly_sequential_drain"
            ):
                try:
                    current = self._requeue_counts.get(task.name, 0)
                    if (
                        self._max_requeue_per_window > 0
                        and current >= self._max_requeue_per_window
                    ):
                        logger.debug(
                            "Re-enqueue cap reached for %s (%s)",
                            task.name,
                            self._max_requeue_per_window,
                        )
                    elif await self._has_pending_work(task.name):
                        if (
                            self._scheduled_enqueue_paused()
                            and task.name not in QUEUE_PAUSE_ALLOW_SCHEDULED
                        ):
                            logger.debug(
                                "Queue soft cap: skip continuous re-queue for %s (depth=%s)",
                                task.name,
                                self._automation_queue_depth(),
                            )
                        elif automation_db_pool_should_defer_phase(task.name):
                            logger.debug(
                                "DB worker pool pressure — skip continuous re-queue for %s",
                                task.name,
                            )
                        else:
                            next_task = Task(
                                id=f"{task.name}_{int(task.completed_at.timestamp())}_next",
                                name=task.name,
                                priority=self.schedules[task.name].get(
                                    "priority", TaskPriority.NORMAL
                                ),
                                status=TaskStatus.PENDING,
                                created_at=task.completed_at,
                                metadata={
                                    "scheduled": True,
                                    "phase": self.schedules[task.name].get("phase", 0),
                                    "estimated_duration": self.schedules[task.name].get(
                                        "estimated_duration", 60
                                    ),
                                    "continuous": True,
                                    "lane_default": self._phase_default_lane(task.name),
                                    "resource_class": self._phase_resource_class(task.name),
                                },
                            )
                            if await self._enqueue_scheduled_task(next_task):
                                self._requeue_counts[task.name] = current + 1
                                logger.debug(
                                    "Queued next %s immediately (pending work remains, requeue %s/%s)",
                                    task.name,
                                    current + 1,
                                    self._max_requeue_per_window,
                                )
                except Exception as e:
                    logger.debug("Re-enqueue check for %s: %s", task.name, e)

            # Chain: request any phase that depends on this one so the pipeline keeps moving
            # When enrichment-backlog-first is enabled and backlog non-empty, do not chain-request phases outside the whitelist
            enrichment_backlog = 0
            if (
                ENRICHMENT_BACKLOG_FIRST_ENABLED
                and get_all_backlog_counts
                and task.name == "content_enrichment"
            ):
                try:
                    counts = get_all_backlog_counts()
                    enrichment_backlog = counts.get("content_enrichment", 0) or 0
                except Exception:
                    pass
            if (task.metadata or {}).get("nightly_sequential_drain"):
                pass
            else:
                for other_name, other_sched in self.schedules.items():
                    if not other_sched.get("enabled", True):
                        continue
                    deps = other_sched.get("depends_on") or []
                    if task.name not in deps:
                        continue
                    if (
                        enrichment_backlog > 0
                        and other_name not in ENRICHMENT_BACKLOG_FIRST_WHITELIST
                    ):
                        logger.info(
                            "Chained: skipping %s (enrichment backlog first, %s articles pending)",
                            other_name,
                            enrichment_backlog,
                        )
                        continue
                    if (
                        self._scheduled_enqueue_paused()
                        and other_name not in QUEUE_PAUSE_ALLOW_SCHEDULED
                    ):
                        logger.debug(
                            "Queue soft cap: skip chained request for %s (depth=%s)",
                            other_name,
                            self._automation_queue_depth(),
                        )
                        continue
                    try:
                        self.request_phase(other_name)
                        logger.info("Chained: requested %s (depends on %s)", other_name, task.name)
                    except Exception as e:
                        logger.debug("Chain request %s: %s", other_name, e)

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

            # Retry if under max retries
            if task.retry_count < task.max_retries:
                task.status = TaskStatus.RETRYING
                await asyncio.sleep(min(60 * task.retry_count, 300))  # Exponential backoff
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

    def _activity_feed_activity_id(self, task: Task) -> str:
        """
        Stable id for phases that should appear once in Monitor \"Current activity\".
        (Otherwise each Task UUID creates a separate row; nightly can enqueue up to MAX_QUEUED.)
        """
        if task.name == "nightly_enrichment_context":
            return "phase:nightly_enrichment_context"
        return task.id

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
        """Execute RSS processing: use domain feeds (collect_rss_feeds) so all politics/finance/science_tech.rss_feeds are used."""
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

        try:
            from services.nightly_ingest_window_service import in_nightly_pipeline_window_est

            if in_nightly_pipeline_window_est() and not (task.metadata or {}).get(
                "nightly_sequential_drain"
            ):
                logger.debug(
                    "Content enrichment: nightly pipeline window — handled by nightly_enrichment_context"
                )
                return
        except Exception:
            pass

        from services.article_content_enrichment_service import enrich_articles_batch

        try:
            async with self._content_enrichment_lock:
                loop = asyncio.get_event_loop()
                # Burst (48h catch-up): batch 60; revert to 40 after
                await loop.run_in_executor(None, lambda: enrich_articles_batch(batch_size=60))
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

        try:
            from services.backlog_metrics import get_backlog_count
            from services.document_processing_service import process_unprocessed_documents

            # Process more per run when backlog is large (batch 10 + backlog over 20 → limit 25)
            backlog = get_backlog_count("document_processing") or 0
            limit = 25 if backlog > 20 else 15 if backlog > 10 else 10
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: process_unprocessed_documents(limit=limit)
            )
            count = result.get("processed", 0) if isinstance(result, dict) else 0
            if count > 0:
                logger.info(f"Document processing (v8): {count} documents processed")
        except Exception as e:
            logger.warning(f"Document processing failed: {e}")

    async def _execute_collection_cycle(self, task: Task):
        """v8: Run collection sub-steps sequentially; drain enrichment and document processing; drain pending_collection_queue."""
        import asyncio

        # Entering collection window — leave analysis pipeline mode
        self._analysis_window_start = None
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
        skip_rss = os.environ.get("AUTOMATION_SKIP_RSS_IN_COLLECTION_CYCLE", "").lower() in (
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
        # 2. Content enrichment — loop until drained or cap (nightly pipeline window: nightly_enrichment_context owns this)
        skip_enrich_nightly = False
        try:
            from services.nightly_ingest_window_service import in_nightly_pipeline_window_est

            skip_enrich_nightly = in_nightly_pipeline_window_est()
        except Exception:
            pass
        if not skip_enrich_nightly:
            max_enrich_iters = 30
            for _ in range(max_enrich_iters):
                if not get_all_pending_counts:
                    break
                try:
                    counts = get_all_pending_counts()
                    if (counts.get("content_enrichment") or 0) == 0:
                        break
                except Exception:
                    break
                try:
                    await self._execute_content_enrichment(dummy)
                except Exception as e:
                    logger.warning(f"Collection cycle enrichment step failed: {e}")
                    break
        # 3. Document collection (skip during backfill pause — avoid adding new external documents)
        if not backfill_pause:
            try:
                await self._execute_document_collection(dummy)
            except Exception as e:
                logger.warning(f"Collection cycle document collection failed: {e}")
        else:
            logger.info("Collection cycle: skipping document collection (PIPELINE_BACKFILL_MODE pause)")
        # 4. Document processing — loop until drained or cap
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
        """Auto-synthesize storylines (Wikipedia-style) that have 3+ articles."""
        import asyncio

        try:
            from services.deep_content_synthesis import DeepContentSynthesisService

            svc = DeepContentSynthesisService()
            loop = asyncio.get_event_loop()

            for domain_key, schema in pipeline_url_schema_pairs():
                conn = await self._get_db_connection()
                if not conn:
                    continue
                try:
                    cur = conn.cursor()
                    # Storylines with 3+ articles: no synthesis yet, or stale (newest article newer than synthesized_at)
                    try:
                        cur.execute(
                            f"""
                            SELECT s.id FROM {schema}.storylines s
                            JOIN (SELECT storyline_id, COUNT(*) AS c FROM {schema}.storyline_articles GROUP BY storyline_id) sa
                              ON sa.storyline_id = s.id AND sa.c >= 3
                            WHERE s.synthesized_content IS NULL
                               OR EXISTS (
                                 SELECT 1 FROM {schema}.storyline_articles sa2
                                 JOIN {schema}.articles a ON a.id = sa2.article_id
                                 WHERE sa2.storyline_id = s.id
                                 AND a.created_at > COALESCE(s.synthesized_at, '1970-01-01'::timestamptz)
                               )
                            ORDER BY s.synthesized_at NULLS FIRST,
                                     (SELECT MAX(a2.created_at) FROM {schema}.storyline_articles sa3
                                      JOIN {schema}.articles a2 ON a2.id = sa3.article_id
                                      WHERE sa3.storyline_id = s.id) DESC NULLS LAST
                            LIMIT 4
                            """
                        )
                    except Exception:
                        # Fallback if synthesized_at column missing
                        cur.execute(
                            f"""
                            SELECT s.id FROM {schema}.storylines s
                            JOIN (SELECT storyline_id, COUNT(*) AS c FROM {schema}.storyline_articles GROUP BY storyline_id) sa
                              ON sa.storyline_id = s.id AND sa.c >= 3
                            WHERE s.synthesized_content IS NULL
                            ORDER BY s.updated_at DESC
                            LIMIT 4
                            """
                        )
                    rows = cur.fetchall()
                    cur.close()
                    conn.close()
                except Exception:
                    try:
                        conn.close()
                    except Exception:
                        pass
                    continue
                for (storyline_id,) in rows:
                    try:
                        await loop.run_in_executor(
                            None,
                            lambda d=domain_key, sid=storyline_id: svc.synthesize_storyline_content(
                                d, sid, depth="standard", save_to_db=True
                            ),
                        )
                        logger.info(
                            f"Storyline synthesis (v8): {domain_key} storyline {storyline_id}"
                        )
                    except Exception as e:
                        logger.warning(f"Storyline synthesis {storyline_id} failed: {e}")
        except Exception as e:
            logger.warning(f"Storyline synthesis phase failed: {e}")

    async def _execute_daily_briefing_synthesis(self, task: Task):
        """Generate breaking-news synthesis per domain for briefing page."""
        import asyncio

        try:
            from services.deep_content_synthesis import DeepContentSynthesisService

            svc = DeepContentSynthesisService()
            loop = asyncio.get_event_loop()
            for domain_key in get_pipeline_active_domain_keys():
                try:
                    await loop.run_in_executor(
                        None,
                        lambda d=domain_key: svc.synthesize_breaking_news(
                            d, hours=72, min_articles=3
                        ),  # v8
                    )
                    logger.info(f"Daily briefing synthesis (v8): {domain_key}")
                except Exception as e:
                    logger.warning(f"Daily briefing synthesis {domain_key} failed: {e}")
        except Exception as e:
            logger.warning(f"Daily briefing synthesis phase failed: {e}")

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

        for domain_key in get_pipeline_active_domain_keys():
            try:
                # Production: 100 contexts/batch, ~5-10s per batch, prevents backlog
                total = await asyncio.get_event_loop().run_in_executor(
                    None, lambda d=domain_key: sync_domain_articles_to_contexts(d, limit=100)
                )
                if total > 0:
                    logger.info(f"Context sync {domain_key}: {total} contexts created")
            except Exception as e:
                logger.warning(f"Context sync {domain_key} failed: {e}")

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

        for domain_key in get_pipeline_active_domain_keys():
            try:
                total = await asyncio.get_event_loop().run_in_executor(
                    None, lambda d=domain_key: sync_domain_entity_profiles(d)
                )
                if total > 0:
                    logger.info(f"Entity profile sync {domain_key}: {total} new mappings")
            except Exception as e:
                logger.warning(f"Entity profile sync {domain_key} failed: {e}")

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
        try:
            # Default: one automation task drains all pending contexts in a loop (CLAIM_EXTRACTION_DRAIN=true).
            # Keeps a single claim_extraction slot busy until idle so we do not stack many queued copies; other
            # workers and LLM lane semaphores handle sharing the GPU with other phases.
            # Drain writes one automation_run_history row per batch; skip the task-level history row.
            run_limit = (task.metadata or {}).get("nightly_limit")
            nlim = int(run_limit) if run_limit else None
            if claim_extraction_drain_enabled():
                task.metadata["skip_automation_run_history"] = True
                total, batches = await drain_claim_extraction_for_automation_task(
                    nightly_limit=nlim,
                )
                if total > 0:
                    logger.info(
                        "Claim extraction: %s claims inserted (%s batch(es) in one task)",
                        total,
                        batches,
                    )
            else:
                res = await run_claim_extraction_batch(limit=nlim)
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

            stats = await asyncio.to_thread(run_legislative_reference_batch)
            if stats and not stats.get("skipped") and int(stats.get("articles_scanned") or 0) > 0:
                logger.info(
                    "Legislative references: scanned %s articles, %s snapshots",
                    stats.get("articles_scanned"),
                    stats.get("references_upserted"),
                )
        except Exception as e:
            logger.warning("Legislative references failed: %s", e)

    async def _execute_claims_to_facts(self, task: Task):
        """Promote high-confidence extracted_claims to versioned_facts (activates story state chain)."""
        from services.claim_extraction_service import (
            claims_to_facts_drain_enabled,
            drain_claims_to_facts_for_automation_task,
            promote_claims_to_versioned_facts,
        )

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
                        "Claims to facts: %s rows promoted (%s batch(es) in one task)",
                        total,
                        batches,
                    )
            else:
                if per_batch is not None:
                    stats = await asyncio.to_thread(
                        promote_claims_to_versioned_facts,
                        None,
                        per_batch,
                    )
                else:
                    stats = await asyncio.to_thread(promote_claims_to_versioned_facts)
                if not isinstance(stats, dict):
                    return
                if stats.get("candidates", 0) == 0:
                    logger.debug("Claims to facts: no promotable claims in batch")
        except Exception as e:
            logger.warning(f"Claims to facts failed: {e}")

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
        try:
            from config.context_centric_config import is_context_centric_task_enabled

            if not is_context_centric_task_enabled("event_tracking"):
                return
        except Exception:
            pass
        try:
            from services.event_tracking_service import run_event_tracking_batch

            # Higher limit to drain unlinked-context backlog; ~30 contexts/batch, 3 domains
            total = await run_event_tracking_batch(limit=300)
            if total > 0:
                logger.info(f"Event tracking: {total} chronicle entries added")
        except Exception as e:
            logger.warning(f"Event tracking failed: {e}")

    async def _execute_investigation_report_refresh(self, task: Task):
        """Regenerate investigation reports for events whose context set has changed (Phase 2.4)."""
        try:
            from config.context_centric_config import is_context_centric_task_enabled

            if not is_context_centric_task_enabled("investigation_report_refresh"):
                return
        except Exception:
            pass
        from services.investigation_report_service import (
            create_initial_reports_for_new_events,
            refresh_stale_investigation_reports,
        )

        try:
            created = await create_initial_reports_for_new_events(limit=5)
            refreshed = await refresh_stale_investigation_reports(limit=3)
            if created > 0 or refreshed > 0:
                logger.info(f"Investigation report refresh: {created} new, {refreshed} updated")
            else:
                logger.debug("Investigation report refresh: no new or stale reports")
        except Exception as e:
            logger.warning(f"Investigation report refresh failed: {e}")

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
        """LLM-powered review: verify each context in an event actually belongs (Phase 3)."""
        try:
            from config.context_centric_config import is_context_centric_task_enabled

            if not is_context_centric_task_enabled("event_coherence_review"):
                return
        except Exception:
            pass
        from services.event_coherence_reviewer import review_all_open_events

        try:
            result = await review_all_open_events(relevance_threshold=0.5, auto_remove=True)
            removed = result.get("total_contexts_removed", 0)
            reviewed = result.get("events_reviewed", 0)
            if removed > 0:
                logger.info(
                    f"Event coherence review: {removed} contexts removed from {reviewed} events"
                )
            else:
                logger.debug(f"Event coherence review: {reviewed} events reviewed, all coherent")
        except Exception as e:
            logger.warning(f"Event coherence review failed: {e}")

    async def _execute_entity_profile_build(self, task: Task):
        """Build Wikipedia-style sections for entity_profiles from contexts (Phase 1.3)."""
        try:
            from config.context_centric_config import is_context_centric_task_enabled

            if not is_context_centric_task_enabled("entity_profile_build"):
                return
        except Exception:
            pass
        from services.entity_profile_builder_service import run_profile_builder_batch

        try:
            updated = await run_profile_builder_batch(limit=25)  # v8
            if updated > 0:
                logger.info(f"Entity profile build: {updated} profiles updated")
        except Exception as e:
            logger.warning(f"Entity profile build failed: {e}")

    async def _execute_entity_dossier_compile(self, task: Task):
        """Compile entity dossiers (chronicle_data, relationships, positions) for entities missing or stale (Phase 2.6)."""
        try:
            from config.context_centric_config import is_context_centric_task_enabled

            if not is_context_centric_task_enabled("entity_dossier_compile"):
                return
        except Exception:
            pass
        import asyncio

        from services.dossier_compiler_service import _run_scheduled_dossier_compiles

        try:
            loop = asyncio.get_event_loop()
            compiled = await loop.run_in_executor(
                self._executor,
                _run_scheduled_dossier_compiles,
                20,  # max_dossiers_per_run
                None,  # get_db_connection_fn -> use default
                7,  # stale_days
            )
            if compiled > 0:
                logger.info(f"Entity dossier compile: {compiled} dossiers compiled")
        except Exception as e:
            logger.warning(f"Entity dossier compile failed: {e}")

    async def _execute_entity_position_tracker(self, task: Task):
        """Extract entity positions (stances, votes, policy) from articles; populate intelligence.entity_positions."""
        try:
            from config.context_centric_config import is_context_centric_task_enabled

            if not is_context_centric_task_enabled("entity_position_tracker"):
                return
        except Exception:
            pass
        from services.entity_position_tracker_service import run_position_tracker_batch

        try:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                self._executor,
                run_position_tracker_batch,
                None,  # domain_key -> all domains
                5,  # min_mentions
                8,  # max_entities
                25,  # max_articles_per_entity (v8)
            )
            total = sum(
                r.get("total_positions", 0) for r in (results or {}).values() if isinstance(r, dict)
            )
            if total > 0:
                logger.info("Entity position tracker: %s positions extracted", total)
        except Exception as e:
            logger.warning("Entity position tracker failed: %s", e)

    async def _execute_metadata_enrichment(self, task: Task):
        """Run metadata enrichment batch for domain articles (language, categories, sentiment, quality)."""
        try:
            from services.metadata_enrichment_service import (
                run_metadata_enrichment_batch_for_domains,
            )

            total = await run_metadata_enrichment_batch_for_domains(limit_per_domain=5)
            if total > 0:
                logger.info("Metadata enrichment: %d articles enriched", total)
        except Exception as e:
            logger.warning("Metadata enrichment failed: %s", e)

    async def _execute_story_enhancement(self, task: Task):
        """Phase 3 RAG: Run full enhancement cycle (triggers + entity enrichment + profile build)."""
        from services.enhancement_orchestrator_service import run_enhancement_cycle

        try:
            # Production: max 10 stories/run, 60s budget; 100 fact changes, 10 queue, 10 enrich, 10 build
            result = await run_enhancement_cycle(
                fact_batch=100, queue_batch=10, enrich_limit=10, build_limit=10
            )
            total = (
                result.get("fact_change_log_processed", 0)
                + result.get("story_update_queue_processed", 0)
                + result.get("entity_profiles_enriched", 0)
                + result.get("entity_profiles_built", 0)
            )
            if total > 0 or result.get("errors"):
                logger.info(
                    "Story enhancement cycle: fact_log=%s queue=%s enriched=%s built=%s",
                    result.get("fact_change_log_processed", 0),
                    result.get("story_update_queue_processed", 0),
                    result.get("entity_profiles_enriched", 0),
                    result.get("entity_profiles_built", 0),
                )
            if result.get("errors"):
                logger.warning("Story enhancement errors: %s", result["errors"])
        except Exception as e:
            logger.warning(f"Story enhancement failed: {e}")

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
                    int(os.environ.get("NIGHTLY_CLAIM_EXTRACTION_BATCH_LIMIT", "250")),
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
            metadata=nightly_meta,
        )
        await self._execute_task(task, "nightly_sequential_drain")
        return {"skipped": False}

    async def _execute_entity_enrichment(self, task: Task):
        """Phase 3 RAG: Run entity enrichment batch (Wikipedia -> entity_profiles + versioned_facts)."""
        from services.entity_enrichment_service import run_enrichment_batch

        try:
            # Production: max 20 entities per run (LLM limits); timeout 10s/entity; skip if queue >1000
            updated = run_enrichment_batch(limit=20)
            if updated > 0:
                logger.info(f"Entity enrichment: {updated} profiles enriched")
        except Exception as e:
            logger.warning(f"Entity enrichment failed: {e}")

    async def _execute_pattern_matching(self, task: Task):
        """Phase 4 RAG: Run watch pattern matching for all domains; record pattern_matches and create watchlist alerts."""
        from services.watch_pattern_service import run_pattern_matching_all_domains

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: run_pattern_matching_all_domains(limit_per_domain=30)
            )
            if result.get("matches_stored", 0) > 0:
                logger.info(
                    "Pattern matching: matches_stored=%s alerts_created=%s "
                    "skipped_no_storyline=%s skipped_not_on_watchlist=%s",
                    result.get("matches_stored", 0),
                    result.get("alerts_created", 0),
                    result.get("alerts_skipped_no_storyline", 0),
                    result.get("alerts_skipped_not_on_watchlist", 0),
                )
        except Exception as e:
            logger.warning("Pattern matching failed: %s", e)

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

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                lambda: run_cycle(domain_key=None, relationship_limit=100),
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
        try:
            from services.graph_connection_processor_service import (
                process_graph_connection_proposals_batch,
            )

            loop = asyncio.get_event_loop()
            stats = await loop.run_in_executor(
                self.executor,
                process_graph_connection_proposals_batch,
                None,
            )
            if stats and (
                stats.get("storyline_merged")
                or stats.get("storyline_links")
                or stats.get("entity_merged")
                or stats.get("entity_links")
                or stats.get("topic_links")
                or stats.get("hyperedge_links")
                or stats.get("rejected")
            ):
                logger.info("Graph connection distillation: %s", stats)
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
        """Discover patterns (network, temporal, behavioral, event) and persist to pattern_discoveries (Phase 2.2)."""
        try:
            from config.context_centric_config import is_context_centric_task_enabled

            if not is_context_centric_task_enabled("pattern_recognition"):
                return
        except Exception:
            pass
        import asyncio

        from services.pattern_recognition_service import run_pattern_discovery_batch

        try:
            total = await asyncio.get_event_loop().run_in_executor(
                None, run_pattern_discovery_batch
            )
            if total > 0:
                logger.info(f"Pattern recognition: {total} patterns discovered")
        except Exception as e:
            logger.warning(f"Pattern recognition failed: {e}")

    async def _execute_editorial_document_generation(self, task: Task):
        """Generate/refine editorial_document for active storylines across all domains."""
        from services.editorial_document_service import generate_storyline_editorial

        for domain in get_pipeline_active_domain_keys():
            try:
                result = await generate_storyline_editorial(domain, limit=5)
                logger.info("Editorial doc generation (%s): %s", domain, result)
            except Exception as e:
                logger.warning("editorial_document_generation (%s): %s", domain, e)

    async def _execute_editorial_briefing_generation(self, task: Task):
        """Global narrative + domain lenses first, then legacy briefing for events without a spine."""
        from services.editorial_document_service import generate_event_editorial
        from services.tracked_event_narrative_service import run_tracked_event_narrative_stack

        try:
            stack = await run_tracked_event_narrative_stack(limit=5)
            logger.info("Tracked event narrative stack: %s", stack)
        except Exception as e:
            logger.warning("tracked_event_narrative_stack: %s", e)
        try:
            result = await generate_event_editorial(limit=5)
            logger.info("Editorial briefing generation: %s", result)
        except Exception as e:
            logger.warning("editorial_briefing_generation: %s", e)

    async def _execute_narrative_thread_build(self, task: Task):
        """Build narrative threads from storylines across all domains, then synthesize."""
        import asyncio

        from services.narrative_thread_service import build_threads_for_domain

        loop = asyncio.get_event_loop()
        for domain in get_pipeline_active_domain_keys():
            try:
                result = await loop.run_in_executor(
                    None, lambda d=domain: build_threads_for_domain(d, limit=30)
                )
                built = result.get("built", 0)
                if built > 0:
                    logger.info("Narrative thread build (%s): %s threads", domain, built)
            except Exception as e:
                logger.warning("narrative_thread_build (%s): %s", domain, e)

    async def _execute_digest_generation(self, task: Task):
        """Execute digest generation task"""
        from services.digest_automation_service import get_digest_service

        digest_service = get_digest_service()
        await digest_service.generate_digest_if_needed()

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
                self._last_completed_at_by_phase["health_check"] = finished_at
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
        """Execute RAG enhancement per domain (v8): enhance storylines with Wikipedia/GDELT context, store by (domain, storyline_id)."""
        from shared.database.connection import get_db_connection

        from services.rag import get_rag_service

        rag_service = get_rag_service()
        enhanced_count = 0
        for domain in get_pipeline_active_domain_keys():
            schema = resolve_domain_schema(domain)
            try:
                conn = get_db_connection()
                if not conn:
                    continue
                try:
                    with conn.cursor() as cur:
                        cur.execute(f"""
                            SELECT s.id, s.title, s.rag_enhanced_at,
                                   COALESCE(array_agg(sa.article_id) FILTER (WHERE sa.article_id IS NOT NULL), '{{}}') AS article_ids
                            FROM {schema}.storylines s
                            LEFT JOIN {schema}.storyline_articles sa ON sa.storyline_id = s.id
                            WHERE s.status = 'active'
                            GROUP BY s.id, s.title, s.rag_enhanced_at
                            HAVING COUNT(sa.article_id) > 0
                        """)
                        rows = cur.fetchall()
                finally:
                    conn.close()

                for row in rows:
                    sid, title, rag_enhanced_at, article_ids = row[0], row[1], row[2], row[3] or []
                    try:
                        if rag_enhanced_at:
                            elapsed = (datetime.now(timezone.utc) - rag_enhanced_at).total_seconds()
                            if elapsed < 3600:
                                continue
                        # Fetch article summaries for context
                        articles_for_rag = []
                        if article_ids:
                            conn = get_db_connection()
                            if conn:
                                try:
                                    with conn.cursor() as cur:
                                        cur.execute(
                                            f"""
                                            SELECT id, title, content, summary, source_domain
                                            FROM {schema}.articles WHERE id = ANY(%s)
                                        """,
                                            (list(article_ids)[:30],),
                                        )
                                        for r in cur.fetchall():
                                            articles_for_rag.append(
                                                {
                                                    "id": r[0],
                                                    "title": r[1],
                                                    "content": r[2] or "",
                                                    "summary": r[3],
                                                    "source": r[4],
                                                }
                                            )
                                finally:
                                    conn.close()
                        await rag_service.enhance_storyline_context(
                            storyline_id=str(sid),
                            storyline_title=title or "",
                            articles=articles_for_rag,
                            domain=domain,
                        )
                        enhanced_count += 1
                    except Exception as e:
                        logger.debug("RAG enhance %s storyline %s: %s", domain, sid, e)
            except Exception as e:
                logger.warning("RAG enhancement domain %s: %s", domain, e)
        logger.info(
            "RAG enhancement completed: %s storylines enhanced (all domains)", enhanced_count
        )

    async def _execute_ml_processing(self, task: Task):
        """Execute ML processing task. Skips cleanly if column ml_processed is missing."""
        try:
            from modules.ml.background_processor import BackgroundMLProcessor

            ml_processor = BackgroundMLProcessor(self.db_config)

            processed_count = 0
            ml_ready = sql_ml_ready_and_content_bounds()
            _ord = sql_order_created_at()
            for schema in get_pipeline_schema_names_active():
                conn = await self._get_db_connection()
                try:
                    with conn.cursor() as cursor:
                        cursor.execute(f"""
                            SELECT id FROM {schema}.articles
                            WHERE ml_processed = FALSE
                              AND ({ml_ready})
                            ORDER BY created_at {_ord}
                            LIMIT 50
                        """)
                        articles = cursor.fetchall()
                finally:
                    conn.close()

                for (article_id,) in articles:
                    try:
                        ml_processor.queue_article_for_processing(
                            article_id, "full_analysis", schema_name=schema
                        )
                        processed_count += 1
                    except Exception as e:
                        logger.error("Error processing article %s (%s): %s", article_id, schema, e)

            logger.info(f"ML processing completed: {processed_count} articles queued")
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
            max_failures = int(os.environ.get(env_key, str(default_max_attempts)))
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
        """Execute sentiment analysis task"""
        from services.ai_processing_service import get_ai_service
        from shared.pipeline_pass_marker import phase_backlog_uses_pass_marker, record_article_phase_pass, sql_article_pass_null

        ai_service = get_ai_service()
        analyzed_count = 0

        ml_ready = sql_ml_ready_and_content_bounds()
        pass_clause = ""
        if phase_backlog_uses_pass_marker("sentiment_analysis"):
            pass_clause = f" AND ({sql_article_pass_null('sentiment_analysis', 'a')}) "
        _ord = sql_order_created_at()
        for schema in get_pipeline_schema_names_active():
            # Fetch candidates quickly, then close transaction before awaited LLM work.
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
                        LIMIT 100
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

                    # Persist each result in a short-lived transaction.
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

        logger.info(f"Sentiment analysis completed: {analyzed_count} articles analyzed")

    async def _execute_storyline_processing(self, task: Task):
        """Execute storyline processing per domain: generates analysis_summary, seeds editorial_document.
        Uses domain-aware StorylineService so politics/finance/science_tech storylines get narratives."""
        from domains.storyline_management.services.storyline_service import (
            StorylineService as DomainStorylineService,
        )
        from shared.database.connection import get_db_connection

        processed_count = 0
        for domain, schema in pipeline_url_schema_pairs():
            try:
                conn = get_db_connection()
                if not conn:
                    continue
                try:
                    with conn.cursor() as cur:
                        cur.execute(f"""
                            SELECT s.id, s.title,
                                   COALESCE(s.analysis_summary, '') AS analysis_summary,
                                   COALESCE(s.master_summary, '') AS master_summary,
                                   (s.editorial_document IS NOT NULL AND s.editorial_document != '{{}}'::jsonb) AS has_ed
                            FROM {schema}.storylines s
                            WHERE s.status = 'active'
                              AND EXISTS (
                                  SELECT 1 FROM {schema}.storyline_articles sa WHERE sa.storyline_id = s.id
                              )
                        """)
                        rows = cur.fetchall()
                finally:
                    conn.close()

                svc = DomainStorylineService(domain=domain)
                for row in rows:
                    sid, _title, analysis_summary, master_summary, has_ed = (
                        row[0],
                        row[1],
                        row[2] or "",
                        row[3] or "",
                        row[4],
                    )
                    summary_for_check = analysis_summary or master_summary
                    if len(summary_for_check) < 100:
                        try:
                            result = await svc.generate_storyline_summary(sid)
                            if not result.get("success"):
                                continue
                            summary_text = (result.get("data") or {}).get("summary", "")
                            if summary_text:
                                processed_count += 1
                                if not has_ed:
                                    try:
                                        conn = get_db_connection()
                                        if conn:
                                            try:
                                                with conn.cursor() as cur:
                                                    cur.execute(
                                                        f"""
                                                        UPDATE {schema}.storylines
                                                        SET editorial_document = jsonb_build_object(
                                                                'lede', LEFT(%s, 300),
                                                                'developments', '[]'::jsonb,
                                                                'analysis', %s,
                                                                'outlook', '',
                                                                'generated_at', NOW()::text
                                                            ),
                                                            document_version = COALESCE(document_version, 0) + 1,
                                                            document_status = 'auto_seeded',
                                                            updated_at = NOW()
                                                        WHERE id = %s AND (editorial_document IS NULL OR editorial_document = '{{}}'::jsonb)
                                                    """,
                                                        (summary_text, summary_text, sid),
                                                    )
                                                conn.commit()
                                            finally:
                                                conn.close()
                                    except Exception as ed_err:
                                        logger.debug(
                                            "Seed editorial_document %s/%s: %s", domain, sid, ed_err
                                        )
                        except Exception as e:
                            logger.error("Error processing storyline %s/%s: %s", domain, sid, e)
            except Exception as e:
                logger.warning("Storyline processing domain %s: %s", domain, e)

        logger.info(
            "Storyline processing completed: %s storylines processed (all domains)", processed_count
        )

    async def _execute_storyline_automation(self, task: Task):
        """Run RAG discovery for one storyline (from metadata) or all automation-enabled storylines."""
        from services.storyline_automation_service import StorylineAutomationService

        meta = task.metadata or {}
        storyline_id = meta.get("storyline_id")
        domain = meta.get("domain")
        if storyline_id and domain:
            try:
                svc = StorylineAutomationService(domain=domain)
                result = await svc.discover_articles_for_storyline(
                    storyline_id, force_refresh=False
                )
                count = len(result.get("articles", []))
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
            for d in get_pipeline_active_domain_keys():
                try:
                    svc = StorylineAutomationService(domain=d)
                    conn = await self._get_db_connection()
                    schema = resolve_domain_schema(d)
                    try:
                        with conn.cursor() as cur:
                            cur.execute(f"""
                                SELECT id FROM {schema}.storylines
                                WHERE automation_enabled = true
                                ORDER BY last_automation_run ASC NULLS FIRST
                                LIMIT 5
                            """)
                            storyline_rows = cur.fetchall()
                    finally:
                        conn.close()
                    for row in storyline_rows:
                        await svc.discover_articles_for_storyline(row[0], force_refresh=False)
                except Exception as e:
                    logger.debug("Storyline automation batch %s: %s", d, e)
            logger.info("Storyline automation: batch run across domains completed")

    async def _execute_storyline_enrichment(self, task: Task):
        """v8: Enrich existing storylines with full-history RAG (past articles/contexts from entire DB)."""
        from services.storyline_automation_service import StorylineAutomationService

        meta = task.metadata or {}
        storyline_id = meta.get("storyline_id")
        domain = meta.get("domain")
        if storyline_id and domain:
            try:
                svc = StorylineAutomationService(domain=domain)
                result = await svc.discover_articles_for_storyline(
                    storyline_id, force_refresh=True, enrichment_mode=True
                )
                count = len(result.get("articles", []))
                logger.info(
                    "Storyline enrichment: storyline_id=%s domain=%s discovered %s articles (full history)",
                    storyline_id,
                    domain,
                    count,
                )
            except Exception as e:
                logger.warning(
                    "Storyline enrichment failed for storyline_id=%s: %s", storyline_id, e
                )
        else:
            for d in get_pipeline_active_domain_keys():
                try:
                    svc = StorylineAutomationService(domain=d)
                    conn = await self._get_db_connection()
                    schema = resolve_domain_schema(d)
                    try:
                        with conn.cursor() as cur:
                            cur.execute(f"""
                                SELECT s.id FROM {schema}.storylines s
                                WHERE s.automation_enabled = true
                                AND EXISTS (SELECT 1 FROM {schema}.storyline_articles sa WHERE sa.storyline_id = s.id)
                                ORDER BY s.last_automation_run ASC NULLS FIRST
                                LIMIT 3
                            """)
                            storyline_rows = cur.fetchall()
                    finally:
                        conn.close()
                    for row in storyline_rows:
                        await svc.discover_articles_for_storyline(
                            row[0], force_refresh=True, enrichment_mode=True
                        )
                except Exception as e:
                    logger.debug("Storyline enrichment batch %s: %s", d, e)
            logger.info("Storyline enrichment: full-history batch run across domains completed")

    async def _execute_storyline_discovery(self, task: Task):
        """Auto-discover storylines from recent article clusters using AI similarity.
        Runs AIStorylineDiscovery.discover_storylines() for each domain (full backlog,
        newest-first cap), creating new storylines from high-similarity clusters."""
        import asyncio

        try:
            from services.ai_storyline_discovery import get_discovery_service

            service = get_discovery_service()
            total_created = 0
            for domain in get_pipeline_active_domain_keys():
                try:
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        None,
                        lambda d=domain: service.discover_storylines(
                            domain=d, hours=None, save_to_db=True
                        ),
                    )
                    saved = len(result.get("saved_storylines", []))
                    clusters = result.get("summary", {}).get("clusters_found", 0)
                    total_created += saved
                    if saved > 0:
                        logger.info(
                            "Storyline discovery [%s]: %d clusters → %d new storylines",
                            domain,
                            clusters,
                            saved,
                        )
                except Exception as e:
                    logger.warning("Storyline discovery failed for %s: %s", domain, e)
            logger.info("Storyline discovery complete: %d new storylines created", total_created)
        except Exception as e:
            logger.warning("Storyline discovery task failed: %s", e)

    async def _execute_proactive_detection(self, task: Task):
        """v8: Detect emerging storylines from unlinked articles (per domain)."""
        try:
            from domains.storyline_management.services.proactive_detection_service import (
                ProactiveDetectionService,
            )

            for domain in get_pipeline_active_domain_keys():
                try:
                    svc = ProactiveDetectionService(domain=domain)
                    result = await svc.detect_emerging_storylines(hours=72, min_articles=3)
                    if result.get("success"):
                        d = result.get("data") or {}
                        if (
                            d.get("stored_count", 0) > 0
                            or d.get("promoted_to_domain_storylines", 0) > 0
                        ):
                            logger.info(
                                "Proactive detection [%s]: emerging_stored=%s promoted_to_domain_storylines=%s",
                                domain,
                                d.get("stored_count", 0),
                                d.get("promoted_to_domain_storylines", 0),
                            )
                except Exception as e:
                    logger.debug("Proactive detection failed for %s: %s", domain, e)
        except Exception as e:
            logger.warning("Proactive detection task failed: %s", e)

    async def _execute_fact_verification(self, task: Task):
        """v8: Verify recent claims per domain (governance-weighted corroboration, Wikipedia + internal checks; results returned to logs/API, not persisted on claim rows)."""
        try:
            from services.fact_verification_service import verify_recent_claims

            loop = asyncio.get_event_loop()
            for domain in get_pipeline_active_domain_keys():
                try:
                    result = await loop.run_in_executor(
                        self._executor,
                        lambda d=domain: verify_recent_claims(d, hours=72, limit=20),
                    )
                    if result.get("success") and result.get("claims_verified", 0) > 0:
                        logger.info(
                            "Fact verification [%s]: %s claims verified",
                            domain,
                            result["claims_verified"],
                        )
                except Exception as e:
                    logger.debug("Fact verification failed for %s: %s", domain, e)
        except Exception as e:
            logger.warning("Fact verification task failed: %s", e)

    async def _execute_entity_extraction(self, task: Task):
        """Execute entity extraction via ArticleEntityExtractionService.

        Routes through the canonical extraction pipeline which does:
        LLM extraction → canonical resolution → Wikipedia backfill → article_entities storage.
        Processes all active domain schemas (registry).
        """
        from services.article_entity_extraction_service import ArticleEntityExtractionService

        extractor = ArticleEntityExtractionService()
        domains = list(pipeline_url_schema_pairs())
        extracted_count = 0

        try:
            articles_per_domain = int(os.environ.get("ENTITY_EXTRACTION_ARTICLES_PER_DOMAIN", "20"))
        except ValueError:
            articles_per_domain = 20
        articles_per_domain = max(5, min(120, articles_per_domain))

        from shared.pipeline_pass_marker import phase_backlog_uses_pass_marker, sql_article_pass_null

        pass_clause = ""
        if phase_backlog_uses_pass_marker("entity_extraction"):
            pass_clause = f" AND ({sql_article_pass_null('entity_extraction', 'a')}) "
        _ord = sql_order_created_at()

        conn = await self._get_db_connection()
        try:
            cursor = conn.cursor()
            domain_articles = {}
            for domain_key, schema_name in domains:
                try:
                    cursor.execute(f"""
                        SELECT a.id, a.title, a.content
                        FROM {schema_name}.articles a
                        LEFT JOIN {schema_name}.article_entities ae ON ae.article_id = a.id
                        WHERE ae.id IS NULL
                          AND COALESCE((a.metadata #>> '{{pipeline_skip,entity_extraction_skip}}')::boolean, false) = false
                          AND a.content IS NOT NULL
                          AND LENGTH(a.content) > 100
                          AND (
                            LENGTH(a.content) >= 500
                            OR a.created_at < NOW() - INTERVAL '2 hours'
                            OR COALESCE(a.enrichment_status, '') IN (
                                'enriched', 'failed', 'inaccessible'
                            )
                          )
                          {pass_clause}
                        ORDER BY a.created_at {_ord}
                        LIMIT {articles_per_domain}
                    """)
                    domain_articles[schema_name] = cursor.fetchall()
                except Exception as e:
                    logger.warning("Entity extraction query for %s: %s", schema_name, e)
                    domain_articles[schema_name] = []
        finally:
            cursor.close()
            conn.close()

        try:
            parallel = max(1, min(16, int(os.environ.get("ENTITY_EXTRACTION_PARALLEL", "4"))))
        except ValueError:
            parallel = 4
        sem = asyncio.Semaphore(parallel)

        async def _extract_one(
            domain_key: str, schema_name: str, article_id: int, title: str, content: str
        ) -> bool:
            async with sem:
                try:
                    result = await extractor.extract_and_store(
                        article_id=article_id,
                        title=title or "",
                        content=content,
                        schema=schema_name,
                    )
                    ok = bool(result.get("success"))
                    if ok:
                        from shared.pipeline_pass_marker import record_article_phase_pass

                        cnt = (result.get("counts") or {}).get("entities") or 0
                        record_article_phase_pass(
                            schema_name,
                            article_id,
                            "entity_extraction",
                            "entities_stored" if int(cnt) > 0 else "no_entities_stored",
                        )
                    return ok
                except Exception as e:
                    logger.error(
                        "Entity extraction for article %s (%s): %s", article_id, domain_key, e
                    )
                    await self._mark_article_phase_failure(
                        schema=schema_name,
                        article_id=article_id,
                        phase_name="entity_extraction",
                        error=e,
                        default_max_attempts=3,
                    )
                    return False

        tasks = []
        for domain_key, schema_name in domains:
            for article_id, title, content in domain_articles.get(schema_name, []):
                tasks.append(_extract_one(domain_key, schema_name, article_id, title, content))
        if tasks:
            results = await asyncio.gather(*tasks)
            extracted_count = sum(1 for r in results if r)

        logger.info(
            f"Entity extraction completed: {extracted_count} articles processed across domains"
        )

        if extracted_count > 0 and os.environ.get("ENTITY_EXTRACTION_POST_SYNC", "").lower() in (
            "1",
            "true",
            "yes",
        ):
            try:
                post_lim = int(os.environ.get("ENTITY_EXTRACTION_POST_MENTION_LIMIT", "1500"))
            except ValueError:
                post_lim = 1500
            from services.context_processor_service import backfill_context_entity_mentions_for_domain
            from services.entity_profile_sync_service import sync_domain_entity_profiles

            for domain_key, _schema_name in domains:
                try:
                    sync_domain_entity_profiles(domain_key)
                except Exception as e:
                    logger.debug("entity_extraction post-sync profiles %s: %s", domain_key, e)
                try:
                    backfill_context_entity_mentions_for_domain(domain_key, limit=max(50, post_lim))
                except Exception as e:
                    logger.debug("entity_extraction post-sync mentions %s: %s", domain_key, e)

    async def _execute_event_extraction_v5(self, task: Task):
        """v5.0 -- Extract structured events with temporal grounding from domain articles."""
        try:
            from services.event_extraction_service import EventExtractionService
            from shared.database.connection import get_db_connection

            svc = EventExtractionService()
            loop = asyncio.get_event_loop()
            try:
                try:
                    parallel = max(1, int(os.environ.get("EVENT_EXTRACTION_PARALLEL", "4")))
                except ValueError:
                    parallel = 4
                sem = asyncio.Semaphore(parallel)
                total_events = 0
                total_articles = 0

                async def _process_article(
                    schema: str, domain_for_events: str, row: tuple
                ) -> int:
                    article_id, content, pub_date, storyline_id = row
                    async with sem:
                        try:
                            if pub_date is None:
                                pub_date = datetime.now(timezone.utc)
                            events = await svc.extract_events_from_article(
                                article_id=article_id,
                                content=content,
                                pub_date=pub_date,
                                storyline_id=storyline_id,
                                domain=domain_for_events,
                            )
                            conn_a = await loop.run_in_executor(None, get_db_connection)
                            if not conn_a:
                                return 0
                            try:
                                saved = await svc.save_events(events, conn_a)
                                cur = conn_a.cursor()
                                cur.execute(
                                    f"""
                                    UPDATE {schema}.articles
                                    SET timeline_processed = true,
                                        timeline_events_generated = %s,
                                        updated_at = CURRENT_TIMESTAMP
                                    WHERE id = %s
                                """,
                                    (len(events), article_id),
                                )
                                conn_a.commit()
                                try:
                                    from shared.pipeline_pass_marker import record_article_phase_pass

                                    record_article_phase_pass(
                                        schema,
                                        article_id,
                                        "event_extraction",
                                        "timeline_saved",
                                    )
                                except Exception:
                                    pass
                                cur.close()
                                return saved
                            except Exception:
                                try:
                                    conn_a.rollback()
                                except Exception:
                                    pass
                                raise
                            finally:
                                conn_a.close()
                        except Exception as e:
                            logger.error(
                                "Event extraction failed for %s article %s: %s",
                                schema,
                                article_id,
                                e,
                            )
                            await self._mark_article_phase_failure(
                                schema=schema,
                                article_id=article_id,
                                phase_name="event_extraction",
                                error=e,
                                default_max_attempts=2,
                            )
                            return 0

                for schema in get_pipeline_schema_names_active():
                    try:
                        domain_for_events = schema_to_primary_domain_key(schema)
                    except KeyError:
                        domain_for_events = schema.replace("_", "-")
                    from shared.pipeline_pass_marker import phase_backlog_uses_pass_marker, sql_article_pass_null

                    ev_pass = ""
                    if phase_backlog_uses_pass_marker("event_extraction"):
                        ev_pass = f" AND ({sql_article_pass_null('event_extraction', 'a')}) "
                    _ev_ord = sql_order_coalesce_pub_created("a")

                    conn = await self._get_db_connection()
                    cursor = conn.cursor()
                    try:
                        cursor.execute(f"""
                            SELECT a.id, a.content, a.published_at,
                                   (
                                       SELECT sa.storyline_id::text
                                       FROM {schema}.storyline_articles sa
                                       WHERE sa.article_id = a.id
                                       ORDER BY sa.added_at DESC NULLS LAST
                                       LIMIT 1
                                   ) AS storyline_id
                            FROM {schema}.articles a
                            WHERE a.timeline_processed = false
                              AND COALESCE((a.metadata #>> '{{pipeline_skip,event_extraction_skip}}')::boolean, false) = false
                              AND a.content IS NOT NULL
                              AND LENGTH(a.content) > 100
                              AND (
                                  a.processing_status = 'completed'
                                  OR a.enrichment_status IN ('completed', 'enriched')
                              )
                              {ev_pass}
                            ORDER BY {_ev_ord}
                            LIMIT 30
                        """)
                        articles = cursor.fetchall()
                    finally:
                        cursor.close()
                        conn.close()

                    total_articles += len(articles)
                    if not articles:
                        continue
                    results = await asyncio.gather(
                        *[
                            _process_article(schema, domain_for_events, row)
                            for row in articles
                        ],
                        return_exceptions=True,
                    )
                    for r in results:
                        if isinstance(r, int):
                            total_events += r
                        elif isinstance(r, Exception):
                            logger.debug("event_extraction gather: %s", r)

                logger.info(
                    "v5 event extraction completed: %s events from %s articles across %s schemas",
                    total_events,
                    total_articles,
                    len(get_pipeline_schema_names_active()),
                )
            finally:
                await svc.close()
        except Exception as e:
            if (
                "timeline_processed" in str(e) or "chronological_events" in str(e)
            ) and "does not exist" in str(e):
                logger.debug("Event extraction skipped (schema not migrated): %s", e)
            else:
                raise

    async def _execute_event_deduplication_v5(self, task: Task):
        """v5.0 -- Deduplicate events across sources. Skips cleanly if chronological_events is missing."""
        try:
            from services.event_deduplication_service import EventDeduplicationService

            conn = await self._get_db_connection()
            try:
                svc = EventDeduplicationService(conn)
                stats = await svc.deduplicate_recent(limit=100)
                logger.info(
                    f"v5 event deduplication completed: "
                    f"checked={stats['checked']}, merged={stats['merged']}"
                )
            finally:
                conn.close()
        except Exception as e:
            if "chronological_events" in str(e) and "does not exist" in str(e):
                logger.debug(
                    "Event deduplication skipped (chronological_events not migrated): %s", e
                )
            else:
                raise

    async def _execute_story_continuation_v5(self, task: Task):
        """v5.0 -- Match events to existing storylines and manage lifecycle states. Runs per domain (storylines/story_entity_index are per-schema)."""
        from services.story_continuation_service import StoryContinuationService

        conn = await self._get_db_connection()
        if not conn:
            logger.warning("Story continuation: no DB connection")
            return
        try:
            total = {"checked": 0, "linked": 0, "flagged": 0}
            for schema in get_pipeline_schema_names_active():
                try:
                    svc = StoryContinuationService(conn, schema=schema)
                    stats = await svc.process_recent_events(limit=30)
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
        from services.ai_processing_service import get_ai_service

        ai_service = get_ai_service()
        scored_count = 0

        ml_ready = sql_ml_ready_and_content_bounds()
        _ord = sql_order_created_at()
        for schema in get_pipeline_schema_names_active():
            # Fetch candidates quickly, then close transaction before awaited LLM work.
            conn = await self._get_db_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute(f"""
                        SELECT id, content, title FROM {schema}.articles
                        WHERE quality_score IS NULL
                          AND COALESCE((metadata #>> '{{pipeline_skip,quality_scoring_skip}}')::boolean, false) = false
                          AND ({ml_ready})
                        ORDER BY created_at {_ord}
                        LIMIT 50
                    """)
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
        """Execute timeline generation per domain using public chronological_events + domain storylines."""
        from services.timeline_builder_service import TimelineBuilderService

        generated_count = 0

        for schema in get_pipeline_schema_names_active():
            conn_sel = await self._get_db_connection()
            storyline_ids: list[int] = []
            try:
                with conn_sel.cursor() as cur:
                    cur.execute(f"""
                        SELECT s.id FROM {schema}.storylines s
                        WHERE s.status = 'active'
                          AND EXISTS (
                              SELECT 1 FROM {schema}.storyline_articles sa
                              WHERE sa.storyline_id = s.id
                          )
                          AND (
                              s.timeline_summary IS NULL
                              OR LENGTH(COALESCE(s.timeline_summary, '')) < 100
                          )
                        ORDER BY s.updated_at DESC NULLS LAST
                        LIMIT 12
                    """)
                    storyline_ids = [row[0] for row in cur.fetchall() if row and row[0] is not None]
            finally:
                conn_sel.close()

            for sid in storyline_ids:
                conn = await self._get_db_connection()
                try:
                    tb = TimelineBuilderService(conn, schema_name=schema)
                    timeline = tb.build_timeline(sid)
                    events = timeline.get("events") or []
                    if not events:
                        continue
                    parts = []
                    for e in events[:25]:
                        title = (e.get("title") or "").strip()
                        d = e.get("event_date")
                        ds = d.isoformat() if hasattr(d, "isoformat") else (str(d) if d else "")
                        if title:
                            parts.append(f"{ds}: {title}" if ds else title)
                    summary = f"Timeline ({len(events)} events): " + " | ".join(parts[:12])
                    if len(summary) > 12000:
                        summary = summary[:11997] + "..."
                    with conn.cursor() as cur:
                        cur.execute(
                            f"""
                            UPDATE {schema}.storylines
                            SET timeline_summary = %s
                            WHERE id = %s
                        """,
                            (summary, sid),
                        )
                        conn.commit()
                    generated_count += 1
                except Exception as e:
                    logger.error(
                        "Timeline generation failed for storyline %s (%s): %s",
                        sid,
                        schema,
                        e,
                    )
                finally:
                    conn.close()

        logger.info(
            "Timeline generation completed: %s timeline summaries updated (all domains)",
            generated_count,
        )

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
        """Execute topic clustering task - continuous iterative refinement with confidence-based stopping"""
        try:
            logger.info(
                "🔄 Starting iterative topic clustering task with confidence-based prioritization (v5.0 - all domains)"
            )

            # Import the topic clustering service
            from domains.content_analysis.services.topic_clustering_service import (
                TopicClusteringService,
            )
            from shared.domain_registry import first_active_domain_key, resolve_domain_schema
            from shared.services.domain_aware_service import get_all_domains

            # Get all active domains
            domains = get_all_domains()
            if not domains:
                fb = first_active_domain_key()
                logger.warning("No active domains found, defaulting to %s", fb)
                domains = [{"domain_key": fb, "schema_name": resolve_domain_schema(fb)}]

            # Topic clustering configuration constants
            try:
                from config.settings import (
                    topic_clustering_backlog_uses_pass_marker,
                    topic_clustering_graduation_confidence,
                    topic_clustering_iterative_refinement_enabled,
                )

                CONFIDENCE_THRESHOLD = float(topic_clustering_graduation_confidence())
                TC_USE_PASS_MARKER = topic_clustering_backlog_uses_pass_marker()
                TC_ITERATIVE = topic_clustering_iterative_refinement_enabled()
            except Exception:
                CONFIDENCE_THRESHOLD = 0.88
                TC_USE_PASS_MARKER = True
                TC_ITERATIVE = False
            LOW_CONFIDENCE_THRESHOLD = 0.7
            BATCH_SIZE = 20
            NEW_ARTICLE_COUNT = 8  # 40% of batch size
            LOW_CONFIDENCE_COUNT = 6  # 30% of batch size
            MEDIUM_CONFIDENCE_COUNT = 6  # 30% of batch size

            from shared.database.connection import get_db_config

            db_config = get_db_config()
            total_processed = 0
            total_graduated = 0

            # Process each domain
            for domain_info in domains:
                domain_key = domain_info["domain_key"]
                schema_name = domain_info.get("schema_name", domain_key.replace("-", "_"))

                logger.info(f"📊 Processing domain: {domain_key} (schema: {schema_name})")

                # Initialize topic clustering service for this domain
                topic_service = TopicClusteringService(db_config, domain=domain_key)

                if TC_USE_PASS_MARKER and not TC_ITERATIVE:
                    tc_where = """(pass_at IS NULL OR TRIM(COALESCE(pass_at, '')) = '')"""
                else:
                    tc_where = """priority_group != 'high_confidence'"""

                # Process articles incrementally with balanced prioritization
                conn = await self._get_db_connection()
                try:
                    cursor = conn.cursor()
                    try:
                        tc_age_order = sql_order_created_at()
                        cursor.execute(
                            f"""
                            WITH article_confidence AS (
                                SELECT
                                    a.id,
                                    a.title,
                                    a.created_at,
                                    COUNT(ata.id) as assignment_count,
                                    COALESCE(AVG(ata.confidence_score), 0.0) as avg_confidence,
                                    COALESCE(MIN(ata.confidence_score), 0.0) as min_confidence,
                                    COALESCE(MAX(ata.confidence_score), 0.0) as max_confidence,
                                    (a.metadata->'pipeline'->'topic_clustering'->>'last_pass_at') AS pass_at,
                                    CASE
                                        WHEN COUNT(ata.id) = 0 THEN 'new'
                                        WHEN COALESCE(AVG(ata.confidence_score), 0.0) < %s THEN 'low_confidence'
                                        WHEN COALESCE(AVG(ata.confidence_score), 0.0) < %s THEN 'medium_confidence'
                                        ELSE 'high_confidence'
                                    END as priority_group
                                FROM {schema_name}.articles a
                                LEFT JOIN {schema_name}.article_topic_assignments ata ON a.id = ata.article_id
                                WHERE a.content IS NOT NULL
                                AND LENGTH(a.content) > 100
                                GROUP BY a.id, a.title, a.created_at,
                                    (a.metadata->'pipeline'->'topic_clustering'->>'last_pass_at')
                            )
                            SELECT
                                id,
                                title,
                                assignment_count,
                                avg_confidence,
                                min_confidence,
                                max_confidence,
                                priority_group,
                                pass_at,
                                created_at
                            FROM article_confidence
                            WHERE {tc_where}
                            ORDER BY
                                CASE priority_group
                                    WHEN 'new' THEN 1
                                    WHEN 'low_confidence' THEN 2
                                    WHEN 'medium_confidence' THEN 3
                                END,
                                avg_confidence ASC,  -- Lower confidence first within each group
                                created_at {tc_age_order}
                        """,
                            (LOW_CONFIDENCE_THRESHOLD, CONFIDENCE_THRESHOLD),
                        )
                        all_articles = cursor.fetchall()
                    finally:
                        cursor.close()
                finally:
                    conn.close()

                if not all_articles:
                    logger.info(
                        f"  ✅ No articles need topic clustering in {domain_key} (all above confidence threshold)"
                    )
                    continue

                # Balanced prioritization: Mix of new, low, and medium confidence articles
                # This ensures we process new articles while refining existing ones
                new_articles = [a for a in all_articles if a[6] == "new"]
                low_confidence = [a for a in all_articles if a[6] == "low_confidence"]
                medium_confidence = [a for a in all_articles if a[6] == "medium_confidence"]

                # Calculate balanced selection (40% new, 30% low, 30% medium)
                # This mix ensures:
                # - New articles get started (40%)
                # - Low confidence articles get refined (30%)
                # - Medium confidence articles graduate out (30%)
                target_count = BATCH_SIZE
                new_count = min(NEW_ARTICLE_COUNT, len(new_articles))  # 40% = 8 articles
                low_count = min(LOW_CONFIDENCE_COUNT, len(low_confidence))  # 30% = 6 articles
                medium_count = min(
                    MEDIUM_CONFIDENCE_COUNT, len(medium_confidence)
                )  # 30% = 6 articles

                # Select articles from each group
                selected_articles = []
                selected_articles.extend(new_articles[:new_count])
                selected_articles.extend(low_confidence[:low_count])
                selected_articles.extend(medium_confidence[:medium_count])

                # If we don't have enough, fill from remaining groups
                # Priority: new > low > medium (to prevent backlog)
                remaining = target_count - len(selected_articles)
                if remaining > 0:
                    # Prioritize new articles first (to prevent backlog)
                    if len(new_articles) > new_count:
                        remaining_new = new_articles[new_count : new_count + remaining]
                        selected_articles.extend(remaining_new)
                        remaining -= len(remaining_new)

                    # Then low confidence articles
                    if remaining > 0 and len(low_confidence) > low_count:
                        remaining_low = low_confidence[low_count : low_count + remaining]
                        selected_articles.extend(remaining_low)
                        remaining -= len(remaining_low)

                    # Finally medium confidence articles
                    if remaining > 0 and len(medium_confidence) > medium_count:
                        remaining_medium = medium_confidence[
                            medium_count : medium_count + remaining
                        ]
                        selected_articles.extend(remaining_medium)

                article_ids = [a[0] for a in selected_articles]

                if not article_ids:
                    logger.info(f"  ✅ No articles selected for processing in {domain_key}")
                    continue

                logger.info(
                    f"  📊 Balanced selection: {len(new_articles[:new_count])} new, "
                    f"{len(low_confidence[:low_count])} low confidence, "
                    f"{len(medium_confidence[:medium_count])} medium confidence "
                    f"({len(article_ids)} total)"
                )

                processed_count = 0
                graduated_count = 0
                topics_created = 0
                topics_assigned = 0

                # Process articles one by one for iterative refinement
                for article_data in selected_articles:
                    article_id = article_data[0]
                    current_avg_confidence = float(article_data[3]) if article_data[3] else 0.0
                    article_data[6]

                    try:
                        # Skip if already above threshold (safety check)
                        if current_avg_confidence >= CONFIDENCE_THRESHOLD:
                            logger.debug(
                                f"  Article {article_id} already above threshold ({current_avg_confidence:.2f}), skipping"
                            )
                            continue

                        result = await topic_service.process_article(article_id)

                        if result.get("success"):
                            processed_count += 1
                            topics_created += len(result.get("created_topics", []))
                            topics_assigned += result.get("total_assigned", 0)

                            # Check if article graduated (above threshold)
                            # Re-check confidence after processing
                            conn_check = await self._get_db_connection()
                            cursor_check = conn_check.cursor()
                            cursor_check.execute(
                                f"""
                                SELECT COALESCE(AVG(confidence_score), 0.0) as avg_confidence
                                FROM {schema_name}.article_topic_assignments
                                WHERE article_id = %s
                            """,
                                (article_id,),
                            )
                            result_row = cursor_check.fetchone()
                            new_confidence = (
                                float(result_row[0]) if result_row and result_row[0] else 0.0
                            )
                            cursor_check.close()
                            conn_check.close()

                            if new_confidence >= CONFIDENCE_THRESHOLD:
                                graduated_count += 1
                                logger.info(
                                    f"  ✅ Article {article_id} graduated: "
                                    f"{current_avg_confidence:.2f} → {new_confidence:.2f}"
                                )

                            if processed_count % 5 == 0:
                                logger.info(
                                    f"  Processed {processed_count}/{len(article_ids)} articles "
                                    f"({graduated_count} graduated)..."
                                )
                        else:
                            logger.warning(
                                f"  Failed to process article {article_id}: {result.get('error')}"
                            )

                    except Exception as e:
                        logger.error(f"  Error processing article {article_id}: {e}")
                        continue

                logger.info(
                    f"  ✅ {domain_key} domain: {processed_count} articles processed, "
                    f"{graduated_count} articles graduated (≥{CONFIDENCE_THRESHOLD}), "
                    f"{topics_assigned} topic assignments made, "
                    f"{topics_created} new topics created"
                )

                total_processed += processed_count
                total_graduated += graduated_count

            logger.info(
                f"✅ Topic clustering cycle completed across all domains: "
                f"{total_processed} articles processed, "
                f"{total_graduated} articles graduated (≥{CONFIDENCE_THRESHOLD})"
            )

        except Exception as e:
            logger.error(f"❌ Error during topic clustering: {e}", exc_info=True)

    async def _get_db_connection(self):
        """Get database connection from shared pool. Runs in executor to avoid blocking the event loop."""
        from shared.database.connection import get_db_connection

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, get_db_connection)

    def _watchdog_required_phases(self) -> list[str]:
        """Flatten analysis pipeline steps and add document_processing for the 60-minute watchdog."""
        phases: list[str] = []
        for step in ANALYSIS_PIPELINE_STEPS:
            phases.extend(step)
        if "document_processing" not in phases:
            phases.append("document_processing")
        if "content_enrichment" not in phases:
            phases.append("content_enrichment")
        return phases

    async def _run_collection_watchdog(self, collection_started_at: datetime) -> None:
        """
        Run once 60 minutes after collection_cycle started. Check each required phase: if it has not
        run since collection started and (has pending work or we can't tell), request_phase so it
        gets added to the queue. No gating of the next collection_cycle.
        """
        try:
            await asyncio.sleep(WATCHDOG_SECONDS)
        except asyncio.CancelledError:
            return
        if not self.is_running:
            return
        required = self._watchdog_required_phases()
        pending_counts: dict[str, int] = {}
        if get_all_pending_counts:
            try:
                pending_counts = get_all_pending_counts()
            except Exception as e:
                logger.debug("Watchdog get_all_pending_counts: %s", e)
        requested: list[str] = []
        for phase_name in required:
            schedule = self.schedules.get(phase_name)
            if not schedule or not schedule.get("enabled", True):
                continue
            try:
                from config.context_centric_config import is_context_centric_task_enabled

                if not is_context_centric_task_enabled(phase_name):
                    continue
            except Exception:
                pass
            # Watchdog lists every pipeline phase; nightly_enrichment_context must not be
            # request_phase'd outside the clock window (scheduler already gates scheduled runs).
            if phase_name == "nightly_enrichment_context":
                try:
                    from services.nightly_ingest_window_service import (
                        in_nightly_pipeline_window_est,
                    )

                    if not in_nightly_pipeline_window_est():
                        continue
                except Exception:
                    continue
            last_run = schedule.get("last_run") or self._last_completed_at_by_phase.get(phase_name)
            if last_run and collection_started_at and last_run >= collection_started_at:
                continue
            has_work = (pending_counts.get(phase_name) or 0) > 0
            if not has_work and phase_name in BATCH_PHASES_CONTINUOUS:
                has_work = await self._has_pending_work(phase_name)
            if (
                not has_work
                and phase_name not in pending_counts
                and phase_name not in BATCH_PHASES_CONTINUOUS
            ):
                has_work = True
            if has_work:
                try:
                    self.request_phase(phase_name)
                    requested.append(phase_name)
                except Exception as e:
                    logger.debug("Watchdog request_phase %s: %s", phase_name, e)
        if requested:
            logger.info("Collection watchdog: requested phases (add to queue) %s", requested)

    async def _has_pending_work(self, phase_name: str) -> bool:
        """Quick check: is there still work for this phase in any domain? Used to re-enqueue for continuous run."""
        if phase_name not in BATCH_PHASES_CONTINUOUS:
            return False
        try:
            conn = await self._get_db_connection()
            if not conn:
                return False
            cur = conn.cursor()
            try:
                if phase_name == "content_enrichment":
                    for schema in get_pipeline_schema_names_active():
                        cur.execute(
                            f"""SELECT 1 FROM {schema}.articles
                                WHERE (enrichment_status IS NULL OR enrichment_status IN ('pending', 'failed'))
                                  AND COALESCE(enrichment_attempts, 0) < 3
                                  AND url IS NOT NULL AND url != ''
                                LIMIT 1"""
                        )
                        if cur.fetchone():
                            return True
                elif phase_name == "ml_processing":
                    for schema in get_pipeline_schema_names_active():
                        cur.execute(
                            f"""SELECT 1 FROM {schema}.articles
                                WHERE ml_processed = FALSE AND content IS NOT NULL AND LENGTH(content) > 100
                                LIMIT 1"""
                        )
                        if cur.fetchone():
                            return True
                elif phase_name == "entity_extraction":
                    for schema in get_pipeline_schema_names_active():
                        cur.execute(
                            f"""SELECT 1 FROM {schema}.articles
                                WHERE (entities IS NULL OR entities = '{{}}') AND content IS NOT NULL AND LENGTH(content) > 100
                                LIMIT 1"""
                        )
                        if cur.fetchone():
                            return True
                elif phase_name == "sentiment_analysis":
                    for schema in get_pipeline_schema_names_active():
                        cur.execute(
                            f"""SELECT 1 FROM {schema}.articles
                                WHERE sentiment_score IS NULL AND content IS NOT NULL AND LENGTH(content) > 50
                                LIMIT 1"""
                        )
                        if cur.fetchone():
                            return True
                elif phase_name == "storyline_processing":
                    for schema in get_pipeline_schema_names_active():
                        cur.execute(
                            f"""SELECT 1 FROM {schema}.storylines s
                                WHERE s.status = 'active'
                                  AND EXISTS (
                                      SELECT 1 FROM {schema}.storyline_articles sa
                                      WHERE sa.storyline_id = s.id
                                  )
                                  AND LENGTH(
                                      TRIM(
                                          COALESCE(s.analysis_summary, '')
                                          || COALESCE(s.master_summary, '')
                                      )
                                  ) < 100
                                LIMIT 1"""
                        )
                        if cur.fetchone():
                            return True
                elif phase_name == "rag_enhancement":
                    for schema in get_pipeline_schema_names_active():
                        cur.execute(
                            f"""SELECT 1 FROM {schema}.storylines
                                WHERE rag_enhanced_at IS NULL
                                   OR rag_enhanced_at < CURRENT_TIMESTAMP - INTERVAL '1 hour'
                                LIMIT 1"""
                        )
                        if cur.fetchone():
                            return True
                elif phase_name == "storyline_automation":
                    for schema in get_pipeline_schema_names_active():
                        cur.execute(
                            f"""SELECT 1 FROM {schema}.storylines
                                WHERE automation_enabled = true
                                LIMIT 1"""
                        )
                        if cur.fetchone():
                            return True
                elif phase_name == "entity_profile_build":
                    cur.execute(
                        """
                        SELECT 1 FROM intelligence.entity_profiles ep
                        WHERE (ep.sections IS NULL OR ep.sections::text IN ('[]', '{}', 'null'))
                        AND EXISTS (
                            SELECT 1 FROM intelligence.context_entity_mentions cem
                            WHERE cem.entity_profile_id = ep.id
                        )
                        LIMIT 1
                        """
                    )
                    if cur.fetchone():
                        return True
                elif phase_name == "quality_scoring":
                    for schema in get_pipeline_schema_names_active():
                        cur.execute(
                            f"""SELECT 1 FROM {schema}.articles
                                WHERE quality_score IS NULL AND content IS NOT NULL AND LENGTH(content) > 100
                                LIMIT 1"""
                        )
                        if cur.fetchone():
                            return True
                elif phase_name == "timeline_generation":
                    for schema in get_pipeline_schema_names_active():
                        cur.execute(
                            f"""SELECT 1 FROM {schema}.storylines
                                WHERE timeline_summary IS NULL OR LENGTH(timeline_summary) < 100
                                LIMIT 1"""
                        )
                        if cur.fetchone():
                            return True
                elif phase_name == "topic_clustering":
                    for schema in get_pipeline_schema_names_active():
                        cur.execute(
                            f"""SELECT 1 FROM {schema}.articles a
                                WHERE a.content IS NOT NULL AND LENGTH(a.content) > 100
                                AND NOT EXISTS (
                                    SELECT 1 FROM {schema}.article_topic_assignments ata
                                    WHERE ata.article_id = a.id
                                )
                                LIMIT 1"""
                        )
                        if cur.fetchone():
                            return True
                elif phase_name == "event_extraction":
                    for schema in get_pipeline_schema_names_active():
                        cur.execute(
                            f"""SELECT 1 FROM {schema}.articles
                                WHERE processing_status = 'completed' AND timeline_processed = false
                                AND content IS NOT NULL AND LENGTH(content) > 100
                                LIMIT 1"""
                        )
                        if cur.fetchone():
                            return True
                elif phase_name == "content_refinement_queue":
                    from services.nightly_ingest_window_service import in_nightly_pipeline_window_est

                    if in_nightly_pipeline_window_est():
                        return False
                    cur.execute(
                        """
                        SELECT 1 FROM intelligence.content_refinement_queue
                        WHERE status = 'pending'
                        LIMIT 1
                        """
                    )
                    if cur.fetchone():
                        return True
            finally:
                cur.close()
                conn.close()
        except Exception as e:
            logger.debug("_has_pending_work %s: %s", phase_name, e)
        return False

    def get_status(self) -> dict[str, Any]:
        """Get automation status. Includes backlog_counts when backlog_metrics is available."""
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
        # Per-phase queue/run metrics for monitoring timeline:
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
            out["runs_last_60m_by_phase"] = {
                k: len(dq) for k, dq in self._phase_run_times_last_60m.items()
            }
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
        try:
            from services.document_pipeline_metrics import get_document_pipeline_metrics

            out["document_pipeline"] = get_document_pipeline_metrics()
        except Exception:
            out["document_pipeline"] = {"error": "unavailable"}
        try:
            from services.workload_balancer import (
                sample_effective_cooldowns,
                workload_balancer_enabled,
                workload_balancer_phase_names,
            )

            pend = out.get("pending_counts") or {}
            out["work_balancer"] = {
                "enabled": workload_balancer_enabled(),
                "phases": sorted(workload_balancer_phase_names()),
                "base_cooldown_seconds": WORKLOAD_MIN_COOLDOWN,
                "effective_cooldown_seconds": sample_effective_cooldowns(
                    pend,
                    base_cooldown=WORKLOAD_MIN_COOLDOWN,
                ),
            }
        except Exception:
            out["work_balancer"] = {"enabled": False, "error": "unavailable"}
        rr: dict[str, Any] = {
            "enabled": AUTOMATION_DYNAMIC_RESOURCE_ROUTING_ENABLED,
            "headroom": self._resource_headroom or {},
            "thresholds": {
                "gpu_saturated_headroom": ROUTER_GPU_SATURATED_HEADROOM,
                "gpu_extra_headroom": ROUTER_GPU_EXTRA_HEADROOM,
                "cpu_hot_headroom": ROUTER_CPU_HOT_HEADROOM,
                "cpu_extra_headroom": ROUTER_CPU_EXTRA_HEADROOM,
                "db_pressure_headroom": ROUTER_DB_PRESSURE_HEADROOM,
                "db_extra_headroom": ROUTER_DB_EXTRA_HEADROOM,
            },
            "phase_lane_defaults": {
                "gpu": sorted(GPU_LANE_PHASES),
                "cpu": sorted([k for k in self.schedules.keys() if k not in GPU_LANE_PHASES]),
            },
            "structured_llm_cpu_phases": sorted(STRUCTURED_LLM_CPU_LANE_PHASES),
            "resource_classes": {
                "db_heavy": sorted(DB_HEAVY_PHASES),
            },
        }
        try:
            from shared.services.llm_service import llm_service as _ls

            rr["llm_endpoints"] = {
                "dual_host_enabled": bool(_ls.dual_host_enabled),
                "default_base_url": _ls.ollama_base_url,
                "cpu_base_url": _ls.ollama_cpu_host,
                "gpu_base_url": _ls.ollama_gpu_host,
                "cpu_concurrency_cap": max(
                    1, int(os.environ.get("OLLAMA_CPU_CONCURRENCY", "6"))
                ),
                "gpu_concurrency_cap": max(
                    1, int(os.environ.get("OLLAMA_GPU_CONCURRENCY", "6"))
                ),
            }
        except Exception as e:
            rr["llm_endpoints"] = {"error": str(e)}
        out["resource_router"] = rr
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
