"""
Local Monitoring & Caching Module for News Intelligence System v3.0
Provides comprehensive monitoring and intelligent caching for local AI processing
"""

import logging
import json
import time
import psutil
import threading
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import hashlib
import pickle
import os

logger = logging.getLogger(__name__)

@dataclass
class SystemMetrics:
    """System performance metrics"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    disk_usage_percent: float
    disk_free_gb: float
    network_io_bytes: int
    process_count: int
    load_average: List[float]

@dataclass
class AIMetrics:
    """AI processing metrics"""
    timestamp: datetime
    model_name: str
    processing_time: float
    tokens_processed: int
    cache_hits: int
    cache_misses: int
    memory_usage_mb: float
    gpu_usage_percent: float
    gpu_memory_mb: float
    success: bool
    error_message: Optional[str] = None

@dataclass
class CacheStats:
    """Cache statistics"""
    total_entries: int
    hit_rate: float
    miss_rate: float
    memory_usage_mb: float
    oldest_entry: datetime
    newest_entry: datetime
    eviction_count: int

class LocalMonitoringSystem:
    """
    Local monitoring and caching system for AI processing
    Provides real-time monitoring and intelligent caching
    """
    
    def __init__(self, cache_size_mb: int = 1000, monitoring_interval: int = 30):
        self.cache_size_mb = cache_size_mb
        self.monitoring_interval = monitoring_interval
        self.is_monitoring = False
        self.monitoring_thread = None
        
        # Caching system
        self.cache = {}
        self.cache_access_times = {}
        self.cache_sizes = {}
        self.cache_hits = 0
        self.cache_misses = 0
        
        # Monitoring data
        self.system_metrics = deque(maxlen=1000)  # Keep last 1000 measurements
        self.ai_metrics = deque(maxlen=1000)
        self.alerts = deque(maxlen=100)
        
        # Performance thresholds
        self.thresholds = {
            'cpu_warning': 80.0,
            'cpu_critical': 95.0,
            'memory_warning': 85.0,
            'memory_critical': 95.0,
            'disk_warning': 90.0,
            'disk_critical': 95.0,
            'processing_time_warning': 30.0,  # seconds
            'processing_time_critical': 60.0,
            'cache_hit_rate_warning': 0.7,
            'cache_hit_rate_critical': 0.5
        }
        
        # Cache eviction policies
        self.eviction_policies = ['lru', 'lfu', 'ttl', 'size']
        self.current_eviction_policy = 'lru'
        
        logger.info(f"Local monitoring system initialized with {cache_size_mb}MB cache")
    
    def start_monitoring(self):
        """Start the monitoring system"""
        if self.is_monitoring:
            logger.warning("Monitoring already started")
            return
        
        self.is_monitoring = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        logger.info("Monitoring system started")
    
    def stop_monitoring(self):
        """Stop the monitoring system"""
        self.is_monitoring = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        logger.info("Monitoring system stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.is_monitoring:
            try:
                # Collect system metrics
                system_metrics = self._collect_system_metrics()
                self.system_metrics.append(system_metrics)
                
                # Check for alerts
                self._check_alerts(system_metrics)
                
                # Cleanup old cache entries
                self._cleanup_cache()
                
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(self.monitoring_interval)
    
    def _collect_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_gb = memory.used / (1024**3)
            memory_total_gb = memory.total / (1024**3)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_usage_percent = (disk.used / disk.total) * 100
            disk_free_gb = disk.free / (1024**3)
            
            # Network I/O
            network = psutil.net_io_counters()
            network_io_bytes = network.bytes_sent + network.bytes_recv
            
            # Process count
            process_count = len(psutil.pids())
            
            # Load average (Unix only)
            try:
                load_avg = psutil.getloadavg()
            except AttributeError:
                load_avg = [0.0, 0.0, 0.0]
            
            return SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_used_gb=memory_used_gb,
                memory_total_gb=memory_total_gb,
                disk_usage_percent=disk_usage_percent,
                disk_free_gb=disk_free_gb,
                network_io_bytes=network_io_bytes,
                process_count=process_count,
                load_average=list(load_avg)
            )
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_used_gb=0.0,
                memory_total_gb=0.0,
                disk_usage_percent=0.0,
                disk_free_gb=0.0,
                network_io_bytes=0,
                process_count=0,
                load_average=[0.0, 0.0, 0.0]
            )
    
    def _check_alerts(self, metrics: SystemMetrics):
        """Check for system alerts"""
        alerts = []
        
        # CPU alerts
        if metrics.cpu_percent >= self.thresholds['cpu_critical']:
            alerts.append({
                'level': 'critical',
                'type': 'cpu',
                'message': f'CPU usage critical: {metrics.cpu_percent:.1f}%',
                'timestamp': metrics.timestamp
            })
        elif metrics.cpu_percent >= self.thresholds['cpu_warning']:
            alerts.append({
                'level': 'warning',
                'type': 'cpu',
                'message': f'CPU usage high: {metrics.cpu_percent:.1f}%',
                'timestamp': metrics.timestamp
            })
        
        # Memory alerts
        if metrics.memory_percent >= self.thresholds['memory_critical']:
            alerts.append({
                'level': 'critical',
                'type': 'memory',
                'message': f'Memory usage critical: {metrics.memory_percent:.1f}%',
                'timestamp': metrics.timestamp
            })
        elif metrics.memory_percent >= self.thresholds['memory_warning']:
            alerts.append({
                'level': 'warning',
                'type': 'memory',
                'message': f'Memory usage high: {metrics.memory_percent:.1f}%',
                'timestamp': metrics.timestamp
            })
        
        # Disk alerts
        if metrics.disk_usage_percent >= self.thresholds['disk_critical']:
            alerts.append({
                'level': 'critical',
                'type': 'disk',
                'message': f'Disk usage critical: {metrics.disk_usage_percent:.1f}%',
                'timestamp': metrics.timestamp
            })
        elif metrics.disk_usage_percent >= self.thresholds['disk_warning']:
            alerts.append({
                'level': 'warning',
                'type': 'disk',
                'message': f'Disk usage high: {metrics.disk_usage_percent:.1f}%',
                'timestamp': metrics.timestamp
            })
        
        # Add alerts to queue
        for alert in alerts:
            self.alerts.append(alert)
            logger.warning(f"ALERT: {alert['message']}")
    
    def record_ai_processing(self, model_name: str, processing_time: float, 
                           tokens_processed: int, success: bool, 
                           error_message: Optional[str] = None):
        """Record AI processing metrics"""
        try:
            # Get current memory usage
            memory_usage_mb = psutil.Process().memory_info().rss / (1024**2)
            
            # Get GPU usage if available
            gpu_usage_percent = 0.0
            gpu_memory_mb = 0.0
            try:
                import GPUtil
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]
                    gpu_usage_percent = gpu.load * 100
                    gpu_memory_mb = gpu.memoryUsed
            except ImportError:
                pass  # GPU monitoring not available
            
            metrics = AIMetrics(
                timestamp=datetime.now(),
                model_name=model_name,
                processing_time=processing_time,
                tokens_processed=tokens_processed,
                cache_hits=self.cache_hits,
                cache_misses=self.cache_misses,
                memory_usage_mb=memory_usage_mb,
                gpu_usage_percent=gpu_usage_percent,
                gpu_memory_mb=gpu_memory_mb,
                success=success,
                error_message=error_message
            )
            
            self.ai_metrics.append(metrics)
            
            # Check for processing time alerts
            if processing_time >= self.thresholds['processing_time_critical']:
                self.alerts.append({
                    'level': 'critical',
                    'type': 'processing_time',
                    'message': f'Processing time critical: {processing_time:.1f}s for {model_name}',
                    'timestamp': metrics.timestamp
                })
            elif processing_time >= self.thresholds['processing_time_warning']:
                self.alerts.append({
                    'level': 'warning',
                    'type': 'processing_time',
                    'message': f'Processing time high: {processing_time:.1f}s for {model_name}',
                    'timestamp': metrics.timestamp
                })
            
        except Exception as e:
            logger.error(f"Error recording AI processing metrics: {e}")
    
    def get_cache(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            if key in self.cache:
                self.cache_access_times[key] = time.time()
                self.cache_hits += 1
                return self.cache[key]
            else:
                self.cache_misses += 1
                return None
        except Exception as e:
            logger.error(f"Error getting from cache: {e}")
            return None
    
    def set_cache(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache with TTL"""
        try:
            # Calculate size of value
            value_size = len(pickle.dumps(value))
            
            # Check if we need to evict entries
            self._ensure_cache_space(value_size)
            
            # Store value
            self.cache[key] = value
            self.cache_access_times[key] = time.time()
            self.cache_sizes[key] = value_size
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting cache: {e}")
            return False
    
    def _ensure_cache_space(self, required_size: int):
        """Ensure there's enough space in cache"""
        try:
            current_size = sum(self.cache_sizes.values())
            max_size_bytes = self.cache_size_mb * 1024 * 1024
            
            while current_size + required_size > max_size_bytes and self.cache:
                # Evict entries based on current policy
                if self.current_eviction_policy == 'lru':
                    self._evict_lru()
                elif self.current_eviction_policy == 'lfu':
                    self._evict_lfu()
                elif self.current_eviction_policy == 'ttl':
                    self._evict_ttl()
                elif self.current_eviction_policy == 'size':
                    self._evict_largest()
                else:
                    self._evict_lru()  # Default fallback
                
                current_size = sum(self.cache_sizes.values())
                
        except Exception as e:
            logger.error(f"Error ensuring cache space: {e}")
    
    def _evict_lru(self):
        """Evict least recently used entry"""
        if not self.cache_access_times:
            return
        
        oldest_key = min(self.cache_access_times.keys(), 
                        key=lambda k: self.cache_access_times[k])
        self._remove_from_cache(oldest_key)
    
    def _evict_lfu(self):
        """Evict least frequently used entry"""
        if not self.cache:
            return
        
        # Simple LFU - evict oldest entry
        oldest_key = min(self.cache_access_times.keys(), 
                        key=lambda k: self.cache_access_times[k])
        self._remove_from_cache(oldest_key)
    
    def _evict_ttl(self):
        """Evict expired entries"""
        current_time = time.time()
        expired_keys = [
            key for key, access_time in self.cache_access_times.items()
            if current_time - access_time > 3600  # 1 hour TTL
        ]
        
        for key in expired_keys:
            self._remove_from_cache(key)
    
    def _evict_largest(self):
        """Evict largest entry"""
        if not self.cache_sizes:
            return
        
        largest_key = max(self.cache_sizes.keys(), 
                         key=lambda k: self.cache_sizes[k])
        self._remove_from_cache(largest_key)
    
    def _remove_from_cache(self, key: str):
        """Remove entry from cache"""
        try:
            if key in self.cache:
                del self.cache[key]
            if key in self.cache_access_times:
                del self.cache_access_times[key]
            if key in self.cache_sizes:
                del self.cache_sizes[key]
        except KeyError:
            pass
    
    def _cleanup_cache(self):
        """Cleanup expired cache entries"""
        try:
            current_time = time.time()
            expired_keys = [
                key for key, access_time in self.cache_access_times.items()
                if current_time - access_time > 3600  # 1 hour TTL
            ]
            
            for key in expired_keys:
                self._remove_from_cache(key)
                
        except Exception as e:
            logger.error(f"Error cleaning up cache: {e}")
    
    def get_system_metrics(self, hours: int = 1) -> List[Dict[str, Any]]:
        """Get system metrics for the last N hours"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            recent_metrics = [
                asdict(metric) for metric in self.system_metrics
                if metric.timestamp > cutoff_time
            ]
            return recent_metrics
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return []
    
    def get_ai_metrics(self, hours: int = 1) -> List[Dict[str, Any]]:
        """Get AI processing metrics for the last N hours"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            recent_metrics = [
                asdict(metric) for metric in self.ai_metrics
                if metric.timestamp > cutoff_time
            ]
            return recent_metrics
        except Exception as e:
            logger.error(f"Error getting AI metrics: {e}")
            return []
    
    def get_cache_stats(self) -> CacheStats:
        """Get cache statistics"""
        try:
            total_entries = len(self.cache)
            total_requests = self.cache_hits + self.cache_misses
            hit_rate = self.cache_hits / total_requests if total_requests > 0 else 0.0
            miss_rate = self.cache_misses / total_requests if total_requests > 0 else 0.0
            
            memory_usage_mb = sum(self.cache_sizes.values()) / (1024 * 1024)
            
            oldest_entry = datetime.now()
            newest_entry = datetime.now()
            if self.cache_access_times:
                oldest_time = min(self.cache_access_times.values())
                newest_time = max(self.cache_access_times.values())
                oldest_entry = datetime.fromtimestamp(oldest_time)
                newest_entry = datetime.fromtimestamp(newest_time)
            
            return CacheStats(
                total_entries=total_entries,
                hit_rate=hit_rate,
                miss_rate=miss_rate,
                memory_usage_mb=memory_usage_mb,
                oldest_entry=oldest_entry,
                newest_entry=newest_entry,
                eviction_count=0  # TODO: Track evictions
            )
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return CacheStats(
                total_entries=0,
                hit_rate=0.0,
                miss_rate=0.0,
                memory_usage_mb=0.0,
                oldest_entry=datetime.now(),
                newest_entry=datetime.now(),
                eviction_count=0
            )
    
    def get_alerts(self, level: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recent alerts, optionally filtered by level"""
        try:
            alerts = list(self.alerts)
            if level:
                alerts = [alert for alert in alerts if alert['level'] == level]
            return alerts
        except Exception as e:
            logger.error(f"Error getting alerts: {e}")
            return []
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get overall performance summary"""
        try:
            # System metrics summary
            recent_system = self.get_system_metrics(1)  # Last hour
            if recent_system:
                avg_cpu = sum(m['cpu_percent'] for m in recent_system) / len(recent_system)
                avg_memory = sum(m['memory_percent'] for m in recent_system) / len(recent_system)
                avg_disk = sum(m['disk_usage_percent'] for m in recent_system) / len(recent_system)
            else:
                avg_cpu = avg_memory = avg_disk = 0.0
            
            # AI metrics summary
            recent_ai = self.get_ai_metrics(1)  # Last hour
            if recent_ai:
                avg_processing_time = sum(m['processing_time'] for m in recent_ai) / len(recent_ai)
                success_rate = sum(1 for m in recent_ai if m['success']) / len(recent_ai)
            else:
                avg_processing_time = 0.0
                success_rate = 1.0
            
            # Cache stats
            cache_stats = self.get_cache_stats()
            
            # Recent alerts
            recent_alerts = self.get_alerts()
            critical_alerts = len([a for a in recent_alerts if a['level'] == 'critical'])
            warning_alerts = len([a for a in recent_alerts if a['level'] == 'warning'])
            
            return {
                'system_health': {
                    'cpu_usage': avg_cpu,
                    'memory_usage': avg_memory,
                    'disk_usage': avg_disk,
                    'status': 'healthy' if critical_alerts == 0 else 'critical'
                },
                'ai_performance': {
                    'avg_processing_time': avg_processing_time,
                    'success_rate': success_rate,
                    'status': 'healthy' if success_rate > 0.9 else 'degraded'
                },
                'cache_performance': {
                    'hit_rate': cache_stats.hit_rate,
                    'memory_usage_mb': cache_stats.memory_usage_mb,
                    'total_entries': cache_stats.total_entries,
                    'status': 'healthy' if cache_stats.hit_rate > 0.7 else 'degraded'
                },
                'alerts': {
                    'critical': critical_alerts,
                    'warning': warning_alerts,
                    'total': len(recent_alerts)
                },
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting performance summary: {e}")
            return {
                'system_health': {'status': 'unknown'},
                'ai_performance': {'status': 'unknown'},
                'cache_performance': {'status': 'unknown'},
                'alerts': {'total': 0},
                'timestamp': datetime.now().isoformat()
            }
    
    def clear_cache(self):
        """Clear all cache entries"""
        try:
            self.cache.clear()
            self.cache_access_times.clear()
            self.cache_sizes.clear()
            self.cache_hits = 0
            self.cache_misses = 0
            logger.info("Cache cleared")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
    
    def set_eviction_policy(self, policy: str):
        """Set cache eviction policy"""
        if policy in self.eviction_policies:
            self.current_eviction_policy = policy
            logger.info(f"Cache eviction policy set to: {policy}")
        else:
            logger.warning(f"Invalid eviction policy: {policy}")
    
    def set_thresholds(self, thresholds: Dict[str, float]):
        """Update monitoring thresholds"""
        try:
            for key, value in thresholds.items():
                if key in self.thresholds:
                    self.thresholds[key] = value
            logger.info("Monitoring thresholds updated")
        except Exception as e:
            logger.error(f"Error updating thresholds: {e}")

# Global instance
local_monitoring = LocalMonitoringSystem()


