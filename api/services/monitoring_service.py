"""
Monitoring and Metrics Service for News Intelligence System v3.0
Prometheus metrics and comprehensive monitoring for RSS feed management
"""

import asyncio
import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

# Try to import Prometheus client
try:
    from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logging.warning("Prometheus client not available - metrics disabled")

from database.connection import get_db
from sqlalchemy import text

logger = logging.getLogger(__name__)

@dataclass
class MetricValue:
    """Represents a metric value with timestamp"""
    name: str
    value: float
    labels: Dict[str, str]
    timestamp: datetime

class MonitoringService:
    """Comprehensive monitoring service with Prometheus metrics"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.registry = None
        self.metrics = {}
        
        if PROMETHEUS_AVAILABLE:
            self._initialize_metrics()
        else:
            self.logger.warning("Prometheus not available - using basic metrics")
    
    def _initialize_metrics(self):
        """Initialize Prometheus metrics"""
        try:
            self.registry = CollectorRegistry()
            
            # RSS Feed Metrics
            self.metrics['rss_feeds_total'] = Gauge(
                'rss_feeds_total',
                'Total number of RSS feeds',
                ['status', 'tier'],
                registry=self.registry
            )
            
            self.metrics['rss_feed_success_rate'] = Gauge(
                'rss_feed_success_rate',
                'Success rate of RSS feeds',
                ['feed_id', 'feed_name'],
                registry=self.registry
            )
            
            self.metrics['rss_feed_response_time'] = Histogram(
                'rss_feed_response_time_seconds',
                'Response time for RSS feed fetching',
                ['feed_id', 'feed_name'],
                buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
                registry=self.registry
            )
            
            # Article Processing Metrics
            self.metrics['articles_total'] = Counter(
                'articles_total',
                'Total number of articles processed',
                ['status', 'source_tier'],
                registry=self.registry
            )
            
            self.metrics['articles_filtered'] = Counter(
                'articles_filtered_total',
                'Total number of articles filtered out',
                ['filter_type', 'reason'],
                registry=self.registry
            )
            
            self.metrics['articles_duplicates'] = Counter(
                'articles_duplicates_total',
                'Total number of duplicate articles found',
                ['algorithm'],
                registry=self.registry
            )
            
            # Processing Performance Metrics
            self.metrics['processing_duration'] = Histogram(
                'processing_duration_seconds',
                'Duration of processing operations',
                ['operation', 'status'],
                buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0],
                registry=self.registry
            )
            
            # System Health Metrics
            self.metrics['system_health'] = Gauge(
                'system_health_score',
                'Overall system health score',
                ['component'],
                registry=self.registry
            )
            
            self.metrics['active_connections'] = Gauge(
                'active_connections',
                'Number of active database connections',
                registry=self.registry
            )
            
            # Error Metrics
            self.metrics['errors_total'] = Counter(
                'errors_total',
                'Total number of errors',
                ['error_type', 'component'],
                registry=self.registry
            )
            
            # Phase 1 Optimization Metrics
            self.metrics['early_quality_gates'] = Counter(
                'early_quality_gates_total',
                'Articles processed through early quality gates',
                ['status', 'rejection_reason'],
                registry=self.registry
            )
            
            self.metrics['quality_pass_rate'] = Gauge(
                'quality_pass_rate',
                'Quality gate pass rate (0-1)',
                ['phase'],
                registry=self.registry
            )
            
            self.metrics['parallel_execution'] = Counter(
                'parallel_execution_total',
                'Parallel task executions',
                ['parallel_group', 'status'],
                registry=self.registry
            )
            
            self.metrics['processing_efficiency'] = Gauge(
                'processing_efficiency',
                'Processing efficiency improvement (0-1)',
                ['metric_type'],
                registry=self.registry
            )
            
            self.metrics['resource_utilization'] = Gauge(
                'resource_utilization',
                'Resource utilization percentage',
                ['resource_type'],
                registry=self.registry
            )
            
            self.logger.info("Prometheus metrics initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Prometheus metrics: {e}")
            self.registry = None
    
    async def record_rss_feed_metrics(self, feed_id: int, feed_name: str, 
                                    success: bool, response_time: float, 
                                    articles_processed: int, articles_filtered: int):
        """Record RSS feed processing metrics"""
        try:
            if not PROMETHEUS_AVAILABLE or not self.registry:
                return
            
            # Update success rate
            success_rate = 100.0 if success else 0.0
            self.metrics['rss_feed_success_rate'].labels(
                feed_id=str(feed_id), 
                feed_name=feed_name
            ).set(success_rate)
            
            # Record response time
            self.metrics['rss_feed_response_time'].labels(
                feed_id=str(feed_id), 
                feed_name=feed_name
            ).observe(response_time)
            
            # Record article counts
            self.metrics['articles_total'].labels(
                status='processed',
                source_tier='unknown'  # Will be updated with actual tier
            ).inc(articles_processed)
            
            if articles_filtered > 0:
                self.metrics['articles_filtered'].labels(
                    filter_type='content',
                    reason='filtering_rules'
                ).inc(articles_filtered)
            
        except Exception as e:
            self.logger.error(f"Error recording RSS feed metrics: {e}")
    
    async def record_duplicate_detection(self, duplicates_found: int, algorithm: str):
        """Record duplicate detection metrics"""
        try:
            if not PROMETHEUS_AVAILABLE or not self.registry:
                return
            
            if duplicates_found > 0:
                self.metrics['articles_duplicates'].labels(
                    algorithm=algorithm
                ).inc(duplicates_found)
            
        except Exception as e:
            self.logger.error(f"Error recording duplicate metrics: {e}")
    
    async def record_processing_duration(self, operation: str, duration: float, success: bool):
        """Record processing duration metrics"""
        try:
            if not PROMETHEUS_AVAILABLE or not self.registry:
                return
            
            status = 'success' if success else 'error'
            self.metrics['processing_duration'].labels(
                operation=operation,
                status=status
            ).observe(duration)
            
        except Exception as e:
            self.logger.error(f"Error recording processing duration: {e}")
    
    async def record_error(self, error_type: str, component: str):
        """Record error metrics"""
        try:
            if not PROMETHEUS_AVAILABLE or not self.registry:
                return
            
            self.metrics['errors_total'].labels(
                error_type=error_type,
                component=component
            ).inc()
            
        except Exception as e:
            self.logger.error(f"Error recording error metrics: {e}")
    
    async def update_system_health(self, component: str, health_score: float):
        """Update system health score"""
        try:
            if not PROMETHEUS_AVAILABLE or not self.registry:
                return
            
            self.metrics['system_health'].labels(
                component=component
            ).set(health_score)
            
        except Exception as e:
            self.logger.error(f"Error updating system health: {e}")
    
    # Phase 1 Optimization Metrics
    async def record_early_quality_gates(self, status: str, rejection_reason: str = "none", count: int = 1):
        """Record early quality gate metrics"""
        try:
            if not PROMETHEUS_AVAILABLE or not self.registry:
                return
            
            self.metrics['early_quality_gates'].labels(
                status=status,
                rejection_reason=rejection_reason
            ).inc(count)
            
        except Exception as e:
            self.logger.error(f"Error recording early quality gates: {e}")
    
    async def update_quality_pass_rate(self, phase: str, pass_rate: float):
        """Update quality pass rate"""
        try:
            if not PROMETHEUS_AVAILABLE or not self.registry:
                return
            
            self.metrics['quality_pass_rate'].labels(
                phase=phase
            ).set(pass_rate)
            
        except Exception as e:
            self.logger.error(f"Error updating quality pass rate: {e}")
    
    async def record_parallel_execution(self, parallel_group: str, status: str, count: int = 1):
        """Record parallel execution metrics"""
        try:
            if not PROMETHEUS_AVAILABLE or not self.registry:
                return
            
            self.metrics['parallel_execution'].labels(
                parallel_group=parallel_group,
                status=status
            ).inc(count)
            
        except Exception as e:
            self.logger.error(f"Error recording parallel execution: {e}")
    
    async def update_processing_efficiency(self, metric_type: str, efficiency: float):
        """Update processing efficiency metrics"""
        try:
            if not PROMETHEUS_AVAILABLE or not self.registry:
                return
            
            self.metrics['processing_efficiency'].labels(
                metric_type=metric_type
            ).set(efficiency)
            
        except Exception as e:
            self.logger.error(f"Error updating processing efficiency: {e}")
    
    async def update_resource_utilization(self, resource_type: str, utilization: float):
        """Update resource utilization metrics"""
        try:
            if not PROMETHEUS_AVAILABLE or not self.registry:
                return
            
            self.metrics['resource_utilization'].labels(
                resource_type=resource_type
            ).set(utilization)
            
        except Exception as e:
            self.logger.error(f"Error updating resource utilization: {e}")
    
    async def get_metrics_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary"""
        try:
            # Get database metrics
            db_metrics = await self._get_database_metrics()
            
            # Get RSS feed metrics
            rss_metrics = await self._get_rss_metrics()
            
            # Get article processing metrics
            article_metrics = await self._get_article_metrics()
            
            # Get system health metrics
            health_metrics = await self._get_health_metrics()
            
            return {
                "database": db_metrics,
                "rss_feeds": rss_metrics,
                "articles": article_metrics,
                "health": health_metrics,
                "prometheus_available": PROMETHEUS_AVAILABLE,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting metrics summary: {e}")
            return {"error": str(e)}
    
    async def _get_database_metrics(self) -> Dict[str, Any]:
        """Get database-related metrics"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Get table sizes
                table_sizes = db.execute(text("""
                    SELECT 
                        schemaname,
                        tablename,
                        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                        pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
                    FROM pg_tables 
                    WHERE schemaname = 'public'
                    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                """)).fetchall()
                
                # Get connection count
                connection_count = db.execute(text("""
                    SELECT count(*) FROM pg_stat_activity 
                    WHERE state = 'active'
                """)).fetchone()[0]
                
                return {
                    "table_sizes": [
                        {
                            "table": row[1],
                            "size": row[2],
                            "size_bytes": row[3]
                        } for row in table_sizes
                    ],
                    "active_connections": connection_count
                }
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error getting database metrics: {e}")
            return {"error": str(e)}
    
    async def _get_rss_metrics(self) -> Dict[str, Any]:
        """Get RSS feed metrics"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Get feed counts by status and tier
                feed_counts = db.execute(text("""
                    SELECT status, tier, COUNT(*) as count
                    FROM rss_feeds 
                    GROUP BY status, tier
                    ORDER BY status, tier
                """)).fetchall()
                
                # Get success rates
                success_rates = db.execute(text("""
                    SELECT 
                        f.id, f.name, f.success_rate, f.avg_response_time,
                        COUNT(a.id) as article_count
                    FROM rss_feeds f
                    LEFT JOIN articles a ON f.name = a.source
                    WHERE f.is_active = true
                    GROUP BY f.id, f.name, f.success_rate, f.avg_response_time
                    ORDER BY f.success_rate DESC
                """)).fetchall()
                
                # Get recent activity
                recent_activity = db.execute(text("""
                    SELECT 
                        DATE(created_at) as date,
                        COUNT(*) as articles_collected
                    FROM articles 
                    WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
                    GROUP BY DATE(created_at)
                    ORDER BY date DESC
                """)).fetchall()
                
                return {
                    "feed_counts": [
                        {
                            "status": row[0],
                            "tier": row[1],
                            "count": row[2]
                        } for row in feed_counts
                    ],
                    "success_rates": [
                        {
                            "feed_id": row[0],
                            "feed_name": row[1],
                            "success_rate": float(row[2]) if row[2] else 0.0,
                            "avg_response_time": row[3],
                            "article_count": row[4]
                        } for row in success_rates
                    ],
                    "recent_activity": [
                        {
                            "date": row[0].isoformat(),
                            "articles_collected": row[1]
                        } for row in recent_activity
                    ]
                }
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error getting RSS metrics: {e}")
            return {"error": str(e)}
    
    async def _get_article_metrics(self) -> Dict[str, Any]:
        """Get article processing metrics"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Get article counts by status and source tier
                article_counts = db.execute(text("""
                    SELECT 
                        CASE 
                            WHEN is_duplicate = true THEN 'duplicate'
                            WHEN filtering_reason IS NOT NULL THEN 'filtered'
                            ELSE 'accepted'
                        END as status,
                        COALESCE(source_tier, 0) as source_tier,
                        COUNT(*) as count
                    FROM articles 
                    GROUP BY 
                        CASE 
                            WHEN is_duplicate = true THEN 'duplicate'
                            WHEN filtering_reason IS NOT NULL THEN 'filtered'
                            ELSE 'accepted'
                        END,
                        COALESCE(source_tier, 0)
                    ORDER BY status, source_tier
                """)).fetchall()
                
                # Get filtering statistics
                filtering_stats = db.execute(text("""
                    SELECT 
                        filtering_reason,
                        COUNT(*) as count
                    FROM articles 
                    WHERE filtering_reason IS NOT NULL
                    GROUP BY filtering_reason
                    ORDER BY count DESC
                """)).fetchall()
                
                # Get duplicate statistics
                duplicate_stats = db.execute(text("""
                    SELECT 
                        algorithm,
                        COUNT(*) as count
                    FROM duplicate_pairs 
                    GROUP BY algorithm
                    ORDER BY count DESC
                """)).fetchall()
                
                # Get enrichment statistics
                enrichment_stats = db.execute(text("""
                    SELECT 
                        enrichment_status,
                        COUNT(*) as count
                    FROM articles 
                    GROUP BY enrichment_status
                    ORDER BY count DESC
                """)).fetchall()
                
                return {
                    "article_counts": [
                        {
                            "status": row[0],
                            "source_tier": row[1],
                            "count": row[2]
                        } for row in article_counts
                    ],
                    "filtering_stats": [
                        {
                            "reason": row[0],
                            "count": row[1]
                        } for row in filtering_stats
                    ],
                    "duplicate_stats": [
                        {
                            "algorithm": row[0],
                            "count": row[1]
                        } for row in duplicate_stats
                    ],
                    "enrichment_stats": [
                        {
                            "status": row[0],
                            "count": row[1]
                        } for row in enrichment_stats
                    ]
                }
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error getting article metrics: {e}")
            return {"error": str(e)}
    
    async def _get_health_metrics(self) -> Dict[str, Any]:
        """Get system health metrics"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Get overall system health
                total_feeds = db.execute(text("SELECT COUNT(*) FROM rss_feeds")).fetchone()[0]
                active_feeds = db.execute(text("SELECT COUNT(*) FROM rss_feeds WHERE is_active = true")).fetchone()[0]
                error_feeds = db.execute(text("SELECT COUNT(*) FROM rss_feeds WHERE status = 'error'")).fetchone()[0]
                
                # Calculate health scores
                feed_health = (active_feeds / total_feeds * 100) if total_feeds > 0 else 0
                error_rate = (error_feeds / total_feeds * 100) if total_feeds > 0 else 0
                
                # Get recent processing success rate
                recent_success = db.execute(text("""
                    SELECT AVG(success_rate) 
                    FROM feed_performance_metrics 
                    WHERE date >= CURRENT_DATE - INTERVAL '7 days'
                """)).fetchone()[0]
                
                recent_success_rate = float(recent_success) if recent_success else 0.0
                
                return {
                    "feed_health": feed_health,
                    "error_rate": error_rate,
                    "recent_success_rate": recent_success_rate,
                    "overall_health": (feed_health + recent_success_rate) / 2,
                    "total_feeds": total_feeds,
                    "active_feeds": active_feeds,
                    "error_feeds": error_feeds
                }
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error getting health metrics: {e}")
            return {"error": str(e)}
    
    async def get_prometheus_metrics(self) -> str:
        """Get Prometheus metrics in text format"""
        try:
            if not PROMETHEUS_AVAILABLE or not self.registry:
                return "# Prometheus metrics not available\n"
            
            # Update metrics from database
            await self._update_metrics_from_database()
            
            # Generate metrics
            return generate_latest(self.registry).decode('utf-8')
            
        except Exception as e:
            self.logger.error(f"Error generating Prometheus metrics: {e}")
            return f"# Error generating metrics: {e}\n"
    
    async def _update_metrics_from_database(self):
        """Update Prometheus metrics from database data"""
        try:
            if not PROMETHEUS_AVAILABLE or not self.registry:
                return
            
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Update RSS feed counts
                feed_counts = db.execute(text("""
                    SELECT status, tier, COUNT(*) as count
                    FROM rss_feeds 
                    GROUP BY status, tier
                """)).fetchall()
                
                # Clear existing metrics
                for metric in self.metrics.values():
                    if hasattr(metric, 'clear'):
                        metric.clear()
                
                # Update feed counts
                for status, tier, count in feed_counts:
                    self.metrics['rss_feeds_total'].labels(
                        status=status, 
                        tier=str(tier)
                    ).set(count)
                
                # Update success rates
                success_rates = db.execute(text("""
                    SELECT id, name, success_rate
                    FROM rss_feeds 
                    WHERE is_active = true
                """)).fetchall()
                
                for feed_id, feed_name, success_rate in success_rates:
                    self.metrics['rss_feed_success_rate'].labels(
                        feed_id=str(feed_id),
                        feed_name=feed_name
                    ).set(float(success_rate) if success_rate else 0.0)
                
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error updating metrics from database: {e}")

# Global monitoring service instance
_monitoring_service = None

async def get_monitoring_service() -> MonitoringService:
    """Get or create global monitoring service instance"""
    global _monitoring_service
    if _monitoring_service is None:
        _monitoring_service = MonitoringService()
    return _monitoring_service
