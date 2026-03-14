"""
News Intelligence System v3.0 - Enterprise Automation Manager
Industry-standard background processing with scalability and reliability
"""

import asyncio
import logging
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
from concurrent.futures import ThreadPoolExecutor
import traceback

# Configure logging
logger = logging.getLogger(__name__)

# Phases that process batches; re-enqueue when pending work remains (continuous until empty)
BATCH_PHASES_CONTINUOUS = {
    "ml_processing",
    "article_processing",
    "entity_extraction",
    "sentiment_analysis",
    "quality_scoring",
    "storyline_processing",
    "basic_summary_generation",
    "rag_enhancement",
    "storyline_automation",
    "entity_profile_build",
    "timeline_generation",
    "topic_clustering",
    "event_extraction",
}
_SCHEMAS = ("politics", "finance", "science_tech")

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
    "article_processing": 180,
    "ml_processing": 240,
    "topic_clustering": 180,
    "entity_extraction": 120,
    "quality_scoring": 90,
    "sentiment_analysis": 120,
    "storyline_processing": 300,
    "basic_summary_generation": 120,
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
    "context_sync": 60,   # ~5-10s per 100 contexts (production batch)
    "entity_profile_sync": 120,
    "claim_extraction": 60,   # 50 contexts @ 2-5s each, parallel 5 → ~20-50s
    "event_tracking": 30,   # 1000 contexts scan ~15-20s (production)
    "event_coherence_review": 180,
    "investigation_report_refresh": 300,
    "entity_profile_build": 600,
    "pattern_recognition": 120,
    "storyline_automation": 180,
    "story_enhancement": 300,
    "entity_enrichment": 180,
    "story_state_triggers": 120,
    "pattern_matching": 90,
    "cross_domain_synthesis": 120,
    "relationship_extraction": 90,
}

class AutomationManager:
    """Enterprise-grade automation manager"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.is_running = False
        self.tasks: Dict[str, Task] = {}
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.task_queue = asyncio.Queue()
        self.workers = []
        # Thread-safe queue for coordinator-driven phase requests (run_phase from another thread)
        self._phase_request_queue = queue.Queue()
        self.health_check_interval = 30  # seconds
        self.task_timeout = 300  # 5 minutes
        self.max_concurrent_tasks = 8  # More parallel work for full-time utilization
        
        # Dynamic resource allocation
        self.dynamic_resource_service = None
        self.resource_allocation = None
        
        # Task schedules (cron-like) - Sequential processing with proper dependencies
        self.schedules = {
            # PHASE 1: Data Collection
            'rss_processing': {
                'interval': 1800,  # 30 minutes - more frequent for all-day runs
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.CRITICAL,
                'phase': 1,
                'depends_on': [],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['rss_processing'],
            },
            
            # PHASE 1b: Context-centric sync (incremental: articles -> intelligence.contexts)
            'context_sync': {
                'interval': 900,  # 15 minutes - incremental sync, 100 contexts/batch, ~30-60s
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 1,
                'depends_on': [],
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
                'depends_on': [],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['claim_extraction'],
            },
            # PHASE 2.3: Event tracking (contexts -> tracked_events; 6h window, overlapping)
            'event_tracking': {
                'interval': 3600,  # 1 hour - max 1000 contexts/run, ~15-20s, catch delayed correlations
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 2,
                'depends_on': [],
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
                'depends_on': [],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['entity_profile_build'],
            },
            # PHASE 2.2: Pattern recognition (network, temporal, behavioral, event)
            'pattern_recognition': {
                'interval': 7200,  # 2 hours
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 2,
                'depends_on': [],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['pattern_recognition'],
            },
            # P2: Relationship extraction (co-mentions -> entity_relationships)
            'relationship_extraction': {
                'interval': 900,  # 15 minutes
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 2,
                'depends_on': [],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['relationship_extraction'],
            },
            # PHASE 2: Article Processing (Runs frequently, processes existing articles)
            'article_processing': {
                'interval': 300,  # 5 minutes - run often, re-enqueue until empty
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.HIGH,
                'phase': 2,
                'depends_on': [],  # Can process articles already in database, no RSS dependency
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['article_processing'],
            },
            
            # PHASE 3: ML Processing (Runs frequently on processed articles)
            'ml_processing': {
                'interval': 300,  # 5 minutes - run often, re-enqueue until empty
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.HIGH,
                'phase': 3,
                'depends_on': ['article_processing'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['ml_processing'],
            },
            
            # PHASE 5: Topic Clustering (Continuous iterative refinement)
            'topic_clustering': {
                'interval': 300,  # 5 minutes - run often, drain backlog
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.HIGH,
                'phase': 5,
                'depends_on': ['article_processing'],  # Only needs articles, not full ML processing
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['topic_clustering'],
            },
            
            # PHASE 4: Parallel ML & Entity Processing (Runs frequently)
            'entity_extraction': {
                'interval': 300,  # 5 minutes - run often, re-enqueue until empty
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 4,
                'depends_on': ['article_processing'],
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
                'depends_on': ['article_processing'],
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
                'depends_on': ['article_processing'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['sentiment_analysis'],
                'parallel_group': 'ml_entity_processing'  # Can run in parallel with ML
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
                'interval': 300,  # 5 minutes - run often, re-enqueue until empty
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 7,
                'depends_on': [],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['storyline_automation'],
            },
            # PHASE 8: RAG Enhancement (Every 30 minutes)
            # PHASE 6: Basic Summary Generation
            'basic_summary_generation': {
                'interval': 300,  # 5 minutes - run often, re-enqueue until empty
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.HIGH,
                'phase': 6,
                'depends_on': ['storyline_processing'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['basic_summary_generation'],
            },
            
            'rag_enhancement': {
                'interval': 300,  # 5 minutes - run often, re-enqueue until storylines enhanced
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.HIGH,
                'phase': 8,
                'depends_on': ['basic_summary_generation'],
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

            # Phase 3 RAG: Story state triggers (fact_change_log -> story_update_queue)
            'story_state_triggers': {
                'interval': 300,  # 5 minutes - 100-change batches, ~2s each; if behind >10k alert
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 9,
                'depends_on': [],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['story_state_triggers'],
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
            
            # PHASE 11: Digest Generation (Every hour)
            'digest_generation': {
                'interval': 3600,  # 1 hour
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 11,
                'depends_on': ['timeline_generation'],
                'estimated_duration': PHASE_ESTIMATED_DURATION_SECONDS['digest_generation'],
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
            }
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
        
    async def start(self):
        """Start the automation manager"""
        logger.info("Starting Enterprise Automation Manager...")
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
        
        logger.info(f"Automation Manager started with {self.max_concurrent_tasks} workers")
        
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
    ) -> None:
        """
        Request a phase to run (thread-safe). Call from coordinator or API.
        The scheduler will drain this queue and enqueue tasks with metadata.
        """
        try:
            self._phase_request_queue.put_nowait((phase_name, domain, storyline_id))
        except Exception as e:
            logger.warning("AutomationManager request_phase failed: %s", e)
        
    async def _worker(self, worker_id: str):
        """Worker process for task execution"""
        logger.info(f"Worker {worker_id} started")
        
        while self.is_running:
            try:
                # Get task from queue with timeout
                task = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
                
                if task:
                    await self._execute_task(task, worker_id)
                    self.task_queue.task_done()
                    
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                await asyncio.sleep(1)
        
        logger.info(f"Worker {worker_id} stopped")
        
    async def _scheduler(self):
        """Task scheduler with dependency management"""
        logger.info("Scheduler started")
        
        while self.is_running:
            try:
                # Drain coordinator-driven phase requests (thread-safe)
                try:
                    while True:
                        phase_name, domain, storyline_id = self._phase_request_queue.get_nowait()
                        if phase_name not in self.schedules:
                            logger.debug("request_phase: unknown phase %s, skipping", phase_name)
                            continue
                        schedule = self.schedules[phase_name]
                        task = Task(
                            id=f"{phase_name}_{int(datetime.now(timezone.utc).timestamp())}",
                            name=phase_name,
                            priority=schedule.get("priority", TaskPriority.NORMAL),
                            status=TaskStatus.PENDING,
                            created_at=datetime.now(timezone.utc),
                            metadata={"domain": domain, "storyline_id": storyline_id},
                        )
                        await self.task_queue.put(task)
                        logger.info("Governor requested phase: %s (domain=%s, storyline_id=%s)", phase_name, domain, storyline_id)
                except queue.Empty:
                    pass

                current_time = datetime.now(timezone.utc)
                
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
                    self.max_concurrent_tasks = min(10, self.max_concurrent_tasks + 1)
                
                # Process each phase
                for phase in sorted(phase_groups.keys()):
                    phase_data = phase_groups[phase]
                    
                    # Process parallel groups first
                    for parallel_group, tasks in phase_data['parallel_groups'].items():
                        if self._should_run_parallel_group(parallel_group, tasks, current_time):
                            await self._execute_parallel_phase(parallel_group)
                    
                    # Process sequential tasks
                    for task_name, schedule in phase_data['sequential_tasks']:
                        if self._should_run_task(task_name, schedule, current_time):
                            await self._create_and_queue_task(task_name, schedule, current_time)
                
                await asyncio.sleep(5)  # Check every 5 seconds for more continuous iteration
                
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(5)
        
        logger.info("Scheduler stopped")
    
    def _should_run_parallel_group(self, parallel_group: str, tasks: List[Tuple[str, Dict]], current_time: datetime) -> bool:
        """Check if parallel group should run"""
        if not tasks:
            return False
        
        # Check if any task in the group should run
        for task_name, schedule in tasks:
            if self._should_run_task(task_name, schedule, current_time):
                return True
        return False
    
    def _should_run_task(self, task_name: str, schedule: Dict[str, Any], current_time: datetime) -> bool:
        """Check if individual task should run"""
        # Check dependencies first
        if not self._check_dependencies(task_name, schedule):
            return False
            
        # Calculate adaptive interval
        base_interval = schedule['interval']
        adaptive_interval = self._calculate_adaptive_interval(task_name, base_interval)
        
        # Check if task should run based on adaptive interval
        if (schedule['last_run'] is None or 
            (current_time - schedule['last_run']).total_seconds() >= adaptive_interval):
            
            # Check if dependencies are satisfied
            if self._are_dependencies_satisfied(task_name, schedule, current_time):
                return True
        return False
    
    async def _create_and_queue_task(self, task_name: str, schedule: Dict[str, Any], current_time: datetime):
        """Create and queue a task"""
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
        """Check if all dependencies have been satisfied recently"""
        depends_on = schedule.get('depends_on', [])
        
        for dep_task in depends_on:
            if dep_task not in self.schedules:
                continue
                
            dep_schedule = self.schedules[dep_task]
            if dep_schedule['last_run'] is None:
                return False
                
            # Check if dependency completed within reasonable time
            time_since_dep = (current_time - dep_schedule['last_run']).total_seconds()
            dep_duration = dep_schedule.get('estimated_duration', 60)
            
            # Apply load factor for adaptive timing
            adjusted_duration = dep_duration * self.metrics['load_factor']
            
            # Dependencies should have completed at least their estimated duration ago
            if time_since_dep < adjusted_duration:
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
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # Get article count from last hour
            cursor.execute("""
                SELECT COUNT(*) FROM articles 
                WHERE created_at > NOW() - INTERVAL '1 hour'
            """)
            
            recent_count = cursor.fetchone()[0]
            cursor.close()
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
            'article_processing', 'storyline_processing', 'rag_enhancement', 'basic_summary_generation',
            'event_extraction', 'event_deduplication', 'story_continuation', 'watchlist_alerts',
            'quality_scoring', 'timeline_generation',
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
        
        logger.info(f"Worker {worker_id} executing task: {task.name}")
        task.started_at = datetime.now(timezone.utc)
        try:
            from services.activity_feed_service import get_activity_feed
            message = self._activity_message(task)
            get_activity_feed().add_current(
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
            if task.name == 'rss_processing':
                await self._execute_rss_processing(task)
            elif task.name == 'context_sync':
                await self._execute_context_sync(task)
            elif task.name == 'entity_profile_sync':
                await self._execute_entity_profile_sync(task)
            elif task.name == 'claim_extraction':
                await self._execute_claim_extraction(task)
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
            elif task.name == 'relationship_extraction':
                await self._execute_relationship_extraction(task)
            elif task.name == 'digest_generation':
                await self._execute_digest_generation(task)
            elif task.name == 'data_cleanup':
                await self._execute_data_cleanup(task)
            elif task.name == 'health_check':
                await self._execute_health_check(task)
            elif task.name == 'basic_summary_generation':
                await self._execute_basic_summary_generation(task)
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
            elif task.name == 'article_processing':
                await self._execute_article_processing(task)
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
            elif task.name == 'entity_enrichment':
                await self._execute_entity_enrichment(task)
            elif task.name == 'story_state_triggers':
                await self._execute_story_state_triggers(task)
            elif task.name == 'pattern_matching':
                await self._execute_pattern_matching(task)
            else:
                raise ValueError(f"Unknown task type: {task.name}")
            
            # Mark as completed
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc)
            self.metrics['tasks_completed'] += 1
            
            # Calculate processing time
            processing_time = (task.completed_at - task.started_at).total_seconds()
            self._update_avg_processing_time(processing_time)
            
            # Update processing history for adaptive timing
            self._update_processing_history(task.name, processing_time)
            
            logger.info(f"Task {task.name} completed in {processing_time:.2f}s (Phase {task.metadata.get('phase', 0)})")

            # Continuous iteration: re-enqueue same phase when work remains so we run until empty
            if task.name in BATCH_PHASES_CONTINUOUS:
                try:
                    if await self._has_pending_work(task.name):
                        self.request_phase(task.name)
                        logger.debug("Re-enqueued %s (pending work remains)", task.name)
                except Exception as e:
                    logger.debug("Re-enqueue check for %s: %s", task.name, e)
            
        except Exception as e:
            # Handle task failure
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.retry_count += 1
            self.metrics['tasks_failed'] += 1
            
            logger.error(f"Task {task.name} failed: {e}")
            
            # Retry if under max retries
            if task.retry_count < task.max_retries:
                task.status = TaskStatus.RETRYING
                await asyncio.sleep(min(60 * task.retry_count, 300))  # Exponential backoff
                await self.task_queue.put(task)
                logger.info(f"Retrying task {task.name} (attempt {task.retry_count + 1})")
        
        finally:
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
        if name == "rss_processing":
            return "Running RSS collection (all domains)"
        if name == "context_sync":
            return f"Syncing articles to contexts ({domain or 'all domains'})"
        if name == "storyline_automation":
            if storyline_id and domain:
                return f"Storyline automation (storyline {storyline_id}, {domain})"
            return f"Storyline automation ({domain or 'all'})"
        if name == "entity_profile_sync":
            return f"Syncing entity profiles ({domain or 'all domains'})"
        if name == "entity_profile_build":
            return "Building entity profiles from contexts"
        if name == "claim_extraction":
            return "Extracting claims from contexts"
        if name == "event_tracking":
            return f"Tracking events ({domain or 'all'})"
        if name == "cross_domain_synthesis":
            return "Cross-domain synthesis"
        if name == "relationship_extraction":
            return "Relationship extraction"
        if name == "story_state_triggers":
            return "Processing story state triggers"
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
        if name == "article_processing":
            return "Article processing"
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
            # Production: context_limit 1000 total, ~15-20s per run, 6h overlapping window
            total = await run_event_tracking_batch(limit=100)
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
        from services.investigation_report_service import refresh_stale_investigation_reports
        try:
            refreshed = await refresh_stale_investigation_reports(limit=3)
            if refreshed > 0:
                logger.info(f"Investigation report refresh: {refreshed} reports updated")
            else:
                logger.debug("Investigation report refresh: no stale reports")
        except Exception as e:
            logger.warning(f"Investigation report refresh failed: {e}")

    async def _execute_cross_domain_synthesis(self, task: Task):
        """Run cross-domain correlation job (events spanning domains -> cross_domain_correlations)."""
        try:
            from services.cross_domain_service import run_cross_domain_synthesis
            result = run_cross_domain_synthesis(
                domains=None,
                time_window_days=7,
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
            updated = await run_profile_builder_batch(limit=15)
            if updated > 0:
                logger.info(f"Entity profile build: {updated} profiles updated")
        except Exception as e:
            logger.warning(f"Entity profile build failed: {e}")

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

    async def _execute_story_state_triggers(self, task: Task):
        """Phase 3 RAG: Process fact_change_log and story_update_queue (story state refresh)."""
        from services.story_state_trigger_service import process_fact_change_log, process_story_update_queue
        try:
            loop = asyncio.get_event_loop()
            # Production: 100-change batches, ~2s each; alert if behind >10k
            fact_processed = await loop.run_in_executor(None, lambda: process_fact_change_log(batch_size=100))
            queue_processed = await loop.run_in_executor(None, lambda: process_story_update_queue(batch_size=20))
            if fact_processed > 0 or queue_processed > 0:
                logger.info("Story state triggers: fact_log=%s queue=%s", fact_processed, queue_processed)
        except Exception as e:
            logger.warning(f"Story state triggers failed: {e}")

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

    async def _execute_relationship_extraction(self, task: Task):
        """Extract entity relationships from context co-mentions -> entity_relationships (P2)."""
        try:
            from services.relationship_extraction_service import extract_relationships_from_contexts
            result = extract_relationships_from_contexts(domain_key=None, limit=50)
            if result.get("extracted", 0) > 0:
                logger.info("Relationship extraction: %d relationship(s) inserted", result["extracted"])
        except Exception as e:
            logger.warning("Relationship extraction failed: %s", e)

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
        
    async def _execute_digest_generation(self, task: Task):
        """Execute digest generation task"""
        from services.digest_automation_service import get_digest_service
        
        digest_service = get_digest_service()
        await digest_service.generate_digest_if_needed()
        
    async def _execute_data_cleanup(self, task: Task):
        """Execute data cleanup task — articles + intelligence layer."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)

        try:
            conn = await self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM articles
                WHERE published_at < %s AND created_at < %s
            """, (cutoff_date, cutoff_date))
            deleted_count = cursor.rowcount
            conn.commit()
            cursor.close()
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
        """Execute RAG enhancement task"""
        from services.rag import get_rag_service
        from services.storyline_service import get_storyline_service
        
        rag_service = get_rag_service()
        storyline_service = get_storyline_service()
        
        # Get all active storylines
        storylines = await storyline_service.get_all_storylines()
        
        enhanced_count = 0
        for storyline in storylines:
            try:
                # Check if storyline needs RAG enhancement
                if not storyline.get('rag_enhanced_at') or \
                   (datetime.now(timezone.utc) - datetime.fromisoformat(storyline['rag_enhanced_at'].replace('Z', '+00:00'))).total_seconds() > 3600:  # 1 hour
                    
                    # Enhance storyline with RAG
                    await rag_service.enhance_storyline_context(
                        storyline_id=storyline['id'],
                        storyline_title=storyline['title'],
                        articles=storyline.get('articles', [])
                    )
                    enhanced_count += 1
                    
            except Exception as e:
                logger.error(f"Error enhancing storyline {storyline['id']}: {e}")
        
        logger.info(f"RAG enhancement completed: {enhanced_count} storylines enhanced")
        
    async def _execute_ml_processing(self, task: Task):
        """Execute ML processing task"""
        from modules.ml.background_processor import BackgroundMLProcessor
        
        ml_processor = BackgroundMLProcessor()
        
        # Process articles that need ML analysis
        conn = await self._get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id FROM articles 
            WHERE ml_processed = FALSE 
            AND content IS NOT NULL 
            AND LENGTH(content) > 100
            ORDER BY created_at DESC 
            LIMIT 50
        """)
        
        articles = cursor.fetchall()
        processed_count = 0
        
        for article_id, in articles:
            try:
                # Process article with ML
                ml_processor.queue_article_for_processing(article_id, 'full_analysis')
                processed_count += 1
            except Exception as e:
                logger.error(f"Error processing article {article_id}: {e}")
        
        cursor.close()
        conn.close()
        
        logger.info(f"ML processing completed: {processed_count} articles queued")
        
    async def _execute_sentiment_analysis(self, task: Task):
        """Execute sentiment analysis task"""
        from services.ai_processing_service import get_ai_service
        
        ai_service = get_ai_service()
        
        # Analyze sentiment for recent articles
        conn = await self._get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, content FROM articles 
            WHERE sentiment_score IS NULL 
            AND content IS NOT NULL 
            AND LENGTH(content) > 50
            ORDER BY created_at DESC 
            LIMIT 100
        """)
        
        articles = cursor.fetchall()
        analyzed_count = 0
        
        for article_id, content in articles:
            try:
                # Analyze sentiment
                sentiment = await ai_service.analyze_sentiment(content)
                
                # Update article with sentiment score
                cursor.execute("""
                    UPDATE articles 
                    SET sentiment_score = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (sentiment.get('score', 0), article_id))
                
                analyzed_count += 1
            except Exception as e:
                logger.error(f"Error analyzing sentiment for article {article_id}: {e}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Sentiment analysis completed: {analyzed_count} articles analyzed")
        
    async def _execute_storyline_processing(self, task: Task):
        """Execute storyline processing task"""
        from services.storyline_service import get_storyline_service
        
        storyline_service = get_storyline_service()
        
        # Process storylines that need updates
        storylines = await storyline_service.get_all_storylines()
        processed_count = 0
        
        for storyline in storylines:
            try:
                # Generate summary if needed
                if not storyline.get('master_summary') or len(storyline.get('master_summary', '')) < 100:
                    summary = await storyline_service.generate_storyline_summary(storyline['id'])
                    processed_count += 1
                    
            except Exception as e:
                logger.error(f"Error processing storyline {storyline['id']}: {e}")
        
        logger.info(f"Storyline processing completed: {processed_count} storylines processed")

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
                    cur = conn.cursor()
                    schema = d.replace("-", "_")
                    cur.execute(f"""
                        SELECT id FROM {schema}.storylines
                        WHERE automation_enabled = true
                        ORDER BY last_automation_run ASC NULLS FIRST
                        LIMIT 5
                    """)
                    for row in cur.fetchall():
                        await svc.discover_articles_for_storyline(row[0], force_refresh=False)
                    cur.close()
                    conn.close()
                except Exception as e:
                    logger.debug("Storyline automation batch %s: %s", d, e)
            logger.info("Storyline automation: batch run across domains completed")
        
    async def _execute_article_processing(self, task: Task):
        """Execute article processing task"""
        from services.article_processing_service import get_article_processor
        
        article_processor = get_article_processor()
        
        # Process articles that need cleaning
        conn = await self._get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, url FROM articles 
            WHERE content IS NULL OR LENGTH(content) < 100
            AND url IS NOT NULL
            ORDER BY created_at DESC 
            LIMIT 20
        """)
        
        articles = cursor.fetchall()
        processed_count = 0
        
        for article_id, url in articles:
            try:
                article_processor.process_single_article(article_id)
                processed_count += 1
            except Exception as e:
                logger.error(f"Error processing article {article_id}: {e}")
        
        cursor.close()
        conn.close()
        
        logger.info(f"Article processing completed: {processed_count} articles processed")
        
    async def _execute_entity_extraction(self, task: Task):
        """Execute entity extraction task"""
        from services.ai_processing_service import get_ai_service
        
        ai_service = get_ai_service()
        
        # Extract entities from recent articles
        conn = await self._get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, content FROM articles 
            WHERE entities IS NULL OR entities = '{}'
            AND content IS NOT NULL 
            AND LENGTH(content) > 100
            ORDER BY created_at DESC 
            LIMIT 50
        """)
        
        articles = cursor.fetchall()
        extracted_count = 0
        
        for article_id, content in articles:
            try:
                # Extract entities
                entities = await ai_service.extract_entities(content)
                
                # Update article with entities
                cursor.execute("""
                    UPDATE articles 
                    SET entities = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (json.dumps(entities), article_id))
                
                extracted_count += 1
            except Exception as e:
                logger.error(f"Error extracting entities for article {article_id}: {e}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Entity extraction completed: {extracted_count} articles processed")

    async def _execute_event_extraction_v5(self, task: Task):
        """v5.0 -- Extract structured events with temporal grounding from articles."""
        from services.event_extraction_service import EventExtractionService

        svc = EventExtractionService()
        conn = await self._get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT id, content, published_at
                FROM articles
                WHERE processing_status = 'completed'
                  AND timeline_processed = false
                  AND content IS NOT NULL
                  AND LENGTH(content) > 100
                ORDER BY published_at DESC
                LIMIT 30
            """)
            articles = cursor.fetchall()

            total_events = 0
            for article_id, content, pub_date in articles:
                try:
                    if pub_date is None:
                        pub_date = datetime.now(timezone.utc)
                    events = await svc.extract_events_from_article(
                        article_id=article_id,
                        content=content,
                        pub_date=pub_date,
                    )
                    saved = await svc.save_events(events, conn)
                    total_events += saved

                    cursor.execute("""
                        UPDATE articles
                        SET timeline_processed = true,
                            timeline_events_generated = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (len(events), article_id))
                    conn.commit()
                except Exception as e:
                    logger.error(f"Event extraction failed for article {article_id}: {e}")
                    conn.rollback()

            logger.info(f"v5 event extraction completed: {total_events} events from {len(articles)} articles")
        finally:
            cursor.close()
            conn.close()
            await svc.close()

    async def _execute_event_deduplication_v5(self, task: Task):
        """v5.0 -- Deduplicate events across sources using fingerprint, semantic, and entity matching."""
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

    async def _execute_story_continuation_v5(self, task: Task):
        """v5.0 -- Match events to existing storylines and manage lifecycle states."""
        from services.story_continuation_service import StoryContinuationService

        conn = await self._get_db_connection()
        try:
            svc = StoryContinuationService(conn)
            stats = await svc.process_recent_events(limit=30)
            svc.update_lifecycle_states()
            logger.info(
                f"v5 story continuation completed: "
                f"checked={stats['checked']}, linked={stats['linked']}, flagged={stats['flagged']}"
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
        finally:
            conn.close()

    async def _execute_quality_scoring(self, task: Task):
        """Execute quality scoring task"""
        from services.ai_processing_service import get_ai_service
        
        ai_service = get_ai_service()
        
        # Score quality for recent articles
        conn = await self._get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, content, title FROM articles 
            WHERE quality_score IS NULL
            AND content IS NOT NULL 
            AND LENGTH(content) > 100
            ORDER BY created_at DESC 
            LIMIT 50
        """)
        
        articles = cursor.fetchall()
        scored_count = 0
        
        for article_id, content, title in articles:
            try:
                # Score quality
                quality = await ai_service.score_article_quality(content, title)
                
                # Update article with quality score
                cursor.execute("""
                    UPDATE articles 
                    SET quality_score = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (quality.get('score', 0), article_id))
                
                scored_count += 1
            except Exception as e:
                logger.error(f"Error scoring quality for article {article_id}: {e}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Quality scoring completed: {scored_count} articles scored")
        
    async def _execute_timeline_generation(self, task: Task):
        """Execute timeline generation task"""
        from services.storyline_service import get_storyline_service
        
        storyline_service = get_storyline_service()
        
        # Generate timelines for storylines
        storylines = await storyline_service.get_all_storylines()
        generated_count = 0
        
        for storyline in storylines:
            try:
                # Generate timeline if needed
                if not storyline.get('timeline_summary') or len(storyline.get('timeline_summary', '')) < 100:
                    timeline = await storyline_service.generate_storyline_timeline(storyline['id'])
                    generated_count += 1
                    
            except Exception as e:
                logger.error(f"Error generating timeline for storyline {storyline['id']}: {e}")
        
        logger.info(f"Timeline generation completed: {generated_count} timelines generated")
    
    async def _execute_basic_summary_generation(self, task: Task):
        """Execute basic summary generation task"""
        from services.progressive_enhancement_service import get_progressive_service
        
        progressive_service = get_progressive_service()
        
        # Get storylines that need basic summaries
        storylines = await progressive_service.storyline_service.get_all_storylines()
        generated_count = 0
        
        for storyline in storylines:
            try:
                # Check if storyline needs basic summary
                if not storyline.get('master_summary') or len(storyline.get('master_summary', '')) < 100:
                    result = await progressive_service.generate_basic_summary(storyline['id'])
                    if result.get('success'):
                        generated_count += 1
                        
            except Exception as e:
                logger.error(f"Error generating basic summary for storyline {storyline['id']}: {e}")
        
        logger.info(f"Basic summary generation completed: {generated_count} summaries generated")
    
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
                cursor = conn.cursor()
                
                # Get articles with their average confidence scores from domain schema
                # This query categorizes articles into priority groups
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
                cursor.close()
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
        """Get database connection from shared pool."""
        from shared.database.connection import get_db_connection
        return get_db_connection()

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
                if phase_name == "ml_processing":
                    for schema in _SCHEMAS:
                        cur.execute(
                            f"""SELECT 1 FROM {schema}.articles
                                WHERE ml_processed = FALSE AND content IS NOT NULL AND LENGTH(content) > 100
                                LIMIT 1"""
                        )
                        if cur.fetchone():
                            return True
                elif phase_name == "article_processing":
                    for schema in _SCHEMAS:
                        cur.execute(
                            f"""SELECT 1 FROM {schema}.articles
                                WHERE (content IS NULL OR LENGTH(content) < 100) AND url IS NOT NULL
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
                elif phase_name == "storyline_processing" or phase_name == "basic_summary_generation":
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
            finally:
                cur.close()
                conn.close()
        except Exception as e:
            logger.debug("_has_pending_work %s: %s", phase_name, e)
        return False

    def get_status(self) -> Dict[str, Any]:
        """Get automation status"""
        return {
            'is_running': self.is_running,
            'active_workers': len([w for w in self.workers if not w.done()]),
            'queue_size': self.task_queue.qsize(),
            'metrics': self.metrics,
            'schedules': self.schedules,
            'recent_tasks': list(self.tasks.values())[-10:]  # Last 10 tasks
        }
    
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
