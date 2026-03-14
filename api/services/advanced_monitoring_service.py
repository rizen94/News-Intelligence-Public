"""
Advanced Monitoring Service for News Intelligence System v3.0
Comprehensive monitoring with alerting, anomaly detection, and performance analytics
"""

import asyncio
import logging
import time
import statistics
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from enum import Enum
import psycopg2
from psycopg2.extras import RealDictCursor
from shared.database.connection import get_db_connection
import json

# Try to import Prometheus client
try:
    from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logging.warning("Prometheus client not available - metrics disabled")

logger = logging.getLogger(__name__)

class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class AlertType(Enum):
    """Alert types"""
    PERFORMANCE = "performance"
    RESOURCE = "resource"
    ERROR = "error"
    AVAILABILITY = "availability"
    DATA_QUALITY = "data_quality"

@dataclass
class Alert:
    """Alert definition"""
    id: str
    type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    timestamp: datetime
    source: str
    metrics: Dict[str, Any]
    resolved: bool = False
    resolved_at: Optional[datetime] = None

@dataclass
class AnomalyDetectionResult:
    """Anomaly detection result"""
    is_anomaly: bool
    anomaly_score: float
    confidence: float
    detected_at: datetime
    metrics: Dict[str, Any]
    explanation: str

class AdvancedMonitoringService:
    """Advanced monitoring service with alerting and anomaly detection"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.alerts = []
        self.alert_rules = self._initialize_alert_rules()
        self.metric_history = []
        self.anomaly_thresholds = self._initialize_anomaly_thresholds()
        self.performance_baselines = {}
        
        # Prometheus metrics
        self.registry = None
        self.prometheus_metrics = {}
        if PROMETHEUS_AVAILABLE:
            self._initialize_prometheus_metrics()
        
        # Monitoring intervals
        self.monitoring_interval = 30  # seconds
        self.alert_check_interval = 60  # seconds
        self.anomaly_detection_interval = 300  # 5 minutes
        
        # Start background tasks
        asyncio.create_task(self._monitoring_task())
        asyncio.create_task(self._alert_check_task())
        asyncio.create_task(self._anomaly_detection_task())
    
    def _initialize_alert_rules(self) -> Dict[str, Dict[str, Any]]:
        """Initialize alert rules"""
        return {
            'high_cpu_usage': {
                'metric': 'cpu_percent',
                'threshold': 85.0,
                'operator': '>',
                'severity': AlertSeverity.WARNING,
                'type': AlertType.RESOURCE,
                'title': 'High CPU Usage',
                'message': 'CPU usage is above 85%'
            },
            'critical_cpu_usage': {
                'metric': 'cpu_percent',
                'threshold': 95.0,
                'operator': '>',
                'severity': AlertSeverity.CRITICAL,
                'type': AlertType.RESOURCE,
                'title': 'Critical CPU Usage',
                'message': 'CPU usage is above 95%'
            },
            'high_memory_usage': {
                'metric': 'memory_percent',
                'threshold': 90.0,
                'operator': '>',
                'severity': AlertSeverity.WARNING,
                'type': AlertType.RESOURCE,
                'title': 'High Memory Usage',
                'message': 'Memory usage is above 90%'
            },
            'critical_memory_usage': {
                'metric': 'memory_percent',
                'threshold': 98.0,
                'operator': '>',
                'severity': AlertSeverity.CRITICAL,
                'type': AlertType.RESOURCE,
                'title': 'Critical Memory Usage',
                'message': 'Memory usage is above 98%'
            },
            'high_error_rate': {
                'metric': 'error_rate',
                'threshold': 0.1,
                'operator': '>',
                'severity': AlertSeverity.ERROR,
                'type': AlertType.ERROR,
                'title': 'High Error Rate',
                'message': 'Error rate is above 10%'
            },
            'low_throughput': {
                'metric': 'articles_per_minute',
                'threshold': 5.0,
                'operator': '<',
                'severity': AlertSeverity.WARNING,
                'type': AlertType.PERFORMANCE,
                'title': 'Low Throughput',
                'message': 'Article processing throughput is below 5 articles/minute'
            },
            'high_response_time': {
                'metric': 'avg_response_time',
                'threshold': 10.0,
                'operator': '>',
                'severity': AlertSeverity.WARNING,
                'type': AlertType.PERFORMANCE,
                'title': 'High Response Time',
                'message': 'Average response time is above 10 seconds'
            },
            'cache_miss_rate_high': {
                'metric': 'cache_miss_rate',
                'threshold': 0.5,
                'operator': '>',
                'severity': AlertSeverity.WARNING,
                'type': AlertType.PERFORMANCE,
                'title': 'High Cache Miss Rate',
                'message': 'Cache miss rate is above 50%'
            }
        }
    
    def _initialize_anomaly_thresholds(self) -> Dict[str, float]:
        """Initialize anomaly detection thresholds"""
        return {
            'cpu_anomaly_threshold': 0.8,
            'memory_anomaly_threshold': 0.8,
            'response_time_anomaly_threshold': 0.7,
            'error_rate_anomaly_threshold': 0.9,
            'throughput_anomaly_threshold': 0.6
        }
    
    async def _monitoring_task(self):
        """Background task for continuous monitoring"""
        while True:
            try:
                # Collect current metrics
                metrics = await self._collect_system_metrics()
                
                # Store in history
                self.metric_history.append({
                    'timestamp': datetime.now(timezone.utc),
                    'metrics': metrics
                })
                
                # Keep only last 1000 data points
                if len(self.metric_history) > 1000:
                    self.metric_history = self.metric_history[-500:]
                
                # Update performance baselines
                await self._update_performance_baselines()
                
                await asyncio.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring task: {e}")
                await asyncio.sleep(self.monitoring_interval)
    
    async def _collect_system_metrics(self) -> Dict[str, Any]:
        """Collect current system metrics"""
        try:
            # Get metrics from various sources
            metrics = {}
            
            # Database metrics
            db_metrics = await self._get_database_metrics()
            metrics.update(db_metrics)
            
            # Cache metrics
            cache_metrics = await self._get_cache_metrics()
            metrics.update(cache_metrics)
            
            # Processing metrics
            processing_metrics = await self._get_processing_metrics()
            metrics.update(processing_metrics)
            
            # System metrics (simplified)
            import psutil
            metrics.update({
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_usage_percent': psutil.disk_usage('/').percent
            })
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return {}
    
    async def _get_database_metrics(self) -> Dict[str, Any]:
        """Get database-related metrics"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get database connection count
            cursor.execute("SELECT count(*) as connections FROM pg_stat_activity")
            connections = cursor.fetchone()['connections']
            
            # Get recent error count
            cursor.execute("""
                SELECT count(*) as error_count
                FROM system_logs 
                WHERE level = 'ERROR' 
                AND created_at > NOW() - INTERVAL '5 minutes'
            """)
            error_count = cursor.fetchone()['error_count']
            
            # Get recent processing count
            cursor.execute("""
                SELECT count(*) as processed_count
                FROM articles 
                WHERE created_at > NOW() - INTERVAL '5 minutes'
            """)
            processed_count = cursor.fetchone()['processed_count']
            
            cursor.close()
            conn.close()
            
            return {
                'db_connections': connections,
                'error_count_5min': error_count,
                'articles_processed_5min': processed_count,
                'articles_per_minute': processed_count / 5.0
            }
            
        except Exception as e:
            logger.warning(f"Error getting database metrics: {e}")
            return {}
    
    async def _get_cache_metrics(self) -> Dict[str, Any]:
        """Get cache-related metrics"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get cache statistics
            cursor.execute("""
                SELECT 
                    count(*) as total_entries,
                    count(*) FILTER (WHERE expires_at > NOW()) as active_entries,
                    avg(size_bytes) as avg_size_bytes
                FROM api_cache
            """)
            cache_stats = cursor.fetchone()
            
            cursor.close()
            conn.close()
            
            return {
                'cache_total_entries': cache_stats['total_entries'],
                'cache_active_entries': cache_stats['active_entries'],
                'cache_avg_size_bytes': float(cache_stats['avg_size_bytes']) if cache_stats['avg_size_bytes'] else 0
            }
            
        except Exception as e:
            logger.warning(f"Error getting cache metrics: {e}")
            return {}
    
    async def _get_processing_metrics(self) -> Dict[str, Any]:
        """Get processing-related metrics"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get processing statistics
            cursor.execute("""
                SELECT 
                    count(*) as total_articles,
                    count(*) FILTER (WHERE status = 'processed') as processed_articles,
                    count(*) FILTER (WHERE status = 'error') as error_articles,
                    avg(processing_time) as avg_processing_time
                FROM articles 
                WHERE created_at > NOW() - INTERVAL '1 hour'
            """)
            processing_stats = cursor.fetchone()
            
            total = processing_stats['total_articles']
            processed = processing_stats['processed_articles']
            errors = processing_stats['error_articles']
            
            error_rate = errors / total if total > 0 else 0.0
            
            cursor.close()
            conn.close()
            
            return {
                'total_articles_1h': total,
                'processed_articles_1h': processed,
                'error_articles_1h': errors,
                'error_rate': error_rate,
                'avg_processing_time': float(processing_stats['avg_processing_time']) if processing_stats['avg_processing_time'] else 0.0
            }
            
        except Exception as e:
            logger.warning(f"Error getting processing metrics: {e}")
            return {}
    
    async def _update_performance_baselines(self):
        """Update performance baselines for anomaly detection"""
        try:
            if len(self.metric_history) < 10:
                return
            
            # Calculate baselines from recent history
            recent_metrics = [entry['metrics'] for entry in self.metric_history[-100:]]
            
            baselines = {}
            for metric_name in ['cpu_percent', 'memory_percent', 'articles_per_minute', 'error_rate']:
                values = [m.get(metric_name, 0) for m in recent_metrics if metric_name in m]
                if values:
                    baselines[metric_name] = {
                        'mean': statistics.mean(values),
                        'std': statistics.stdev(values) if len(values) > 1 else 0,
                        'min': min(values),
                        'max': max(values)
                    }
            
            self.performance_baselines = baselines
            
        except Exception as e:
            logger.error(f"Error updating performance baselines: {e}")
    
    async def _alert_check_task(self):
        """Background task for checking alert conditions"""
        while True:
            try:
                if self.metric_history:
                    current_metrics = self.metric_history[-1]['metrics']
                    await self._check_alert_conditions(current_metrics)
                
                await asyncio.sleep(self.alert_check_interval)
                
            except Exception as e:
                logger.error(f"Error in alert check task: {e}")
                await asyncio.sleep(self.alert_check_interval)
    
    async def _check_alert_conditions(self, metrics: Dict[str, Any]):
        """Check if any alert conditions are met"""
        try:
            for rule_name, rule in self.alert_rules.items():
                metric_name = rule['metric']
                threshold = rule['threshold']
                operator = rule['operator']
                
                if metric_name not in metrics:
                    continue
                
                value = metrics[metric_name]
                condition_met = False
                
                if operator == '>':
                    condition_met = value > threshold
                elif operator == '<':
                    condition_met = value < threshold
                elif operator == '>=':
                    condition_met = value >= threshold
                elif operator == '<=':
                    condition_met = value <= threshold
                elif operator == '==':
                    condition_met = value == threshold
                
                if condition_met:
                    await self._create_alert(rule_name, rule, metrics)
                
        except Exception as e:
            logger.error(f"Error checking alert conditions: {e}")
    
    async def _create_alert(self, rule_name: str, rule: Dict[str, Any], metrics: Dict[str, Any]):
        """Create a new alert"""
        try:
            # Check if alert already exists and is not resolved
            existing_alert = None
            for alert in self.alerts:
                if (alert.title == rule['title'] and 
                    not alert.resolved and 
                    (datetime.now(timezone.utc) - alert.timestamp).total_seconds() < 300):  # 5 minutes
                    existing_alert = alert
                    break
            
            if existing_alert:
                return  # Alert already exists
            
            alert = Alert(
                id=f"{rule_name}_{int(time.time())}",
                type=rule['type'],
                severity=rule['severity'],
                title=rule['title'],
                message=rule['message'],
                timestamp=datetime.now(timezone.utc),
                source=rule_name,
                metrics=metrics
            )
            
            self.alerts.append(alert)
            
            # Log alert
            logger.warning(f"ALERT [{rule['severity'].value.upper()}] {rule['title']}: {rule['message']}")
            
            # Store in database
            await self._store_alert(alert)
            
        except Exception as e:
            logger.error(f"Error creating alert: {e}")
    
    async def _store_alert(self, alert: Alert):
        """Store alert in database"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO alerts (
                    id, type, severity, title, message, timestamp, 
                    source, metrics, resolved, resolved_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                alert.id,
                alert.type.value,
                alert.severity.value,
                alert.title,
                alert.message,
                alert.timestamp,
                alert.source,
                json.dumps(alert.metrics),
                alert.resolved,
                alert.resolved_at
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error storing alert: {e}")
    
    async def _anomaly_detection_task(self):
        """Background task for anomaly detection"""
        while True:
            try:
                if len(self.metric_history) >= 20:  # Need enough data for anomaly detection
                    current_metrics = self.metric_history[-1]['metrics']
                    anomaly_result = await self._detect_anomalies(current_metrics)
                    
                    if anomaly_result.is_anomaly:
                        await self._handle_anomaly(anomaly_result)
                
                await asyncio.sleep(self.anomaly_detection_interval)
                
            except Exception as e:
                logger.error(f"Error in anomaly detection task: {e}")
                await asyncio.sleep(self.anomaly_detection_interval)
    
    async def _detect_anomalies(self, current_metrics: Dict[str, Any]) -> AnomalyDetectionResult:
        """Detect anomalies in current metrics"""
        try:
            anomaly_scores = {}
            explanations = []
            
            for metric_name, baseline in self.performance_baselines.items():
                if metric_name not in current_metrics:
                    continue
                
                value = current_metrics[metric_name]
                mean = baseline['mean']
                std = baseline['std']
                
                if std == 0:
                    continue
                
                # Calculate z-score
                z_score = abs((value - mean) / std)
                
                # Determine anomaly threshold
                threshold_key = f"{metric_name}_anomaly_threshold"
                threshold = self.anomaly_thresholds.get(threshold_key, 0.8)
                
                if z_score > threshold:
                    anomaly_scores[metric_name] = z_score
                    explanations.append(f"{metric_name}: {value:.2f} (z-score: {z_score:.2f})")
            
            # Calculate overall anomaly score
            overall_score = max(anomaly_scores.values()) if anomaly_scores else 0.0
            is_anomaly = overall_score > 0.5  # Threshold for overall anomaly
            
            return AnomalyDetectionResult(
                is_anomaly=is_anomaly,
                anomaly_score=overall_score,
                confidence=min(1.0, overall_score),
                detected_at=datetime.now(timezone.utc),
                metrics=current_metrics,
                explanation="; ".join(explanations) if explanations else "No anomalies detected"
            )
            
        except Exception as e:
            logger.error(f"Error detecting anomalies: {e}")
            return AnomalyDetectionResult(
                is_anomaly=False,
                anomaly_score=0.0,
                confidence=0.0,
                detected_at=datetime.now(timezone.utc),
                metrics=current_metrics,
                explanation=f"Error in anomaly detection: {str(e)}"
            )
    
    async def _handle_anomaly(self, anomaly_result: AnomalyDetectionResult):
        """Handle detected anomaly"""
        try:
            # Create anomaly alert
            alert = Alert(
                id=f"anomaly_{int(time.time())}",
                type=AlertType.PERFORMANCE,
                severity=AlertSeverity.WARNING if anomaly_result.anomaly_score < 2.0 else AlertSeverity.ERROR,
                title="Anomaly Detected",
                message=f"Anomalous behavior detected: {anomaly_result.explanation}",
                timestamp=anomaly_result.detected_at,
                source="anomaly_detection",
                metrics=anomaly_result.metrics
            )
            
            self.alerts.append(alert)
            await self._store_alert(alert)
            
            logger.warning(f"ANOMALY DETECTED: {anomaly_result.explanation}")
            
        except Exception as e:
            logger.error(f"Error handling anomaly: {e}")
    
    async def get_monitoring_dashboard(self) -> Dict[str, Any]:
        """Get comprehensive monitoring dashboard data"""
        try:
            current_metrics = self.metric_history[-1]['metrics'] if self.metric_history else {}
            
            # Get recent alerts
            recent_alerts = [alert for alert in self.alerts 
                           if not alert.resolved and 
                           (datetime.now(timezone.utc) - alert.timestamp).total_seconds() < 3600]
            
            # Calculate system health score
            health_score = await self._calculate_health_score(current_metrics)
            
            # Get performance trends
            trends = await self._calculate_performance_trends()
            
            return {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'current_metrics': current_metrics,
                'health_score': health_score,
                'active_alerts': len(recent_alerts),
                'alerts': [
                    {
                        'id': alert.id,
                        'type': alert.type.value,
                        'severity': alert.severity.value,
                        'title': alert.title,
                        'message': alert.message,
                        'timestamp': alert.timestamp.isoformat()
                    }
                    for alert in recent_alerts
                ],
                'trends': trends,
                'performance_baselines': self.performance_baselines
            }
            
        except Exception as e:
            logger.error(f"Error getting monitoring dashboard: {e}")
            return {'error': str(e)}
    
    async def _calculate_health_score(self, metrics: Dict[str, Any]) -> float:
        """Calculate overall system health score (0-1)"""
        try:
            health_factors = []
            
            # CPU health
            cpu = metrics.get('cpu_percent', 50)
            cpu_health = max(0, 1 - (cpu - 50) / 50)  # 50% CPU = 1.0, 100% CPU = 0.0
            health_factors.append(cpu_health)
            
            # Memory health
            memory = metrics.get('memory_percent', 50)
            memory_health = max(0, 1 - (memory - 50) / 50)
            health_factors.append(memory_health)
            
            # Error rate health
            error_rate = metrics.get('error_rate', 0)
            error_health = max(0, 1 - error_rate * 10)  # 10% error rate = 0.0
            health_factors.append(error_health)
            
            # Throughput health
            throughput = metrics.get('articles_per_minute', 0)
            throughput_health = min(1.0, throughput / 10)  # 10 articles/min = 1.0
            health_factors.append(throughput_health)
            
            return sum(health_factors) / len(health_factors) if health_factors else 0.5
            
        except Exception as e:
            logger.error(f"Error calculating health score: {e}")
            return 0.5
    
    async def _calculate_performance_trends(self) -> Dict[str, Any]:
        """Calculate performance trends over time"""
        try:
            if len(self.metric_history) < 10:
                return {}
            
            # Get recent data points
            recent_data = self.metric_history[-20:]
            
            trends = {}
            for metric_name in ['cpu_percent', 'memory_percent', 'articles_per_minute', 'error_rate']:
                values = [entry['metrics'].get(metric_name, 0) for entry in recent_data 
                         if metric_name in entry['metrics']]
                
                if len(values) >= 5:
                    # Calculate trend (positive = increasing, negative = decreasing)
                    trend = (values[-1] - values[0]) / len(values)
                    trends[metric_name] = {
                        'trend': trend,
                        'current': values[-1],
                        'average': sum(values) / len(values),
                        'min': min(values),
                        'max': max(values)
                    }
            
            return trends
            
        except Exception as e:
            logger.error(f"Error calculating performance trends: {e}")
            return {}
    
    def _initialize_prometheus_metrics(self):
        """Initialize Prometheus metrics"""
        try:
            if not PROMETHEUS_AVAILABLE:
                return
            
            self.registry = CollectorRegistry()
            
            # RSS Feed Metrics
            self.prometheus_metrics['rss_feeds_total'] = Gauge(
                'rss_feeds_total',
                'Total number of RSS feeds',
                ['status', 'tier'],
                registry=self.registry
            )
            
            self.prometheus_metrics['rss_feed_success_rate'] = Gauge(
                'rss_feed_success_rate',
                'Success rate of RSS feeds',
                ['feed_id', 'feed_name'],
                registry=self.registry
            )
            
            self.prometheus_metrics['rss_feed_response_time'] = Histogram(
                'rss_feed_response_time_seconds',
                'Response time for RSS feed fetching',
                ['feed_id', 'feed_name'],
                buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
                registry=self.registry
            )
            
            # Article Processing Metrics
            self.prometheus_metrics['articles_total'] = Counter(
                'articles_total',
                'Total number of articles processed',
                ['status', 'source_tier'],
                registry=self.registry
            )
            
            self.prometheus_metrics['articles_filtered'] = Counter(
                'articles_filtered_total',
                'Total number of articles filtered out',
                ['filter_type', 'reason'],
                registry=self.registry
            )
            
            self.prometheus_metrics['articles_duplicates'] = Counter(
                'articles_duplicates_total',
                'Total number of duplicate articles found',
                ['algorithm'],
                registry=self.registry
            )
            
            # Processing Performance Metrics
            self.prometheus_metrics['processing_duration'] = Histogram(
                'processing_duration_seconds',
                'Duration of processing operations',
                ['operation', 'status'],
                buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0],
                registry=self.registry
            )
            
            # System Health Metrics
            self.prometheus_metrics['system_health'] = Gauge(
                'system_health_score',
                'Overall system health score',
                ['component'],
                registry=self.registry
            )
            
            self.prometheus_metrics['active_connections'] = Gauge(
                'active_connections',
                'Number of active database connections',
                registry=self.registry
            )
            
            # Error Metrics
            self.prometheus_metrics['errors_total'] = Counter(
                'errors_total',
                'Total number of errors',
                ['error_type', 'component'],
                registry=self.registry
            )
            
            logger.info("Prometheus metrics initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Prometheus metrics: {e}")
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
            self.prometheus_metrics['rss_feed_success_rate'].labels(
                feed_id=str(feed_id), 
                feed_name=feed_name
            ).set(success_rate)
            
            # Record response time
            self.prometheus_metrics['rss_feed_response_time'].labels(
                feed_id=str(feed_id), 
                feed_name=feed_name
            ).observe(response_time)
            
            # Record article counts
            self.prometheus_metrics['articles_total'].labels(
                status='processed',
                source_tier='unknown'
            ).inc(articles_processed)
            
            if articles_filtered > 0:
                self.prometheus_metrics['articles_filtered'].labels(
                    filter_type='content',
                    reason='filtering_rules'
                ).inc(articles_filtered)
            
        except Exception as e:
            logger.error(f"Error recording RSS feed metrics: {e}")
    
    async def record_duplicate_detection(self, duplicates_found: int, algorithm: str):
        """Record duplicate detection metrics"""
        try:
            if not PROMETHEUS_AVAILABLE or not self.registry:
                return
            
            if duplicates_found > 0:
                self.prometheus_metrics['articles_duplicates'].labels(
                    algorithm=algorithm
                ).inc(duplicates_found)
            
        except Exception as e:
            logger.error(f"Error recording duplicate metrics: {e}")
    
    async def record_processing_duration(self, operation: str, duration: float, success: bool):
        """Record processing duration metrics"""
        try:
            if not PROMETHEUS_AVAILABLE or not self.registry:
                return
            
            status = 'success' if success else 'error'
            self.prometheus_metrics['processing_duration'].labels(
                operation=operation,
                status=status
            ).observe(duration)
            
        except Exception as e:
            logger.error(f"Error recording processing duration: {e}")
    
    async def record_error(self, error_type: str, component: str):
        """Record error metrics"""
        try:
            if not PROMETHEUS_AVAILABLE or not self.registry:
                return
            
            self.prometheus_metrics['errors_total'].labels(
                error_type=error_type,
                component=component
            ).inc()
            
        except Exception as e:
            logger.error(f"Error recording error metrics: {e}")
    
    async def update_system_health_metric(self, component: str, health_score: float):
        """Update system health score in Prometheus"""
        try:
            if not PROMETHEUS_AVAILABLE or not self.registry:
                return
            
            self.prometheus_metrics['system_health'].labels(
                component=component
            ).set(health_score)
            
        except Exception as e:
            logger.error(f"Error updating system health metric: {e}")
    
    async def get_prometheus_metrics(self) -> str:
        """Get Prometheus metrics in text format"""
        try:
            if not PROMETHEUS_AVAILABLE or not self.registry:
                return "# Prometheus metrics not available\n"
            
            # Update metrics from database
            await self._update_prometheus_metrics_from_database()
            
            # Generate metrics
            return generate_latest(self.registry).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Error generating Prometheus metrics: {e}")
            return f"# Error generating metrics: {e}\n"
    
    async def _update_prometheus_metrics_from_database(self):
        """Update Prometheus metrics from database data"""
        try:
            if not PROMETHEUS_AVAILABLE or not self.registry:
                return
            
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Update RSS feed counts
            cursor.execute("""
                SELECT status, tier, COUNT(*) as count
                FROM rss_feeds 
                GROUP BY status, tier
            """)
            feed_counts = cursor.fetchall()
            
            # Clear and update feed counts
            for status, tier, count in feed_counts:
                self.prometheus_metrics['rss_feeds_total'].labels(
                    status=status, 
                    tier=str(tier)
                ).set(count)
            
            # Update success rates
            cursor.execute("""
                SELECT id, name, success_rate
                FROM rss_feeds 
                WHERE is_active = true
            """)
            success_rates = cursor.fetchall()
            
            for row in success_rates:
                self.prometheus_metrics['rss_feed_success_rate'].labels(
                    feed_id=str(row['id']),
                    feed_name=row['name']
                ).set(float(row['success_rate']) if row['success_rate'] else 0.0)
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error updating Prometheus metrics from database: {e}")
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get basic system health status (from health_service)"""
        try:
            current_metrics = self.metric_history[-1]['metrics'] if self.metric_history else {}
            health_score = await self._calculate_health_score(current_metrics)
            
            # Check database connection
            db_healthy = True
            try:
                conn = get_db_connection()
                conn.close()
            except Exception:
                db_healthy = False
            
            return {
                "status": "healthy" if health_score > 0.7 and db_healthy else "degraded",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "health_score": health_score,
                "services": {
                    "database": "healthy" if db_healthy else "unhealthy",
                    "monitoring": "healthy",
                    "system": "healthy" if health_score > 0.7 else "degraded"
                },
                "details": {
                    "database": {"status": "healthy" if db_healthy else "unhealthy"},
                    "monitoring": {"status": "healthy", "health_score": health_score},
                    "system": {"status": "healthy" if health_score > 0.7 else "degraded", "score": health_score}
                }
            }
        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return {
                "status": "error",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e)
            }
    
    async def get_readiness_status(self) -> Dict[str, Any]:
        """Check if system is ready to serve requests (from health_service)"""
        try:
            # Check database connection
            db_ready = True
            try:
                conn = get_db_connection()
                conn.close()
            except Exception:
                db_ready = False
            
            return {
                "ready": db_ready,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "checks": {
                    "database": "healthy" if db_ready else "unhealthy",
                    "monitoring": "healthy"
                }
            }
        except Exception as e:
            logger.error(f"Error getting readiness status: {e}")
            return {
                "ready": False,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e)
            }
    
    async def get_liveness_status(self) -> Dict[str, Any]:
        """Check if system is alive and responding (from health_service)"""
        return {
            "live": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime": time.time()
        }
    
    async def is_system_ready(self) -> bool:
        """Check if system is ready to serve requests"""
        status = await self.get_readiness_status()
        return status.get("ready", False)
    
    async def is_system_live(self) -> bool:
        """Check if system is alive and responding"""
        return True
    
    async def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert"""
        try:
            for alert in self.alerts:
                if alert.id == alert_id and not alert.resolved:
                    alert.resolved = True
                    alert.resolved_at = datetime.now(timezone.utc)
                    
                    # Update in database
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        UPDATE alerts 
                        SET resolved = true, resolved_at = %s 
                        WHERE id = %s
                    """, (alert.resolved_at, alert_id))
                    
                    conn.commit()
                    cursor.close()
                    conn.close()
                    
                    logger.info(f"Alert {alert_id} resolved")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error resolving alert: {e}")
            return False

# Global instance
_advanced_monitoring_service = None

def get_advanced_monitoring_service() -> AdvancedMonitoringService:
    """Get global advanced monitoring service instance"""
    global _advanced_monitoring_service
    if _advanced_monitoring_service is None:
        from config.database import get_db_config
        _advanced_monitoring_service = AdvancedMonitoringService(get_db_config())
    return _advanced_monitoring_service




