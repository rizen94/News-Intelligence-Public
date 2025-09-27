"""
Optimized Parallel ML Processor for News Intelligence System
Designed for RTX 5090 with 32GB VRAM and llama3.1:70b model
"""

import asyncio
import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from queue import PriorityQueue, Empty
import psycopg2
import json
import requests

logger = logging.getLogger(__name__)

class TaskPriority(Enum):
    """Task priority levels optimized for 70b model"""
    LOW = 1          # Readability, preprocessing
    NORMAL = 2       # Sentiment, entity extraction
    HIGH = 3         # Article summarization
    URGENT = 4       # Storyline analysis, critical content

class TaskType(Enum):
    """ML task types with resource requirements"""
    ARTICLE_SUMMARIZATION = "article_summarization"    # GPU-intensive, 2-3 concurrent
    STORYLINE_ANALYSIS = "storyline_analysis"          # GPU-intensive, 1-2 concurrent
    CONTENT_ANALYSIS = "content_analysis"              # GPU-intensive, 2-3 concurrent
    SENTIMENT_ANALYSIS = "sentiment_analysis"          # Medium GPU, 4-6 concurrent
    ENTITY_EXTRACTION = "entity_extraction"            # Medium GPU, 4-6 concurrent
    QUALITY_SCORING = "quality_scoring"                # Medium GPU, 3-4 concurrent
    READABILITY_ANALYSIS = "readability_analysis"      # CPU-only, 8-10 concurrent
    TIMELINE_GENERATION = "timeline_generation"        # GPU-intensive, 2-3 concurrent

@dataclass
class MLTask:
    """Optimized ML task with resource requirements"""
    task_id: str
    task_type: TaskType
    priority: TaskPriority
    storyline_id: Optional[str] = None
    article_id: Optional[int] = None
    payload: Dict[str, Any] = None
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "pending"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    estimated_duration: int = 30
    resource_requirements: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.payload is None:
            self.payload = {}
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.resource_requirements is None:
            self.resource_requirements = self._get_resource_requirements()
    
    def _get_resource_requirements(self) -> Dict[str, Any]:
        """Get resource requirements based on task type"""
        requirements = {
            TaskType.ARTICLE_SUMMARIZATION: {"gpu_layers": 80, "max_concurrent": 3, "memory_gb": 8},
            TaskType.STORYLINE_ANALYSIS: {"gpu_layers": 80, "max_concurrent": 2, "memory_gb": 12},
            TaskType.CONTENT_ANALYSIS: {"gpu_layers": 80, "max_concurrent": 3, "memory_gb": 8},
            TaskType.SENTIMENT_ANALYSIS: {"gpu_layers": 40, "max_concurrent": 6, "memory_gb": 4},
            TaskType.ENTITY_EXTRACTION: {"gpu_layers": 40, "max_concurrent": 6, "memory_gb": 4},
            TaskType.QUALITY_SCORING: {"gpu_layers": 60, "max_concurrent": 4, "memory_gb": 6},
            TaskType.READABILITY_ANALYSIS: {"gpu_layers": 0, "max_concurrent": 10, "memory_gb": 1},
            TaskType.TIMELINE_GENERATION: {"gpu_layers": 80, "max_concurrent": 3, "memory_gb": 8},
        }
        return requirements.get(self.task_type, {"gpu_layers": 40, "max_concurrent": 4, "memory_gb": 4})

class OptimizedParallelProcessor:
    """
    Optimized parallel processor for 70b model with RTX 5090
    """
    
    def __init__(self, db_config: Dict[str, str], ollama_url: str = "http://localhost:11434"):
        self.db_config = db_config
        self.ollama_url = ollama_url
        
        # Resource pools for different task types
        self.gpu_intensive_pool = ThreadPoolExecutor(max_workers=3)  # Article summarization, storyline analysis
        self.medium_gpu_pool = ThreadPoolExecutor(max_workers=6)     # Sentiment, entity extraction
        self.cpu_only_pool = ThreadPoolExecutor(max_workers=10)     # Readability analysis
        
        # Task queues by priority
        self.task_queues = {
            TaskType.ARTICLE_SUMMARIZATION: PriorityQueue(),
            TaskType.STORYLINE_ANALYSIS: PriorityQueue(),
            TaskType.CONTENT_ANALYSIS: PriorityQueue(),
            TaskType.SENTIMENT_ANALYSIS: PriorityQueue(),
            TaskType.ENTITY_EXTRACTION: PriorityQueue(),
            TaskType.QUALITY_SCORING: PriorityQueue(),
            TaskType.READABILITY_ANALYSIS: PriorityQueue(),
            TaskType.TIMELINE_GENERATION: PriorityQueue(),
        }
        
        # Running tasks tracking
        self.running_tasks: Dict[str, MLTask] = {}
        self.completed_tasks: Dict[str, MLTask] = {}
        
        # Statistics
        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'avg_processing_time': 0.0,
            'gpu_utilization': 0.0,
            'cpu_utilization': 0.0
        }
        
        self.is_running = False
        self.worker_threads = []
        
        # Initialize task handlers
        self._register_task_handlers()
    
    def _register_task_handlers(self):
        """Register optimized handlers for different task types"""
        self.task_handlers = {
            TaskType.ARTICLE_SUMMARIZATION: self._handle_article_summarization,
            TaskType.STORYLINE_ANALYSIS: self._handle_storyline_analysis,
            TaskType.CONTENT_ANALYSIS: self._handle_content_analysis,
            TaskType.SENTIMENT_ANALYSIS: self._handle_sentiment_analysis,
            TaskType.ENTITY_EXTRACTION: self._handle_entity_extraction,
            TaskType.QUALITY_SCORING: self._handle_quality_scoring,
            TaskType.READABILITY_ANALYSIS: self._handle_readability_analysis,
            TaskType.TIMELINE_GENERATION: self._handle_timeline_generation,
        }
    
    def start(self):
        """Start the optimized parallel processor"""
        if self.is_running:
            logger.warning("Processor is already running")
            return
        
        self.is_running = True
        logger.info("🚀 Starting optimized parallel ML processor for 70b model")
        logger.info(f"   GPU-intensive pool: 3 workers")
        logger.info(f"   Medium GPU pool: 6 workers") 
        logger.info(f"   CPU-only pool: 10 workers")
        
        # Start worker threads for each task type
        for task_type in TaskType:
            worker = threading.Thread(
                target=self._worker_loop,
                args=(task_type,),
                name=f"MLWorker-{task_type.value}",
                daemon=True
            )
            worker.start()
            self.worker_threads.append(worker)
        
        # Start resource monitor
        monitor = threading.Thread(
            target=self._resource_monitor,
            name="ResourceMonitor",
            daemon=True
        )
        monitor.start()
        self.worker_threads.append(monitor)
    
    def stop(self):
        """Stop the parallel processor"""
        if not self.is_running:
            return
        
        logger.info("Stopping optimized parallel processor...")
        self.is_running = False
        
        # Shutdown thread pools
        self.gpu_intensive_pool.shutdown(wait=True)
        self.medium_gpu_pool.shutdown(wait=True)
        self.cpu_only_pool.shutdown(wait=True)
        
        # Wait for worker threads
        for worker in self.worker_threads:
            worker.join(timeout=30)
        
        self.worker_threads.clear()
        logger.info("Optimized parallel processor stopped")
    
    def submit_task(self, task: MLTask) -> str:
        """Submit a task for processing"""
        task.task_id = str(uuid.uuid4())
        task.status = "pending"
        task.created_at = datetime.now()
        
        # Add to appropriate queue
        self.task_queues[task.task_type].put((task.priority.value, task.created_at, task))
        
        logger.info(f"📝 Task submitted: {task.task_type.value} (ID: {task.task_id})")
        return task.task_id
    
    def _worker_loop(self, task_type: TaskType):
        """Worker loop for specific task type"""
        while self.is_running:
            try:
                # Get next task from queue
                priority, created_at, task = self.task_queues[task_type].get(timeout=1)
                
                if task is None:
                    continue
                
                # Check if we can process this task type
                if not self._can_process_task(task):
                    # Put task back in queue
                    self.task_queues[task_type].put((priority, created_at, task))
                    time.sleep(0.1)
                    continue
                
                # Process task
                self._process_task(task)
                
            except Empty:
                continue
            except Exception as e:
                logger.error(f"❌ Error in worker loop for {task_type.value}: {e}")
                time.sleep(1)
    
    def _can_process_task(self, task: MLTask) -> bool:
        """Check if we can process a task based on resource availability"""
        requirements = task.resource_requirements
        max_concurrent = requirements.get("max_concurrent", 4)
        
        # Count running tasks of this type
        running_count = sum(1 for t in self.running_tasks.values() if t.task_type == task.task_type)
        
        return running_count < max_concurrent
    
    def _process_task(self, task: MLTask):
        """Process a task using the appropriate thread pool"""
        task.status = "running"
        task.started_at = datetime.now()
        self.running_tasks[task.task_id] = task
        
        try:
            # Select appropriate thread pool
            if task.task_type in [TaskType.ARTICLE_SUMMARIZATION, TaskType.STORYLINE_ANALYSIS, 
                                TaskType.CONTENT_ANALYSIS, TaskType.TIMELINE_GENERATION]:
                pool = self.gpu_intensive_pool
            elif task.task_type in [TaskType.SENTIMENT_ANALYSIS, TaskType.ENTITY_EXTRACTION, 
                                  TaskType.QUALITY_SCORING]:
                pool = self.medium_gpu_pool
            else:
                pool = self.cpu_only_pool
            
            # Submit to thread pool
            future = pool.submit(self._execute_task, task)
            
            # Wait for completion
            result = future.result(timeout=300)  # 5 minute timeout
            
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
            
            logger.info(f"✅ Task completed: {task.task_type.value} (ID: {task.task_id}) in {processing_time:.2f}s")
            
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            task.completed_at = datetime.now()
            self.stats['failed'] += 1
            
            logger.error(f"❌ Task failed: {task.task_type.value} (ID: {task.task_id}): {e}")
            
            # Retry logic
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = "pending"
                task.started_at = None
                task.completed_at = None
                task.error = None
                
                # Put back in queue
                self.task_queues[task.task_type].put((task.priority.value, task.created_at, task))
                logger.info(f"🔄 Retrying task: {task.task_type.value} (ID: {task.task_id}) - attempt {task.retry_count}")
        
        finally:
            # Move to completed tasks
            if task.task_id in self.running_tasks:
                del self.running_tasks[task.task_id]
            
            self.completed_tasks[task.task_id] = task
            self.stats['total_processed'] += 1
    
    def _execute_task(self, task: MLTask) -> Dict[str, Any]:
        """Execute the actual ML task"""
        handler = self.task_handlers.get(task.task_type)
        if not handler:
            raise ValueError(f"No handler for task type: {task.task_type}")
        
        return handler(task)
    
    def _handle_article_summarization(self, task: MLTask) -> Dict[str, Any]:
        """Handle article summarization with 70b model"""
        # Implementation would call the ML service
        # This is a placeholder for the actual implementation
        return {"summary": "Generated summary", "model": "llama3.1:70b"}
    
    def _handle_storyline_analysis(self, task: MLTask) -> Dict[str, Any]:
        """Handle storyline analysis with 70b model"""
        return {"analysis": "Generated analysis", "model": "llama3.1:70b"}
    
    def _handle_content_analysis(self, task: MLTask) -> Dict[str, Any]:
        """Handle content analysis with 70b model"""
        return {"analysis": "Generated content analysis", "model": "llama3.1:70b"}
    
    def _handle_sentiment_analysis(self, task: MLTask) -> Dict[str, Any]:
        """Handle sentiment analysis with 70b model"""
        return {"sentiment": "positive", "model": "llama3.1:70b"}
    
    def _handle_entity_extraction(self, task: MLTask) -> Dict[str, Any]:
        """Handle entity extraction with 70b model"""
        return {"entities": [], "model": "llama3.1:70b"}
    
    def _handle_quality_scoring(self, task: MLTask) -> Dict[str, Any]:
        """Handle quality scoring with 70b model"""
        return {"quality_score": 0.8, "model": "llama3.1:70b"}
    
    def _handle_readability_analysis(self, task: MLTask) -> Dict[str, Any]:
        """Handle readability analysis (CPU-only)"""
        return {"readability": "good", "model": "cpu-only"}
    
    def _handle_timeline_generation(self, task: MLTask) -> Dict[str, Any]:
        """Handle timeline generation with 70b model"""
        return {"timeline": [], "model": "llama3.1:70b"}
    
    def _resource_monitor(self):
        """Monitor resource utilization"""
        while self.is_running:
            try:
                # Check GPU utilization
                gpu_util = self._get_gpu_utilization()
                self.stats['gpu_utilization'] = gpu_util
                
                # Check CPU utilization
                cpu_util = self._get_cpu_utilization()
                self.stats['cpu_utilization'] = cpu_util
                
                # Log resource status
                if gpu_util > 80 or cpu_util > 80:
                    logger.warning(f"⚠️ High resource utilization - GPU: {gpu_util}%, CPU: {cpu_util}%")
                
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"❌ Error in resource monitor: {e}")
                time.sleep(10)
    
    def _get_gpu_utilization(self) -> float:
        """Get GPU utilization percentage"""
        try:
            import subprocess
            result = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'], 
                                  capture_output=True, text=True)
            return float(result.stdout.strip())
        except:
            return 0.0
    
    def _get_cpu_utilization(self) -> float:
        """Get CPU utilization percentage"""
        try:
            import psutil
            return psutil.cpu_percent()
        except:
            return 0.0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        return {
            **self.stats,
            'running_tasks': len(self.running_tasks),
            'completed_tasks': len(self.completed_tasks),
            'queue_sizes': {task_type.value: queue.qsize() for task_type, queue in self.task_queues.items()}
        }
