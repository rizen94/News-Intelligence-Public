"""
News Intelligence System v8.0 - Enterprise Automation Manager
Collect-then-analyze pipeline: collection_cycle, pipeline-ordered analysis (Foundation → Extraction → Intelligence → Output).

Workload-driven scheduling (USE_WORKLOAD_DRIVEN_ORDER=True): the scheduler checks every process every tick.
Order and run eligibility are determined by current workload, not fixed intervals. When a phase has pending
work it is eligible every WORKLOAD_MIN_COOLDOWN seconds; when idle, intervals apply. Collection is throttled
when downstream backlog (enrichment + context_sync + document_processing) exceeds
COLLECTION_THROTTLE_PENDING_THRESHOLD so the sequence collection → processing → synthesis completes before
adding more RSS. No process is left behind because of fast RSS; phases with no work are skipped or deprioritized.

When AUTOMATION_QUEUE_SOFT_CAP > 0 and combined queue depth (task_queue + requested queue) reaches the cap,
new scheduled enqueues, continuous batch re-queues, and dependency-chain request_phase calls are skipped
except phases in AUTOMATION_QUEUE_PAUSE_ALLOW (default: collection_cycle, health_check) so the backlog can drain.
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
"""

import asyncio
import logging
import os
import signal
import sys
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import time
from dataclasses import dataclass
from enum import Enum
import threading
import queue
from collections import defaultdict, deque, Counter
from concurrent.futures import ThreadPoolExecutor
import traceback

# Configure logging
logger = logging.getLogger(__name__)

# Backlog-driven scheduling: skip empty cycles, run more often when backlog is high
try:
    from services.backlog_metrics import (
        get_all_backlog_counts,
        get_all_pending_counts,
        SKIP_WHEN_EMPTY,
        BACKLOG_HIGH_THRESHOLD,
        BACKLOG_MODE_INTERVAL,
        BACKLOG_ANY_INTERVAL,
    )
except ImportError:
    get_all_backlog_counts = None
    get_all_pending_counts = None
    SKIP_WHEN_EMPTY = frozenset()
    BACKLOG_HIGH_THRESHOLD = 200
    BACKLOG_MODE_INTERVAL = 300
    BACKLOG_ANY_INTERVAL = 30

# Persist each automation run to DB so "last 24h" is based on wall-clock time, not API restart
def _persist_automation_run(phase_name: str, started_at: datetime, finished_at: datetime, success: bool, error_message: Optional[str] = None) -> None:
    """Write one run to automation_run_history (chronological; survives restart)."""
    try:
        from shared.database.connection import get_db_connection
        conn = get_db_connection()
        if not conn:
            return
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO automation_run_history (phase_name, started_at, finished_at, success, error_message)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (phase_name, started_at, finished_at, success, error_message),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        # Must be visible: silent failure makes automation look healthy when history is not persisted
        logger.warning("persist automation_run_history failed (runs not recorded): %s", e)
        try:
            from shared.database.pending_db_writes import enqueue_automation_run_history

            enqueue_automation_run_history(
                phase_name,
                started_at.isoformat() if started_at else "",
                finished_at.isoformat() if finished_at else "",
                success,
                error_message,
            )
        except Exception as qe:
            logger.warning("pending_db_writes enqueue also failed: %s", qe)


# Legacy enrichment-backlog-first flag — removed in v8.1.
# The pipeline cycle now handles sequencing; no need for per-backlog gating.
ENRICHMENT_BACKLOG_FIRST_ENABLED = False
ENRICHMENT_BACKLOG_FIRST_WHITELIST = frozenset()

# Phases that process batches; re-enqueue when pending work remains (v8: capped per analysis window)
BATCH_PHASES_CONTINUOUS = {
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
MAX_REQUEUE_PER_WINDOW = 3  # v8: cap re-enqueues per analysis window so one task cannot monopolize
_SCHEMAS = ("politics", "finance", "science_tech")

# Workload-driven scheduling: order and run decisions by current work, not fixed intervals.
# When a phase has pending work, it is eligible every tick (subject to cooldown); intervals apply only when idle.
WORKLOAD_MIN_COOLDOWN = 10  # seconds between enqueueing the same phase when it has work (avoid flood)
# Don't run collection_cycle when downstream (enrichment + context_sync + document_processing) pending exceeds this.
# Ensures collection → processing → synthesis sequence completes before adding more RSS.
COLLECTION_THROTTLE_PENDING_THRESHOLD = 500
# When True, scheduler ignores analysis-window step lock; workload + pipeline order determine what runs.
USE_WORKLOAD_DRIVEN_ORDER = True

# When combined queue depth (main + requested) >= this, stop enqueueing scheduled work except allowlist
# so the backlog can drain. 0 = disabled. Tuned for ~12–16 workers × ~12 tasks ahead each.
AUTOMATION_QUEUE_SOFT_CAP = int(os.environ.get("AUTOMATION_QUEUE_SOFT_CAP", "200"))
QUEUE_PAUSE_ALLOW_SCHEDULED = frozenset(
    x.strip()
    for x in os.environ.get(
        "AUTOMATION_QUEUE_PAUSE_ALLOW",
        "collection_cycle,health_check,pending_db_flush",
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
DATA_LOAD_PHASES = ("collection_cycle", "entity_extraction")  # v8: collection_cycle is the data load
DOWNTIME_IDLE_SECONDS = 300   # Consider "downtime" if no data-load phase ran in last 5 min
DOWNTIME_ORGANIZER_SLEEP = 45  # Seconds between organizer cycles during downtime
DOWNTIME_POLL_SLEEP = 30       # Seconds to sleep when data load is active (before rechecking)

# v8: Pipeline-ordered analysis (run after each collection_cycle)
ANALYSIS_PIPELINE_STEPS: Tuple[Tuple[str, ...], ...] = (
    # Step 0: Foundation
    ("context_sync", "entity_profile_sync", "ml_processing", "entity_extraction", "metadata_enrichment"),
    # Step 1: Extraction
    ("claim_extraction", "claims_to_facts", "event_tracking", "topic_clustering", "quality_scoring", "sentiment_analysis"),
    # Step 2: Intelligence
    (
        "entity_profile_build", "entity_organizer", "pattern_recognition", "cross_domain_synthesis",
        "storyline_discovery", "proactive_detection", "fact_verification", "event_coherence_review",
        "entity_enrichment", "story_enhancement", "pattern_matching", "research_topic_refinement",
        "investigation_report_refresh",
    ),
    # Step 3: Output (remaining time until next collection)
    (
        "storyline_processing", "rag_enhancement", "storyline_automation", "storyline_enrichment", "story_continuation",
        "event_extraction", "event_deduplication", "timeline_generation", "editorial_document_generation",
        "editorial_briefing_generation", "entity_dossier_compile", "entity_position_tracker",
        "storyline_synthesis", "daily_briefing_synthesis", "digest_generation", "watchlist_alerts",
        "content_refinement_queue",
        "cache_cleanup", "data_cleanup",
    ),
)
STEP_TIME_BUDGETS: Tuple[Optional[int], ...] = (1800, 1200, 1200, None)  # seconds; None = no limit (step 3)

# Cap concurrent Ollama/GPU tasks. Scale up when you have GPU/CPU headroom (e.g. 12).
MAX_CONCURRENT_OLLAMA_TASKS = 12

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
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None

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
    "context_sync": 60,   # ~5-10s per 100 contexts (production batch)
    "entity_profile_sync": 225,  # observed ~223s avg; was 120
    "claim_extraction": 60,   # 50 contexts @ 2-5s each, parallel 5 → ~20-50s
    "claims_to_facts": 30,    # promote high-confidence claims to versioned_facts (DB only)
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
    "entity_dossier_compile": 90,  # compile entity dossiers (no LLM), ~2-5s per dossier
    "entity_position_tracker": 300,  # LLM position extraction per entity, ~30-60s per entity
    "metadata_enrichment": 90,  # language/categories/sentiment/quality per domain batch
    "research_topic_refinement": 60,  # pick one topic, submit to finance orchestrator (idle-only)
    "editorial_document_generation": 300,  # LLM-generate/refine editorial_document on storylines
    "editorial_briefing_generation": 300,  # LLM-generate/refine editorial_briefing on tracked_events
    # v7: full-text enrichment, document pipeline, auto synthesis
    "content_enrichment": 120,   # trafilatura fetch per article, rate-limited
    "document_collection": 300,   # government + academic PDF discovery
    "document_processing": 180,   # observed ~152s when small batch; was 600
    "storyline_synthesis": 600,   # deep content synthesis per storyline
    "daily_briefing_synthesis": 300,  # breaking news synthesis per domain
    "storyline_discovery": 600,  # AI clustering + LLM title generation per domain
    # v8: collect-then-analyze — single master task runs RSS + enrichment + docs
    "collection_cycle": 1800,  # 30 min; RSS + drain enrichment + doc collection + drain doc processing + pending queue
    "proactive_detection": 300,  # v8: emerging storylines per domain
    "fact_verification": 120,  # v8: verify_recent_claims per domain
    "content_refinement_queue": 420,  # storyline RAG / timeline narrative / ~70B finisher (queued user jobs)
}

class AutomationManager:
    """Enterprise-grade automation manager"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.is_running = False
        self.tasks: Dict[str, Task] = {}
        self.executor = ThreadPoolExecutor(max_workers=6)
        self._executor = self.executor  # alias used by entity_dossier_compile, entity_position_tracker, fact_verification
        self.task_queue = asyncio.Queue()
        # User/governor-requested tasks run before scheduled tasks so "Request phase" is not starved
        self._requested_task_queue: asyncio.Queue = asyncio.Queue()
        self.ollama_semaphore = asyncio.Semaphore(MAX_CONCURRENT_OLLAMA_TASKS)
        self.workers = []
        # Thread-safe queue for coordinator-driven phase requests (run_phase from another thread)
        self._phase_request_queue = queue.Queue()
        # Optional: callable() -> finance orchestrator, set by main after app.state.finance_orchestrator exists
        self._get_finance_orchestrator = None
        self.health_check_interval = 30  # seconds
        self.task_timeout = 300  # 5 minutes
        self.max_concurrent_tasks = 12  # Phase workers; scale up when you have CPU/GPU headroom
        
        # Dynamic resource allocation
        self.dynamic_resource_service = None
        self.resource_allocation = None
        
        # v8: Pending collection queue — RAG/synthesis add URLs here; drained each collection_cycle
        self._pending_collection_queue: List[Dict[str, Any]] = []
        # v8: Pipeline-ordered analysis state (set when collection_cycle completes, cleared when next collection starts)
        self._analysis_window_start: Optional[datetime] = None
        self._active_step: int = 0
        self._step_started_at: Optional[datetime] = None
        # v8: Re-enqueue count per task in current analysis window (reset when window starts)
        self._requeue_counts: Dict[str, int] = {}

        # Monitor metrics for phase timeline:
        # - queued_tasks_by_phase: computed from in-memory asyncio queues
        # - running_tasks_by_phase: tracked while tasks are executing
        # - runs_last_60m_by_phase: recorded from completion timestamps
        self._running_tasks_by_phase: Dict[str, int] = defaultdict(int)
        self._phase_run_times_last_60m: Dict[str, deque[datetime]] = defaultdict(deque)

        # Collection-cycle watchdog: when current cycle started; per-phase last completion (for "has it run since start?")
        self._collection_cycle_started_at: Optional[datetime] = None
        self._last_completed_at_by_phase: Dict[str, datetime] = {}

        # v8: Optional config from orchestrator_governance.yaml (analysis_pipeline, collection_cycle)
        try:
            from config.orchestrator_governance import get_orchestrator_governance_config
            gov = get_orchestrator_governance_config()
            ap = gov.get("analysis_pipeline") or {}
            cc = gov.get("collection_cycle") or {}
        except Exception:
            ap, cc = {}, {}
        budgets = ap.get("step_budgets_seconds")
        self._step_time_budgets: Tuple[Optional[int], ...] = tuple(budgets) if budgets else STEP_TIME_BUDGETS
        self._max_requeue_per_window: int = ap.get("max_requeue_per_window", MAX_REQUEUE_PER_WINDOW)
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
            'collection_cycle': {
                'interval': collection_interval,
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.CRITICAL,
                'phase': 0,
                'depends_on': [],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['collection_cycle'],
            },
            # PDF document processing (also runs inside collection_cycle); standalone so backlog drains between cycles
            'document_processing': {
                'interval': 600,  # 10 minutes - drain unprocessed PDFs (fetch + extract sections/entities)
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 0,
                'depends_on': [],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['document_processing'],
            },
            # PHASE 1b: Context-centric sync (incremental: articles -> intelligence.contexts)
            'context_sync': {
                'interval': 900,  # 15 minutes - incremental sync, 100 contexts/batch, ~30-60s
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 1,
                'depends_on': ['collection_cycle'],  # v8: after collection cycle
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['context_sync'],
            },
            # PHASE 1c: Entity profile sync (entity_canonical -> entity_profiles, old_entity_to_new)
            'entity_profile_sync': {
                'interval': 21600,  # 6 hours
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 1,
                'depends_on': [],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['entity_profile_sync'],
            },
            # PHASE 2a: Claim extraction (contexts -> extracted_claims; LLM rate limits)
            'claim_extraction': {
                'interval': 1800,  # 30 minutes - max 50 contexts/run, ~1-2 min, cost-controlled
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 2,
                'depends_on': ['context_sync'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['claim_extraction'],
            },
            # PHASE 2a.1: Promote high-confidence claims to versioned_facts (activates story state chain)
            'claims_to_facts': {
                'interval': 3600,  # 1 hour - after claim_extraction has run
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 2,
                'depends_on': ['claim_extraction'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['claims_to_facts'],
            },
            # PHASE 2.3: Event tracking (contexts -> tracked_events; drain unlinked backlog)
            'event_tracking': {
                'interval': 900,  # 15 min - process more contexts per run when backlog is large
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 2,
                'depends_on': ['context_sync'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['event_tracking'],
            },
            # PHASE 3: Event coherence review (LLM verifies context-event fit)
            'event_coherence_review': {
                'interval': 7200,  # 2 hours
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.LOW,
                'phase': 3,
                'depends_on': [],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['event_coherence_review'],
            },
            # PHASE 2.4: Refresh investigation reports when events gain new context (after event_tracking)
            'investigation_report_refresh': {
                'interval': 7200,  # 2 hours
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.LOW,
                'phase': 2,
                'depends_on': ['event_tracking'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['investigation_report_refresh'],
            },
            # PHASE 2.5: Cross-domain synthesis (correlate events across politics/finance/science-tech)
            'cross_domain_synthesis': {
                'interval': 1800,  # 30 minutes
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 2,
                'depends_on': ['event_tracking'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['cross_domain_synthesis'],
            },
            # PHASE 1.3: Entity profile builder (sections, relationships from contexts)
            'entity_profile_build': {
                'interval': 900,  # 15 minutes - run often, re-enqueue until profiles built
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 1,
                'depends_on': ['context_sync', 'entity_profile_sync'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['entity_profile_build'],
            },
            # PHASE 2.2: Pattern recognition (network, temporal, behavioral, event)
            'pattern_recognition': {
                'interval': 7200,  # 2 hours
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 2,
                'depends_on': ['context_sync', 'entity_profile_sync'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['pattern_recognition'],
            },
            # PHASE 2.6: Entity dossier compile (articles + storylines + relationships -> entity_dossiers)
            'entity_dossier_compile': {
                'interval': 3600,  # 1 hour - compile dossiers for entities missing or stale
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 2,
                'depends_on': ['entity_profile_sync'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['entity_dossier_compile'],
            },
            # PHASE 2: Entity position tracker (stances, votes, policy from articles -> entity_positions)
            'entity_position_tracker': {
                'interval': 7200,  # 2 hours
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 2,
                'depends_on': ['entity_profile_sync'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['entity_position_tracker'],
            },
            # Metadata enrichment (language, categories, sentiment, quality) for domain articles
            'metadata_enrichment': {
                'interval': 900,  # 15 minutes
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 2,
                'depends_on': ['collection_cycle'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['metadata_enrichment'],
            },
            # Entity organizer: cleanup (merge/prune/cap) + relationship extraction; also runs in downtime loop
            'entity_organizer': {
                'interval': 600,  # 10 minutes - run after we have entities
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 2,
                'depends_on': ['entity_profile_sync'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['entity_organizer'],
            },
            # PHASE 3: ML Processing (Runs frequently on processed articles)
            'ml_processing': {
                'interval': 300,  # 5 minutes - run often, re-enqueue until empty
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.HIGH,
                'phase': 3,
                'depends_on': ['collection_cycle'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['ml_processing'],
            },
            
            # PHASE 5: Topic Clustering (Continuous iterative refinement)
            'topic_clustering': {
                'interval': 300,  # 5 minutes - run often, drain backlog
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.HIGH,
                'phase': 5,
                'depends_on': ['collection_cycle'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['topic_clustering'],
            },
            
            # PHASE 4: Parallel ML & Entity Processing (Runs frequently)
            'entity_extraction': {
                'interval': 300,  # 5 minutes - run often, re-enqueue until empty
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 4,
                'depends_on': ['collection_cycle'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['entity_extraction'],
                'parallel_group': 'ml_entity_processing'  # Can run in parallel with ML
            },
            
            # PHASE 4: Parallel ML & Entity Processing (Runs frequently)
            'quality_scoring': {
                'interval': 300,  # 5 minutes - run often
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 4,
                'depends_on': ['collection_cycle'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['quality_scoring'],
                'parallel_group': 'ml_entity_processing'  # Can run in parallel with ML
            },
            
            # PHASE 4: Parallel ML & Entity Processing (Runs frequently)
            'sentiment_analysis': {
                'interval': 300,  # 5 minutes - run often, re-enqueue until empty
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 4,
                'depends_on': ['collection_cycle'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['sentiment_analysis'],
                'parallel_group': 'ml_entity_processing'  # Can run in parallel with ML
            },
            
            # PHASE 6: Storyline Discovery (AI auto-creates storylines from article clusters)
            'storyline_discovery': {
                'interval': 14400,  # 4 hours — discover new storylines from recent articles
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 6,
                'depends_on': ['collection_cycle'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['storyline_discovery'],
            },
            'proactive_detection': {
                'interval': 7200,  # 2 hours — emerging storylines (v8)
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 6,
                'depends_on': ['collection_cycle'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['proactive_detection'],
            },
            'fact_verification': {
                'interval': 14400,  # 4 hours — verify recent claims (v8)
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 6,
                'depends_on': ['collection_cycle'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['fact_verification'],
            },
            # PHASE 7: Storyline Processing (summaries; continuous until empty)
            'storyline_processing': {
                'interval': 300,  # 5 minutes - run often, re-enqueue until empty
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.HIGH,
                'phase': 7,
                'depends_on': ['ml_processing', 'sentiment_analysis'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['storyline_processing'],
            },
            # Governor-triggered: RAG discovery for one or all automation-enabled storylines
            'storyline_automation': {
                'interval': 300,  # 5 min: recent incoming → match to existing storylines
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 7,
                'depends_on': [],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['storyline_automation'],
            },
            # v8: Enrich existing storylines/dossiers with full-history search (past articles/contexts)
            'storyline_enrichment': {
                'interval': 43200,  # 12 hours - full-history pass
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 7,
                'depends_on': ['storyline_automation'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['storyline_enrichment'],
            },
            # PHASE 8: RAG Enhancement (Every 30 minutes)
            'rag_enhancement': {
                'interval': 300,  # 5 minutes - run often, re-enqueue until storylines enhanced
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.HIGH,
                'phase': 8,
                'depends_on': ['storyline_processing'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['rag_enhancement'],
            },
            
            # PHASE 9a: Event Extraction (v5.0 - runs after entity extraction)
            'event_extraction': {
                'interval': 300,  # 5 minutes - run often, re-enqueue until empty
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 9,
                'depends_on': ['entity_extraction'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['event_extraction'],
                'parallel_group': 'event_processing'
            },
            
            # PHASE 9b: Event Deduplication (v5.0 - runs after event extraction)
            'event_deduplication': {
                'interval': 600,  # 10 minutes
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 9,
                'depends_on': ['event_extraction'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['event_deduplication'],
                'parallel_group': 'event_processing'
            },
            
            # PHASE 9c: Story Continuation Matching (v5.0)
            'story_continuation': {
                'interval': 600,  # 10 minutes
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 9,
                'depends_on': ['event_deduplication'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['story_continuation'],
            },

            # PHASE 9d: Timeline Generation (continuous until empty)
            'timeline_generation': {
                'interval': 300,  # 5 minutes - run often, re-enqueue until empty
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 9,
                'depends_on': ['rag_enhancement'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['timeline_generation'],
            },

            # Phase 3 RAG: Entity enrichment (Wikipedia -> entity_profiles; LLM limits)
            'entity_enrichment': {
                'interval': 1800,  # 30 minutes - max 20 entities/run, 10s timeout/entity; skip if queue >1000
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 9,
                'depends_on': ['entity_profile_sync'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['entity_enrichment'],
            },
            # Phase 3 RAG: Full enhancement cycle (triggers + enrichment + profile build)
            'story_enhancement': {
                'interval': 300,  # 5 minutes - max 10 stories/run, 60s budget
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 9,
                'depends_on': [],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['story_enhancement'],
            },
            # User-requested storyline refinement (DB queue; no ad-hoc HTTP LLM)
            'content_refinement_queue': {
                'interval': 120,  # 2 min when idle; workload-driven when pending > 0
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 9,
                'depends_on': [],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['content_refinement_queue'],
            },
            
            # PHASE 10: Cache Cleanup (Every hour)
            'cache_cleanup': {
                'interval': 3600,  # 1 hour - Clean expired cache
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.LOW,
                'phase': 10,
                'depends_on': [],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['cache_cleanup'],
            },
            
            # PHASE 10.5: Editorial Document Generation — build/refine editorial_document + editorial_briefing
            'editorial_document_generation': {
                'interval': 1800,  # 30 minutes
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 10,
                'depends_on': ['storyline_processing'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['editorial_document_generation'],
            },
            'editorial_briefing_generation': {
                'interval': 1800,  # 30 minutes
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 10,
                'depends_on': ['event_tracking'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['editorial_briefing_generation'],
            },

            # PHASE 11: Digest Generation (Every hour)
            'digest_generation': {
                'interval': 3600,  # 1 hour
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 11,
                'depends_on': ['editorial_document_generation'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['digest_generation'],
            },

            # v7: Auto storyline synthesis (Wikipedia-style articles)
            'storyline_synthesis': {
                'interval': 3600,  # 60 minutes
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 10,
                'depends_on': ['storyline_processing'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['storyline_synthesis'],
            },
            # v7: Auto daily briefing synthesis (breaking news)
            'daily_briefing_synthesis': {
                'interval': 14400,  # 4 hours
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.LOW,
                'phase': 11,
                'depends_on': ['storyline_synthesis'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['daily_briefing_synthesis'],
            },

            # PHASE 12: Watchlist Alert Generation (v5.0)
            'watchlist_alerts': {
                'interval': 1200,  # 20 minutes - Relaxed from 15 min
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.LOW,
                'phase': 12,
                'depends_on': ['story_continuation'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['watchlist_alerts'],
            },
            # Phase 4 RAG: Watch patterns — match content, record pattern_matches, create watchlist alerts
            'pattern_matching': {
                'interval': 1800,  # 30 minutes
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.LOW,
                'phase': 12,
                'depends_on': [],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['pattern_matching'],
            },

            # IDLE-ONLY: Research topic refinement (finance) — run when no data load / higher-priority work
            'research_topic_refinement': {
                'interval': 3600,  # consider every hour when idle
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.LOW,
                'phase': 98,
                'depends_on': [],
                'idle_only': True,
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['research_topic_refinement'],
            },

            # PHASE 11: Narrative thread build + synthesis (cross-storyline narrative arcs)
            'narrative_thread_build': {
                'interval': 7200,  # 2 hours
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.LOW,
                'phase': 11,
                'depends_on': ['storyline_processing', 'editorial_document_generation'],
                'estimated_duration': 120,
            },

            # MAINTENANCE: Data Cleanup (Daily)
            'data_cleanup': {
                'interval': 86400,  # 24 hours
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.LOW,
                'phase': 99,
                'depends_on': [],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['data_cleanup'],
            },
            
            # MONITORING: Health Check
            'health_check': {
                'interval': 120,  # 2 minutes - Relaxed from 1 min
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.CRITICAL,
                'phase': 0,
                'depends_on': [],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['health_check'],
            },
            # OUTAGE: Replay local spill file (automation_run_history) when DB was down
            'pending_db_flush': {
                'interval': 45,
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.CRITICAL,
                'phase': 0,
                'depends_on': [],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['pending_db_flush'],
            },
        }
        
        # Performance metrics
        self.metrics = {
            'tasks_completed': 0,
            'tasks_failed': 0,
            'avg_processing_time': 0,
            'system_uptime': 0,
            'last_health_check': None,
            'adaptive_timing': True,
            'load_factor': 1.0,  # Multiplier for intervals based on load
            'processing_history': {}  # Track actual vs estimated durations
        }

    def _automation_queue_depth(self) -> int:
        """Approximate pending tasks in worker queues (scheduled + governor-requested)."""
        try:
            return int(self.task_queue.qsize()) + int(self._requested_task_queue.qsize())
        except Exception:
            return 0

    def _scheduled_enqueue_paused(self) -> bool:
        """When True, skip adding new scheduled / chained / continuous tasks (allowlist still runs)."""
        if AUTOMATION_QUEUE_SOFT_CAP <= 0:
            return False
        return self._automation_queue_depth() >= AUTOMATION_QUEUE_SOFT_CAP

    def queue_collection_request(self, request_type: str = "url", url: str = "", source: str = "") -> None:
        """v8: Queue a URL or feed for the next collection cycle (e.g. from RAG/synthesis). Thread-safe append."""
        self._pending_collection_queue.append({
            "type": request_type,
            "url": url,
            "source": source,
            "queued_at": datetime.now(timezone.utc).isoformat(),
        })

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
                    logger.info("Loaded %s pending collection request(s) from DB", len(self._pending_collection_queue))
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
                        (json.dumps([{k: v for k, v in req.items() if k in ("type", "url", "source", "queued_at")} for req in self._pending_collection_queue]),),
                    )
                conn.commit()
                if self._pending_collection_queue:
                    logger.info("Persisted %s pending collection request(s) to DB", len(self._pending_collection_queue))
            finally:
                conn.close()
        except Exception as e:
            logger.debug("Persist pending_collection_queue: %s", e)

    async def start(self):
        """Start the automation manager"""
        logger.info("Starting Enterprise Automation Manager...")
        self._load_pending_collection_queue()
        self.is_running = True

        # Start worker processes
        for i in range(self.max_concurrent_tasks):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(worker)
        
        # Start scheduler
        scheduler = asyncio.create_task(self._scheduler())
        self.workers.append(scheduler)
        
        # Start health monitor
        health_monitor = asyncio.create_task(self._health_monitor())
        self.workers.append(health_monitor)
        
        # Start metrics collector
        metrics_collector = asyncio.create_task(self._metrics_collector())
        self.workers.append(metrics_collector)
        
        # Entity organizer downtime loop: keep cleaning up and generating relationships between data loads
        entity_organizer_loop = asyncio.create_task(self._entity_organizer_downtime_loop())
        self.workers.append(entity_organizer_loop)
        
        logger.info(f"Automation Manager started with {self.max_concurrent_tasks} workers")

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
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        logger.info("Automation Manager stopped")

    def request_phase(
        self,
        phase_name: str,
        domain: Optional[str] = None,
        storyline_id: Optional[int] = None,
        requested_activity_id: Optional[str] = None,
    ) -> None:
        """
        Request a phase to run (thread-safe). Call from coordinator or API.
        The scheduler will drain this queue and enqueue tasks with metadata.
        If requested_activity_id is set (e.g. from Monitor trigger), the worker
        will complete that activity when the task starts so Current activity shows the real task.
        """
        try:
            self._phase_request_queue.put_nowait((phase_name, domain, storyline_id, requested_activity_id))
        except Exception as e:
            logger.warning("AutomationManager request_phase failed: %s", e)

    def set_finance_orchestrator_getter(self, getter):
        """Set callable() -> finance orchestrator (used by research_topic_refinement when idle)."""
        self._get_finance_orchestrator = getter

    def get_phase_request_warning(self, phase_name: str) -> Optional[str]:
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
            need = dep_schedule.get("estimated_duration", 60) * max(0.5, self.metrics.get("load_factor", 1.0))
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
                    task = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
                
                if task:
                    await self._execute_task(task, worker_id)
                    if from_requested:
                        self._requested_task_queue.task_done()
                    else:
                        self.task_queue.task_done()
                    
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                await asyncio.sleep(1)
        
        logger.info(f"Worker {worker_id} stopped")
        
    def _bootstrap_initial_tasks(self):
        """Queue key phases immediately on startup so work starts without waiting for first interval."""
        now = datetime.now(timezone.utc)
        # Phases that should run once as soon as we start (no deps, or bootstrap allows)
        for task_name in ("collection_cycle", "health_check"):
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
                metadata={"scheduled": True, "phase": schedule.get("phase", 0), "bootstrap": True},
            )
            try:
                self.task_queue.put_nowait(task)
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
                backlog_counts: Dict[str, int] = {}
                self._pending_counts: Dict[str, int] = {}
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

                # Drain coordinator-driven phase requests (thread-safe); respect enrichment-backlog-first
                try:
                    while True:
                        item = self._phase_request_queue.get_nowait()
                        # Support both 3-tuple (legacy) and 4-tuple (with requested_activity_id)
                        if len(item) == 4:
                            phase_name, domain, storyline_id, requested_activity_id = item
                        else:
                            phase_name, domain, storyline_id = item[0], item[1], item[2]
                            requested_activity_id = None
                        if phase_name not in self.schedules:
                            logger.debug("request_phase: unknown phase %s, skipping", phase_name)
                            continue
                        schedule = self.schedules[phase_name]
                        if not schedule.get("enabled", True):
                            logger.debug("request_phase: phase %s is disabled, skipping", phase_name)
                            continue
                        if ENRICHMENT_BACKLOG_FIRST_ENABLED and backlog_counts.get("content_enrichment", 0) > 0 and phase_name not in ENRICHMENT_BACKLOG_FIRST_WHITELIST:
                            logger.info("request_phase: skipping %s (enrichment backlog first, %s articles pending)", phase_name, backlog_counts.get("content_enrichment", 0))
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
                            },
                        )
                        await self._requested_task_queue.put(task)
                        logger.info("Governor requested phase: %s (domain=%s, storyline_id=%s)", phase_name, domain, storyline_id)
                except queue.Empty:
                    pass

                # Sort tasks by phase for proper sequencing
                sorted_tasks = sorted(self.schedules.items(), key=lambda x: x[1].get('phase', 0))
                
                # Group tasks by phase and parallel groups
                phase_groups = {}
                for task_name, schedule in sorted_tasks:
                    if not schedule['enabled']:
                        continue
                    
                    phase = schedule.get('phase', 0)
                    parallel_group = schedule.get('parallel_group')
                    
                    if parallel_group:
                        # Add to parallel group
                        if phase not in phase_groups:
                            phase_groups[phase] = {'parallel_groups': {}, 'sequential_tasks': []}
                        if 'parallel_groups' not in phase_groups[phase]:
                            phase_groups[phase]['parallel_groups'] = {}
                        if parallel_group not in phase_groups[phase]['parallel_groups']:
                            phase_groups[phase]['parallel_groups'][parallel_group] = []
                        phase_groups[phase]['parallel_groups'][parallel_group].append((task_name, schedule))
                    else:
                        # Sequential task
                        if phase not in phase_groups:
                            phase_groups[phase] = {'parallel_groups': {}, 'sequential_tasks': []}
                        phase_groups[phase]['sequential_tasks'].append((task_name, schedule))
                
                # Update resource allocation periodically
                if current_time.second % 60 == 0:  # Every minute
                    await self._update_resource_allocation()
                
                # Check if we should scale down
                if await self._should_scale_down():
                    logger.warning("High system load detected - scaling down processing")
                    # Reduce parallel processing temporarily
                    self.max_concurrent_tasks = max(1, self.max_concurrent_tasks - 1)
                
                # Check if we should scale up
                elif await self._should_scale_up():
                    logger.info("Low system load detected - scaling up processing")
                    # Increase parallel processing
                    self.max_concurrent_tasks = min(12, self.max_concurrent_tasks + 1)
                
                # Process parallel groups first (phase order)
                for phase in sorted(phase_groups.keys()):
                    phase_data = phase_groups[phase]
                    for parallel_group, tasks in phase_data['parallel_groups'].items():
                        if self._should_run_parallel_group(parallel_group, tasks, current_time, backlog_counts):
                            await self._execute_parallel_phase(parallel_group)

                # Sequential tasks: collect all runnable across phases, then queue by work-driven priority.
                # Select processes intelligently: effective priority (boost when backlog high), then most work first, then phase order.
                all_runnable: List[Tuple[str, Dict[str, Any]]] = []
                for phase in sorted(phase_groups.keys()):
                    phase_data = phase_groups[phase]
                    runnable = [
                        (task_name, schedule)
                        for task_name, schedule in phase_data['sequential_tasks']
                        if self._should_run_task(task_name, schedule, current_time, backlog_counts)
                    ]
                    all_runnable.extend(runnable)
                def _work_driven_sort_key(item):
                    task_name, schedule = item
                    p = schedule.get("priority", TaskPriority.NORMAL).value  # lower = higher priority
                    backlog = backlog_counts.get(task_name, 0)
                    if ENRICHMENT_BACKLOG_FIRST_ENABLED and task_name == "content_enrichment" and backlog > 0:
                        p = TaskPriority.CRITICAL.value
                    elif backlog > BACKLOG_HIGH_THRESHOLD:
                        # Boost priority by one level when this task has a lot of work (prioritize work that needs doing)
                        p = max(TaskPriority.CRITICAL.value, p - 1)
                    phase = schedule.get("phase", 0)
                    # Sort: higher priority first (lower p), then more backlog first (-backlog), then earlier phase
                    return (p, -backlog, phase)

                for task_name, schedule in sorted(all_runnable, key=_work_driven_sort_key):
                    await self._create_and_queue_task(task_name, schedule, current_time)
                
                await asyncio.sleep(5)  # Check every 5 seconds for more continuous iteration
                
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(5)
        
        logger.info("Scheduler stopped")
    
    def _should_run_parallel_group(
        self,
        parallel_group: str,
        tasks: List[Tuple[str, Dict]],
        current_time: datetime,
        backlog_counts: Optional[Dict[str, int]] = None,
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
        schedule: Dict[str, Any],
        current_time: datetime,
        backlog_counts: Optional[Dict[str, int]] = None,
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
        if task_name in ("collection_cycle", "health_check", "document_processing"):
            pass
        elif not USE_WORKLOAD_DRIVEN_ORDER and self._analysis_window_start is not None:
            # Legacy: only run tasks in current pipeline step when step budget is enforced
            if self._active_step < len(self._step_time_budgets) and self._step_started_at is not None:
                budget = self._step_time_budgets[self._active_step]
                if budget is not None and (current_time - self._step_started_at).total_seconds() >= budget:
                    self._active_step = min(self._active_step + 1, len(ANALYSIS_PIPELINE_STEPS) - 1)
                    self._step_started_at = current_time
            if self._active_step < len(ANALYSIS_PIPELINE_STEPS):
                if task_name not in ANALYSIS_PIPELINE_STEPS[self._active_step]:
                    return False
        elif USE_WORKLOAD_DRIVEN_ORDER and self._analysis_window_start is not None:
            # Advance step for reporting only; do not gate tasks — workload order decides
            if self._active_step < len(self._step_time_budgets) and self._step_started_at is not None:
                budget = self._step_time_budgets[self._active_step]
                if budget is not None and (current_time - self._step_started_at).total_seconds() >= budget:
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
            downstream = (
                (self._pending_counts.get("content_enrichment", 0) if hasattr(self, "_pending_counts") else 0)
                + (self._pending_counts.get("context_sync", 0) if hasattr(self, "_pending_counts") else 0)
                + (self._pending_counts.get("document_processing", 0) if hasattr(self, "_pending_counts") else 0)
            )
            if downstream > COLLECTION_THROTTLE_PENDING_THRESHOLD:
                return False

        if schedule.get("idle_only") and not self._is_system_idle():
            return False

        backlog_counts = backlog_counts or {}
        if ENRICHMENT_BACKLOG_FIRST_ENABLED and backlog_counts.get("content_enrichment", 0) > 0 and task_name not in ENRICHMENT_BACKLOG_FIRST_WHITELIST:
            return False

        backlog = backlog_counts.get(task_name, 0)

        # SKIP_WHEN_EMPTY: skip when no work (so we don't run empty cycles).
        pending = self._pending_counts.get(task_name, 0) if hasattr(self, '_pending_counts') else backlog
        if task_name in SKIP_WHEN_EMPTY and pending == 0:
            return False

        has_work = pending > 0 or backlog > 0

        # Workload-driven: when there is work, eligibility is based on cooldown + deps only (no interval).
        # Each tick we check every process; if it has work and deps are satisfied, we add it to the candidate
        # list; sort order (priority, -backlog, phase) then decides what gets queued first.
        if USE_WORKLOAD_DRIVEN_ORDER and has_work:
            time_since = (current_time - schedule['last_run']).total_seconds() if schedule.get('last_run') else 9999
            if time_since >= WORKLOAD_MIN_COOLDOWN and self._are_dependencies_satisfied(task_name, schedule, current_time):
                return True
            return False

        # No work (or legacy mode): use interval so we don't run e.g. collection_cycle every tick when idle.
        base_interval = schedule['interval']
        adaptive_interval = self._calculate_adaptive_interval(task_name, base_interval)
        if backlog > BACKLOG_HIGH_THRESHOLD:
            effective_interval = min(adaptive_interval, BACKLOG_MODE_INTERVAL)
        elif backlog > 0:
            effective_interval = min(adaptive_interval, BACKLOG_ANY_INTERVAL)
        else:
            effective_interval = adaptive_interval

        if (
            schedule['last_run'] is None
            or (current_time - schedule['last_run']).total_seconds() >= effective_interval
        ):
            if self._are_dependencies_satisfied(task_name, schedule, current_time):
                return True
        return False
    
    async def _create_and_queue_task(self, task_name: str, schedule: Dict[str, Any], current_time: datetime):
        """Create and queue a task"""
        if self._scheduled_enqueue_paused() and task_name not in QUEUE_PAUSE_ALLOW_SCHEDULED:
            logger.info(
                "Queue soft cap: skipping scheduled enqueue for %s (depth=%s cap=%s)",
                task_name,
                self._automation_queue_depth(),
                AUTOMATION_QUEUE_SOFT_CAP,
            )
            return
        # Create task
        task = Task(
            id=f"{task_name}_{int(current_time.timestamp())}",
            name=task_name,
            priority=schedule['priority'],
            status=TaskStatus.PENDING,
            created_at=current_time,
            metadata={
                'scheduled': True,
                'phase': schedule.get('phase', 0),
                'estimated_duration': schedule.get('estimated_duration', 60)
            }
        )
        
        # Add to queue
        await self.task_queue.put(task)
        schedule['last_run'] = current_time
        logger.info(f"Scheduled task: {task_name} (Phase {schedule.get('phase', 0)})")
    
    def _check_dependencies(self, task_name: str, schedule: Dict[str, Any]) -> bool:
        """Check if task has dependencies"""
        depends_on = schedule.get('depends_on', [])
        return len(depends_on) == 0 or all(
            dep_task in self.schedules and self.schedules[dep_task]['enabled']
            for dep_task in depends_on
        )
    
    def _are_dependencies_satisfied(self, task_name: str, schedule: Dict[str, Any], current_time: datetime) -> bool:
        """Check if all dependencies have been satisfied recently.
        When this task has never run, treat 'dependency never run' as satisfied so we queue
        both (phase order ensures the dependency runs first); otherwise nothing would ever
        call the dependent.
        """
        depends_on = schedule.get('depends_on', [])
        this_never_run = schedule.get('last_run') is None

        for dep_task in depends_on:
            if dep_task not in self.schedules:
                continue

            dep_schedule = self.schedules[dep_task]
            dep_never_run = dep_schedule['last_run'] is None

            # Bootstrap: if both this task and the dependency have never run, allow queuing
            # so the scheduler queues both; phase order queues the dependency first.
            if this_never_run and dep_never_run:
                continue

            if dep_never_run:
                return False

            # Require a short settle window after dependency completed (DB / pipeline visibility).
            # Cap by AUTOMATION_DEPENDENCY_SETTLE_CAP_SEC so long phases (e.g. collection_cycle ~30m
            # estimated) do not block dependents indefinitely while collection runs often.
            time_since_dep = (current_time - dep_schedule['last_run']).total_seconds()
            dep_duration = dep_schedule.get('estimated_duration', 60)
            adjusted_duration = dep_duration * self.metrics['load_factor']
            settle = min(max(adjusted_duration, 15.0), float(AUTOMATION_DEPENDENCY_SETTLE_CAP_SEC))
            if time_since_dep < settle:
                return False

        return True
    
    def _can_run_parallel(self, task_name: str) -> bool:
        """Check if task can run in parallel with other tasks"""
        schedule = self.schedules.get(task_name, {})
        return 'parallel_group' in schedule
    
    def _get_parallel_group_tasks(self, parallel_group: str) -> List[str]:
        """Get all tasks in a parallel group"""
        parallel_tasks = []
        for task_name, schedule in self.schedules.items():
            if schedule.get('parallel_group') == parallel_group and schedule.get('enabled', True):
                parallel_tasks.append(task_name)
        return parallel_tasks
    
    async def _execute_parallel_phase(self, parallel_group: str) -> Dict[str, Any]:
        """Execute all tasks in a parallel group simultaneously"""
        try:
            parallel_tasks = self._get_parallel_group_tasks(parallel_group)
            if not parallel_tasks:
                return {'success': True, 'completed_tasks': [], 'errors': []}
            
            logger.info(f"Executing parallel phase '{parallel_group}' with tasks: {parallel_tasks}")
            
            # Create tasks for parallel execution
            parallel_execution_tasks = []
            for task_name in parallel_tasks:
                if self._can_run_parallel(task_name):
                    task = Task(
                        id=f"{task_name}_{int(time.time())}",
                        name=task_name,
                        priority=self.schedules[task_name].get('priority', TaskPriority.NORMAL),
                        status=TaskStatus.PENDING,
                        created_at=datetime.now(timezone.utc)
                    )
                    parallel_execution_tasks.append(self._execute_task(task, f"parallel_{parallel_group}"))
            
            # Execute all tasks in parallel
            results = await asyncio.gather(*parallel_execution_tasks, return_exceptions=True)
            
            # Process results
            completed_tasks = []
            errors = []
            
            for i, result in enumerate(results):
                task_name = parallel_tasks[i]
                if isinstance(result, Exception):
                    errors.append(f"Task {task_name} failed: {str(result)}")
                    logger.error(f"Parallel task {task_name} failed: {result}")
                else:
                    completed_tasks.append(task_name)
                    logger.info(f"Parallel task {task_name} completed successfully")
            
            logger.info(f"Parallel phase '{parallel_group}' completed: {len(completed_tasks)}/{len(parallel_tasks)} tasks successful")
            
            return {
                'success': len(errors) == 0,
                'completed_tasks': completed_tasks,
                'errors': errors,
                'parallel_group': parallel_group
            }
            
        except Exception as e:
            logger.error(f"Error executing parallel phase '{parallel_group}': {e}")
            return {
                'success': False,
                'error': str(e),
                'completed_tasks': [],
                'errors': [str(e)]
            }
    
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
            
            # Update max concurrent tasks based on allocation
            self.max_concurrent_tasks = self.resource_allocation.max_parallel_tasks
            
            logger.info(f"Resource allocation updated: {self.max_concurrent_tasks} max parallel tasks")
            
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
        if not self.metrics['adaptive_timing']:
            return base_interval
        
        # Get processing history for this task
        history = self.metrics['processing_history'].get(task_name, [])
        if len(history) < 3:  # Need at least 3 data points
            return base_interval
        
        # Calculate average processing time vs estimated
        recent_times = history[-5:]  # Last 5 runs
        avg_actual = sum(recent_times) / len(recent_times)
        estimated = self.schedules[task_name].get('estimated_duration', 60)
        
        # Calculate load factor
        load_ratio = avg_actual / estimated if estimated > 0 else 1.0
        
        # Adjust interval based on load
        if load_ratio > 1.5:  # Processing taking 50% longer than estimated
            self.metrics['load_factor'] = min(2.0, self.metrics['load_factor'] * 1.1)
        elif load_ratio < 0.8:  # Processing faster than estimated
            self.metrics['load_factor'] = max(0.5, self.metrics['load_factor'] * 0.95)
        
        # Apply load factor to interval
        adjusted_interval = int(base_interval * self.metrics['load_factor'])
        
        # Ensure minimum interval (at least 2x estimated duration)
        min_interval = max(60, estimated * 2)
        # Cap at 1.5x base so we don't slow down too much during full-time runs
        max_interval = int(base_interval * 1.5)
        return min(max(adjusted_interval, min_interval), max_interval)
    
    def _update_processing_history(self, task_name: str, actual_duration: float):
        """Update processing history for adaptive timing"""
        if task_name not in self.metrics['processing_history']:
            self.metrics['processing_history'][task_name] = []
        
        # Keep only last 10 runs
        history = self.metrics['processing_history'][task_name]
        history.append(actual_duration)
        if len(history) > 10:
            history.pop(0)
        
        self.metrics['processing_history'][task_name] = history
    
    def _get_input_volume_factor(self) -> float:
        """Calculate input volume factor based on recent article counts"""
        try:
            conn = self._get_db_connection_sync()
            if not conn:
                return 1.0
            try:
                with conn.cursor() as cursor:
                    recent_count = 0
                    for schema in _SCHEMAS:
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
        
        # Priority hierarchy: yield to web page loads — skip Ollama tasks when API is active
        _OLLAMA_TASKS = {
            'topic_clustering', 'ml_processing', 'entity_extraction', 'sentiment_analysis',
            'storyline_processing', 'rag_enhancement',
            'event_extraction', 'event_deduplication', 'story_continuation', 'watchlist_alerts',
            'quality_scoring', 'timeline_generation',
            'claim_extraction', 'event_tracking', 'entity_profile_build', 'entity_position_tracker',
            'editorial_document_generation', 'editorial_briefing_generation', 'story_enhancement',
            'content_refinement_queue',
            'storyline_synthesis', 'daily_briefing_synthesis',             'document_processing',  # v7
            'content_refinement_queue',
        }
        if task.name in _OLLAMA_TASKS:
            try:
                from shared.services.api_request_tracker import should_yield_to_api
                if should_yield_to_api():
                    logger.debug(f"Yielding to API — deferring {task.name} (web page load takes priority)")
                    task.status = TaskStatus.PENDING
                    await self.task_queue.put(task)  # Re-queue for next cycle when API is idle
                    await asyncio.sleep(5)  # Avoid tight loop — wait before worker picks next task
                    return
            except ImportError:
                pass
            # GPU temperature throttle: pause Ollama work if GPU is too hot
            try:
                from shared.gpu_metrics import should_throttle_ollama, get_gpu_metrics, GPU_THROTTLE_SLEEP_SECONDS
                if should_throttle_ollama():
                    metrics = get_gpu_metrics()
                    temp = metrics.get("gpu_temperature_c")
                    logger.warning(
                        "GPU temp %s C >= 82 C — pausing Ollama task %s for %ss to cool",
                        temp, task.name, GPU_THROTTLE_SLEEP_SECONDS,
                    )
                    await asyncio.sleep(GPU_THROTTLE_SLEEP_SECONDS)
                    if should_throttle_ollama():
                        logger.warning("GPU still hot after pause — deferring %s", task.name)
                        task.status = TaskStatus.PENDING
                        await self.task_queue.put(task)
                        return
            except ImportError:
                pass
            await self.ollama_semaphore.acquire()

        logger.info(f"Worker {worker_id} executing task: {task.name}")
        self._running_tasks_by_phase[task.name] += 1
        try:
            from services.activity_feed_service import get_activity_feed
            feed = get_activity_feed()
            requested_id = (task.metadata or {}).get("requested_activity_id")
            if requested_id:
                feed.complete(requested_id, success=True)
            message = self._activity_message(task)
            feed.add_current(
                task.id,
                message,
                task_name=task.name,
                domain=task.metadata.get("domain"),
                storyline_id=task.metadata.get("storyline_id"),
            )
        except Exception as e:
            logger.debug("Activity feed add_current: %s", e)

        try:
            # Execute task based on type
            if task.name == 'collection_cycle':
                self._collection_cycle_started_at = task.started_at
                asyncio.create_task(self._run_collection_watchdog(task.started_at))
                await self._execute_collection_cycle(task)
            elif task.name == 'document_processing':
                await self._execute_document_processing(task)
            elif task.name == 'storyline_synthesis':
                await self._execute_storyline_synthesis(task)
            elif task.name == 'daily_briefing_synthesis':
                await self._execute_daily_briefing_synthesis(task)
            elif task.name == 'context_sync':
                await self._execute_context_sync(task)
            elif task.name == 'entity_profile_sync':
                await self._execute_entity_profile_sync(task)
            elif task.name == 'claim_extraction':
                await self._execute_claim_extraction(task)
            elif task.name == 'claims_to_facts':
                await self._execute_claims_to_facts(task)
            elif task.name == 'event_tracking':
                await self._execute_event_tracking(task)
            elif task.name == 'investigation_report_refresh':
                await self._execute_investigation_report_refresh(task)
            elif task.name == 'cross_domain_synthesis':
                await self._execute_cross_domain_synthesis(task)
            elif task.name == 'event_coherence_review':
                await self._execute_event_coherence_review(task)
            elif task.name == 'entity_profile_build':
                await self._execute_entity_profile_build(task)
            elif task.name == 'pattern_recognition':
                await self._execute_pattern_recognition(task)
            elif task.name == 'entity_dossier_compile':
                await self._execute_entity_dossier_compile(task)
            elif task.name == 'entity_position_tracker':
                await self._execute_entity_position_tracker(task)
            elif task.name == 'metadata_enrichment':
                await self._execute_metadata_enrichment(task)
            elif task.name == 'entity_organizer':
                await self._execute_entity_organizer(task)
            elif task.name == 'digest_generation':
                await self._execute_digest_generation(task)
            elif task.name == 'data_cleanup':
                await self._execute_data_cleanup(task)
            elif task.name == 'health_check':
                await self._execute_health_check(task)
            elif task.name == 'pending_db_flush':
                await self._execute_pending_db_flush(task)
            elif task.name == 'rag_enhancement':
                await self._execute_rag_enhancement(task)
            elif task.name == 'cache_cleanup':
                await self._execute_cache_cleanup(task)
            elif task.name == 'ml_processing':
                await self._execute_ml_processing(task)
            elif task.name == 'sentiment_analysis':
                await self._execute_sentiment_analysis(task)
            elif task.name == 'storyline_processing':
                await self._execute_storyline_processing(task)
            elif task.name == 'storyline_automation':
                await self._execute_storyline_automation(task)
            elif task.name == 'storyline_enrichment':
                await self._execute_storyline_enrichment(task)
            elif task.name == 'entity_extraction':
                await self._execute_entity_extraction(task)
            elif task.name == 'quality_scoring':
                await self._execute_quality_scoring(task)
            elif task.name == 'timeline_generation':
                await self._execute_timeline_generation(task)
            elif task.name == 'topic_clustering':
                await self._execute_topic_clustering(task)
            elif task.name == 'event_extraction':
                await self._execute_event_extraction_v5(task)
            elif task.name == 'event_deduplication':
                await self._execute_event_deduplication_v5(task)
            elif task.name == 'story_continuation':
                await self._execute_story_continuation_v5(task)
            elif task.name == 'watchlist_alerts':
                await self._execute_watchlist_alerts_v5(task)
            elif task.name == 'story_enhancement':
                await self._execute_story_enhancement(task)
            elif task.name == 'content_refinement_queue':
                await self._execute_content_refinement_queue(task)
            elif task.name == 'entity_enrichment':
                await self._execute_entity_enrichment(task)
            elif task.name == 'pattern_matching':
                await self._execute_pattern_matching(task)
            elif task.name == 'research_topic_refinement':
                await self._execute_research_topic_refinement(task)
            elif task.name == 'editorial_document_generation':
                await self._execute_editorial_document_generation(task)
            elif task.name == 'editorial_briefing_generation':
                await self._execute_editorial_briefing_generation(task)
            elif task.name == 'narrative_thread_build':
                await self._execute_narrative_thread_build(task)
            elif task.name == 'storyline_discovery':
                await self._execute_storyline_discovery(task)
            elif task.name == 'proactive_detection':
                await self._execute_proactive_detection(task)
            elif task.name == 'fact_verification':
                await self._execute_fact_verification(task)
            else:
                raise ValueError(f"Unknown task type: {task.name}")
            
            # Mark as completed
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc)
            self.metrics['tasks_completed'] += 1
            if task.name in self.schedules:
                self.schedules[task.name]['last_run'] = task.completed_at
            self._last_completed_at_by_phase[task.name] = task.completed_at
            _persist_automation_run(task.name, task.started_at, task.completed_at, True, None)
            # Record completion for last-60m run counts (used by monitoring timeline).
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(minutes=60)
                dq = self._phase_run_times_last_60m[task.name]
                dq.append(task.completed_at)
                while dq and dq[0] < cutoff:
                    dq.popleft()
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

            logger.info(f"Task {task.name} completed in {processing_time:.2f}s (Phase {task.metadata.get('phase', 0)})")

            # Continuous iteration: when work remains, queue next run (v8: capped per analysis window)
            if task.name in BATCH_PHASES_CONTINUOUS:
                try:
                    current = self._requeue_counts.get(task.name, 0)
                    if current >= self._max_requeue_per_window:
                        logger.debug("Re-enqueue cap reached for %s (%s)", task.name, self._max_requeue_per_window)
                    elif await self._has_pending_work(task.name):
                        if self._scheduled_enqueue_paused() and task.name not in QUEUE_PAUSE_ALLOW_SCHEDULED:
                            logger.debug(
                                "Queue soft cap: skip continuous re-queue for %s (depth=%s)",
                                task.name,
                                self._automation_queue_depth(),
                            )
                        else:
                            next_task = Task(
                                id=f"{task.name}_{int(task.completed_at.timestamp())}_next",
                                name=task.name,
                                priority=self.schedules[task.name].get("priority", TaskPriority.NORMAL),
                                status=TaskStatus.PENDING,
                                created_at=task.completed_at,
                                metadata={
                                    "scheduled": True,
                                    "phase": self.schedules[task.name].get("phase", 0),
                                    "estimated_duration": self.schedules[task.name].get("estimated_duration", 60),
                                    "continuous": True,
                                },
                            )
                            await self.task_queue.put(next_task)
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
            if ENRICHMENT_BACKLOG_FIRST_ENABLED and get_all_backlog_counts and task.name == "content_enrichment":
                try:
                    counts = get_all_backlog_counts()
                    enrichment_backlog = counts.get("content_enrichment", 0) or 0
                except Exception:
                    pass
            for other_name, other_sched in self.schedules.items():
                if not other_sched.get("enabled", True):
                    continue
                deps = other_sched.get("depends_on") or []
                if task.name in deps:
                    if enrichment_backlog > 0 and other_name not in ENRICHMENT_BACKLOG_FIRST_WHITELIST:
                        logger.info("Chained: skipping %s (enrichment backlog first, %s articles pending)", other_name, enrichment_backlog)
                        continue
                    if self._scheduled_enqueue_paused() and other_name not in QUEUE_PAUSE_ALLOW_SCHEDULED:
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
            self.metrics['tasks_failed'] += 1
            finished_at = datetime.now(timezone.utc)
            if task.name in self.schedules:
                self.schedules[task.name]['last_run'] = finished_at
            _persist_automation_run(task.name, task.started_at, finished_at, False, str(e))
            # Record failure for last-60m run counts (used by monitoring timeline).
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(minutes=60)
                dq = self._phase_run_times_last_60m[task.name]
                dq.append(finished_at)
                while dq and dq[0] < cutoff:
                    dq.popleft()
            except Exception:
                pass

            logger.error(f"Task {task.name} failed: {e}")
            
            # Retry if under max retries
            if task.retry_count < task.max_retries:
                task.status = TaskStatus.RETRYING
                await asyncio.sleep(min(60 * task.retry_count, 300))  # Exponential backoff
                await self.task_queue.put(task)
                logger.info(f"Retrying task {task.name} (attempt {task.retry_count + 1})")
        
        finally:
            # Keep per-phase worker counts in sync even when task fails.
            try:
                if self._running_tasks_by_phase.get(task.name, 0) > 0:
                    self._running_tasks_by_phase[task.name] -= 1
            except Exception:
                pass
            if task.name in _OLLAMA_TASKS:
                self.ollama_semaphore.release()
            try:
                from services.activity_feed_service import get_activity_feed
                get_activity_feed().complete(
                    task.id,
                    success=(task.status == TaskStatus.COMPLETED),
                    error_message=getattr(task, "error_message", None),
                )
            except Exception as e:
                logger.debug("Activity feed complete: %s", e)
            # Store task result
            self.tasks[task.id] = task

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
        if name == "event_tracking":
            return f"Tracking events ({domain or 'all'})"
        if name == "cross_domain_synthesis":
            return "Cross-domain synthesis"
        if name == "narrative_thread_build":
            return "Building narrative threads (cross-storyline arcs)"
        if name == "entity_organizer":
            return "Entity organizer (cleanup + relationships)"
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
        from collectors.rss_collector import collect_rss_feeds
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            added = await loop.run_in_executor(None, collect_rss_feeds)
            if added > 0:
                logger.info(f"RSS processing: {added} articles collected from domain feeds")
        except Exception as e:
            logger.warning(f"RSS processing failed: {e}")

    async def _execute_content_enrichment(self, task: Task):
        """v7: Fetch full article text with trafilatura for articles with short content."""
        import asyncio
        from services.article_content_enrichment_service import enrich_articles_batch
        try:
            loop = asyncio.get_event_loop()
            # Burst (48h catch-up): batch 60; revert to 40 after
            await loop.run_in_executor(None, lambda: enrich_articles_batch(batch_size=60))
        except Exception as e:
            logger.warning(f"Content enrichment failed: {e}")

    async def _execute_document_collection(self, task: Task):
        """v7: Discover government and academic PDF documents."""
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
        """v7: Process pending PDFs (download, extract text, sections, entities)."""
        import asyncio
        try:
            from services.document_processing_service import process_unprocessed_documents
            from services.backlog_metrics import get_backlog_count
            # Process more per run when backlog is large (batch 10 + backlog over 20 → limit 25)
            backlog = get_backlog_count("document_processing") or 0
            limit = 25 if backlog > 20 else 15 if backlog > 10 else 10
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: process_unprocessed_documents(limit=limit))
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
        loop = asyncio.get_event_loop()
        dummy = Task(
            id=task.id + "_sub",
            name=task.name,
            priority=task.priority,
            status=TaskStatus.PENDING,
            created_at=task.created_at,
            metadata=task.metadata or {},
        )
        # 1. RSS fetch
        try:
            await self._execute_rss_processing(dummy)
        except Exception as e:
            logger.warning(f"Collection cycle RSS step failed: {e}")
        # 2. Content enrichment — loop until drained or cap
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
        # 3. Document collection
        try:
            await self._execute_document_collection(dummy)
        except Exception as e:
            logger.warning(f"Collection cycle document collection failed: {e}")
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
        while self._pending_collection_queue:
            req = self._pending_collection_queue.pop(0)
            drained += 1
            try:
                req_type = req.get("type") or "url"
                url = req.get("url") or ""
                source = req.get("source") or ""
                if req_type == "url" and url:
                    # Optional: add URL to document ingest or RSS; for now just log
                    logger.info("Collection cycle drained request: type=%s url=%s source=%s", req_type, url[:80], source)
            except Exception as e:
                logger.debug("Pending collection item failed: %s", e)
        if drained:
            logger.info("Collection cycle drained %s pending collection request(s)", drained)

    async def _execute_storyline_synthesis(self, task: Task):
        """v7: Auto-synthesize storylines (Wikipedia-style) that have 3+ articles."""
        import asyncio
        try:
            from services.deep_content_synthesis import DeepContentSynthesisService
            svc = DeepContentSynthesisService()
            loop = asyncio.get_event_loop()

            for domain_key, schema in (("politics", "politics"), ("finance", "finance"), ("science-tech", "science_tech")):
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
                            lambda d=domain_key, sid=storyline_id: svc.synthesize_storyline_content(d, sid, depth="standard", save_to_db=True),
                        )
                        logger.info(f"Storyline synthesis (v8): {domain_key} storyline {storyline_id}")
                    except Exception as e:
                        logger.warning(f"Storyline synthesis {storyline_id} failed: {e}")
        except Exception as e:
            logger.warning(f"Storyline synthesis phase failed: {e}")

    async def _execute_daily_briefing_synthesis(self, task: Task):
        """v7: Generate breaking-news synthesis per domain for briefing page."""
        import asyncio
        try:
            from services.deep_content_synthesis import DeepContentSynthesisService
            svc = DeepContentSynthesisService()
            loop = asyncio.get_event_loop()
            for domain_key in ("politics", "finance", "science-tech"):
                try:
                    await loop.run_in_executor(
                        None,
                        lambda d=domain_key: svc.synthesize_breaking_news(d, hours=72, min_articles=3),  # v8
                    )
                    logger.info(f"Daily briefing synthesis (v8): {domain_key}")
                except Exception as e:
                    logger.warning(f"Daily briefing synthesis {domain_key} failed: {e}")
        except Exception as e:
            logger.warning(f"Daily briefing synthesis phase failed: {e}")

    async def _execute_context_sync(self, task: Task):
        """Backfill: sync domain articles to intelligence.contexts (Phase 1.2 context-centric)."""
        try:
            from config.context_centric_config import is_context_centric_task_enabled
            if not is_context_centric_task_enabled("context_sync"):
                return
        except Exception:
            pass
        from services.context_processor_service import sync_domain_articles_to_contexts
        import asyncio

        for domain_key in ("politics", "finance", "science-tech"):
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
        from services.entity_profile_sync_service import sync_domain_entity_profiles
        import asyncio

        for domain_key in ("politics", "finance", "science-tech"):
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
        from services.claim_extraction_service import run_claim_extraction_batch
        try:
            # Production: max 50 contexts (LLM rate limits), ~20-50s, parallel_requests in service
            total = await run_claim_extraction_batch(limit=50)
            if total > 0:
                logger.info(f"Claim extraction: {total} claims inserted")
        except Exception as e:
            logger.warning(f"Claim extraction failed: {e}")

    async def _execute_claims_to_facts(self, task: Task):
        """Promote high-confidence extracted_claims to versioned_facts (activates story state chain)."""
        from services.claim_extraction_service import promote_claims_to_versioned_facts
        try:
            promoted = await asyncio.to_thread(promote_claims_to_versioned_facts, 0.7, 100)
            if promoted > 0:
                logger.info(f"Claims to facts: {promoted} claims promoted to versioned_facts")
        except Exception as e:
            logger.warning(f"Claims to facts failed: {e}")

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
                logger.info(
                    f"Investigation report refresh: {created} new, {refreshed} updated"
                )
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
                time_window_days=30,  # v8: full-history
                correlation_threshold=0.5,
            )
            if result.get("correlations"):
                logger.info(f"Cross-domain synthesis: {len(result['correlations'])} correlation(s) written")
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
                logger.info(f"Event coherence review: {removed} contexts removed from {reviewed} events")
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
        from services.dossier_compiler_service import _run_scheduled_dossier_compiles
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            compiled = await loop.run_in_executor(
                self._executor,
                _run_scheduled_dossier_compiles,
                20,   # max_dossiers_per_run
                None, # get_db_connection_fn -> use default
                7,    # stale_days
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
                None,   # domain_key -> all domains
                5,     # min_mentions
                8,     # max_entities
                25,    # max_articles_per_entity (v8)
            )
            total = sum(
                r.get("total_positions", 0)
                for r in (results or {}).values()
                if isinstance(r, dict)
            )
            if total > 0:
                logger.info("Entity position tracker: %s positions extracted", total)
        except Exception as e:
            logger.warning("Entity position tracker failed: %s", e)

    async def _execute_metadata_enrichment(self, task: Task):
        """Run metadata enrichment batch for domain articles (language, categories, sentiment, quality)."""
        try:
            from services.metadata_enrichment_service import run_metadata_enrichment_batch_for_domains
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
            result = await run_enhancement_cycle(fact_batch=100, queue_batch=10, enrich_limit=10, build_limit=10)
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
        from services.content_refinement_queue_service import process_content_refinement_queue_batch
        try:
            stats = await process_content_refinement_queue_batch()
            if stats.get("processed", 0) > 0 or stats.get("failed", 0) > 0:
                logger.info(
                    "Content refinement queue: processed=%s failed=%s by_type=%s",
                    stats.get("processed"),
                    stats.get("failed"),
                    stats.get("by_type"),
                )
        except Exception as e:
            logger.warning("Content refinement queue failed: %s", e)

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
            result = await loop.run_in_executor(None, lambda: run_pattern_matching_all_domains(limit_per_domain=30))
            if result.get("matches_stored", 0) > 0 or result.get("alerts_created", 0) > 0:
                logger.info("Pattern matching: matches_stored=%s alerts_created=%s", result.get("matches_stored", 0), result.get("alerts_created", 0))
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
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, query, topic, date_range_start, date_range_end
                    FROM finance.research_topics
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
            from domains.finance.orchestrator_types import TaskType, TaskPriority as FinTaskPriority
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
                    """
                    UPDATE finance.research_topics
                    SET last_refined_task_id = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (task_id, topic_id),
                )
            conn.commit()
            logger.info(
                "Research topic refinement: topic_id=%s submitted as task_id=%s (low priority)",
                topic_id, task_id,
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
                    total_actions, rel,
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
                lambda: run_resolution_batch(auto_merge_confidence=0.9, cross_domain_confidence=0.8),
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
                        total_actions, rel,
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
        from services.pattern_recognition_service import run_pattern_discovery_batch
        import asyncio
        try:
            total = await asyncio.get_event_loop().run_in_executor(None, run_pattern_discovery_batch)
            if total > 0:
                logger.info(f"Pattern recognition: {total} patterns discovered")
        except Exception as e:
            logger.warning(f"Pattern recognition failed: {e}")
        
    async def _execute_editorial_document_generation(self, task: Task):
        """Generate/refine editorial_document for active storylines across all domains."""
        from services.editorial_document_service import generate_storyline_editorial
        for domain in ("politics", "finance", "science-tech"):
            try:
                result = await generate_storyline_editorial(domain, limit=5)
                logger.info("Editorial doc generation (%s): %s", domain, result)
            except Exception as e:
                logger.warning("editorial_document_generation (%s): %s", domain, e)

    async def _execute_editorial_briefing_generation(self, task: Task):
        """Generate/refine editorial_briefing for tracked events."""
        from services.editorial_document_service import generate_event_editorial
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
        for domain in ("politics", "finance", "science-tech"):
            try:
                result = await loop.run_in_executor(None, lambda d=domain: build_threads_for_domain(d, limit=30))
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
                    for schema in _SCHEMAS:
                        cursor.execute(f"""
                            DELETE FROM {schema}.articles
                            WHERE published_at < %s AND created_at < %s
                        """, (cutoff_date, cutoff_date))
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
        """Execute health check task"""
        # Check database connectivity
        try:
            conn = await self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            conn.close()
            
            self.metrics['last_health_check'] = datetime.now(timezone.utc)
            logger.debug("Health check passed")
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            raise
    
    async def _health_monitor(self):
        """Monitor system health"""
        logger.info("Health monitor started")
        
        while self.is_running:
            try:
                # Check worker health
                active_workers = sum(1 for worker in self.workers if not worker.done())
                
                if active_workers < self.max_concurrent_tasks:
                    logger.warning(f"Only {active_workers} workers active, expected {self.max_concurrent_tasks}")
                
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
                self.metrics['system_uptime'] = time.time()
                
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
        if self.metrics['avg_processing_time'] == 0:
            self.metrics['avg_processing_time'] = new_time
        else:
            # Exponential moving average
            alpha = 0.1
            self.metrics['avg_processing_time'] = (
                alpha * new_time + (1 - alpha) * self.metrics['avg_processing_time']
            )
    
    async def _execute_rag_enhancement(self, task: Task):
        """Execute RAG enhancement per domain (v8): enhance storylines with Wikipedia/GDELT context, store by (domain, storyline_id)."""
        from services.rag import get_rag_service
        from shared.database.connection import get_db_connection

        rag_service = get_rag_service()
        enhanced_count = 0
        for domain in ("politics", "finance", "science_tech"):
            schema = domain.replace("-", "_")
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
                                        cur.execute(f"""
                                            SELECT id, title, content, summary, source_domain
                                            FROM {schema}.articles WHERE id = ANY(%s)
                                        """, (list(article_ids)[:30],))
                                        for r in cur.fetchall():
                                            articles_for_rag.append({
                                                "id": r[0], "title": r[1], "content": r[2] or "",
                                                "summary": r[3], "source": r[4],
                                            })
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
        logger.info("RAG enhancement completed: %s storylines enhanced (all domains)", enhanced_count)
        
    async def _execute_ml_processing(self, task: Task):
        """Execute ML processing task. Skips cleanly if column ml_processed is missing."""
        try:
            from modules.ml.background_processor import BackgroundMLProcessor

            ml_processor = BackgroundMLProcessor(self.db_config)

            processed_count = 0
            for schema in _SCHEMAS:
                conn = await self._get_db_connection()
                try:
                    with conn.cursor() as cursor:
                        cursor.execute(f"""
                            SELECT id FROM {schema}.articles
                            WHERE ml_processed = FALSE
                              AND content IS NOT NULL
                              AND LENGTH(content) > 100
                            ORDER BY created_at DESC
                            LIMIT 50
                        """)
                        articles = cursor.fetchall()
                finally:
                    conn.close()

                for article_id, in articles:
                    try:
                        ml_processor.queue_article_for_processing(article_id, 'full_analysis')
                        processed_count += 1
                    except Exception as e:
                        logger.error("Error processing article %s (%s): %s", article_id, schema, e)

            logger.info(f"ML processing completed: {processed_count} articles queued")
        except Exception as e:
            if "ml_processed" in str(e) and ("does not exist" in str(e) or "UndefinedColumn" in str(e)):
                logger.debug("ML processing skipped (column ml_processed not in schema): %s", e)
            else:
                raise
        
    async def _execute_sentiment_analysis(self, task: Task):
        """Execute sentiment analysis task"""
        from services.ai_processing_service import get_ai_service
        
        ai_service = get_ai_service()
        analyzed_count = 0

        for schema in _SCHEMAS:
            # Fetch candidates quickly, then close transaction before awaited LLM work.
            conn = await self._get_db_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute(f"""
                        SELECT id, content FROM {schema}.articles
                        WHERE sentiment_score IS NULL
                          AND content IS NOT NULL
                          AND LENGTH(content) > 50
                        ORDER BY created_at DESC
                        LIMIT 100
                    """)
                    articles = cursor.fetchall()
            finally:
                conn.close()

            for article_id, content in articles:
                try:
                    sentiment = await ai_service.analyze_sentiment(content)
                    score = sentiment.get('score', 0)
                    label = sentiment.get('label', '')

                    # Persist each result in a short-lived transaction.
                    write_conn = await self._get_db_connection()
                    try:
                        with write_conn.cursor() as write_cur:
                            write_cur.execute(f"""
                                UPDATE {schema}.articles
                                SET sentiment_score = %s,
                                    sentiment_label = COALESCE(%s, sentiment_label),
                                    updated_at = CURRENT_TIMESTAMP
                                WHERE id = %s
                            """, (score, label or None, article_id))
                            write_conn.commit()
                        analyzed_count += 1
                    finally:
                        write_conn.close()
                except Exception as e:
                    logger.error("Error analyzing sentiment for article %s (%s): %s", article_id, schema, e)
        
        logger.info(f"Sentiment analysis completed: {analyzed_count} articles analyzed")
        
    async def _execute_storyline_processing(self, task: Task):
        """Execute storyline processing per domain: generates analysis_summary, seeds editorial_document.
        Uses domain-aware StorylineService so politics/finance/science_tech storylines get narratives."""
        from domains.storyline_management.services.storyline_service import StorylineService as DomainStorylineService
        from shared.database.connection import get_db_connection

        processed_count = 0
        for domain in ("politics", "finance", "science_tech"):
            schema = domain.replace("-", "_")
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
                    sid, title, analysis_summary, master_summary, has_ed = row[0], row[1], row[2] or "", row[3] or "", row[4]
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
                                                    cur.execute(f"""
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
                                                    """, (summary_text, summary_text, sid))
                                                conn.commit()
                                            finally:
                                                conn.close()
                                    except Exception as ed_err:
                                        logger.debug("Seed editorial_document %s/%s: %s", domain, sid, ed_err)
                        except Exception as e:
                            logger.error("Error processing storyline %s/%s: %s", domain, sid, e)
            except Exception as e:
                logger.warning("Storyline processing domain %s: %s", domain, e)

        logger.info("Storyline processing completed: %s storylines processed (all domains)", processed_count)

    async def _execute_storyline_automation(self, task: Task):
        """Run RAG discovery for one storyline (from metadata) or all automation-enabled storylines."""
        from services.storyline_automation_service import StorylineAutomationService
        meta = task.metadata or {}
        storyline_id = meta.get("storyline_id")
        domain = meta.get("domain")
        if storyline_id and domain:
            try:
                svc = StorylineAutomationService(domain=domain)
                result = await svc.discover_articles_for_storyline(storyline_id, force_refresh=False)
                count = len(result.get("articles", []))
                logger.info("Storyline automation: storyline_id=%s domain=%s discovered %s articles", storyline_id, domain, count)
            except Exception as e:
                logger.warning("Storyline automation failed for storyline_id=%s: %s", storyline_id, e)
        else:
            # Run for all automation-enabled storylines (each domain)
            for d in ("politics", "finance", "science_tech"):
                try:
                    svc = StorylineAutomationService(domain=d)
                    conn = await self._get_db_connection()
                    schema = d.replace("-", "_")
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
                    storyline_id, domain, count,
                )
            except Exception as e:
                logger.warning("Storyline enrichment failed for storyline_id=%s: %s", storyline_id, e)
        else:
            for d in ("politics", "finance", "science_tech"):
                try:
                    svc = StorylineAutomationService(domain=d)
                    conn = await self._get_db_connection()
                    schema = d.replace("-", "_")
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
        Runs AIStorylineDiscovery.discover_storylines() for each domain, creating new
        storylines from high-similarity article clusters that aren't already tracked."""
        import asyncio
        try:
            from services.ai_storyline_discovery import get_discovery_service
            service = get_discovery_service()
            total_created = 0
            for domain in ("politics", "finance", "science-tech"):
                try:
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        None,
                        lambda d=domain: service.discover_storylines(
                            domain=d, hours=168, save_to_db=True
                        ),
                    )
                    saved = len(result.get("saved_storylines", []))
                    clusters = result.get("summary", {}).get("clusters_found", 0)
                    total_created += saved
                    if saved > 0:
                        logger.info(
                            "Storyline discovery [%s]: %d clusters → %d new storylines",
                            domain, clusters, saved,
                        )
                except Exception as e:
                    logger.warning("Storyline discovery failed for %s: %s", domain, e)
            logger.info("Storyline discovery complete: %d new storylines created", total_created)
        except Exception as e:
            logger.warning("Storyline discovery task failed: %s", e)

    async def _execute_proactive_detection(self, task: Task):
        """v8: Detect emerging storylines from unlinked articles (per domain)."""
        try:
            from domains.storyline_management.services.proactive_detection_service import ProactiveDetectionService
            for domain in ("politics", "finance", "science-tech"):
                try:
                    svc = ProactiveDetectionService(domain=domain)
                    result = await svc.detect_emerging_storylines(hours=72, min_articles=3)
                    if result.get("success"):
                        d = result.get("data") or {}
                        if d.get("stored_count", 0) > 0 or d.get("promoted_to_domain_storylines", 0) > 0:
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
        """v8: Verify recent claims per domain; write corroboration/contradiction to extracted_claims."""
        try:
            from services.fact_verification_service import verify_recent_claims
            loop = asyncio.get_event_loop()
            for domain in ("politics", "finance", "science-tech"):
                try:
                    result = await loop.run_in_executor(
                        self._executor,
                        lambda d=domain: verify_recent_claims(d, hours=72, limit=20),
                    )
                    if result.get("success") and result.get("claims_verified", 0) > 0:
                        logger.info(
                            "Fact verification [%s]: %s claims verified",
                            domain, result["claims_verified"],
                        )
                except Exception as e:
                    logger.debug("Fact verification failed for %s: %s", domain, e)
        except Exception as e:
            logger.warning("Fact verification task failed: %s", e)

    async def _execute_entity_extraction(self, task: Task):
        """Execute entity extraction via ArticleEntityExtractionService.

        Routes through the canonical extraction pipeline which does:
        LLM extraction → canonical resolution → Wikipedia backfill → article_entities storage.
        Processes all three domain schemas.
        """
        from services.article_entity_extraction_service import ArticleEntityExtractionService

        extractor = ArticleEntityExtractionService()
        domains = [("politics", "politics"), ("finance", "finance"), ("science-tech", "science_tech")]
        extracted_count = 0

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
                          AND a.content IS NOT NULL
                          AND LENGTH(a.content) > 100
                          AND (LENGTH(a.content) >= 500 OR a.created_at < NOW() - INTERVAL '2 hours')
                        ORDER BY a.created_at DESC
                        LIMIT 20
                    """)
                    domain_articles[schema_name] = cursor.fetchall()
                except Exception as e:
                    logger.warning("Entity extraction query for %s: %s", schema_name, e)
                    domain_articles[schema_name] = []
        finally:
            cursor.close()
            conn.close()

        for domain_key, schema_name in domains:
            for article_id, title, content in domain_articles.get(schema_name, []):
                try:
                    result = await extractor.extract_and_store(
                        article_id=article_id,
                        title=title or "",
                        content=content,
                        schema=schema_name,
                    )
                    if result.get("success"):
                        extracted_count += 1
                except Exception as e:
                    logger.error("Entity extraction for article %s (%s): %s", article_id, domain_key, e)

        logger.info(f"Entity extraction completed: {extracted_count} articles processed across domains")

    async def _execute_event_extraction_v5(self, task: Task):
        """v5.0 -- Extract structured events with temporal grounding from domain articles."""
        try:
            from services.event_extraction_service import EventExtractionService

            svc = EventExtractionService()
            conn = await self._get_db_connection()
            cursor = conn.cursor()

            try:
                total_events = 0
                total_articles = 0

                for schema in _SCHEMAS:
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
                          AND a.content IS NOT NULL
                          AND LENGTH(a.content) > 100
                          AND (
                              a.processing_status = 'completed'
                              OR a.enrichment_status IN ('completed', 'enriched')
                          )
                        ORDER BY a.published_at DESC NULLS LAST
                        LIMIT 30
                    """)
                    articles = cursor.fetchall()
                    total_articles += len(articles)

                    for article_id, content, pub_date, storyline_id in articles:
                        try:
                            if pub_date is None:
                                pub_date = datetime.now(timezone.utc)
                            events = await svc.extract_events_from_article(
                                article_id=article_id,
                                content=content,
                                pub_date=pub_date,
                                storyline_id=storyline_id,
                                domain=schema.replace("_", "-"),
                            )
                            saved = await svc.save_events(events, conn)
                            total_events += saved

                            cursor.execute(f"""
                                UPDATE {schema}.articles
                                SET timeline_processed = true,
                                    timeline_events_generated = %s,
                                    updated_at = CURRENT_TIMESTAMP
                                WHERE id = %s
                            """, (len(events), article_id))
                            conn.commit()
                        except Exception as e:
                            logger.error("Event extraction failed for %s article %s: %s", schema, article_id, e)
                            conn.rollback()

                logger.info(
                    "v5 event extraction completed: %s events from %s articles across %s schemas",
                    total_events,
                    total_articles,
                    len(_SCHEMAS),
                )
            finally:
                cursor.close()
                conn.close()
                await svc.close()
        except Exception as e:
            if ("timeline_processed" in str(e) or "chronological_events" in str(e)) and "does not exist" in str(e):
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
                logger.debug("Event deduplication skipped (chronological_events not migrated): %s", e)
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
            for schema in ("politics", "finance", "science_tech"):
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
                            schema, stats["checked"], stats["linked"], stats["flagged"],
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
            logger.info(
                f"v5 watchlist alerts: {reactivation} reactivation, {new_events} new-event"
            )
        except Exception as e:
            if "does not exist" in str(e) or "relation" in str(e).lower():
                logger.debug("Watchlist alerts skipped (watchlist/chronological_events not migrated): %s", e)
            else:
                logger.warning("Watchlist alerts failed: %s", e)
        finally:
            conn.close()

    async def _execute_quality_scoring(self, task: Task):
        """Execute quality scoring task"""
        from services.ai_processing_service import get_ai_service
        
        ai_service = get_ai_service()
        scored_count = 0

        for schema in _SCHEMAS:
            # Fetch candidates quickly, then close transaction before awaited LLM work.
            conn = await self._get_db_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute(f"""
                        SELECT id, content, title FROM {schema}.articles
                        WHERE quality_score IS NULL
                          AND content IS NOT NULL
                          AND LENGTH(content) > 100
                        ORDER BY created_at DESC
                        LIMIT 50
                    """)
                    articles = cursor.fetchall()
            finally:
                conn.close()

            for article_id, content, title in articles:
                try:
                    quality = await ai_service.score_article_quality(content, title)
                    write_conn = await self._get_db_connection()
                    try:
                        with write_conn.cursor() as write_cur:
                            write_cur.execute(f"""
                                UPDATE {schema}.articles
                                SET quality_score = %s, updated_at = CURRENT_TIMESTAMP
                                WHERE id = %s
                            """, (quality.get('score', 0), article_id))
                            write_conn.commit()
                        scored_count += 1
                    finally:
                        write_conn.close()
                except Exception as e:
                    logger.error("Error scoring quality for article %s (%s): %s", article_id, schema, e)
        
        logger.info(f"Quality scoring completed: {scored_count} articles scored")
        
    async def _execute_timeline_generation(self, task: Task):
        """Execute timeline generation per domain using public chronological_events + domain storylines."""
        from services.timeline_builder_service import TimelineBuilderService

        generated_count = 0

        for schema in _SCHEMAS:
            conn_sel = await self._get_db_connection()
            storyline_ids: List[int] = []
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
                    summary = (
                        f"Timeline ({len(events)} events): "
                        + " | ".join(parts[:12])
                    )
                    if len(summary) > 12000:
                        summary = summary[:11997] + "..."
                    with conn.cursor() as cur:
                        cur.execute(f"""
                            UPDATE {schema}.storylines
                            SET timeline_summary = %s, updated_at = NOW()
                            WHERE id = %s
                        """, (summary, sid))
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
            logger.info("🔄 Starting iterative topic clustering task with confidence-based prioritization (v5.0 - all domains)")
            
            # Import the topic clustering service
            from domains.content_analysis.services.topic_clustering_service import TopicClusteringService
            from shared.services.domain_aware_service import get_all_domains
            
            # Get all active domains
            domains = get_all_domains()
            if not domains:
                logger.warning("No active domains found, defaulting to 'politics'")
                domains = [{'domain_key': 'politics', 'schema_name': 'politics'}]
            
            # Topic clustering configuration constants
            CONFIDENCE_THRESHOLD = 0.93
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
                domain_key = domain_info['domain_key']
                schema_name = domain_info.get('schema_name', domain_key.replace('-', '_'))
                
                logger.info(f"📊 Processing domain: {domain_key} (schema: {schema_name})")
                
                # Initialize topic clustering service for this domain
                topic_service = TopicClusteringService(db_config, domain=domain_key)
                
                # Process articles incrementally with balanced prioritization
                conn = await self._get_db_connection()
                try:
                    cursor = conn.cursor()
                    try:
                        cursor.execute(f"""
                            WITH article_confidence AS (
                                SELECT 
                                    a.id,
                                    a.title,
                                    a.created_at,
                                    COUNT(ata.id) as assignment_count,
                                    COALESCE(AVG(ata.confidence_score), 0.0) as avg_confidence,
                                    COALESCE(MIN(ata.confidence_score), 0.0) as min_confidence,
                                    COALESCE(MAX(ata.confidence_score), 0.0) as max_confidence,
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
                                GROUP BY a.id, a.title, a.created_at
                            )
                            SELECT 
                                id,
                                title,
                                assignment_count,
                                avg_confidence,
                                min_confidence,
                                max_confidence,
                                priority_group,
                                created_at
                            FROM article_confidence
                            WHERE priority_group != 'high_confidence'  -- Exclude articles above threshold
                            ORDER BY 
                                CASE priority_group
                                    WHEN 'new' THEN 1
                                    WHEN 'low_confidence' THEN 2
                                    WHEN 'medium_confidence' THEN 3
                                END,
                                avg_confidence ASC,  -- Lower confidence first within each group
                                created_at DESC
                        """, (LOW_CONFIDENCE_THRESHOLD, CONFIDENCE_THRESHOLD))
                        all_articles = cursor.fetchall()
                    finally:
                        cursor.close()
                finally:
                    conn.close()

                if not all_articles:
                    logger.info(f"  ✅ No articles need topic clustering in {domain_key} (all above confidence threshold)")
                    continue
            
                # Balanced prioritization: Mix of new, low, and medium confidence articles
                # This ensures we process new articles while refining existing ones
                new_articles = [a for a in all_articles if a[6] == 'new']
                low_confidence = [a for a in all_articles if a[6] == 'low_confidence']
                medium_confidence = [a for a in all_articles if a[6] == 'medium_confidence']
                
                # Calculate balanced selection (40% new, 30% low, 30% medium)
                # This mix ensures:
                # - New articles get started (40%)
                # - Low confidence articles get refined (30%)
                # - Medium confidence articles graduate out (30%)
                target_count = BATCH_SIZE
                new_count = min(NEW_ARTICLE_COUNT, len(new_articles))  # 40% = 8 articles
                low_count = min(LOW_CONFIDENCE_COUNT, len(low_confidence))  # 30% = 6 articles
                medium_count = min(MEDIUM_CONFIDENCE_COUNT, len(medium_confidence))  # 30% = 6 articles
                
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
                        remaining_new = new_articles[new_count:new_count + remaining]
                        selected_articles.extend(remaining_new)
                        remaining -= len(remaining_new)
                    
                    # Then low confidence articles
                    if remaining > 0 and len(low_confidence) > low_count:
                        remaining_low = low_confidence[low_count:low_count + remaining]
                        selected_articles.extend(remaining_low)
                        remaining -= len(remaining_low)
                    
                    # Finally medium confidence articles
                    if remaining > 0 and len(medium_confidence) > medium_count:
                        remaining_medium = medium_confidence[medium_count:medium_count + remaining]
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
                    priority_group = article_data[6]
                    
                    try:
                        # Skip if already above threshold (safety check)
                        if current_avg_confidence >= CONFIDENCE_THRESHOLD:
                            logger.debug(f"  Article {article_id} already above threshold ({current_avg_confidence:.2f}), skipping")
                            continue
                        
                        result = await topic_service.process_article(article_id)
                        
                        if result.get('success'):
                            processed_count += 1
                            topics_created += len(result.get('created_topics', []))
                            topics_assigned += result.get('total_assigned', 0)
                            
                            # Check if article graduated (above threshold)
                            # Re-check confidence after processing
                            conn_check = await self._get_db_connection()
                            cursor_check = conn_check.cursor()
                            cursor_check.execute(f"""
                                SELECT COALESCE(AVG(confidence_score), 0.0) as avg_confidence
                                FROM {schema_name}.article_topic_assignments
                                WHERE article_id = %s
                            """, (article_id,))
                            result_row = cursor_check.fetchone()
                            new_confidence = float(result_row[0]) if result_row and result_row[0] else 0.0
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
                            logger.warning(f"  Failed to process article {article_id}: {result.get('error')}")
                            
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

    def _watchdog_required_phases(self) -> List[str]:
        """Flatten analysis pipeline steps and add document_processing for the 60-minute watchdog."""
        phases: List[str] = []
        for step in ANALYSIS_PIPELINE_STEPS:
            phases.extend(step)
        if "document_processing" not in phases:
            phases.append("document_processing")
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
        pending_counts: Dict[str, int] = {}
        if get_all_pending_counts:
            try:
                pending_counts = get_all_pending_counts()
            except Exception as e:
                logger.debug("Watchdog get_all_pending_counts: %s", e)
        requested: List[str] = []
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
            last_run = schedule.get("last_run") or self._last_completed_at_by_phase.get(phase_name)
            if last_run and collection_started_at and last_run >= collection_started_at:
                continue
            has_work = (pending_counts.get(phase_name) or 0) > 0
            if not has_work and phase_name in BATCH_PHASES_CONTINUOUS:
                has_work = await self._has_pending_work(phase_name)
            if not has_work and phase_name not in pending_counts and phase_name not in BATCH_PHASES_CONTINUOUS:
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
                    for schema in _SCHEMAS:
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
                    for schema in _SCHEMAS:
                        cur.execute(
                            f"""SELECT 1 FROM {schema}.articles
                                WHERE ml_processed = FALSE AND content IS NOT NULL AND LENGTH(content) > 100
                                LIMIT 1"""
                        )
                        if cur.fetchone():
                            return True
                elif phase_name == "entity_extraction":
                    for schema in _SCHEMAS:
                        cur.execute(
                            f"""SELECT 1 FROM {schema}.articles
                                WHERE (entities IS NULL OR entities = '{{}}') AND content IS NOT NULL AND LENGTH(content) > 100
                                LIMIT 1"""
                        )
                        if cur.fetchone():
                            return True
                elif phase_name == "sentiment_analysis":
                    for schema in _SCHEMAS:
                        cur.execute(
                            f"""SELECT 1 FROM {schema}.articles
                                WHERE sentiment_score IS NULL AND content IS NOT NULL AND LENGTH(content) > 50
                                LIMIT 1"""
                        )
                        if cur.fetchone():
                            return True
                elif phase_name == "storyline_processing":
                    for schema in _SCHEMAS:
                        cur.execute(
                            f"""SELECT 1 FROM {schema}.storylines
                                WHERE master_summary IS NULL OR LENGTH(master_summary) < 100
                                LIMIT 1"""
                        )
                        if cur.fetchone():
                            return True
                elif phase_name == "rag_enhancement":
                    for schema in _SCHEMAS:
                        cur.execute(
                            f"""SELECT 1 FROM {schema}.storylines
                                WHERE rag_enhanced_at IS NULL
                                   OR rag_enhanced_at < CURRENT_TIMESTAMP - INTERVAL '1 hour'
                                LIMIT 1"""
                        )
                        if cur.fetchone():
                            return True
                elif phase_name == "storyline_automation":
                    for schema in _SCHEMAS:
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
                    for schema in _SCHEMAS:
                        cur.execute(
                            f"""SELECT 1 FROM {schema}.articles
                                WHERE quality_score IS NULL AND content IS NOT NULL AND LENGTH(content) > 100
                                LIMIT 1"""
                        )
                        if cur.fetchone():
                            return True
                elif phase_name == "timeline_generation":
                    for schema in _SCHEMAS:
                        cur.execute(
                            f"""SELECT 1 FROM {schema}.storylines
                                WHERE timeline_summary IS NULL OR LENGTH(timeline_summary) < 100
                                LIMIT 1"""
                        )
                        if cur.fetchone():
                            return True
                elif phase_name == "topic_clustering":
                    for schema in _SCHEMAS:
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
                    for schema in _SCHEMAS:
                        cur.execute(
                            f"""SELECT 1 FROM {schema}.articles
                                WHERE processing_status = 'completed' AND timeline_processed = false
                                AND content IS NOT NULL AND LENGTH(content) > 100
                                LIMIT 1"""
                        )
                        if cur.fetchone():
                            return True
                elif phase_name == "content_refinement_queue":
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

    def get_status(self) -> Dict[str, Any]:
        """Get automation status. Includes backlog_counts when backlog_metrics is available."""
        out = {
            'is_running': self.is_running,
            'active_workers': len([w for w in self.workers if not w.done()]),
            'queue_size': self.task_queue.qsize(),
            'requested_queue_size': self._requested_task_queue.qsize(),
            'combined_queue_depth': self._automation_queue_depth(),
            'queue_soft_cap': AUTOMATION_QUEUE_SOFT_CAP,
            'scheduled_enqueue_paused': self._scheduled_enqueue_paused(),
            'metrics': self.metrics,
            'schedules': self.schedules,
            'recent_tasks': list(self.tasks.values())[-10:]  # Last 10 tasks
        }
        # Per-phase queue/run metrics for monitoring timeline:
        # - queued_tasks_by_phase: tasks currently enqueued (not yet executing)
        # - active_tasks_by_phase: tasks currently executing (workers)
        # - runs_last_60m_by_phase: how many phase runs completed in the last 60 minutes
        try:
            from collections import Counter
            queued_counter = Counter()
            for q in (self.task_queue, self._requested_task_queue):
                try:
                    internal = getattr(q, "_queue", None)
                    if internal is not None:
                        queued_counter.update([t.name for t in list(internal) if hasattr(t, "name")])
                except Exception:
                    pass
            out["queued_tasks_by_phase"] = dict(queued_counter)
        except Exception:
            out["queued_tasks_by_phase"] = {}
        try:
            out["active_tasks_by_phase"] = {k: v for k, v in self._running_tasks_by_phase.items() if v > 0}
        except Exception:
            out["active_tasks_by_phase"] = {}
        try:
            out["runs_last_60m_by_phase"] = {k: len(dq) for k, dq in self._phase_run_times_last_60m.items()}
        except Exception:
            out["runs_last_60m_by_phase"] = {}
        if get_all_backlog_counts:
            try:
                out['backlog_counts'] = get_all_backlog_counts()
            except Exception:
                pass
        if get_all_pending_counts:
            try:
                out['pending_counts'] = get_all_pending_counts()
            except Exception:
                pass
        return out
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get detailed metrics"""
        return {
            'performance': self.metrics,
            'task_distribution': {
                status.value: len([t for t in self.tasks.values() if t.status == status])
                for status in TaskStatus
            },
            'system_health': {
                'uptime': self.metrics['system_uptime'],
                'last_health_check': self.metrics['last_health_check'],
                'active_workers': len([w for w in self.workers if not w.done()])
            }
        }

# Global instance
automation_manager = None

def get_automation_manager() -> AutomationManager:
    """Get the global automation manager instance"""
    global automation_manager
    if automation_manager is None:
        from config.database import get_db_config
        db_config = get_db_config()
        automation_manager = AutomationManager(db_config)
    return automation_manager
