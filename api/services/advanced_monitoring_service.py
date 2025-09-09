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
import json

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
            conn = psycopg2.connect(**self.db_config)
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
            conn = psycopg2.connect(**self.db_config)
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
            conn = psycopg2.connect(**self.db_config)
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
            conn = psycopg2.connect(**self.db_config)
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
    
    async def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert"""
        try:
            for alert in self.alerts:
                if alert.id == alert_id and not alert.resolved:
                    alert.resolved = True
                    alert.resolved_at = datetime.now(timezone.utc)
                    
                    # Update in database
                    conn = psycopg2.connect(**self.db_config)
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
        from database.connection import get_db_config
        _advanced_monitoring_service = AdvancedMonitoringService(get_db_config())
    return _advanced_monitoring_service


