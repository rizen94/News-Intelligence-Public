"""
Quality Assessment Service
Provides comprehensive quality assessment and validation for all pipeline processes
"""

import logging
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from services.content_quality_service import get_content_quality_service
from services.pipeline_logger import get_pipeline_logger
from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)


class QualityMetric(Enum):
    """Types of quality metrics"""
    CONTENT_QUALITY = "content_quality"
    VALIDATION_SCORE = "validation_score"
    COMPLETENESS = "completeness"
    CONSISTENCY = "consistency"
    ACCURACY = "accuracy"
    RELEVANCE = "relevance"
    READABILITY = "readability"


@dataclass
class QualityAssessment:
    """Quality assessment result"""
    assessment_id: str
    process_name: str
    item_id: str
    quality_score: float
    quality_tier: int
    metrics: Dict[str, Any]
    issues: List[str]
    recommendations: List[str]
    timestamp: datetime
    status: str  # "passed", "failed", "warning", "review_needed"
    confidence: float


class QualityAssessmentService:
    """Comprehensive quality assessment service for pipeline processes"""

    def __init__(self):
        self.quality_service = get_content_quality_service()
        self.pipeline_logger = get_pipeline_logger()
        self.quality_thresholds = {
            "minimum_quality_score": 0.4,
            "warning_quality_score": 0.6,
            "minimum_tier_for_storylines": 3,
            "minimum_tier_for_briefings": 2,
            "minimum_tier_for_events": 2,
        }

    def assess_content_quality(self, content_data: Dict[str, Any], 
                             process_name: str, item_id: str) -> QualityAssessment:
        """
        Assess quality of generated content
        
        Args:
            content_data: Content to assess (title, content, source, etc.)
            process_name: Name of the process that generated the content
            item_id: ID of the item being assessed
            
        Returns:
            QualityAssessment object with results
        """
        try:
            # Perform quality analysis
            quality_result = self.quality_service.analyze_content_quality(content_data)
            
            # Extract key metrics
            quality_score = quality_result.get("quality_score", 0)
            quality_tier = quality_result.get("quality_tier", 0)
            
            # Determine status based on thresholds
            status = "passed"
            issues = []
            recommendations = []
            
            if quality_score < self.quality_thresholds["minimum_quality_score"]:
                status = "failed"
                issues.append(f"Quality score {quality_score} below minimum threshold")
            elif quality_score < self.quality_thresholds["warning_quality_score"]:
                status = "warning"
                issues.append(f"Quality score {quality_score} below warning threshold")
                
            # Additional quality checks based on content type
            if process_name == "editorial_document_generation":
                # Check for minimum content requirements
                content = content_data.get("content", "")
                if len(content) < 100:
                    issues.append("Content too short for editorial document")
                    status = "failed" if status == "passed" else status
                    
            elif process_name == "editorial_briefing_generation":
                # Check briefing structure
                title = content_data.get("title", "")
                if not title or len(title) < 5:
                    issues.append("Briefing title too short")
                    status = "failed" if status == "passed" else status
                    
            # Generate recommendations
            if quality_score < 0.5:
                recommendations.append("Consider re-generating with more context")
            elif quality_score < 0.7:
                recommendations.append("Review content for clarity and completeness")
                
            # Log quality metrics
            self.pipeline_logger.log_quality_metric(
                process_name,
                item_id,
                quality_score,
                {
                    "quality_tier": quality_tier,
                    "process": process_name,
                    "content_length": len(str(content_data.get("content", "")))
                }
            )
            
            assessment = QualityAssessment(
                assessment_id=f"{process_name}_{item_id}_{datetime.now().timestamp()}",
                process_name=process_name,
                item_id=item_id,
                quality_score=quality_score,
                quality_tier=quality_tier,
                metrics=quality_result,
                issues=issues,
                recommendations=recommendations,
                timestamp=datetime.now(),
                status=status,
                confidence=quality_score
            )
            
            return assessment
            
        except Exception as e:
            logger.error(f"Error in quality assessment for {process_name}: {e}")
            return QualityAssessment(
                assessment_id=f"{process_name}_{item_id}_{datetime.now().timestamp()}",
                process_name=process_name,
                item_id=item_id,
                quality_score=0.0,
                quality_tier=0,
                metrics={},
                issues=[f"Assessment failed: {str(e)}"],
                recommendations=[],
                timestamp=datetime.now(),
                status="failed",
                confidence=0.0
            )

    def validate_generated_content(self, content: Any, content_type: str) -> Dict[str, Any]:
        """
        Validate generated content structure and integrity
        
        Args:
            content: Generated content to validate
            content_type: Type of content (editorial_document, briefing, etc.)
            
        Returns:
            Validation results
        """
        try:
            validation_results = {
                "valid": True,
                "errors": [],
                "warnings": [],
                "structure": {},
                "completeness": 0.0
            }
            
            if content is None:
                validation_results["valid"] = False
                validation_results["errors"].append("Content is null")
                return validation_results
                
            if content_type == "editorial_document":
                required_fields = ["lede", "who", "what", "when", "where", "why", "how"]
                if isinstance(content, dict):
                    for field in required_fields:
                        if field not in content:
                            validation_results["errors"].append(f"Missing required field: {field}")
                            validation_results["valid"] = False
                            
                    # Check content length
                    total_length = sum(len(str(v)) for v in content.values() if isinstance(v, str))
                    if total_length < 200:
                        validation_results["warnings"].append("Content appears too brief")
                        
            elif content_type == "editorial_briefing":
                required_fields = ["headline", "summary"]
                if isinstance(content, dict):
                    for field in required_fields:
                        if field not in content:
                            validation_results["errors"].append(f"Missing required field: {field}")
                            validation_results["valid"] = False
                            
            # Calculate completeness score
            if isinstance(content, dict):
                total_fields = len(content)
                present_fields = sum(1 for v in content.values() if v is not None and str(v).strip())
                validation_results["completeness"] = present_fields / total_fields if total_fields > 0 else 0
                
            return validation_results
            
        except Exception as e:
            logger.error(f"Error validating content: {e}")
            validation_results["valid"] = False
            validation_results["errors"].append(f"Validation failed: {str(e)}")
            return validation_results

    def get_process_quality_report(self, process_name: str, time_window_hours: int = 24) -> Dict[str, Any]:
        """
        Generate quality report for a specific process
        
        Args:
            process_name: Name of the process to report on
            time_window_hours: Time window for reporting (default 24 hours)
            
        Returns:
            Quality report
        """
        try:
            conn = get_db_connection()
            if not conn:
                return {"error": "No database connection"}
                
            # This would query the database for quality metrics
            # For now, return a mock structure
            report = {
                "process_name": process_name,
                "time_window_hours": time_window_hours,
                "total_assessments": 0,
                "average_quality_score": 0.0,
                "quality_tier_distribution": {},
                "issues_count": 0,
                "recommendations_count": 0,
                "success_rate": 0.0,
                "timestamp": datetime.now().isoformat()
            }
            
            # In a real implementation, this would query the database for:
            # - Quality metrics from pipeline_logger
            # - Assessment results from quality_assessment table
            # - Process performance data
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating quality report for {process_name}: {e}")
            return {"error": f"Report generation failed: {str(e)}"}

    def log_quality_assessment(self, assessment: QualityAssessment):
        """
        Log quality assessment to database
        
        Args:
            assessment: QualityAssessment object to log
        """
        try:
            conn = get_db_connection()
            if not conn:
                return
                
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO quality_assessments (
                        assessment_id, process_name, item_id, quality_score, quality_tier,
                        metrics, issues, recommendations, status, confidence, timestamp
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        assessment.assessment_id,
                        assessment.process_name,
                        assessment.item_id,
                        assessment.quality_score,
                        assessment.quality_tier,
                        json.dumps(assessment.metrics),
                        json.dumps(assessment.issues),
                        json.dumps(assessment.recommendations),
                        assessment.status,
                        assessment.confidence,
                        assessment.timestamp,
                    )
                )
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error logging quality assessment: {e}")


# Global instance
_quality_assessment_service = None


def get_quality_assessment_service() -> QualityAssessmentService:
    """Get global quality assessment service instance"""
    global _quality_assessment_service
    if _quality_assessment_service is None:
        _quality_assessment_service = QualityAssessmentService()
    return _quality_assessment_service


def validate_and_assess_content(content: Any, content_type: str, 
                              process_name: str, item_id: str) -> QualityAssessment:
    """
    Convenience function to validate and assess content
    
    Args:
        content: Content to validate and assess
        content_type: Type of content
        process_name: Process that generated content
        item_id: Item ID
        
    Returns:
        QualityAssessment result
    """
    service = get_quality_assessment_service()
    
    # Create content data structure for quality assessment
    content_data = {
        "title": str(content.get("title", "")) if isinstance(content, dict) else str(content),
        "content": str(content) if not isinstance(content, dict) else str(content.get("summary", "")),
        "source_domain": "unknown",
        "url": ""
    }
    
    # Perform quality assessment
    assessment = service.assess_content_quality(content_data, process_name, item_id)
    
    # Perform structural validation
    validation = service.validate_generated_content(content, content_type)
    
    # Update assessment with validation results
    if not validation["valid"]:
        assessment.issues.extend(validation["errors"])
        assessment.status = "failed"
        
    # Log the assessment
    service.log_quality_assessment(assessment)
    
    return assessment