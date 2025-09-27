"""
Dynamic Priority Manager for News Intelligence System
Handles competing priorities and workload balancing for 70b model
"""

import asyncio
import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from queue import PriorityQueue, Empty
import psycopg2
import json
import requests
import numpy as np
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

class WorkloadType(Enum):
    """Types of workloads with different resource requirements"""
    BREAKING_NEWS = "breaking_news"          # High volume, fast processing needed
    STORYLINE_ANALYSIS = "storyline_analysis" # Deep analysis, sustained attention
    USER_REQUEST = "user_request"            # Immediate user interaction
    BATCH_PROCESSING = "batch_processing"    # Large volume, can be delayed
    MAINTENANCE = "maintenance"              # Background tasks
    REAL_TIME = "real_time"                  # Live updates, low latency

class PriorityLevel(Enum):
    """Dynamic priority levels that can change based on context"""
    CRITICAL = 1      # Breaking news, user requests
    HIGH = 2          # Storyline analysis, important updates
    NORMAL = 3        # Regular article processing
    LOW = 4           # Batch processing, maintenance
    BACKGROUND = 5    # Cleanup, optimization

@dataclass
class WorkloadContext:
    """Context information for workload management"""
    current_workload_type: WorkloadType
    article_volume: int = 0
    storyline_queue_size: int = 0
    user_requests_pending: int = 0
    system_load: float = 0.0
    gpu_utilization: float = 0.0
    memory_usage: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class DynamicTask:
    """Task with dynamic priority that can change based on context"""
    task_id: str
    task_type: str
    base_priority: PriorityLevel
    current_priority: PriorityLevel
    workload_type: WorkloadType
    payload: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "pending"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    estimated_duration: int = 30
    resource_requirements: Dict[str, Any] = field(default_factory=dict)
    priority_factors: Dict[str, float] = field(default_factory=dict)
    
    def calculate_dynamic_priority(self, context: WorkloadContext) -> PriorityLevel:
        """Calculate dynamic priority based on current context"""
        base_score = self.base_priority.value
        
        # Adjust based on workload type
        workload_multipliers = {
            WorkloadType.BREAKING_NEWS: 0.5,      # Higher priority during breaking news
            WorkloadType.USER_REQUEST: 0.3,       # Always high priority
            WorkloadType.STORYLINE_ANALYSIS: 1.0, # Normal priority
            WorkloadType.BATCH_PROCESSING: 1.5,   # Lower priority
            WorkloadType.MAINTENANCE: 2.0,        # Lowest priority
            WorkloadType.REAL_TIME: 0.2,          # Highest priority
        }
        
        # Adjust based on system load
        load_factor = 1.0 + (context.system_load * 0.5)
        
        # Adjust based on queue sizes
        queue_factor = 1.0
        if self.workload_type == WorkloadType.BREAKING_NEWS and context.article_volume > 100:
            queue_factor = 0.7  # Higher priority when many articles
        elif self.workload_type == WorkloadType.STORYLINE_ANALYSIS and context.storyline_queue_size > 10:
            queue_factor = 0.8  # Slightly higher priority when backlogged
        
        # Calculate final priority
        final_score = base_score * workload_multipliers.get(self.workload_type, 1.0) * load_factor * queue_factor
        
        # Convert back to priority level
        if final_score <= 0.5:
            return PriorityLevel.CRITICAL
        elif final_score <= 1.0:
            return PriorityLevel.HIGH
        elif final_score <= 1.5:
            return PriorityLevel.NORMAL
        elif final_score <= 2.0:
            return PriorityLevel.LOW
        else:
            return PriorityLevel.BACKGROUND

class DynamicPriorityManager:
    """
    Manages competing priorities and workload balancing for 70b model
    """
    
    def __init__(self, db_config: Dict[str, str], ollama_url: str = "http://localhost:11434"):
        self.db_config = db_config
        self.ollama_url = ollama_url
        
        # Resource pools with dynamic sizing
        self.gpu_intensive_pool = ThreadPoolExecutor(max_workers=3)
        self.medium_gpu_pool = ThreadPoolExecutor(max_workers=6)
        self.cpu_only_pool = ThreadPoolExecutor(max_workers=10)
        
        # Dynamic task queues by workload type
        self.workload_queues = {
            workload_type: PriorityQueue() for workload_type in WorkloadType
        }
        
        # Running tasks tracking
        self.running_tasks: Dict[str, DynamicTask] = {}
        self.completed_tasks: Dict[str, DynamicTask] = {}
        
        # Context tracking
        self.current_context = WorkloadContext(WorkloadType.NORMAL)
        self.context_history = deque(maxlen=100)  # Keep last 100 context snapshots
        
        # Statistics
        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'avg_processing_time': 0.0,
            'priority_changes': 0,
            'workload_switches': 0,
            'gpu_utilization': 0.0,
            'cpu_utilization': 0.0,
            'queue_sizes': {wt.value: 0 for wt in WorkloadType}
        }
        
        self.is_running = False
        self.worker_threads = []
        
        # Priority adjustment intervals
        self.priority_adjustment_interval = 30  # seconds
        self.context_update_interval = 10       # seconds
        
        # Initialize task handlers
        self._register_task_handlers()
    
    def _register_task_handlers(self):
        """Register handlers for different task types"""
        self.task_handlers = {
            "article_summarization": self._handle_article_summarization,
            "storyline_analysis": self._handle_storyline_analysis,
            "content_analysis": self._handle_content_analysis,
            "sentiment_analysis": self._handle_sentiment_analysis,
            "entity_extraction": self._handle_entity_extraction,
            "quality_scoring": self._handle_quality_scoring,
            "readability_analysis": self._handle_readability_analysis,
            "timeline_generation": self._handle_timeline_generation,
        }
    
    def start(self):
        """Start the dynamic priority manager"""
        if self.is_running:
            logger.warning("Dynamic priority manager is already running")
            return
        
        self.is_running = True
        logger.info("🚀 Starting dynamic priority manager for 70b model")
        logger.info("   - Adaptive workload balancing")
        logger.info("   - Dynamic priority adjustment")
        logger.info("   - Context-aware resource allocation")
        
        # Start worker threads for each workload type
        for workload_type in WorkloadType:
            worker = threading.Thread(
                target=self._workload_worker_loop,
                args=(workload_type,),
                name=f"WorkloadWorker-{workload_type.value}",
                daemon=True
            )
            worker.start()
            self.worker_threads.append(worker)
        
        # Start context monitor
        context_monitor = threading.Thread(
            target=self._context_monitor,
            name="ContextMonitor",
            daemon=True
        )
        context_monitor.start()
        self.worker_threads.append(context_monitor)
        
        # Start priority adjuster
        priority_adjuster = threading.Thread(
            target=self._priority_adjuster,
            name="PriorityAdjuster",
            daemon=True
        )
        priority_adjuster.start()
        self.worker_threads.append(priority_adjuster)
    
    def stop(self):
        """Stop the dynamic priority manager"""
        if not self.is_running:
            return
        
        logger.info("Stopping dynamic priority manager...")
        self.is_running = False
        
        # Shutdown thread pools
        self.gpu_intensive_pool.shutdown(wait=True)
        self.medium_gpu_pool.shutdown(wait=True)
        self.cpu_only_pool.shutdown(wait=True)
        
        # Wait for worker threads
        for worker in self.worker_threads:
            worker.join(timeout=30)
        
        self.worker_threads.clear()
        logger.info("Dynamic priority manager stopped")
    
    def submit_task(self, task: DynamicTask) -> str:
        """Submit a task with dynamic priority management"""
        task.task_id = str(uuid.uuid4())
        task.status = "pending"
        task.created_at = datetime.now()
        
        # Calculate initial dynamic priority
        task.current_priority = task.calculate_dynamic_priority(self.current_context)
        
        # Add to appropriate workload queue
        self.workload_queues[task.workload_type].put((
            task.current_priority.value,
            task.created_at,
            task
        ))
        
        # Update statistics
        self.stats['queue_sizes'][task.workload_type.value] += 1
        
        logger.info(f"📝 Task submitted: {task.task_type} ({task.workload_type.value}) - Priority: {task.current_priority.name}")
        return task.task_id
    
    def _workload_worker_loop(self, workload_type: WorkloadType):
        """Worker loop for specific workload type"""
        while self.is_running:
            try:
                # Get next task from queue
                priority, created_at, task = self.workload_queues[workload_type].get(timeout=1)
                
                if task is None:
                    continue
                
                # Recalculate priority based on current context
                old_priority = task.current_priority
                task.current_priority = task.calculate_dynamic_priority(self.current_context)
                
                if old_priority != task.current_priority:
                    self.stats['priority_changes'] += 1
                    logger.debug(f"🔄 Priority changed for task {task.task_id}: {old_priority.name} -> {task.current_priority.name}")
                
                # Check if we can process this task
                if not self._can_process_task(task):
                    # Put task back in queue with updated priority
                    self.workload_queues[workload_type].put((
                        task.current_priority.value,
                        created_at,
                        task
                    ))
                    time.sleep(0.1)
                    continue
                
                # Process task
                self._process_task(task)
                
            except Empty:
                continue
            except Exception as e:
                logger.error(f"❌ Error in workload worker loop for {workload_type.value}: {e}")
                time.sleep(1)
    
    def _can_process_task(self, task: DynamicTask) -> bool:
        """Check if we can process a task based on resource availability and priority"""
        requirements = task.resource_requirements
        max_concurrent = requirements.get("max_concurrent", 4)
        
        # Count running tasks of this type
        running_count = sum(1 for t in self.running_tasks.values() if t.task_type == task.task_type)
        
        # Check if we have capacity
        if running_count >= max_concurrent:
            return False
        
        # Check if higher priority tasks are waiting
        if self._has_higher_priority_tasks_waiting(task):
            return False
        
        return True
    
    def _has_higher_priority_tasks_waiting(self, task: DynamicTask) -> bool:
        """Check if there are higher priority tasks waiting"""
        for workload_type, queue in self.workload_queues.items():
            if queue.qsize() > 0:
                # Check if any task in this queue has higher priority
                try:
                    # Peek at the next task without removing it
                    with queue.mutex:
                        if queue.queue:
                            next_priority = queue.queue[0][0]
                            if next_priority < task.current_priority.value:
                                return True
                except:
                    pass
        
        return False
    
    def _process_task(self, task: DynamicTask):
        """Process a task using the appropriate thread pool"""
        task.status = "running"
        task.started_at = datetime.now()
        self.running_tasks[task.task_id] = task
        
        # Update queue size
        self.stats['queue_sizes'][task.workload_type.value] -= 1
        
        try:
            # Select appropriate thread pool based on task type and current load
            pool = self._select_thread_pool(task)
            
            # Submit to thread pool
            future = pool.submit(self._execute_task, task)
            
            # Wait for completion with timeout based on priority
            timeout = self._calculate_timeout(task)
            result = future.result(timeout=timeout)
            
            task.result = result
            task.status = "completed"
            task.completed_at = datetime.now()
            
            # Update statistics
            self.stats['successful'] += 1
            processing_time = (task.completed_at - task.started_at).total_seconds()
            self.stats['avg_processing_time'] = (
                (self.stats['avg_processing_time'] * (self.stats['total_processed'] - 1) + processing_time) 
                / self.stats['total_processed']
            )
            
            logger.info(f"✅ Task completed: {task.task_type} ({task.workload_type.value}) in {processing_time:.2f}s")
            
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            task.completed_at = datetime.now()
            self.stats['failed'] += 1
            
            logger.error(f"❌ Task failed: {task.task_type} ({task.workload_type.value}): {e}")
            
            # Retry logic with exponential backoff
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = "pending"
                task.started_at = None
                task.completed_at = None
                task.error = None
                
                # Exponential backoff delay
                delay = min(60, 2 ** task.retry_count)
                time.sleep(delay)
                
                # Put back in queue
                self.workload_queues[task.workload_type].put((
                    task.current_priority.value,
                    task.created_at,
                    task
                ))
                self.stats['queue_sizes'][task.workload_type.value] += 1
                logger.info(f"🔄 Retrying task: {task.task_type} ({task.workload_type.value}) - attempt {task.retry_count}")
        
        finally:
            # Move to completed tasks
            if task.task_id in self.running_tasks:
                del self.running_tasks[task.task_id]
            
            self.completed_tasks[task.task_id] = task
            self.stats['total_processed'] += 1
    
    def _select_thread_pool(self, task: DynamicTask) -> ThreadPoolExecutor:
        """Select appropriate thread pool based on task type and current load"""
        # Base selection on task type
        if task.task_type in ["article_summarization", "storyline_analysis", "content_analysis", "timeline_generation"]:
            base_pool = self.gpu_intensive_pool
        elif task.task_type in ["sentiment_analysis", "entity_extraction", "quality_scoring"]:
            base_pool = self.medium_gpu_pool
        else:
            base_pool = self.cpu_only_pool
        
        # Adjust based on current system load
        if self.current_context.gpu_utilization > 80:
            # If GPU is overloaded, try to use CPU pool for some tasks
            if task.task_type in ["sentiment_analysis", "entity_extraction"]:
                return self.cpu_only_pool
        
        return base_pool
    
    def _calculate_timeout(self, task: DynamicTask) -> int:
        """Calculate timeout based on task priority and type"""
        base_timeout = 300  # 5 minutes
        
        # Adjust based on priority
        priority_multipliers = {
            PriorityLevel.CRITICAL: 0.5,
            PriorityLevel.HIGH: 0.7,
            PriorityLevel.NORMAL: 1.0,
            PriorityLevel.LOW: 1.5,
            PriorityLevel.BACKGROUND: 2.0,
        }
        
        # Adjust based on workload type
        workload_multipliers = {
            WorkloadType.BREAKING_NEWS: 0.5,
            WorkloadType.USER_REQUEST: 0.3,
            WorkloadType.REAL_TIME: 0.2,
            WorkloadType.STORYLINE_ANALYSIS: 2.0,
            WorkloadType.BATCH_PROCESSING: 3.0,
            WorkloadType.MAINTENANCE: 5.0,
        }
        
        timeout = base_timeout * priority_multipliers.get(task.current_priority, 1.0) * workload_multipliers.get(task.workload_type, 1.0)
        return int(timeout)
    
    def _execute_task(self, task: DynamicTask) -> Dict[str, Any]:
        """Execute the actual ML task"""
        handler = self.task_handlers.get(task.task_type)
        if not handler:
            raise ValueError(f"No handler for task type: {task.task_type}")
        
        return handler(task)
    
    def _context_monitor(self):
        """Monitor system context and update workload type"""
        while self.is_running:
            try:
                # Update system metrics
                self.current_context.gpu_utilization = self._get_gpu_utilization()
                self.current_context.system_load = self._get_system_load()
                self.current_context.memory_usage = self._get_memory_usage()
                
                # Update queue sizes
                self.current_context.article_volume = self.stats['queue_sizes'][WorkloadType.BREAKING_NEWS.value]
                self.current_context.storyline_queue_size = self.stats['queue_sizes'][WorkloadType.STORYLINE_ANALYSIS.value]
                self.current_context.user_requests_pending = self.stats['queue_sizes'][WorkloadType.USER_REQUEST.value]
                
                # Determine current workload type
                old_workload_type = self.current_context.current_workload_type
                self.current_context.current_workload_type = self._determine_workload_type()
                
                if old_workload_type != self.current_context.current_workload_type:
                    self.stats['workload_switches'] += 1
                    logger.info(f"🔄 Workload type changed: {old_workload_type.value} -> {self.current_context.current_workload_type.value}")
                
                # Store context history
                self.context_history.append(self.current_context)
                
                time.sleep(self.context_update_interval)
                
            except Exception as e:
                logger.error(f"❌ Error in context monitor: {e}")
                time.sleep(self.context_update_interval)
    
    def _determine_workload_type(self) -> WorkloadType:
        """Determine current workload type based on system state"""
        # Check for breaking news (high article volume)
        if self.current_context.article_volume > 50:
            return WorkloadType.BREAKING_NEWS
        
        # Check for user requests
        if self.current_context.user_requests_pending > 0:
            return WorkloadType.USER_REQUEST
        
        # Check for real-time requirements
        if self.current_context.gpu_utilization > 70 and self.current_context.system_load > 0.8:
            return WorkloadType.REAL_TIME
        
        # Check for storyline analysis backlog
        if self.current_context.storyline_queue_size > 5:
            return WorkloadType.STORYLINE_ANALYSIS
        
        # Check for batch processing
        if self.current_context.article_volume > 20:
            return WorkloadType.BATCH_PROCESSING
        
        # Default to normal processing
        return WorkloadType.NORMAL
    
    def _priority_adjuster(self):
        """Adjust task priorities based on current context"""
        while self.is_running:
            try:
                # Recalculate priorities for all pending tasks
                for workload_type, queue in self.workload_queues.items():
                    if queue.qsize() > 0:
                        # Get all tasks from queue
                        tasks = []
                        while not queue.empty():
                            try:
                                priority, created_at, task = queue.get_nowait()
                                # Recalculate priority
                                task.current_priority = task.calculate_dynamic_priority(self.current_context)
                                tasks.append((task.current_priority.value, created_at, task))
                            except Empty:
                                break
                        
                        # Put tasks back with updated priorities
                        for priority, created_at, task in tasks:
                            queue.put((priority, created_at, task))
                
                time.sleep(self.priority_adjustment_interval)
                
            except Exception as e:
                logger.error(f"❌ Error in priority adjuster: {e}")
                time.sleep(self.priority_adjustment_interval)
    
    def _get_gpu_utilization(self) -> float:
        """Get GPU utilization percentage"""
        try:
            import subprocess
            result = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'], 
                                  capture_output=True, text=True)
            return float(result.stdout.strip())
        except:
            return 0.0
    
    def _get_system_load(self) -> float:
        """Get system load average"""
        try:
            import psutil
            return psutil.getloadavg()[0]
        except:
            return 0.0
    
    def _get_memory_usage(self) -> float:
        """Get memory usage percentage"""
        try:
            import psutil
            return psutil.virtual_memory().percent
        except:
            return 0.0
    
    # Task handlers (placeholder implementations)
    def _handle_article_summarization(self, task: DynamicTask) -> Dict[str, Any]:
        return {"summary": "Generated summary", "model": "llama3.1:70b", "workload_type": task.workload_type.value}
    
    def _handle_storyline_analysis(self, task: DynamicTask) -> Dict[str, Any]:
        return {"analysis": "Generated analysis", "model": "llama3.1:70b", "workload_type": task.workload_type.value}
    
    def _handle_content_analysis(self, task: DynamicTask) -> Dict[str, Any]:
        return {"analysis": "Generated content analysis", "model": "llama3.1:70b", "workload_type": task.workload_type.value}
    
    def _handle_sentiment_analysis(self, task: DynamicTask) -> Dict[str, Any]:
        return {"sentiment": "positive", "model": "llama3.1:70b", "workload_type": task.workload_type.value}
    
    def _handle_entity_extraction(self, task: DynamicTask) -> Dict[str, Any]:
        return {"entities": [], "model": "llama3.1:70b", "workload_type": task.workload_type.value}
    
    def _handle_quality_scoring(self, task: DynamicTask) -> Dict[str, Any]:
        return {"quality_score": 0.8, "model": "llama3.1:70b", "workload_type": task.workload_type.value}
    
    def _handle_readability_analysis(self, task: DynamicTask) -> Dict[str, Any]:
        return {"readability": "good", "model": "cpu-only", "workload_type": task.workload_type.value}
    
    def _handle_timeline_generation(self, task: DynamicTask) -> Dict[str, Any]:
        return {"timeline": [], "model": "llama3.1:70b", "workload_type": task.workload_type.value}
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive processing statistics"""
        return {
            **self.stats,
            'running_tasks': len(self.running_tasks),
            'completed_tasks': len(self.completed_tasks),
            'current_workload_type': self.current_context.current_workload_type.value,
            'gpu_utilization': self.current_context.gpu_utilization,
            'system_load': self.current_context.system_load,
            'memory_usage': self.current_context.memory_usage,
            'context_history_size': len(self.context_history)
        }
    
    def get_workload_recommendations(self) -> Dict[str, Any]:
        """Get recommendations for workload optimization"""
        recommendations = []
        
        # GPU utilization recommendations
        if self.current_context.gpu_utilization > 90:
            recommendations.append("⚠️ GPU utilization very high - consider reducing concurrent tasks")
        elif self.current_context.gpu_utilization < 50:
            recommendations.append("💡 GPU utilization low - can increase concurrent tasks")
        
        # Queue size recommendations
        if self.current_context.article_volume > 100:
            recommendations.append("🚨 High article volume - prioritize breaking news processing")
        
        if self.current_context.storyline_queue_size > 10:
            recommendations.append("📚 Storyline analysis backlog - consider increasing resources")
        
        # System load recommendations
        if self.current_context.system_load > 0.8:
            recommendations.append("⚡ High system load - consider reducing task complexity")
        
        return {
            "recommendations": recommendations,
            "current_context": {
                "workload_type": self.current_context.current_workload_type.value,
                "article_volume": self.current_context.article_volume,
                "storyline_queue_size": self.current_context.storyline_queue_size,
                "user_requests_pending": self.current_context.user_requests_pending,
                "gpu_utilization": self.current_context.gpu_utilization,
                "system_load": self.current_context.system_load,
                "memory_usage": self.current_context.memory_usage
            }
        }
