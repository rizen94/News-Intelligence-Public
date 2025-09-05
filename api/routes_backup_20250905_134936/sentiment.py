"""
Sentiment Analysis API Routes for News Intelligence System v3.0
Provides sentiment analysis endpoints using local LLM models
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from modules.ml.sentiment_analyzer import sentiment_analyzer, SentimentResult
from schemas.response_schemas import create_success_response, create_error_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sentiment", tags=["sentiment"])

@router.post("/analyze")
async def analyze_sentiment(
    text: str,
    model: Optional[str] = None,
    use_cache: bool = True
) -> Dict[str, Any]:
    """
    Analyze sentiment of a single text
    
    Args:
        text: Text to analyze
        model: Specific model to use (optional)
        use_cache: Whether to use cached results
        
    Returns:
        Sentiment analysis result
    """
    try:
        if not text or len(text.strip()) == 0:
            raise HTTPException(
                status_code=400,
                detail=create_error_response("Text cannot be empty").dict()
            )
        
        # Analyze sentiment
        result = sentiment_analyzer.analyze_sentiment(
            text=text,
            model=model,
            use_cache=use_cache
        )
        
        return create_success_response(
            data={
                "sentiment_score": result.sentiment_score,
                "confidence": result.confidence,
                "emotions": result.emotions,
                "context": result.context,
                "model_used": result.model_used,
                "processing_time": result.processing_time,
                "local_processing": result.local_processing
            },
            message="Sentiment analysis completed successfully"
        ).dict()
        
    except Exception as e:
        logger.error(f"Error in sentiment analysis API: {e}")
        raise HTTPException(
            status_code=500,
            detail=create_error_response(f"Sentiment analysis failed: {str(e)}").dict()
        )

@router.post("/analyze-batch")
async def analyze_sentiment_batch(
    texts: List[str],
    model: Optional[str] = None,
    use_cache: bool = True
) -> Dict[str, Any]:
    """
    Analyze sentiment of multiple texts
    
    Args:
        texts: List of texts to analyze
        model: Specific model to use (optional)
        use_cache: Whether to use cached results
        
    Returns:
        List of sentiment analysis results
    """
    try:
        if not texts or len(texts) == 0:
            raise HTTPException(
                status_code=400,
                detail=create_error_response("Texts list cannot be empty").dict()
            )
        
        if len(texts) > 100:  # Limit batch size
            raise HTTPException(
                status_code=400,
                detail=create_error_response("Batch size cannot exceed 100 texts").dict()
            )
        
        # Analyze sentiments
        results = sentiment_analyzer.analyze_batch(
            texts=texts,
            model=model
        )
        
        # Convert results to dict format
        results_data = []
        for i, result in enumerate(results):
            results_data.append({
                "text": texts[i],
                "sentiment_score": result.sentiment_score,
                "confidence": result.confidence,
                "emotions": result.emotions,
                "context": result.context,
                "model_used": result.model_used,
                "processing_time": result.processing_time,
                "local_processing": result.local_processing
            })
        
        return create_success_response(
            data={
                "results": results_data,
                "total_analyzed": len(results),
                "model_used": results[0].model_used if results else None
            },
            message=f"Batch sentiment analysis completed for {len(results)} texts"
        ).dict()
        
    except Exception as e:
        logger.error(f"Error in batch sentiment analysis API: {e}")
        raise HTTPException(
            status_code=500,
            detail=create_error_response(f"Batch sentiment analysis failed: {str(e)}").dict()
        )

@router.post("/trends")
async def get_sentiment_trends(
    articles: List[Dict[str, Any]],
    time_window_hours: int = Query(24, ge=1, le=168)  # 1 hour to 1 week
) -> Dict[str, Any]:
    """
    Analyze sentiment trends over time
    
    Args:
        articles: List of articles with sentiment data
        time_window_hours: Time window for trend analysis (1-168 hours)
        
    Returns:
        Sentiment trend analysis
    """
    try:
        if not articles:
            raise HTTPException(
                status_code=400,
                detail=create_error_response("Articles list cannot be empty").dict()
            )
        
        # Analyze trends
        trends = sentiment_analyzer.get_sentiment_trends(
            articles=articles,
            time_window_hours=time_window_hours
        )
        
        if "error" in trends:
            raise HTTPException(
                status_code=400,
                detail=create_error_response(trends["error"]).dict()
            )
        
        return create_success_response(
            data=trends,
            message="Sentiment trends analysis completed successfully"
        ).dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in sentiment trends API: {e}")
        raise HTTPException(
            status_code=500,
            detail=create_error_response(f"Sentiment trends analysis failed: {str(e)}").dict()
        )

@router.get("/models")
async def get_available_models() -> Dict[str, Any]:
    """
    Get available sentiment analysis models
    
    Returns:
        List of available models
    """
    try:
        cache_stats = sentiment_analyzer.get_cache_stats()
        
        return create_success_response(
            data={
                "available_models": cache_stats["available_models"],
                "default_model": cache_stats["default_model"],
                "cache_size": cache_stats["cache_size"],
                "cache_ttl": cache_stats["cache_ttl"]
            },
            message="Available models retrieved successfully"
        ).dict()
        
    except Exception as e:
        logger.error(f"Error getting available models: {e}")
        raise HTTPException(
            status_code=500,
            detail=create_error_response(f"Failed to get available models: {str(e)}").dict()
        )

@router.post("/clear-cache")
async def clear_sentiment_cache() -> Dict[str, Any]:
    """
    Clear sentiment analysis cache
    
    Returns:
        Confirmation message
    """
    try:
        sentiment_analyzer.clear_cache()
        
        return create_success_response(
            data={"cache_cleared": True},
            message="Sentiment analysis cache cleared successfully"
        ).dict()
        
    except Exception as e:
        logger.error(f"Error clearing sentiment cache: {e}")
        raise HTTPException(
            status_code=500,
            detail=create_error_response(f"Failed to clear cache: {str(e)}").dict()
        )

@router.get("/health")
async def sentiment_health_check() -> Dict[str, Any]:
    """
    Health check for sentiment analysis service
    
    Returns:
        Service health status
    """
    try:
        # Test with a simple sentiment analysis
        test_result = sentiment_analyzer.analyze_sentiment(
            text="This is a test for health check.",
            use_cache=False
        )
        
        return create_success_response(
            data={
                "status": "healthy",
                "model_used": test_result.model_used,
                "processing_time": test_result.processing_time,
                "local_processing": test_result.local_processing,
                "timestamp": datetime.now().isoformat()
            },
            message="Sentiment analysis service is healthy"
        ).dict()
        
    except Exception as e:
        logger.error(f"Sentiment health check failed: {e}")
        return create_success_response(
            data={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            },
            message="Sentiment analysis service is unhealthy"
        ).dict()


