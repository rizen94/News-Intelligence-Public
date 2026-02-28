"""
LLM Activity Tracker
Tracks real-time LLM usage and current processing status
"""

import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)

class LLMActivityTracker:
    """
    Tracks LLM activity in real-time
    Provides visibility into what's currently being processed
    """
    
    def __init__(self):
        # Active tasks being processed right now
        self.active_tasks: Dict[str, Dict[str, Any]] = {}
        self.active_tasks_lock = threading.Lock()
        
        # Task history (last 100 tasks)
        self.task_history: List[Dict[str, Any]] = []
        self.history_lock = threading.Lock()
        self.max_history = 100
        
        # Statistics
        self.stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'active_tasks_count': 0,
            'llm_available': True,
            'last_llm_check': None,
            'last_activity': None
        }
        self.stats_lock = threading.Lock()
    
    def start_task(self, task_id: str, task_type: str, article_id: Optional[int] = None, 
                   domain: Optional[str] = None, metadata: Dict[str, Any] = None):
        """Record that a task has started"""
        with self.active_tasks_lock:
            self.active_tasks[task_id] = {
                'task_id': task_id,
                'task_type': task_type,
                'article_id': article_id,
                'domain': domain,
                'status': 'processing',
                'started_at': datetime.now(),
                'metadata': metadata or {}
            }
        
        with self.stats_lock:
            self.stats['active_tasks_count'] = len(self.active_tasks)
            self.stats['total_tasks'] += 1
            self.stats['last_activity'] = datetime.now()
        
        logger.info(f"📊 LLM Task Started: {task_type} (ID: {task_id}, Article: {article_id})")
    
    def complete_task(self, task_id: str, success: bool = True, error: Optional[str] = None):
        """Record that a task has completed"""
        task_info = None
        
        with self.active_tasks_lock:
            if task_id in self.active_tasks:
                task_info = self.active_tasks[task_id].copy()
                task_info['completed_at'] = datetime.now()
                task_info['duration'] = (task_info['completed_at'] - task_info['started_at']).total_seconds()
                task_info['success'] = success
                task_info['error'] = error
                del self.active_tasks[task_id]
        
        if task_info:
            # Add to history
            with self.history_lock:
                self.task_history.append(task_info)
                # Keep only last max_history
                if len(self.task_history) > self.max_history:
                    self.task_history = self.task_history[-self.max_history:]
            
            with self.stats_lock:
                self.stats['active_tasks_count'] = len(self.active_tasks)
                if success:
                    self.stats['completed_tasks'] += 1
                else:
                    self.stats['failed_tasks'] += 1
                self.stats['last_activity'] = datetime.now()
            
            status = "✅" if success else "❌"
            logger.info(f"{status} LLM Task Completed: {task_info['task_type']} (ID: {task_id}, Duration: {task_info['duration']:.2f}s)")
    
    def update_llm_availability(self, available: bool):
        """Update LLM availability status"""
        with self.stats_lock:
            self.stats['llm_available'] = available
            self.stats['last_llm_check'] = datetime.now()
    
    def get_active_tasks(self) -> List[Dict[str, Any]]:
        """Get list of currently active tasks"""
        with self.active_tasks_lock:
            tasks = []
            for task_id, task_info in self.active_tasks.items():
                task_copy = task_info.copy()
                # Calculate current duration
                task_copy['duration'] = (datetime.now() - task_info['started_at']).total_seconds()
                tasks.append(task_copy)
            return tasks
    
    def get_stats(self) -> Dict[str, Any]:
        """Get overall statistics"""
        with self.stats_lock:
            stats_copy = self.stats.copy()
            stats_copy['active_tasks_count'] = len(self.active_tasks)
        
        # Add active task details
        active_tasks = self.get_active_tasks()
        
        return {
            **stats_copy,
            'active_tasks': active_tasks,
            'recent_history_count': len(self.task_history)
        }
    
    def get_recent_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent task history"""
        with self.history_lock:
            return self.task_history[-limit:]

# Global tracker instance
_llm_activity_tracker = LLMActivityTracker()

def get_llm_activity_tracker() -> LLMActivityTracker:
    """Get the global LLM activity tracker"""
    return _llm_activity_tracker

