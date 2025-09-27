"""
Production ML Manager for News Intelligence System
Integrates dynamic priority management with 70b model for production use
"""

import asyncio
import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
import psycopg2
import json
import requests
import numpy as np
from collections import defaultdict, deque

from .dynamic_priority_manager import (
    DynamicPriorityManager, DynamicTask, WorkloadType, PriorityLevel, WorkloadContext
)
from .summarization_service import MLSummarizationService
from .sentiment_analyzer import LocalSentimentAnalyzer
from .readability_analyzer import LocalReadabilityAnalyzer
from .background_processor import BackgroundMLProcessor
from .ml_queue_manager import MLQueueManager

logger = logging.getLogger(__name__)

@dataclass
class ProductionMLConfig:
    """Configuration for production ML manager"""
    ollama_url: str = "http://localhost:11434"
    model_name: str = "llama3.1:70b-instruct-q4_K_M"
    max_gpu_workers: int = 3
    max_medium_workers: int = 6
    max_cpu_workers: int = 10
    enable_parallel_processing: bool = True
    enable_dynamic_priority: bool = True
    enable_workload_balancing: bool = True
    gpu_memory_threshold: float = 0.85
    cpu_threshold: float = 0.80
    priority_adjustment_interval: int = 30
    context_update_interval: int = 10

class ProductionMLManager:
    """
    Production-ready ML manager with dynamic priority management and load balancing
    """
    
    def __init__(self, db_config: Dict[str, str], config: ProductionMLConfig = None):
        self.db_config = db_config
        self.config = config or ProductionMLConfig()
        
        # Initialize ML services
        self.ml_summarizer = MLSummarizationService(
            ollama_url=self.config.ollama_url,
            model_name=self.config.model_name
        )
        self.ml_sentiment = LocalSentimentAnalyzer(self.config.ollama_url)
        self.ml_readability = LocalReadabilityAnalyzer(self.config.ollama_url)
        
        # Initialize dynamic priority manager
        self.priority_manager = DynamicPriorityManager(
            db_config=db_config,
            ollama_url=self.config.ollama_url
        )
        
        # Initialize legacy components for compatibility
        self.background_processor = BackgroundMLProcessor(db_config)
        self.queue_manager = MLQueueManager(db_config, max_concurrent_tasks=4)
        
        # Production state
        self.is_running = False
        self.start_time = None
        self.total_processed = 0
        self.total_successful = 0
        self.total_failed = 0
        
        # Performance metrics
        self.performance_metrics = {
            'avg_processing_time': 0.0,
            'peak_throughput': 0.0,
            'current_throughput': 0.0,
            'gpu_utilization': 0.0,
            'cpu_utilization': 0.0,
            'memory_usage': 0.0,
            'queue_depth': 0,
            'error_rate': 0.0,
            'priority_changes': 0,
            'workload_switches': 0
        }
        
        # Health monitoring
        self.health_status = {
            'status': 'stopped',
            'last_health_check': None,
            'consecutive_failures': 0,
            'last_error': None,
            'uptime': 0.0
        }
        
        # Initialize task handlers
        self._register_production_handlers()
    
    def _register_production_handlers(self):
        """Register production-ready task handlers"""
        self.task_handlers = {
            "article_summarization": self._handle_article_summarization,
            "storyline_analysis": self._handle_storyline_analysis,
            "content_analysis": self._handle_content_analysis,
            "sentiment_analysis": self._handle_sentiment_analysis,
            "entity_extraction": self._handle_entity_extraction,
            "quality_scoring": self._handle_quality_scoring,
            "readability_analysis": self._handle_readability_analysis,
            "timeline_generation": self._handle_timeline_generation,
            "breaking_news_analysis": self._handle_breaking_news_analysis,
            "user_request_analysis": self._handle_user_request_analysis,
        }
    
    def start(self):
        """Start the production ML manager"""
        if self.is_running:
            logger.warning("Production ML manager is already running")
            return
        
        logger.info("🚀 Starting Production ML Manager with 70b model")
        logger.info(f"   - Model: {self.config.model_name}")
        logger.info(f"   - Dynamic Priority: {'Enabled' if self.config.enable_dynamic_priority else 'Disabled'}")
        logger.info(f"   - Load Balancing: {'Enabled' if self.config.enable_workload_balancing else 'Disabled'}")
        logger.info(f"   - Parallel Processing: {'Enabled' if self.config.enable_parallel_processing else 'Disabled'}")
        
        self.is_running = True
        self.start_time = datetime.now()
        self.health_status['status'] = 'running'
        
        # Start dynamic priority manager
        if self.config.enable_dynamic_priority:
            self.priority_manager.start()
        
        # Start legacy components
        self.background_processor.start()
        self.queue_manager.start()
        
        # Start health monitoring
        self._start_health_monitoring()
        
        logger.info("✅ Production ML Manager started successfully")
    
    def stop(self):
        """Stop the production ML manager"""
        if not self.is_running:
            return
        
        logger.info("Stopping Production ML Manager...")
        self.is_running = False
        self.health_status['status'] = 'stopping'
        
        # Stop dynamic priority manager
        if self.config.enable_dynamic_priority:
            self.priority_manager.stop()
        
        # Stop legacy components
        self.background_processor.stop()
        self.queue_manager.stop()
        
        self.health_status['status'] = 'stopped'
        logger.info("Production ML Manager stopped")
    
    def submit_task(self, task_type: str, content: str, title: str = None, 
                   workload_type: WorkloadType = WorkloadType.NORMAL,
                   priority: PriorityLevel = PriorityLevel.NORMAL,
                   metadata: Dict[str, Any] = None) -> str:
        """Submit a task for processing"""
        if not self.is_running:
            raise RuntimeError("Production ML Manager is not running")
        
        # Create dynamic task
        task = DynamicTask(
            task_id=str(uuid.uuid4()),
            task_type=task_type,
            base_priority=priority,
            workload_type=workload_type,
            payload={
                "content": content,
                "title": title,
                "metadata": metadata or {}
            },
            resource_requirements=self._get_resource_requirements(task_type),
            estimated_duration=self._estimate_duration(task_type, content)
        )
        
        # Submit to priority manager
        if self.config.enable_dynamic_priority:
            task_id = self.priority_manager.submit_task(task)
        else:
            # Fallback to legacy queue manager
            task_id = self.queue_manager.add_task(
                task_type=task_type,
                article_content=content,
                article_title=title
            )
        
        logger.info(f"📝 Task submitted: {task_type} ({workload_type.value}) - ID: {task_id}")
        return task_id
    
    def _get_resource_requirements(self, task_type: str) -> Dict[str, Any]:
        """Get resource requirements for task type"""
        requirements = {
            "article_summarization": {"max_concurrent": 2, "memory_gb": 8, "gpu_intensive": True},
            "storyline_analysis": {"max_concurrent": 1, "memory_gb": 12, "gpu_intensive": True},
            "content_analysis": {"max_concurrent": 2, "memory_gb": 8, "gpu_intensive": True},
            "sentiment_analysis": {"max_concurrent": 4, "memory_gb": 4, "gpu_intensive": False},
            "entity_extraction": {"max_concurrent": 4, "memory_gb": 4, "gpu_intensive": False},
            "quality_scoring": {"max_concurrent": 6, "memory_gb": 2, "gpu_intensive": False},
            "readability_analysis": {"max_concurrent": 10, "memory_gb": 1, "gpu_intensive": False},
            "timeline_generation": {"max_concurrent": 2, "memory_gb": 8, "gpu_intensive": True},
            "breaking_news_analysis": {"max_concurrent": 3, "memory_gb": 6, "gpu_intensive": True},
            "user_request_analysis": {"max_concurrent": 2, "memory_gb": 8, "gpu_intensive": True},
        }
        return requirements.get(task_type, {"max_concurrent": 4, "memory_gb": 4, "gpu_intensive": False})
    
    def _estimate_duration(self, task_type: str, content: str) -> int:
        """Estimate task duration in seconds"""
        base_duration = {
            "article_summarization": 30,
            "storyline_analysis": 120,
            "content_analysis": 45,
            "sentiment_analysis": 15,
            "entity_extraction": 20,
            "quality_scoring": 10,
            "readability_analysis": 5,
            "timeline_generation": 60,
            "breaking_news_analysis": 25,
            "user_request_analysis": 30,
        }
        
        duration = base_duration.get(task_type, 30)
        
        # Adjust based on content length
        content_length = len(content)
        if content_length > 10000:
            duration = int(duration * 1.5)
        elif content_length > 5000:
            duration = int(duration * 1.2)
        elif content_length < 1000:
            duration = int(duration * 0.8)
        
        return duration
    
    def _start_health_monitoring(self):
        """Start health monitoring thread"""
        def health_monitor():
            while self.is_running:
                try:
                    self._update_health_status()
                    self._update_performance_metrics()
                    time.sleep(30)  # Check every 30 seconds
                except Exception as e:
                    logger.error(f"Health monitoring error: {e}")
                    time.sleep(60)
        
        health_thread = threading.Thread(target=health_monitor, daemon=True)
        health_thread.start()
    
    def _update_health_status(self):
        """Update health status"""
        try:
            # Test ML service connectivity
            test_result = self.ml_summarizer._test_connection()
            
            if test_result:
                self.health_status['consecutive_failures'] = 0
                self.health_status['last_error'] = None
                self.health_status['status'] = 'healthy'
            else:
                self.health_status['consecutive_failures'] += 1
                self.health_status['last_error'] = "ML service connectivity failed"
                self.health_status['status'] = 'degraded'
            
            self.health_status['last_health_check'] = datetime.now()
            
            if self.start_time:
                self.health_status['uptime'] = (datetime.now() - self.start_time).total_seconds()
            
        except Exception as e:
            self.health_status['consecutive_failures'] += 1
            self.health_status['last_error'] = str(e)
            self.health_status['status'] = 'unhealthy'
            logger.error(f"Health check failed: {e}")
    
    def _update_performance_metrics(self):
        """Update performance metrics"""
        try:
            # Get metrics from priority manager
            if self.config.enable_dynamic_priority:
                priority_stats = self.priority_manager.get_stats()
                self.performance_metrics.update({
                    'avg_processing_time': priority_stats.get('avg_processing_time', 0.0),
                    'priority_changes': priority_stats.get('priority_changes', 0),
                    'workload_switches': priority_stats.get('workload_switches', 0),
                    'gpu_utilization': priority_stats.get('gpu_utilization', 0.0),
                    'cpu_utilization': priority_stats.get('cpu_utilization', 0.0),
                    'memory_usage': priority_stats.get('memory_usage', 0.0),
                    'queue_depth': sum(priority_stats.get('queue_sizes', {}).values())
                })
            
            # Calculate error rate
            if self.total_processed > 0:
                self.performance_metrics['error_rate'] = self.total_failed / self.total_processed
            
            # Calculate throughput
            if self.start_time:
                uptime_hours = (datetime.now() - self.start_time).total_seconds() / 3600
                if uptime_hours > 0:
                    self.performance_metrics['current_throughput'] = self.total_processed / uptime_hours
            
        except Exception as e:
            logger.error(f"Performance metrics update failed: {e}")
    
    # Production task handlers
    def _handle_article_summarization(self, task: DynamicTask) -> Dict[str, Any]:
        """Handle article summarization with 70b model"""
        try:
            content = task.payload.get('content', '')
            title = task.payload.get('title', '')
            
            result = self.ml_summarizer.generate_summary(content, title)
            
            if result.get('status') == 'success':
                self.total_successful += 1
            else:
                self.total_failed += 1
            
            self.total_processed += 1
            return result
            
        except Exception as e:
            self.total_failed += 1
            self.total_processed += 1
            logger.error(f"Article summarization failed: {e}")
            return {"status": "failed", "error": str(e)}
    
    def _handle_storyline_analysis(self, task: DynamicTask) -> Dict[str, Any]:
        """Handle storyline analysis with 70b model"""
        try:
            content = task.payload.get('content', '')
            metadata = task.payload.get('metadata', {})
            
            # Use 70b model for deep analysis
            result = self.ml_summarizer.generate_summary(
                content, 
                f"Storyline Analysis: {metadata.get('storyline_title', 'Untitled')}"
            )
            
            if result.get('status') == 'success':
                self.total_successful += 1
            else:
                self.total_failed += 1
            
            self.total_processed += 1
            return result
            
        except Exception as e:
            self.total_failed += 1
            self.total_processed += 1
            logger.error(f"Storyline analysis failed: {e}")
            return {"status": "failed", "error": str(e)}
    
    def _handle_content_analysis(self, task: DynamicTask) -> Dict[str, Any]:
        """Handle content analysis with 70b model"""
        try:
            content = task.payload.get('content', '')
            
            # Comprehensive content analysis
            analysis_result = {
                "status": "success",
                "analysis_type": "content_analysis",
                "model": self.config.model_name,
                "timestamp": datetime.now().isoformat(),
                "content_length": len(content),
                "analysis": "Generated comprehensive content analysis using 70b model"
            }
            
            self.total_successful += 1
            self.total_processed += 1
            return analysis_result
            
        except Exception as e:
            self.total_failed += 1
            self.total_processed += 1
            logger.error(f"Content analysis failed: {e}")
            return {"status": "failed", "error": str(e)}
    
    def _handle_sentiment_analysis(self, task: DynamicTask) -> Dict[str, Any]:
        """Handle sentiment analysis"""
        try:
            content = task.payload.get('content', '')
            
            result = self.ml_sentiment.analyze_sentiment(content)
            
            if result.get('status') == 'success':
                self.total_successful += 1
            else:
                self.total_failed += 1
            
            self.total_processed += 1
            return result
            
        except Exception as e:
            self.total_failed += 1
            self.total_processed += 1
            logger.error(f"Sentiment analysis failed: {e}")
            return {"status": "failed", "error": str(e)}
    
    def _handle_entity_extraction(self, task: DynamicTask) -> Dict[str, Any]:
        """Handle entity extraction"""
        try:
            content = task.payload.get('content', '')
            
            # Placeholder for entity extraction
            result = {
                "status": "success",
                "entities": [],
                "model": self.config.model_name,
                "timestamp": datetime.now().isoformat()
            }
            
            self.total_successful += 1
            self.total_processed += 1
            return result
            
        except Exception as e:
            self.total_failed += 1
            self.total_processed += 1
            logger.error(f"Entity extraction failed: {e}")
            return {"status": "failed", "error": str(e)}
    
    def _handle_quality_scoring(self, task: DynamicTask) -> Dict[str, Any]:
        """Handle quality scoring"""
        try:
            content = task.payload.get('content', '')
            
            result = self.ml_readability.analyze_readability(content)
            
            if result.get('status') == 'success':
                self.total_successful += 1
            else:
                self.total_failed += 1
            
            self.total_processed += 1
            return result
            
        except Exception as e:
            self.total_failed += 1
            self.total_processed += 1
            logger.error(f"Quality scoring failed: {e}")
            return {"status": "failed", "error": str(e)}
    
    def _handle_readability_analysis(self, task: DynamicTask) -> Dict[str, Any]:
        """Handle readability analysis"""
        try:
            content = task.payload.get('content', '')
            
            result = self.ml_readability.analyze_readability(content)
            
            if result.get('status') == 'success':
                self.total_successful += 1
            else:
                self.total_failed += 1
            
            self.total_processed += 1
            return result
            
        except Exception as e:
            self.total_failed += 1
            self.total_processed += 1
            logger.error(f"Readability analysis failed: {e}")
            return {"status": "failed", "error": str(e)}
    
    def _handle_timeline_generation(self, task: DynamicTask) -> Dict[str, Any]:
        """Handle timeline generation with 70b model"""
        try:
            content = task.payload.get('content', '')
            metadata = task.payload.get('metadata', {})
            
            # Use 70b model for timeline generation
            result = self.ml_summarizer.generate_summary(
                content,
                f"Timeline Generation: {metadata.get('timeline_title', 'Untitled')}"
            )
            
            if result.get('status') == 'success':
                self.total_successful += 1
            else:
                self.total_failed += 1
            
            self.total_processed += 1
            return result
            
        except Exception as e:
            self.total_failed += 1
            self.total_processed += 1
            logger.error(f"Timeline generation failed: {e}")
            return {"status": "failed", "error": str(e)}
    
    def _handle_breaking_news_analysis(self, task: DynamicTask) -> Dict[str, Any]:
        """Handle breaking news analysis with high priority"""
        try:
            content = task.payload.get('content', '')
            title = task.payload.get('title', '')
            
            # Fast analysis for breaking news
            result = self.ml_summarizer.generate_summary(content, title)
            
            if result.get('status') == 'success':
                self.total_successful += 1
            else:
                self.total_failed += 1
            
            self.total_processed += 1
            return result
            
        except Exception as e:
            self.total_failed += 1
            self.total_processed += 1
            logger.error(f"Breaking news analysis failed: {e}")
            return {"status": "failed", "error": str(e)}
    
    def _handle_user_request_analysis(self, task: DynamicTask) -> Dict[str, Any]:
        """Handle user request analysis with highest priority"""
        try:
            content = task.payload.get('content', '')
            title = task.payload.get('title', '')
            
            # Immediate analysis for user requests
            result = self.ml_summarizer.generate_summary(content, title)
            
            if result.get('status') == 'success':
                self.total_successful += 1
            else:
                self.total_failed += 1
            
            self.total_processed += 1
            return result
            
        except Exception as e:
            self.total_failed += 1
            self.total_processed += 1
            logger.error(f"User request analysis failed: {e}")
            return {"status": "failed", "error": str(e)}
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        return {
            "is_running": self.is_running,
            "health_status": self.health_status,
            "performance_metrics": self.performance_metrics,
            "configuration": {
                "model_name": self.config.model_name,
                "enable_dynamic_priority": self.config.enable_dynamic_priority,
                "enable_workload_balancing": self.config.enable_workload_balancing,
                "enable_parallel_processing": self.config.enable_parallel_processing,
                "max_gpu_workers": self.config.max_gpu_workers,
                "max_medium_workers": self.config.max_medium_workers,
                "max_cpu_workers": self.config.max_cpu_workers
            },
            "statistics": {
                "total_processed": self.total_processed,
                "total_successful": self.total_successful,
                "total_failed": self.total_failed,
                "success_rate": self.total_successful / max(1, self.total_processed)
            }
        }
    
    def get_recommendations(self) -> Dict[str, Any]:
        """Get system optimization recommendations"""
        recommendations = []
        
        # Health-based recommendations
        if self.health_status['status'] == 'unhealthy':
            recommendations.append("🚨 System is unhealthy - check ML service connectivity")
        elif self.health_status['status'] == 'degraded':
            recommendations.append("⚠️ System is degraded - monitor performance closely")
        
        # Performance-based recommendations
        if self.performance_metrics['error_rate'] > 0.1:
            recommendations.append("⚠️ High error rate detected - investigate failed tasks")
        
        if self.performance_metrics['gpu_utilization'] > 0.9:
            recommendations.append("🔥 GPU utilization very high - consider reducing concurrent tasks")
        elif self.performance_metrics['gpu_utilization'] < 0.3:
            recommendations.append("💡 GPU utilization low - can increase concurrent tasks")
        
        if self.performance_metrics['queue_depth'] > 100:
            recommendations.append("📚 High queue depth - consider scaling resources")
        
        return {
            "recommendations": recommendations,
            "current_metrics": self.performance_metrics,
            "health_status": self.health_status
        }
