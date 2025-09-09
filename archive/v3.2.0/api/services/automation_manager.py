"""
News Intelligence System v3.1.0 - Enterprise Automation Manager
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
from concurrent.futures import ThreadPoolExecutor
import traceback

# Configure logging
logger = logging.getLogger(__name__)

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

class AutomationManager:
    """Enterprise-grade automation manager"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.is_running = False
        self.tasks: Dict[str, Task] = {}
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.task_queue = asyncio.Queue()
        self.workers = []
        self.health_check_interval = 30  # seconds
        self.task_timeout = 300  # 5 minutes
        self.max_concurrent_tasks = 5
        
        # Dynamic resource allocation
        self.dynamic_resource_service = None
        self.resource_allocation = None
        
        # Task schedules (cron-like) - Sequential processing with proper dependencies
        self.schedules = {
            # PHASE 1: Data Collection (Every 10 minutes)
            'rss_processing': {
                'interval': 600,  # 10 minutes - Base collection cycle
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.CRITICAL,
                'phase': 1,
                'depends_on': [],
                'estimated_duration': 120  # 2 minutes
            },
            
            # PHASE 2: Article Processing (Starts 3 minutes after RSS)
            'article_processing': {
                'interval': 600,  # 10 minutes - Same cycle as RSS
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.HIGH,
                'phase': 2,
                'depends_on': ['rss_processing'],
                'estimated_duration': 180  # 3 minutes
            },
            
            # PHASE 3: ML Processing (Starts 6 minutes after RSS)
            'ml_processing': {
                'interval': 600,  # 10 minutes - Same cycle as RSS
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.HIGH,
                'phase': 3,
                'depends_on': ['article_processing'],
                'estimated_duration': 240  # 4 minutes
            },
            
            # PHASE 4: Parallel ML & Entity Processing (Starts 6 minutes after RSS)
            'entity_extraction': {
                'interval': 600,  # 10 minutes - Same cycle as RSS
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 4,
                'depends_on': ['article_processing'],
                'estimated_duration': 120,  # 2 minutes
                'parallel_group': 'ml_entity_processing'  # Can run in parallel with ML
            },
            
            # PHASE 4: Parallel ML & Entity Processing (Starts 6 minutes after RSS)
            'quality_scoring': {
                'interval': 600,  # 10 minutes - Same cycle as RSS
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 4,
                'depends_on': ['article_processing'],
                'estimated_duration': 90,  # 1.5 minutes
                'parallel_group': 'ml_entity_processing'  # Can run in parallel with ML
            },
            
            # PHASE 4: Parallel ML & Entity Processing (Starts 6 minutes after RSS)
            'sentiment_analysis': {
                'interval': 600,  # 10 minutes - Same cycle as RSS
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 4,
                'depends_on': ['article_processing'],
                'estimated_duration': 120,  # 2 minutes
                'parallel_group': 'ml_entity_processing'  # Can run in parallel with ML
            },
            
            # PHASE 7: Storyline Processing (Every 20 minutes)
            'storyline_processing': {
                'interval': 1200,  # 20 minutes - Half cycle of RSS
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.HIGH,
                'phase': 7,
                'depends_on': ['ml_processing', 'sentiment_analysis'],
                'estimated_duration': 300  # 5 minutes
            },
            
            # PHASE 8: RAG Enhancement (Every 30 minutes)
            # PHASE 6: Basic Summary Generation (Starts 15 minutes after RSS)
            'basic_summary_generation': {
                'interval': 300,  # 5 minutes - Fast, frequent
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.HIGH,
                'phase': 6,
                'depends_on': ['storyline_processing'],
                'estimated_duration': 120  # 2 minutes
            },
            
            'rag_enhancement': {
                'interval': 1800,  # 30 minutes - Third cycle of RSS
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.HIGH,
                'phase': 8,
                'depends_on': ['basic_summary_generation'],
                'estimated_duration': 600  # 10 minutes
            },
            
            # PHASE 9: Timeline Generation (Every 30 minutes)
            'timeline_generation': {
                'interval': 1800,  # 30 minutes - Same as RAG
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 9,
                'depends_on': ['rag_enhancement'],
                'estimated_duration': 300  # 5 minutes
            },
            
            # PHASE 10: Cache Cleanup (Every hour)
            'cache_cleanup': {
                'interval': 3600,  # 1 hour - Clean expired cache
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.LOW,
                'phase': 10,
                'depends_on': [],
                'estimated_duration': 60  # 1 minute
            },
            
            # PHASE 11: Digest Generation (Every hour)
            'digest_generation': {
                'interval': 3600,  # 1 hour
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL,
                'phase': 11,
                'depends_on': ['timeline_generation'],
                'estimated_duration': 180  # 3 minutes
            },
            
            # MAINTENANCE: Data Cleanup (Daily)
            'data_cleanup': {
                'interval': 86400,  # 24 hours
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.LOW,
                'phase': 99,
                'depends_on': [],
                'estimated_duration': 300  # 5 minutes
            },
            
            # MONITORING: Health Check (Every minute)
            'health_check': {
                'interval': 60,  # 1 minute
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.CRITICAL,
                'phase': 0,
                'depends_on': [],
                'estimated_duration': 10  # 10 seconds
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
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(10)
        
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
        
        # Ensure minimum interval
        min_interval = max(60, estimated * 2)  # At least 2x estimated duration
        return max(adjusted_interval, min_interval)
    
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
        
        logger.info(f"Worker {worker_id} executing task: {task.name}")
        
        try:
            # Execute task based on type
            if task.name == 'rss_processing':
                await self._execute_rss_processing(task)
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
            elif task.name == 'article_processing':
                await self._execute_article_processing(task)
            elif task.name == 'entity_extraction':
                await self._execute_entity_extraction(task)
            elif task.name == 'quality_scoring':
                await self._execute_quality_scoring(task)
            elif task.name == 'timeline_generation':
                await self._execute_timeline_generation(task)
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
            # Store task result
            self.tasks[task.id] = task
            
    async def _execute_rss_processing(self, task: Task):
        """Execute RSS processing task"""
        from services.rss_processing_service import get_rss_processor
        
        rss_processor = get_rss_processor()
        await rss_processor.process_all_feeds()
        
    async def _execute_digest_generation(self, task: Task):
        """Execute digest generation task"""
        from services.digest_automation_service import get_digest_service
        
        digest_service = get_digest_service()
        await digest_service.generate_digest_if_needed()
        
    async def _execute_data_cleanup(self, task: Task):
        """Execute data cleanup task"""
        # Clean up old articles (keep last 30 days)
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
        
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
        from services.rag_service import get_rag_service
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
                # Process article
                await article_processor.process_single_article(url)
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
        from services.api_cache_service import get_cache_service
        
        cache_service = get_cache_service()
        
        try:
            # Clear expired cache entries
            cleared_count = await cache_service.clear_expired_cache()
            logger.info(f"Cache cleanup completed: {cleared_count} expired entries cleared")
            
        except Exception as e:
            logger.error(f"Error during cache cleanup: {e}")
        
    async def _get_db_connection(self):
        """Get database connection"""
        return psycopg2.connect(**self.db_config)
    
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
        from database.connection import get_db_config
        db_config = get_db_config()
        automation_manager = AutomationManager(db_config)
    return automation_manager
