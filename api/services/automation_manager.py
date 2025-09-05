"""
News Intelligence System v3.1.0 - Enterprise Automation Manager
Industry-standard background processing with scalability and reliability
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
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
        
        # Task schedules (cron-like)
        self.schedules = {
            'rss_processing': {
                'interval': 300,  # 5 minutes
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.HIGH
            },
            'digest_generation': {
                'interval': 3600,  # 1 hour
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.NORMAL
            },
            'data_cleanup': {
                'interval': 86400,  # 24 hours
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.LOW
            },
            'health_check': {
                'interval': 60,  # 1 minute
                'last_run': None,
                'enabled': True,
                'priority': TaskPriority.CRITICAL
            }
        }
        
        # Performance metrics
        self.metrics = {
            'tasks_completed': 0,
            'tasks_failed': 0,
            'avg_processing_time': 0,
            'system_uptime': 0,
            'last_health_check': None
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
        """Task scheduler"""
        logger.info("Scheduler started")
        
        while self.is_running:
            try:
                current_time = datetime.now(timezone.utc)
                
                for task_name, schedule in self.schedules.items():
                    if not schedule['enabled']:
                        continue
                        
                    # Check if task should run
                    if (schedule['last_run'] is None or 
                        (current_time - schedule['last_run']).total_seconds() >= schedule['interval']):
                        
                        # Create task
                        task = Task(
                            id=f"{task_name}_{int(current_time.timestamp())}",
                            name=task_name,
                            priority=schedule['priority'],
                            status=TaskStatus.PENDING,
                            created_at=current_time,
                            metadata={'scheduled': True}
                        )
                        
                        # Add to queue
                        await self.task_queue.put(task)
                        schedule['last_run'] = current_time
                        
                        logger.info(f"Scheduled task: {task_name}")
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(10)
        
        logger.info("Scheduler stopped")
        
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
            else:
                raise ValueError(f"Unknown task type: {task.name}")
            
            # Mark as completed
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc)
            self.metrics['tasks_completed'] += 1
            
            # Calculate processing time
            processing_time = (task.completed_at - task.started_at).total_seconds()
            self._update_avg_processing_time(processing_time)
            
            logger.info(f"Task {task.name} completed in {processing_time:.2f}s")
            
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
        db_config = {
            'host': 'news-system-postgres',
            'database': 'newsintelligence',
            'user': 'newsapp',
            'password': 'Database@NEWSINT2025',
            'port': '5432'
        }
        automation_manager = AutomationManager(db_config)
    return automation_manager
