"""
Dynamic Resource Allocation Service for News Intelligence System v3.0
Intelligent resource management based on system load and processing demands
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import psutil
from psycopg2.extras import RealDictCursor
from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)


@dataclass
class ResourceMetrics:
    """System resource metrics"""

    cpu_percent: float
    memory_percent: float
    memory_available_gb: float
    disk_io_percent: float
    network_io_percent: float
    active_connections: int
    queue_length: int
    processing_load: float
    timestamp: datetime


@dataclass
class ResourceAllocation:
    """Resource allocation configuration"""

    max_parallel_tasks: int
    max_memory_usage_gb: float
    cpu_threshold: float
    memory_threshold: float
    queue_threshold: int
    processing_priority: str
    adaptive_scaling: bool


class DynamicResourceService:
    """Dynamic resource allocation and management service"""

    def __init__(self, db_config: dict[str, str]):
        self.db_config = db_config
        self.current_allocation = ResourceAllocation(
            max_parallel_tasks=12,
            max_memory_usage_gb=8.0,
            cpu_threshold=80.0,
            memory_threshold=85.0,
            queue_threshold=100,
            processing_priority="balanced",
            adaptive_scaling=True,
        )

        # Resource monitoring history
        self.resource_history = []
        self.max_history_size = 100

        # Load patterns for prediction
        self.load_patterns = {
            "low": {"cpu": 0.3, "memory": 0.4, "parallel_tasks": 12},
            "medium": {"cpu": 0.6, "memory": 0.6, "parallel_tasks": 8},
            "high": {"cpu": 0.8, "memory": 0.8, "parallel_tasks": 4},
            "critical": {"cpu": 0.9, "memory": 0.9, "parallel_tasks": 2},
        }

    async def get_current_resource_metrics(self) -> ResourceMetrics:
        """Get current system resource metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available_gb = memory.available / (1024**3)

            # Disk I/O
            psutil.disk_io_counters()
            disk_io_percent = 0.0  # Simplified for now

            # Network I/O
            psutil.net_io_counters()
            network_io_percent = 0.0  # Simplified for now

            # Database connections
            active_connections = await self._get_active_db_connections()

            # Queue length (from automation manager)
            queue_length = await self._get_queue_length()

            # Processing load (articles processed in last 10 minutes)
            processing_load = await self._get_processing_load()

            metrics = ResourceMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_available_gb=memory_available_gb,
                disk_io_percent=disk_io_percent,
                network_io_percent=network_io_percent,
                active_connections=active_connections,
                queue_length=queue_length,
                processing_load=processing_load,
                timestamp=datetime.now(timezone.utc),
            )

            # Store in history
            self.resource_history.append(metrics)
            if len(self.resource_history) > self.max_history_size:
                self.resource_history.pop(0)

            return metrics

        except Exception as e:
            logger.error(f"Error getting resource metrics: {e}")
            return ResourceMetrics(0, 0, 0, 0, 0, 0, 0, 0, datetime.now(timezone.utc))

    async def _get_active_db_connections(self) -> int:
        """Get number of active database connections"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT count(*) as active_connections
                FROM pg_stat_activity
                WHERE state = 'active'
            """)

            result = cursor.fetchone()
            cursor.close()
            conn.close()

            return result["active_connections"] if result else 0

        except Exception as e:
            logger.warning(f"Error getting DB connections: {e}")
            return 0

    async def _get_queue_length(self) -> int:
        """Get current task queue length"""
        try:
            # This would normally get from the automation manager
            # For now, we'll estimate based on recent processing
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT COUNT(*) as pending_tasks
                FROM articles
                WHERE processing_status IN ('raw', 'processing')
                AND created_at > NOW() - INTERVAL '10 minutes'
            """)

            result = cursor.fetchone()
            cursor.close()
            conn.close()

            return result["pending_tasks"] if result else 0

        except Exception as e:
            logger.warning(f"Error getting queue length: {e}")
            return 0

    async def _get_processing_load(self) -> float:
        """Get current processing load (0.0 to 1.0)"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Get articles processed in last 10 minutes
            cursor.execute("""
                SELECT COUNT(*) as processed_count
                FROM articles
                WHERE created_at > NOW() - INTERVAL '10 minutes'
                AND processing_status = 'processed'
            """)

            result = cursor.fetchone()
            cursor.close()
            conn.close()

            processed_count = result["processed_count"] if result else 0

            # Convert to load factor (assume 100 articles = 50% load)
            load_factor = min(processed_count / 200, 1.0)

            return load_factor

        except Exception as e:
            logger.warning(f"Error getting processing load: {e}")
            return 0.5

    def calculate_load_level(self, metrics: ResourceMetrics) -> str:
        """Calculate current load level based on metrics"""
        try:
            # Weighted scoring system
            cpu_score = metrics.cpu_percent / 100.0
            memory_score = metrics.memory_percent / 100.0
            queue_score = min(metrics.queue_length / 50, 1.0)  # 50 tasks = 100% queue load
            processing_score = metrics.processing_load

            # Calculate overall load score
            load_score = (
                cpu_score * 0.3 + memory_score * 0.3 + queue_score * 0.2 + processing_score * 0.2
            )

            # Determine load level
            if load_score >= 0.9:
                return "critical"
            elif load_score >= 0.8:
                return "high"
            elif load_score >= 0.6:
                return "medium"
            else:
                return "low"

        except Exception as e:
            logger.error(f"Error calculating load level: {e}")
            return "medium"

    async def allocate_resources_dynamically(self) -> ResourceAllocation:
        """Dynamically allocate resources based on current load"""
        try:
            metrics = await self.get_current_resource_metrics()
            load_level = self.calculate_load_level(metrics)

            # Get load pattern for current level
            pattern = self.load_patterns.get(load_level, self.load_patterns["medium"])

            # Calculate adaptive scaling factors
            cpu_factor = min(metrics.cpu_percent / 80.0, 1.0)  # Scale down if CPU > 80%
            memory_factor = min(metrics.memory_percent / 85.0, 1.0)  # Scale down if memory > 85%

            # Calculate new allocation
            new_allocation = ResourceAllocation(
                max_parallel_tasks=max(
                    1, int(pattern["parallel_tasks"] * min(cpu_factor, memory_factor))
                ),
                max_memory_usage_gb=max(
                    2.0,
                    self.current_allocation.max_memory_usage_gb * min(cpu_factor, memory_factor),
                ),
                cpu_threshold=max(
                    60.0, 90.0 - (metrics.cpu_percent * 0.5)
                ),  # Lower threshold if CPU is high
                memory_threshold=max(
                    70.0, 95.0 - (metrics.memory_percent * 0.5)
                ),  # Lower threshold if memory is high
                queue_threshold=max(20, int(100 * min(cpu_factor, memory_factor))),
                processing_priority=self._get_processing_priority(load_level),
                adaptive_scaling=True,
            )

            # Apply smoothing to prevent rapid changes
            self.current_allocation = self._smooth_allocation_changes(new_allocation)

            logger.info(
                f"Resource allocation updated for {load_level} load: {new_allocation.max_parallel_tasks} parallel tasks"
            )

            return self.current_allocation

        except Exception as e:
            logger.error(f"Error allocating resources dynamically: {e}")
            return self.current_allocation

    def _get_processing_priority(self, load_level: str) -> str:
        """Get processing priority based on load level"""
        priority_map = {
            "low": "performance",  # Focus on speed
            "medium": "balanced",  # Balance speed and resource usage
            "high": "conservative",  # Focus on stability
            "critical": "minimal",  # Minimal resource usage
        }
        return priority_map.get(load_level, "balanced")

    def _smooth_allocation_changes(self, new_allocation: ResourceAllocation) -> ResourceAllocation:
        """Smooth allocation changes to prevent rapid oscillations"""
        try:
            # Smooth parallel tasks (max change of 2 per update)
            max_tasks_change = 2
            current_tasks = self.current_allocation.max_parallel_tasks
            new_tasks = new_allocation.max_parallel_tasks

            if abs(new_tasks - current_tasks) > max_tasks_change:
                if new_tasks > current_tasks:
                    new_tasks = current_tasks + max_tasks_change
                else:
                    new_tasks = current_tasks - max_tasks_change

            # Smooth memory allocation (max change of 20% per update)
            max_memory_change = 0.2
            current_memory = self.current_allocation.max_memory_usage_gb
            new_memory = new_allocation.max_memory_usage_gb

            if abs(new_memory - current_memory) / current_memory > max_memory_change:
                if new_memory > current_memory:
                    new_memory = current_memory * (1 + max_memory_change)
                else:
                    new_memory = current_memory * (1 - max_memory_change)

            return ResourceAllocation(
                max_parallel_tasks=new_tasks,
                max_memory_usage_gb=new_memory,
                cpu_threshold=new_allocation.cpu_threshold,
                memory_threshold=new_allocation.memory_threshold,
                queue_threshold=new_allocation.queue_threshold,
                processing_priority=new_allocation.processing_priority,
                adaptive_scaling=new_allocation.adaptive_scaling,
            )

        except Exception as e:
            logger.error(f"Error smoothing allocation changes: {e}")
            return new_allocation

    async def should_scale_down(self) -> bool:
        """Check if system should scale down due to high load"""
        try:
            metrics = await self.get_current_resource_metrics()

            # Scale down if any critical threshold is exceeded
            scale_down_conditions = [
                metrics.cpu_percent > self.current_allocation.cpu_threshold,
                metrics.memory_percent > self.current_allocation.memory_threshold,
                metrics.queue_length > self.current_allocation.queue_threshold,
                metrics.active_connections > 20,  # Too many DB connections
            ]

            return any(scale_down_conditions)

        except Exception as e:
            logger.error(f"Error checking scale down conditions: {e}")
            return False

    async def should_scale_up(self) -> bool:
        """Check if system should scale up due to low load"""
        try:
            metrics = await self.get_current_resource_metrics()

            # Scale up if all conditions are favorable
            scale_up_conditions = [
                metrics.cpu_percent < 50.0,  # Low CPU usage
                metrics.memory_percent < 60.0,  # Low memory usage
                metrics.queue_length < 10,  # Short queue
                metrics.active_connections < 10,  # Few DB connections
                metrics.processing_load < 0.3,  # Low processing load
            ]

            return all(scale_up_conditions)

        except Exception as e:
            logger.error(f"Error checking scale up conditions: {e}")
            return False

    async def get_resource_recommendations(self) -> dict[str, Any]:
        """Get resource optimization recommendations"""
        try:
            metrics = await self.get_current_resource_metrics()
            load_level = self.calculate_load_level(metrics)

            recommendations = {
                "current_load_level": load_level,
                "resource_utilization": {
                    "cpu_percent": metrics.cpu_percent,
                    "memory_percent": metrics.memory_percent,
                    "queue_length": metrics.queue_length,
                },
                "recommendations": [],
                "optimization_opportunities": [],
            }

            # CPU recommendations
            if metrics.cpu_percent > 80:
                recommendations["recommendations"].append(
                    {
                        "type": "cpu",
                        "priority": "high",
                        "message": "High CPU usage detected. Consider reducing parallel tasks or optimizing processing algorithms.",
                        "action": "scale_down_parallel_tasks",
                    }
                )
            elif metrics.cpu_percent < 30:
                recommendations["optimization_opportunities"].append(
                    {
                        "type": "cpu",
                        "message": "Low CPU usage. Consider increasing parallel tasks for better throughput.",
                        "action": "scale_up_parallel_tasks",
                    }
                )

            # Memory recommendations
            if metrics.memory_percent > 85:
                recommendations["recommendations"].append(
                    {
                        "type": "memory",
                        "priority": "high",
                        "message": "High memory usage detected. Consider reducing memory-intensive operations or increasing available memory.",
                        "action": "reduce_memory_usage",
                    }
                )
            elif metrics.memory_percent < 40:
                recommendations["optimization_opportunities"].append(
                    {
                        "type": "memory",
                        "message": "Low memory usage. Consider increasing cache size or processing batch sizes.",
                        "action": "increase_memory_usage",
                    }
                )

            # Queue recommendations
            if metrics.queue_length > 50:
                recommendations["recommendations"].append(
                    {
                        "type": "queue",
                        "priority": "medium",
                        "message": "Long processing queue detected. Consider increasing parallel processing capacity.",
                        "action": "increase_processing_capacity",
                    }
                )

            # Database connection recommendations
            if metrics.active_connections > 15:
                recommendations["recommendations"].append(
                    {
                        "type": "database",
                        "priority": "medium",
                        "message": "High database connection count. Consider connection pooling optimization.",
                        "action": "optimize_db_connections",
                    }
                )

            return recommendations

        except Exception as e:
            logger.error(f"Error getting resource recommendations: {e}")
            return {"error": str(e)}

    async def get_resource_history(self, hours: int = 24) -> list[dict[str, Any]]:
        """Get resource usage history"""
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

            # Filter history to requested time range
            recent_history = [
                {
                    "timestamp": metrics.timestamp.isoformat(),
                    "cpu_percent": metrics.cpu_percent,
                    "memory_percent": metrics.memory_percent,
                    "memory_available_gb": metrics.memory_available_gb,
                    "active_connections": metrics.active_connections,
                    "queue_length": metrics.queue_length,
                    "processing_load": metrics.processing_load,
                }
                for metrics in self.resource_history
                if metrics.timestamp >= cutoff_time
            ]

            return recent_history

        except Exception as e:
            logger.error(f"Error getting resource history: {e}")
            return []

    async def optimize_for_workload(self, workload_type: str) -> ResourceAllocation:
        """Optimize resource allocation for specific workload types"""
        try:
            workload_configs = {
                "high_volume": ResourceAllocation(
                    max_parallel_tasks=8,
                    max_memory_usage_gb=12.0,
                    cpu_threshold=85.0,
                    memory_threshold=90.0,
                    queue_threshold=150,
                    processing_priority="performance",
                    adaptive_scaling=True,
                ),
                "high_quality": ResourceAllocation(
                    max_parallel_tasks=3,
                    max_memory_usage_gb=6.0,
                    cpu_threshold=70.0,
                    memory_threshold=75.0,
                    queue_threshold=50,
                    processing_priority="conservative",
                    adaptive_scaling=True,
                ),
                "balanced": ResourceAllocation(
                    max_parallel_tasks=8,
                    max_memory_usage_gb=8.0,
                    cpu_threshold=80.0,
                    memory_threshold=85.0,
                    queue_threshold=100,
                    processing_priority="balanced",
                    adaptive_scaling=True,
                ),
                "minimal": ResourceAllocation(
                    max_parallel_tasks=2,
                    max_memory_usage_gb=4.0,
                    cpu_threshold=60.0,
                    memory_threshold=70.0,
                    queue_threshold=25,
                    processing_priority="minimal",
                    adaptive_scaling=False,
                ),
            }

            if workload_type in workload_configs:
                self.current_allocation = workload_configs[workload_type]
                logger.info(f"Optimized resource allocation for {workload_type} workload")
            else:
                logger.warning(f"Unknown workload type: {workload_type}")

            return self.current_allocation

        except Exception as e:
            logger.error(f"Error optimizing for workload: {e}")
            return self.current_allocation


# Global instance
_dynamic_resource_service = None


def get_dynamic_resource_service() -> DynamicResourceService:
    """Get global dynamic resource service instance"""
    global _dynamic_resource_service
    if _dynamic_resource_service is None:
        from config.database import get_db_config

        _dynamic_resource_service = DynamicResourceService(get_db_config())
    return _dynamic_resource_service
