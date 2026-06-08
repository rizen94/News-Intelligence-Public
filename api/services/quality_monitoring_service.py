"""
Quality Monitoring Service for News Intelligence System
Provides comprehensive quality assessment and monitoring across all pipeline processes
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from services.content_quality_service import ContentQualityService, get_content_quality_service
from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)


class QualityStatus(Enum):
    """Quality assessment status"""
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    PENDING = "pending"


class QualityMetricType(Enum):
    """Types of quality metrics"""
    FACT_DENSITY = "fact_density"
    SOURCE_QUALITY = "source_quality"
    CLICKBAIT_SCORE = "clickbait_score"
    EMOTIONAL_MANIPULATION = "emotional_manipulation"
    INFORMATION_DEPTH = "information_depth"
    CLAIM_SPECIFICITY = "claim_specificity"
    COMPOSITE_SCORE = "composite_score"


@dataclass
class QualityAssessment:
    """Quality assessment result for a piece of content"""
    content_id: str
    content_type: str
    quality_score: float
    quality_tier: int
    scores: Dict[str, float]
    flags: List[str]
    recommendation: str
    status: QualityStatus
    assessment_time: datetime
    process_name: str
    metadata: Dict[str, Any]


@dataclass
class QualityReport:
    """Comprehensive quality report for a pipeline process"""
    process_name: str
    timestamp: datetime
    total_processed: int
    quality_passed: int
    quality_failed: int
    average_quality_score: float
    quality_metrics: Dict[str, Any]
    warning_flags: List[str]
    error_details: List[str]
    success_rate: float


class QualityMonitoringService:
    """Comprehensive quality monitoring service for the pipeline"""

    def __init__(self):
        self.content_quality_service = get_content_quality_service()
        self.quality_metrics = {
            "total_processed": 0,
            "quality_passed": 0,
            "quality_failed": 0,
            "average_quality_score": 0.0,
            "last_assessment": None,
            "process_history": [],
        }
        self.alert_thresholds = {
            "low_quality_threshold": 0.4,  # Below this, flag as low quality
            "clickbait_threshold": 0.7,    # Above this, flag as clickbait
            "warning_threshold": 0.6,      # Above this, flag as warning
        }

    def assess_content_quality(self, content_data: Dict[str, Any], 
                             process_name: str = "unknown") -> QualityAssessment:
        """
        Assess quality of content using the content quality service
        
        Args:
            content_data: Dictionary containing content to assess
            process_name: Name of the process that generated this content
            
        Returns:
            QualityAssessment object with results
        """
        try:
            # Prepare article data for quality assessment
            article = {
                "title": content_data.get("title", ""),
                "content": content_data.get("content", content_data.get("summary", "")),
                "source_domain": content_data.get("source_domain", content_data.get("source", "")),
                "url": content_data.get("url", ""),
            }
            
            # Run quality analysis
            quality_result = self.content_quality_service.analyze_content_quality(article)
            
            # Determine overall status
            quality_score = quality_result.get("quality_score", 0.0)
            quality_tier = quality_result.get("quality_tier", 4)
            
            # Determine status based on thresholds
            status = QualityStatus.PASS
            if quality_score < self.alert_thresholds["low_quality_threshold"]:
                status = QualityStatus.FAIL
            elif quality_score < self.alert_thresholds["warning_threshold"]:
                status = QualityStatus.WARNING
            elif quality_tier >= 3:
                status = QualityStatus.WARNING
            
            # Check for specific flags
            flags = quality_result.get("flags", [])
            recommendation = quality_result.get("recommendation", "standard_reporting")
            
            # Create assessment object
            assessment = QualityAssessment(
                content_id=content_data.get("id", str(hash(str(content_data)))),
                content_type=content_data.get("type", "unknown"),
                quality_score=quality_score,
                quality_tier=quality_tier,
                scores=quality_result.get("scores", {}),
                flags=flags,
                recommendation=recommendation,
                status=status,
                assessment_time=datetime.now(timezone.utc),
                process_name=process_name,
                metadata=content_data
            )
            
            # Update metrics
            self._update_metrics(assessment)
            
            return assessment
            
        except Exception as e:
            logger.error(f"Error in quality assessment for {process_name}: {e}")
            # Return a basic assessment with error status
            return QualityAssessment(
                content_id=content_data.get("id", "unknown"),
                content_type=content_data.get("type", "unknown"),
                quality_score=0.0,
                quality_tier=4,
                scores={},
                flags=["assessment_error"],
                recommendation="low_value_demote",
                status=QualityStatus.FAIL,
                assessment_time=datetime.now(timezone.utc),
                process_name=process_name,
                metadata=content_data
            )

    def _update_metrics(self, assessment: QualityAssessment):
        """Update quality metrics based on assessment"""
        self.quality_metrics["total_processed"] += 1
        self.quality_metrics["last_assessment"] = datetime.now(timezone.utc)
        
        if assessment.status == QualityStatus.PASS:
            self.quality_metrics["quality_passed"] += 1
        else:
            self.quality_metrics["quality_failed"] += 1
            
        # Calculate running average quality score
        if self.quality_metrics["total_processed"] > 0:
            self.quality_metrics["average_quality_score"] = (
                (self.quality_metrics["average_quality_score"] * 
                 (self.quality_metrics["total_processed"] - 1) + assessment.quality_score) /
                self.quality_metrics["total_processed"]
            )
            
        # Keep process history
        self.quality_metrics["process_history"].append({
            "content_id": assessment.content_id,
            "process_name": assessment.process_name,
            "quality_score": assessment.quality_score,
            "quality_tier": assessment.quality_tier,
            "status": assessment.status.value,
            "timestamp": assessment.assessment_time.isoformat()
        })
        
        # Keep only last 1000 entries
        if len(self.quality_metrics["process_history"]) > 1000:
            self.quality_metrics["process_history"] = self.quality_metrics["process_history"][-1000:]

    def generate_quality_report(self, process_name: str = None) -> QualityReport:
        """
        Generate a comprehensive quality report
        
        Args:
            process_name: Specific process to report on, or None for all
            
        Returns:
            QualityReport object with comprehensive metrics
        """
        total = self.quality_metrics["total_processed"]
        passed = self.quality_metrics["quality_passed"]
        failed = self.quality_metrics["quality_failed"]
        success_rate = (passed / total * 100) if total > 0 else 0.0
        
        # Analyze warning flags from process history
        warning_flags = []
        error_details = []
        
        # Check recent process history for issues
        recent_history = self.quality_metrics["process_history"][-100:] if len(self.quality_metrics["process_history"]) > 100 else self.quality_metrics["process_history"]
        
        for entry in recent_history:
            if entry.get("quality_tier", 4) >= 3:  # Low quality tier
                warning_flags.append(f"Low quality content in {entry.get('process_name', 'unknown')}")
            if entry.get("status", "") == "fail":
                error_details.append(f"Failed assessment in {entry.get('process_name', 'unknown')}")
        
        return QualityReport(
            process_name=process_name or "all_processes",
            timestamp=datetime.now(timezone.utc),
            total_processed=total,
            quality_passed=passed,
            quality_failed=failed,
            average_quality_score=self.quality_metrics["average_quality_score"],
            quality_metrics=self.quality_metrics,
            warning_flags=warning_flags,
            error_details=error_details,
            success_rate=round(success_rate, 2)
        )

    def check_quality_alerts(self) -> List[str]:
        """
        Check for quality alerts based on thresholds
        
        Returns:
            List of alert messages
        """
        alerts = []
        
        # Check overall quality score
        if self.quality_metrics["average_quality_score"] < 0.5:
            alerts.append("Overall pipeline quality is below threshold (0.5)")
            
        # Check for too many failures
        total = self.quality_metrics["total_processed"]
        failed = self.quality_metrics["quality_failed"]
        if total > 0 and (failed / total) > 0.3:  # More than 30% failures
            alerts.append(f"High failure rate in quality checks: {(failed/total)*100:.1f}%")
            
        # Check for recent quality issues
        recent_history = self.quality_metrics["process_history"][-50:] if len(self.quality_metrics["process_history"]) > 50 else self.quality_metrics["process_history"]
        recent_failures = [entry for entry in recent_history if entry.get("status", "") == "fail"]
        if len(recent_failures) > 5:
            alerts.append(f"High recent failure count: {len(recent_failures)} failed assessments")
            
        return alerts

    def get_quality_trend(self, window_hours: int = 24) -> Dict[str, Any]:
        """
        Get quality trend over time
        
        Args:
            window_hours: Time window in hours
            
        Returns:
            Dictionary with quality trend data
        """
        from datetime import datetime, timedelta
        
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        
        # Filter history by time window
        recent_history = [
            entry for entry in self.quality_metrics["process_history"]
            if datetime.fromisoformat(entry["timestamp"]) > cutoff_time
        ]
        
        if not recent_history:
            return {"message": "No recent data available"}
            
        # Calculate metrics for the window
        total = len(recent_history)
        passed = sum(1 for entry in recent_history if entry.get("status", "") == "pass")
        avg_score = sum(entry.get("quality_score", 0) for entry in recent_history) / total if total > 0 else 0
        
        return {
            "window_hours": window_hours,
            "total_assessments": total,
            "pass_rate": round((passed / total) * 100, 2) if total > 0 else 0,
            "average_quality_score": round(avg_score, 4),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def validate_pipeline_output(self, output_data: Dict[str, Any], 
                               process_name: str = "unknown") -> bool:
        """
        Validate pipeline output quality
        
        Args:
            output_data: Data to validate
            process_name: Name of the process
            
        Returns:
            True if output passes quality checks, False otherwise
        """
        try:
            # Basic validation
            if not output_data:
                logger.warning(f"Empty output data from {process_name}")
                return False
                
            # If content has quality metrics, check them
            if "quality_score" in output_data:
                score = output_data["quality_score"]
                if score < self.alert_thresholds["low_quality_threshold"]:
                    logger.warning(f"Low quality output from {process_name}: score={score}")
                    return False
                    
            # Run full quality assessment
            assessment = self.assess_content_quality(output_data, process_name)
            
            # Return True if assessment passes quality gates
            return assessment.status != QualityStatus.FAIL
            
        except Exception as e:
            logger.error(f"Error validating pipeline output from {process_name}: {e}")
            return False


# Global instance
_quality_monitoring_service = None


def get_quality_monitoring_service() -> QualityMonitoringService:
    """Get global quality monitoring service instance"""
    global _quality_monitoring_service
    if _quality_monitoring_service is None:
        _quality_monitoring_service = QualityMonitoringService()
    return _quality_monitoring_service


def quality_assessment_middleware(process_func):
    """
    Middleware decorator for adding quality assessment to pipeline processes
    
    Args:
        process_func: Function to wrap with quality assessment
        
    Returns:
        Wrapped function with quality assessment
    """
    def wrapper(*args, **kwargs):
        # Get service instance
        service = get_quality_monitoring_service()
        
        # Call the original function
        result = process_func(*args, **kwargs)
        
        # If result contains content, assess quality
        if isinstance(result, dict) and 'content' in result:
            assessment = service.assess_content_quality(result, process_func.__name__)
            result['quality_assessment'] = assessment
            
        return result
    
    return wrapper