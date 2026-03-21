#!/usr/bin/env python3
"""
ML Queue Manager for News Intelligence System
Manages LLM workloads, prevents collisions, and optimizes resource utilization
"""

import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from queue import Empty, PriorityQueue
from typing import Any

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """Task priority levels"""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class TaskStatus(Enum):
    """Task status states"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(Enum):
    """Types of ML tasks"""

    TIMELINE_GENERATION = "timeline_generation"
    ARTICLE_SUMMARIZATION = "article_summarization"
    CONTENT_ANALYSIS = "content_analysis"
    ENTITY_EXTRACTION = "entity_extraction"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    QUALITY_SCORING = "quality_scoring"
    STORYLINE_ANALYSIS = "storyline_analysis"


@dataclass
class MLTask:
    """Represents an ML processing task"""

    task_id: str
    task_type: TaskType
    priority: TaskPriority
    storyline_id: str | None = None
    article_id: int | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    status: TaskStatus = TaskStatus.PENDING
    result: dict[str, Any] | None = None
    error: str | None = None
    retry_count: int = 0
    max_retries: int = 3
    estimated_duration: int = 30  # seconds
    resource_requirements: dict[str, Any] = field(default_factory=dict)


class MLQueueManager:
    """Manages ML task queue and resource allocation"""

    def __init__(self, db_config: dict[str, str], max_concurrent_tasks: int = 2):
        self.db_config = db_config
        self.max_concurrent_tasks = max_concurrent_tasks
        self.task_queue = PriorityQueue()
        self.running_tasks: dict[str, MLTask] = {}
        self.completed_tasks: dict[str, MLTask] = {}
        self.task_handlers: dict[TaskType, Callable] = {}
        self.resource_monitor = ResourceMonitor()
        self.is_running = False
        self.worker_threads: list[threading.Thread] = []

        # Initialize task handlers
        self._register_task_handlers()

        # Load pending tasks from database
        self._load_pending_tasks()

    def _register_task_handlers(self):
        """Register handlers for different task types"""
        self.task_handlers = {
            TaskType.TIMELINE_GENERATION: self._handle_timeline_generation,
            TaskType.ARTICLE_SUMMARIZATION: self._handle_article_summarization,
            TaskType.CONTENT_ANALYSIS: self._handle_content_analysis,
            TaskType.ENTITY_EXTRACTION: self._handle_entity_extraction,
            TaskType.SENTIMENT_ANALYSIS: self._handle_sentiment_analysis,
            TaskType.QUALITY_SCORING: self._handle_quality_scoring,
            TaskType.STORYLINE_ANALYSIS: self._handle_storyline_analysis,
        }

    def start(self):
        """Start the ML queue manager"""
        if self.is_running:
            logger.warning("ML Queue Manager is already running")
            return

        self.is_running = True
        logger.info("Starting ML Queue Manager")

        # Start worker threads
        for i in range(self.max_concurrent_tasks):
            worker = threading.Thread(target=self._worker_loop, name=f"MLWorker-{i}")
            worker.daemon = True
            worker.start()
            self.worker_threads.append(worker)

        # Start resource monitor
        self.resource_monitor.start()

        logger.info(f"ML Queue Manager started with {self.max_concurrent_tasks} workers")

    def stop(self):
        """Stop the ML queue manager"""
        if not self.is_running:
            return

        logger.info("Stopping ML Queue Manager")
        self.is_running = False

        # Wait for running tasks to complete
        for task in self.running_tasks.values():
            task.status = TaskStatus.CANCELLED

        # Stop resource monitor
        self.resource_monitor.stop()

        logger.info("ML Queue Manager stopped")

    def submit_task(self, task: MLTask) -> str:
        """Submit a new task to the queue"""
        try:
            # Validate task
            if not self._validate_task(task):
                raise ValueError("Invalid task")

            # Add to queue
            priority_value = task.priority.value
            self.task_queue.put((priority_value, task.created_at, task))

            # Store in database
            self._store_task(task)

            logger.info(f"Task {task.task_id} submitted with priority {task.priority.name}")
            return task.task_id

        except Exception as e:
            logger.error(f"Error submitting task {task.task_id}: {e}")
            raise

    def get_task_status(self, task_id: str) -> MLTask | None:
        """Get the status of a specific task"""
        # Check running tasks
        if task_id in self.running_tasks:
            return self.running_tasks[task_id]

        # Check completed tasks
        if task_id in self.completed_tasks:
            return self.completed_tasks[task_id]

        # Check database
        return self._load_task_from_db(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or running task"""
        try:
            # Check if task is running
            if task_id in self.running_tasks:
                task = self.running_tasks[task_id]
                task.status = TaskStatus.CANCELLED
                self._update_task_status(task_id, TaskStatus.CANCELLED)
                return True

            # Check if task is in queue (would need to implement queue removal)
            # For now, mark as cancelled in database
            self._update_task_status(task_id, TaskStatus.CANCELLED)
            return True

        except Exception as e:
            logger.error(f"Error cancelling task {task_id}: {e}")
            return False

    def get_queue_status(self) -> dict[str, Any]:
        """Get current queue status and statistics"""
        return {
            "is_running": self.is_running,
            "queue_size": self.task_queue.qsize(),
            "running_tasks": len(self.running_tasks),
            "completed_tasks": len(self.completed_tasks),
            "max_concurrent": self.max_concurrent_tasks,
            "resource_usage": self.resource_monitor.get_current_usage(),
            "task_types": {
                task_type.value: self._count_tasks_by_type(task_type) for task_type in TaskType
            },
        }

    def _worker_loop(self):
        """Main worker loop for processing tasks"""
        while self.is_running:
            try:
                # Get next task from queue
                priority, created_at, task = self.task_queue.get(timeout=1)

                # Check if task should be cancelled
                if task.status == TaskStatus.CANCELLED:
                    continue

                # Check resource availability
                if not self.resource_monitor.can_allocate_resources(task.resource_requirements):
                    # Put task back in queue
                    self.task_queue.put((priority, created_at, task))
                    time.sleep(1)
                    continue

                # Process task
                self._process_task(task)

            except Empty:
                # No tasks in queue, continue
                continue
            except Exception as e:
                logger.error(f"Error in worker loop: {e}")
                time.sleep(1)

    def _process_task(self, task: MLTask):
        """Process a single task"""
        try:
            # Update task status
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            self.running_tasks[task.task_id] = task
            self._update_task_status(task.task_id, TaskStatus.RUNNING)

            logger.info(f"Processing task {task.task_id} of type {task.task_type.value}")

            # Get task handler
            handler = self.task_handlers.get(task.task_type)
            if not handler:
                raise ValueError(f"No handler for task type {task.task_type}")

            # Execute task
            result = handler(task)

            # Update task with result
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result

            # Move to completed tasks
            self.completed_tasks[task.task_id] = task
            del self.running_tasks[task.task_id]

            # Update database
            self._update_task_completion(task)

            logger.info(f"Task {task.task_id} completed successfully")

        except Exception as e:
            logger.error(f"Error processing task {task.task_id}: {e}")
            self._handle_task_failure(task, str(e))

    def _handle_task_failure(self, task: MLTask, error: str):
        """Handle task failure with retry logic"""
        task.error = error
        task.retry_count += 1

        if task.retry_count < task.max_retries:
            # Retry task
            task.status = TaskStatus.PENDING
            task.started_at = None
            task.error = None
            self.task_queue.put((task.priority.value, task.created_at, task))
            logger.info(f"Retrying task {task.task_id} (attempt {task.retry_count + 1})")
        else:
            # Mark as failed
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            self.completed_tasks[task.task_id] = task
            if task.task_id in self.running_tasks:
                del self.running_tasks[task.task_id]

            self._update_task_completion(task)
            logger.error(f"Task {task.task_id} failed after {task.max_retries} retries")

    # Task handlers for different ML operations
    def _handle_timeline_generation(self, task: MLTask) -> dict[str, Any]:
        """
        Legacy ML timeline path retired (was TimelineGenerator + unscoped articles / timeline_events).

        Use automation phase 'timeline_generation' (TimelineBuilderService, public.chronological_events,
        domain storylines) or GET /api/{domain}/storylines/{id}/timeline.
        """
        logger.warning(
            "Ignoring retired ML queue task TIMELINE_GENERATION task_id=%s storyline_id=%s — "
            "use automation timeline_generation or timeline API",
            task.task_id,
            task.storyline_id,
        )
        return {
            "events_generated": 0,
            "events": [],
            "deprecated": True,
            "message": (
                "ML queue timeline_generation is retired. "
                "Use automation task timeline_generation or GET /api/{domain}/storylines/{id}/timeline."
            ),
        }

    def _handle_article_summarization(self, task: MLTask) -> dict[str, Any]:
        """Handle article summarization task"""
        # Implementation for article summarization
        return {"summary": "Generated summary", "status": "completed"}

    def _handle_content_analysis(self, task: MLTask) -> dict[str, Any]:
        """Handle content analysis task"""
        # Implementation for content analysis
        return {"analysis": "Content analyzed", "status": "completed"}

    def _handle_entity_extraction(self, task: MLTask) -> dict[str, Any]:
        """Handle entity extraction task"""
        # Implementation for entity extraction
        return {"entities": [], "status": "completed"}

    def _handle_sentiment_analysis(self, task: MLTask) -> dict[str, Any]:
        """Handle sentiment analysis task"""
        # Implementation for sentiment analysis
        return {"sentiment": "neutral", "score": 0.0}

    def _handle_quality_scoring(self, task: MLTask) -> dict[str, Any]:
        """Handle quality scoring task"""
        # Implementation for quality scoring
        return {"quality_score": 0.8, "status": "completed"}

    def _handle_storyline_analysis(self, task: MLTask) -> dict[str, Any]:
        """Handle storyline analysis task"""
        # Implementation for storyline analysis
        return {"analysis": "Storyline analyzed", "status": "completed"}

    def _validate_task(self, task: MLTask) -> bool:
        """Validate task before submission"""
        if not task.task_id or not task.task_type:
            return False

        if task.task_type not in self.task_handlers:
            return False

        return True

    def _store_task(self, task: MLTask):
        """Store task in database"""
        conn = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute(
                """
                INSERT INTO ml_task_queue (
                    task_id, task_type, priority, storyline_id, article_id,
                    payload, status, created_at, estimated_duration, resource_requirements
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (task_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    updated_at = CURRENT_TIMESTAMP
            """,
                (
                    task.task_id,
                    task.task_type.value,
                    task.priority.value,
                    task.storyline_id,
                    task.article_id,
                    json.dumps(task.payload),
                    task.status.value,
                    task.created_at,
                    task.estimated_duration,
                    json.dumps(task.resource_requirements),
                ),
            )

            conn.commit()
            cur.close()

        except Exception as e:
            logger.error(f"Error storing task {task.task_id}: {e}")
        finally:
            if conn:
                conn.close()

    def _load_pending_tasks(self):
        """Load pending tasks from database on startup"""
        conn = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute("""
                SELECT task_id, task_type, priority, storyline_id, article_id,
                       payload, status, created_at, estimated_duration, resource_requirements
                FROM ml_task_queue
                WHERE status IN ('pending', 'running')
                ORDER BY priority DESC, created_at ASC
            """)

            rows = cur.fetchall()
            cur.close()

            for row in rows:
                task = MLTask(
                    task_id=row[0],
                    task_type=TaskType(row[1]),
                    priority=TaskPriority(row[2]),
                    storyline_id=row[3],
                    article_id=row[4],
                    payload=json.loads(row[5]) if row[5] else {},
                    status=TaskStatus(row[6]),
                    created_at=row[7],
                    estimated_duration=row[8],
                    resource_requirements=json.loads(row[9]) if row[9] else {},
                )

                # Add to queue
                self.task_queue.put((task.priority.value, task.created_at, task))

            logger.info(f"Loaded {len(rows)} pending tasks from database")

        except Exception as e:
            logger.error(f"Error loading pending tasks: {e}")
        finally:
            if conn:
                conn.close()

    def _load_task_from_db(self, task_id: str) -> MLTask | None:
        """Load a specific task from database"""
        conn = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute(
                """
                SELECT task_id, task_type, priority, storyline_id, article_id,
                       payload, status, created_at, started_at, completed_at,
                       result, error, retry_count, estimated_duration, resource_requirements
                FROM ml_task_queue
                WHERE task_id = %s
            """,
                (task_id,),
            )

            row = cur.fetchone()
            cur.close()

            if row:
                return MLTask(
                    task_id=row[0],
                    task_type=TaskType(row[1]),
                    priority=TaskPriority(row[2]),
                    storyline_id=row[3],
                    article_id=row[4],
                    payload=json.loads(row[5]) if row[5] else {},
                    status=TaskStatus(row[6]),
                    created_at=row[7],
                    started_at=row[8],
                    completed_at=row[9],
                    result=json.loads(row[10]) if row[10] else None,
                    error=row[11],
                    retry_count=row[12] or 0,
                    estimated_duration=row[13] or 30,
                    resource_requirements=json.loads(row[14]) if row[14] else {},
                )

            return None

        except Exception as e:
            logger.error(f"Error loading task {task_id}: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def _update_task_status(self, task_id: str, status: TaskStatus):
        """Update task status in database"""
        conn = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute(
                """
                UPDATE ml_task_queue
                SET status = %s, updated_at = CURRENT_TIMESTAMP
                WHERE task_id = %s
            """,
                (status.value, task_id),
            )

            conn.commit()
            cur.close()

        except Exception as e:
            logger.error(f"Error updating task status: {e}")
        finally:
            if conn:
                conn.close()

    def _update_task_completion(self, task: MLTask):
        """Update task completion in database"""
        conn = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute(
                """
                UPDATE ml_task_queue
                SET status = %s, started_at = %s, completed_at = %s,
                    result = %s, error = %s, retry_count = %s, updated_at = CURRENT_TIMESTAMP
                WHERE task_id = %s
            """,
                (
                    task.status.value,
                    task.started_at,
                    task.completed_at,
                    json.dumps(task.result) if task.result else None,
                    task.error,
                    task.retry_count,
                    task.task_id,
                ),
            )

            conn.commit()
            cur.close()

        except Exception as e:
            logger.error(f"Error updating task completion: {e}")
        finally:
            if conn:
                conn.close()

    def _count_tasks_by_type(self, task_type: TaskType) -> int:
        """Count tasks by type"""
        count = 0
        for task in self.running_tasks.values():
            if task.task_type == task_type:
                count += 1
        for task in self.completed_tasks.values():
            if task.task_type == task_type:
                count += 1
        return count


class ResourceMonitor:
    """Monitors system resources for ML tasks"""

    def __init__(self):
        self.cpu_usage = 0.0
        self.memory_usage = 0.0
        self.gpu_usage = 0.0
        self.is_monitoring = False
        self.monitor_thread = None

    def start(self):
        """Start resource monitoring"""
        if self.is_monitoring:
            return

        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

    def stop(self):
        """Stop resource monitoring"""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join()

    def _monitor_loop(self):
        """Resource monitoring loop"""
        while self.is_monitoring:
            try:
                # Monitor CPU and memory usage
                import psutil

                self.cpu_usage = psutil.cpu_percent()
                self.memory_usage = psutil.virtual_memory().percent

                # Monitor GPU usage if available
                try:
                    import subprocess

                    result = subprocess.run(
                        [
                            "nvidia-smi",
                            "--query-gpu=utilization.gpu",
                            "--format=csv,noheader,nounits",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if result.returncode == 0:
                        self.gpu_usage = float(result.stdout.strip())
                except:
                    self.gpu_usage = 0.0

                time.sleep(5)  # Monitor every 5 seconds

            except Exception as e:
                logger.error(f"Error in resource monitoring: {e}")
                time.sleep(10)

    def can_allocate_resources(self, requirements: dict[str, Any]) -> bool:
        """Check if resources can be allocated for a task"""
        max_cpu = requirements.get("max_cpu_usage", 80.0)
        max_memory = requirements.get("max_memory_usage", 80.0)
        max_gpu = requirements.get("max_gpu_usage", 80.0)

        return (
            self.cpu_usage < max_cpu and self.memory_usage < max_memory and self.gpu_usage < max_gpu
        )

    def get_current_usage(self) -> dict[str, float]:
        """Get current resource usage"""
        return {
            "cpu_usage": self.cpu_usage,
            "memory_usage": self.memory_usage,
            "gpu_usage": self.gpu_usage,
        }
