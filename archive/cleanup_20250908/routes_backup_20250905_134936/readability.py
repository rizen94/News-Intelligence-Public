"""
Readability & Quality Analysis API Routes for News Intelligence System v3.0
Provides readability and quality metrics using local LLM models
"""

from fastapi import APIRouter, HTTPException, Body
from typing import Optional, Dict, Any
from datetime import datetime
import logging

from modules.ml.readability_analyzer import readability_analyzer, ContentAnalysisResult
from schemas.response_schemas import create_success_response, create_error_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/readability", tags=["readability"])

@router.post("/analyze")
async def analyze_content(
    text: str = Body(..., description="Text to analyze for readability and quality"),
    model: Optional[str] = Body(None, description="Specific model to use"),
    use_cache: bool = Body(True, description="Whether to use cached results")
) -> Dict[str, Any]:
    """
    Analyze content for readability and quality metrics
    
    Args:
        text: Text to analyze
        model: Specific model to use (optional)
        use_cache: Whether to use cached results
        
    Returns:
        Content analysis result with readability and quality metrics
    """
    try:
        if not text or len(text.strip()) == 0:
            raise HTTPException(
                status_code=400,
                detail=create_error_response("Text cannot be empty").dict()
            )
        
        # Analyze content
        result = readability_analyzer.analyze_content(
            text=text,
            model=model,
            use_cache=use_cache
        )
        
        return create_success_response(
            data={
                "readability": {
                    "flesch_reading_ease": result.readability.flesch_reading_ease,
                    "flesch_kincaid_grade": result.readability.flesch_kincaid_grade,
                    "gunning_fog": result.readability.gunning_fog,
                    "smog_index": result.readability.smog_index,
                    "automated_readability_index": result.readability.automated_readability_index,
                    "coleman_liau_index": result.readability.coleman_liau_index,
                    "average_grade_level": result.readability.average_grade_level,
                    "reading_time_minutes": result.readability.reading_time_minutes,
                    "word_count": result.readability.word_count,
                    "sentence_count": result.readability.sentence_count,
                    "syllable_count": result.readability.syllable_count,
                    "character_count": result.readability.character_count,
                    "local_processing": result.readability.local_processing
                },
                "quality": {
                    "overall_quality_score": result.quality.overall_quality_score,
                    "clarity_score": result.quality.clarity_score,
                    "coherence_score": result.quality.coherence_score,
                    "completeness_score": result.quality.completeness_score,
                    "accuracy_score": result.quality.accuracy_score,
                    "engagement_score": result.quality.engagement_score,
                    "bias_score": result.quality.bias_score,
                    "factual_consistency": result.quality.factual_consistency,
                    "source_reliability": result.quality.source_reliability,
                    "writing_style": result.quality.writing_style,
                    "content_type": result.quality.content_type,
                    "target_audience": result.quality.target_audience,
                    "recommendations": result.quality.recommendations,
                    "model_used": result.quality.model_used,
                    "processing_time": result.quality.processing_time,
                    "local_processing": result.quality.local_processing
                },
                "text": result.text,
                "model_used": result.model_used,
                "total_processing_time": result.total_processing_time,
                "local_processing": result.local_processing
            },
            message="Content analysis completed successfully"
        ).dict()
        
    except Exception as e:
        logger.error(f"Error in content analysis API: {e}")
        raise HTTPException(
            status_code=500,
            detail=create_error_response(f"Content analysis failed: {str(e)}").dict()
        )

@router.post("/readability-only")
async def analyze_readability_only(
    text: str = Body(..., description="Text to analyze for readability only"),
    use_cache: bool = Body(True, description="Whether to use cached results")
) -> Dict[str, Any]:
    """
    Analyze content for readability metrics only (faster, no LLM required)
    
    Args:
        text: Text to analyze
        use_cache: Whether to use cached results
        
    Returns:
        Readability metrics only
    """
    try:
        if not text or len(text.strip()) == 0:
            raise HTTPException(
                status_code=400,
                detail=create_error_response("Text cannot be empty").dict()
            )
        
        # Calculate readability metrics only
        readability = readability_analyzer._calculate_readability_metrics(text)
        
        return create_success_response(
            data={
                "flesch_reading_ease": readability.flesch_reading_ease,
                "flesch_kincaid_grade": readability.flesch_kincaid_grade,
                "gunning_fog": readability.gunning_fog,
                "smog_index": readability.smog_index,
                "automated_readability_index": readability.automated_readability_index,
                "coleman_liau_index": readability.coleman_liau_index,
                "average_grade_level": readability.average_grade_level,
                "reading_time_minutes": readability.reading_time_minutes,
                "word_count": readability.word_count,
                "sentence_count": readability.sentence_count,
                "syllable_count": readability.syllable_count,
                "character_count": readability.character_count,
                "local_processing": readability.local_processing
            },
            message="Readability analysis completed successfully"
        ).dict()
        
    except Exception as e:
        logger.error(f"Error in readability analysis API: {e}")
        raise HTTPException(
            status_code=500,
            detail=create_error_response(f"Readability analysis failed: {str(e)}").dict()
        )

@router.get("/metrics")
async def get_readability_metrics() -> Dict[str, Any]:
    """
    Get available readability metrics and their descriptions
    
    Returns:
        Dictionary with metric descriptions and ranges
    """
    try:
        return create_success_response(
            data={
                "metrics": {
                    "flesch_reading_ease": {
                        "description": "Ease of reading score (0-100)",
                        "range": "0-100 (higher = easier to read)",
                        "interpretation": {
                            "90-100": "Very easy (5th grade)",
                            "80-89": "Easy (6th grade)",
                            "70-79": "Fairly easy (7th grade)",
                            "60-69": "Standard (8th-9th grade)",
                            "50-59": "Fairly difficult (10th-12th grade)",
                            "30-49": "Difficult (college level)",
                            "0-29": "Very difficult (graduate level)"
                        }
                    },
                    "flesch_kincaid_grade": {
                        "description": "U.S. grade level required to understand text",
                        "range": "0-20+ (grade level)",
                        "interpretation": "Lower grade = easier to read"
                    },
                    "gunning_fog": {
                        "description": "Years of formal education needed to understand text",
                        "range": "0-20+ (years)",
                        "interpretation": "Lower years = easier to read"
                    },
                    "smog_index": {
                        "description": "Years of education needed to understand text",
                        "range": "0-20+ (years)",
                        "interpretation": "Lower years = easier to read"
                    },
                    "automated_readability_index": {
                        "description": "U.S. grade level required to understand text",
                        "range": "0-20+ (grade level)",
                        "interpretation": "Lower grade = easier to read"
                    },
                    "coleman_liau_index": {
                        "description": "U.S. grade level required to understand text",
                        "range": "0-20+ (grade level)",
                        "interpretation": "Lower grade = easier to read"
                    }
                },
                "quality_metrics": {
                    "overall_quality_score": "Overall content quality (0-1)",
                    "clarity_score": "How clear and understandable (0-1)",
                    "coherence_score": "How well-organized and logical (0-1)",
                    "completeness_score": "How complete and comprehensive (0-1)",
                    "accuracy_score": "How accurate and factual (0-1)",
                    "engagement_score": "How engaging and interesting (0-1)",
                    "bias_score": "Level of bias (0-1, lower = less biased)",
                    "factual_consistency": "Internal factual consistency (0-1)",
                    "source_reliability": "Reliability of sources (0-1)"
                },
                "reading_speeds": readability_analyzer.READING_SPEEDS
            },
            message="Readability metrics information retrieved successfully"
        ).dict()
        
    except Exception as e:
        logger.error(f"Error getting readability metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail=create_error_response(f"Failed to get readability metrics: {str(e)}").dict()
        )

@router.post("/clear-cache")
async def clear_readability_cache() -> Dict[str, Any]:
    """
    Clear readability analysis cache
    
    Returns:
        Confirmation message
    """
    try:
        readability_analyzer.clear_cache()
        
        return create_success_response(
            data={"cache_cleared": True},
            message="Readability analysis cache cleared successfully"
        ).dict()
        
    except Exception as e:
        logger.error(f"Error clearing readability cache: {e}")
        raise HTTPException(
            status_code=500,
            detail=create_error_response(f"Failed to clear cache: {str(e)}").dict()
        )

@router.get("/health")
async def readability_health_check() -> Dict[str, Any]:
    """
    Health check for readability analysis service
    
    Returns:
        Service health status
    """
    try:
        # Test with a simple readability analysis
        test_result = readability_analyzer.analyze_content(
            text="This is a test sentence for health check.",
            use_cache=False
        )
        
        return create_success_response(
            data={
                "status": "healthy",
                "model_used": test_result.model_used,
                "processing_time": test_result.total_processing_time,
                "readability_available": True,
                "quality_analysis_available": True,
                "local_processing": test_result.local_processing,
                "timestamp": datetime.now().isoformat()
            },
            message="Readability analysis service is healthy"
        ).dict()
        
    except Exception as e:
        logger.error(f"Readability health check failed: {e}")
        return create_success_response(
            data={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            },
            message="Readability analysis service is unhealthy"
        ).dict()


