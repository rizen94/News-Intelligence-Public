"""
Pipeline Monitoring and Alerting Service
Provides comprehensive monitoring, alerting, and quality control for the entire pipeline
"""

import logging
import time
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import json

from services.pipeline_logger import get_pipeline_logger
from services.quality_monitoring_service import get_quality_monitoring_service
from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of pipeline alerts"""
    QUALITY_DEGRADATION = "quality_degradation"
    PROCESS_FAILURE = "process_failure"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    RESOURCE_LIMIT = "resource_limit"
    DATA_INTEGRITY = "data_integrity"
    CONFIGURATION_ERROR = "configuration_error"
    SECURITY_ISSUE = "security_issue"


@dataclass
class Alert:
    """Pipeline alert structure"""
    alert_id: str
    alert_type: AlertType
    alert_level: AlertLevel
    message: str
    timestamp: datetime
    process_name: str
    severity_score: int
    metadata: Dict[str, Any]
    resolved: bool = False
    resolved_at: Optional[datetime] = None


@dataclass
class PipelineHealth:
    """Pipeline health status"""
    timestamp: datetime
    overall_health: str  # "healthy", "warning", "critical"
    health_score: float
    process_health: Dict[str, Any]
    quality_metrics: Dict[str, Any]
    performance_metrics: Dict[str, Any]
    alert_count: int
    last_alerts: List[Alert]


class PipelineMonitoringService:
    """Comprehensive pipeline monitoring and alerting service"""

    def __init__(self):
        self.pipeline_logger = get_pipeline_logger()
        self.quality_service = get_quality_monitoring_service()
        self.alerts: List[Alert] = []
        self.alert_history: List[Alert] = []
        self.health_cache = None
        self.health_cache_time = None
        self.alert_thresholds = {
            "quality_degradation_threshold": 0.5,
            "failure_rate_threshold": 0.3,
            "performance_degradation_threshold": 10000,  # 10 seconds
            "resource_usage_threshold": 0.8,  # 80% usage
        }
        self.monitoring_config = {
            "enable_alerting": True,
            "enable_health_check": True,
            "alert_cooldown_minutes": 30,
            "health_check_interval": 300,  # 5 minutes
        }

    def check_pipeline_health(self) -> PipelineHealth:
        """
        Check overall pipeline health
        
        Returns:
            PipelineHealth object with current status
        """
        now = datetime.now(timezone.utc)
        
        # Check cache
        if (self.health_cache and self.health_cache_time and 
            (now - self.health_cache_time) < timedelta(seconds=self.monitoring_config["health_check_interval"])):
            return self.health_cache
        
        # Get quality report
        quality_report = self.quality_service.generate_quality_report()
        
        # Get performance metrics
        performance_metrics = self._get_performance_metrics()
        
        # Calculate health score
        health_score = 100.0
        process_health = {}
        alert_count = len(self.alerts)
        
        # Quality-based health
        if quality_report.average_quality_score < self.alert_thresholds["quality_degradation_threshold"]:
            health_score -= 30
        elif quality_report.average_quality_score < 0.7:
            health_score -= 15
            
        # Failure rate health
        if quality_report.total_processed > 0:
            failure_rate = quality_report.quality_failed / quality_report.total_processed
            if failure_rate > self.alert_thresholds["failure_rate_threshold"]:
                health_score -= 40
            elif failure_rate > 0.15:
                health_score -= 20
                
        # Performance health
        avg_duration = performance_metrics.get("average_duration_ms", 0)
        if avg_duration > self.alert_thresholds["performance_degradation_threshold"]:
            health_score -= 25
            
        # Ensure health score is within bounds
        health_score = max(0, min(100, health_score))
        
        # Determine overall health status
        if health_score >= 80:
            overall_health = "healthy"
        elif health_score >= 60:
            overall_health = "warning"
        else:
            overall_health = "critical"
            
        # Get recent alerts
        recent_alerts = [a for a in self.alerts if not a.resolved and 
                        (now - a.timestamp) < timedelta(hours=24)]
        
        health = PipelineHealth(
            timestamp=now,
            overall_health=overall_health,
            health_score=round(health_score, 2),
            process_health=process_health,
            quality_metrics={
                "total_processed": quality_report.total_processed,
                "quality_passed": quality_report.quality_passed,
                "quality_failed": quality_report.quality_failed,
                "average_quality_score": round(quality_report.average_quality_score, 4),
                "success_rate": quality_report.success_rate,
            },
            performance_metrics=performance_metrics,
            alert_count=len(recent_alerts),
            last_alerts=recent_alerts[:10]  # Last 10 alerts
        )
        
        # Cache result
        self.health_cache = health
        self.health_cache_time = now
        
        return health

    def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics from pipeline logger"""
        try:
            # This would typically query the database for performance data
            # For now, return a mock structure
            return {
                "average_duration_ms": 5000,
                "total_operations": 1000,
                "success_rate": 95.5,
                "peak_concurrent_operations": 50,
                "error_rate": 4.5,
            }
        except Exception as e:
            logger.warning(f"Error getting performance metrics: {e}")
            return {
                "average_duration_ms": 0,
                "total_operations": 0,
                "success_rate": 0,
                "peak_concurrent_operations": 0,
                "error_rate": 0,
            }

    def check_for_alerts(self) -> List[Alert]:
        """
        Check for pipeline issues that should trigger alerts
        
        Returns:
            List of new alerts to be triggered
        """
        new_alerts = []
        
        # Get current health
        health = self.check_pipeline_health()
        
        # Check quality degradation
        if (health.quality_metrics["average_quality_score"] < self.alert_thresholds["quality_degradation_threshold"] and
            not self._is_alert_active(AlertType.QUALITY_DEGRADATION)):
            alert = Alert(
                alert_id=f"quality_degradation_{datetime.now().timestamp()}",
                alert_type=AlertType.QUALITY_DEGRADATION,
                alert_level=AlertLevel.WARNING,
                message=f"Pipeline quality score below threshold: {health.quality_metrics['average_quality_score']}",
                timestamp=datetime.now(timezone.utc),
                process_name="all_processes",
                severity_score=70,
                metadata={
                    "quality_score": health.quality_metrics["average_quality_score"],
                    "threshold": self.alert_thresholds["quality_degradation_threshold"]
                }
            )
            new_alerts.append(alert)
            self._add_alert(alert)
            
        # Check failure rate
        if (health.quality_metrics["success_rate"] < 70 and
            not self._is_alert_active(AlertType.PROCESS_FAILURE)):
            alert = Alert(
                alert_id=f"failure_rate_{datetime.now().timestamp()}",
                alert_type=AlertType.PROCESS_FAILURE,
                alert_level=AlertLevel.ERROR,
                message=f"High failure rate in pipeline: {health.quality_metrics['success_rate']}%",
                timestamp=datetime.now(timezone.utc),
                process_name="all_processes",
                severity_score=80,
                metadata={
                    "success_rate": health.quality_metrics["success_rate"],
                    "failure_rate": 100 - health.quality_metrics["success_rate"]
                }
            )
            new_alerts.append(alert)
            self._add_alert(alert)
            
        # Check performance degradation
        avg_duration = health.performance_metrics.get("average_duration_ms", 0)
        if (avg_duration > self.alert_thresholds["performance_degradation_threshold"] and
            not self._is_alert_active(AlertType.PERFORMANCE_DEGRADATION)):
            alert = Alert(
                alert_id=f"performance_degradation_{datetime.now().timestamp()}",
                alert_type=AlertType.PERFORMANCE_DEGRADATION,
                alert_level=AlertLevel.WARNING,
                message=f"Pipeline performance degraded: {avg_duration}ms average",
                timestamp=datetime.now(timezone.utc),
                process_name="all_processes",
                severity_score=60,
                metadata={
                    "average_duration_ms": avg_duration,
                    "threshold_ms": self.alert_thresholds["performance_degradation_threshold"]
                }
            )
            new_alerts.append(alert)
            self._add_alert(alert)
            
        return new_alerts

    def _is_alert_active(self, alert_type: AlertType) -> bool:
        """Check if an alert of this type is already active"""
        now = datetime.now(timezone.utc)
        cooldown = timedelta(minutes=self.monitoring_config["alert_cooldown_minutes"])
        
        for alert in self.alerts:
            if (alert.alert_type == alert_type and 
                not alert.resolved and 
                (now - alert.timestamp) < cooldown):
                return True
        return False

    def _add_alert(self, alert: Alert):
        """Add alert to active alerts list"""
        self.alerts.append(alert)
        self.alert_history.append(alert)
        
        # Keep only last 1000 alerts
        if len(self.alert_history) > 1000:
            self.alert_history = self.alert_history[-1000:]

    def resolve_alert(self, alert_id: str) -> bool:
        """
        Resolve an alert
        
        Args:
            alert_id: ID of alert to resolve
            
        Returns:
            True if alert was found and resolved, False otherwise
        """
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.resolved = True
                alert.resolved_at = datetime.now(timezone.utc)
                return True
        return False

    def get_active_alerts(self) -> List[Alert]:
        """Get all currently active alerts"""
        return [a for a in self.alerts if not a.resolved]

    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """Get alert history"""
        return self.alert_history[-limit:]

    def send_alert(self, alert: Alert):
        """
        Send alert through configured channels
        
        Args:
            alert: Alert to send
        """
        try:
            # Log alert
            logger.warning(f"ALERT [{alert.alert_level.value.upper()}] {alert.message}")
            
            # In a real implementation, this would send to:
            # - Email notifications
            # - Slack/Teams channels
            # - SMS alerts
            # - Database logging
            # - External monitoring systems
            
            # For now, just log to console and database
            self._log_alert_to_database(alert)
            
        except Exception as e:
            logger.error(f"Error sending alert: {e}")

    def _log_alert_to_database(self, alert: Alert):
        """Log alert to database"""
        try:
            conn = get_db_connection()
            if not conn:
                return
                
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO pipeline_alerts (
                        alert_id, alert_type, alert_level, message, 
                        timestamp, process_name, severity_score, metadata, resolved
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        alert.alert_id,
                        alert.alert_type.value,
                        alert.alert_level.value,
                        alert.message,
                        alert.timestamp,
                        alert.process_name,
                        alert.severity_score,
                        json.dumps(alert.metadata),
                        alert.resolved
                    )
                )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error logging alert to database: {e}")

    def run_health_check(self):
        """Run periodic health check and alerting"""
        try:
            # Check pipeline health
            health = self.check_pipeline_health()
            
            # Check for new alerts
            new_alerts = self.check_for_alerts()
            
            # Send alerts
            for alert in new_alerts:
                self.send_alert(alert)
                
            # Log health status
            logger.info(
                f"Pipeline Health: {health.overall_health} (Score: {health.health_score}) - "
                f"{health.alert_count} active alerts"
            )
            
        except Exception as e:
            logger.error(f"Error in health check: {e}")

    def get_pipeline_status_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive pipeline status report
        
        Returns:
            Dictionary with pipeline status information
        """
        health = self.check_pipeline_health()
        alerts = self.get_active_alerts()
        
        return {
            "timestamp": health.timestamp.isoformat(),
            "overall_health": health.overall_health,
            "health_score": health.health_score,
            "quality_metrics": health.quality_metrics,
            "performance_metrics": health.performance_metrics,
            "alert_count": health.alert_count,
            "active_alerts": [
                {
                    "alert_id": a.alert_id,
                    "alert_type": a.alert_type.value,
                    "alert_level": a.alert_level.value,
                    "message": a.message,
                    "timestamp": a.timestamp.isoformat(),
                    "severity_score": a.severity_score
                }
                for a in alerts
            ],
            "last_alerts": [
                {
                    "alert_id": a.alert_id,
                    "alert_type": a.alert_type.value,
                    "message": a.message,
                    "timestamp": a.timestamp.isoformat()
                }
                for a in self.alert_history[-5:]  # Last 5 alerts
            ]
        }


# Global instance
_pipeline_monitoring_service = None


def get_pipeline_monitoring_service() -> PipelineMonitoringService:
    """Get global pipeline monitoring service instance"""
    global _pipeline_monitoring_service
    if _pipeline_monitoring_service is None:
        _pipeline_monitoring_service = PipelineMonitoringService()
    return _pipeline_monitoring_service


# Periodic monitoring task
async def periodic_health_check():
    """Periodic health check task"""
    service = get_pipeline_monitoring_service()
    
    while True:
        try:
            service.run_health_check()
            await asyncio.sleep(300)  # Check every 5 minutes
        except Exception as e:
            logger.error(f"Error in periodic health check: {e}")
            await asyncio.sleep(60)  # Wait 1 minute before retry


# Start monitoring task in background
def start_pipeline_monitoring():
    """Start the pipeline monitoring service"""
    try:
        # Start periodic health check in background
        asyncio.create_task(periodic_health_check())
        logger.info("Pipeline monitoring service started")
    except Exception as e:
        logger.error(f"Error starting pipeline monitoring: {e}")