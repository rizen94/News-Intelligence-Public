"""
Advanced ML API Routes for News Intelligence System v3.0
Provides endpoints for readability, clustering, trends, and monitoring
"""

from fastapi import APIRouter, HTTPException, Body, Query
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from modules.ml.readability_analyzer import readability_analyzer
from modules.ml.advanced_clustering import advanced_clustering
from modules.ml.trend_analyzer import trend_analyzer
from modules.ml.local_monitoring import local_monitoring
from schemas.response_schemas import create_success_response, create_error_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/advanced-ml", tags=["advanced-ml"])

# Readability Analysis Endpoints
@router.post("/readability/analyze")
async def analyze_readability(
    text: str = Body(..., description="Text to analyze for readability and quality"),
    model: Optional[str] = Body(None, description="Specific model to use"),
    use_cache: bool = Body(True, description="Whether to use cached results")
) -> Dict[str, Any]:
    """Analyze content for readability and quality metrics"""
    try:
        if not text or len(text.strip()) == 0:
            raise HTTPException(
                status_code=400,
                detail=create_error_response("Text cannot be empty").dict()
            )
        
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
            message="Readability analysis completed successfully"
        ).dict()
        
    except Exception as e:
        logger.error(f"Error in readability analysis API: {e}")
        raise HTTPException(
            status_code=500,
            detail=create_error_response(f"Readability analysis failed: {str(e)}").dict()
        )

# Clustering Endpoints
@router.post("/clustering/cluster")
async def cluster_articles(
    articles: Optional[List[Dict[str, Any]]] = Body(None, description="Articles to cluster"),
    texts: Optional[List[str]] = Body(None, description="Texts to cluster"),
    algorithm: str = Body("kmeans", description="Clustering algorithm"),
    num_clusters: Optional[int] = Body(None, description="Number of clusters"),
    model: Optional[str] = Body(None, description="Specific model to use"),
    use_cache: bool = Body(True, description="Whether to use cached results")
) -> Dict[str, Any]:
    """Cluster articles using advanced algorithms"""
    try:
        # Handle both articles and texts input
        if articles and len(articles) >= 2:
            input_data = articles
        elif texts and len(texts) >= 2:
            # Convert texts to article format
            input_data = [{"content": text, "title": f"Text {i+1}"} for i, text in enumerate(texts)]
        else:
            raise HTTPException(
                status_code=400,
                detail=create_error_response("At least 2 articles or texts are required for clustering").dict()
            )
        
        result = advanced_clustering.cluster_articles(
            articles=input_data,
            algorithm=algorithm,
            num_clusters=num_clusters,
            model=model,
            use_cache=use_cache
        )
        
        return create_success_response(
            data={
                "clusters": [
                    {
                        "cluster_id": cluster.cluster_id,
                        "articles": cluster.articles,
                        "centroid": cluster.centroid,
                        "size": cluster.size,
                        "keywords": cluster.keywords,
                        "summary": cluster.summary,
                        "coherence_score": cluster.coherence_score,
                        "local_processing": cluster.local_processing
                    } for cluster in result.clusters
                ],
                "total_articles": result.total_articles,
                "num_clusters": result.num_clusters,
                "algorithm_used": result.algorithm_used,
                "silhouette_score": result.silhouette_score,
                "processing_time": result.processing_time,
                "model_used": result.model_used,
                "local_processing": result.local_processing
            },
            message="Clustering completed successfully"
        ).dict()
        
    except Exception as e:
        logger.error(f"Error in clustering API: {e}")
        raise HTTPException(
            status_code=500,
            detail=create_error_response(f"Clustering failed: {str(e)}").dict()
        )

# Trend Analysis Endpoints
@router.post("/trends/analyze")
async def analyze_trends(
    articles: Optional[List[Dict[str, Any]]] = Body(None, description="Articles to analyze for trends"),
    texts: Optional[List[str]] = Body(None, description="Texts to analyze for trends"),
    metric: str = Body("sentiment", description="Metric to analyze"),
    time_window_hours: int = Body(24, description="Time window for analysis"),
    model: Optional[str] = Body(None, description="Specific model to use"),
    use_cache: bool = Body(True, description="Whether to use cached results")
) -> Dict[str, Any]:
    """Analyze trends in article data"""
    try:
        # Handle both articles and texts input
        if articles and len(articles) >= 3:
            input_data = articles
        elif texts and len(texts) >= 3:
            # Convert texts to article format
            input_data = [{"content": text, "title": f"Text {i+1}"} for i, text in enumerate(texts)]
        else:
            raise HTTPException(
                status_code=400,
                detail=create_error_response("At least 3 articles or texts are required for trend analysis").dict()
            )
        
        result = trend_analyzer.analyze_trends(
            articles=input_data,
            metric=metric,
            time_window_hours=time_window_hours,
            model=model,
            use_cache=use_cache
        )
        
        return create_success_response(
            data={
                "trends": [
                    {
                        "pattern_type": trend.pattern_type,
                        "strength": trend.strength,
                        "duration_hours": trend.duration_hours,
                        "start_time": trend.start_time.isoformat(),
                        "end_time": trend.end_time.isoformat(),
                        "peak_value": trend.peak_value,
                        "valley_value": trend.valley_value,
                        "volatility": trend.volatility,
                        "description": trend.description
                    } for trend in result.trends
                ],
                "overall_trend": result.overall_trend,
                "trend_strength": result.trend_strength,
                "volatility_score": result.volatility_score,
                "key_events": result.key_events,
                "predictions": result.predictions,
                "analysis_period": {
                    "start": result.analysis_period["start"].isoformat(),
                    "end": result.analysis_period["end"].isoformat()
                },
                "processing_time": result.processing_time,
                "model_used": result.model_used,
                "local_processing": result.local_processing
            },
            message="Trend analysis completed successfully"
        ).dict()
        
    except Exception as e:
        logger.error(f"Error in trend analysis API: {e}")
        raise HTTPException(
            status_code=500,
            detail=create_error_response(f"Trend analysis failed: {str(e)}").dict()
        )

# Monitoring Endpoints
@router.get("/monitoring/status")
async def get_monitoring_status() -> Dict[str, Any]:
    """Get monitoring system status"""
    try:
        performance_summary = local_monitoring.get_performance_summary()
        
        return create_success_response(
            data=performance_summary,
            message="Monitoring status retrieved successfully"
        ).dict()
        
    except Exception as e:
        logger.error(f"Error getting monitoring status: {e}")
        raise HTTPException(
            status_code=500,
            detail=create_error_response(f"Failed to get monitoring status: {str(e)}").dict()
        )

@router.get("/monitoring/metrics/system")
async def get_system_metrics(
    hours: int = Query(1, description="Hours of metrics to retrieve")
) -> Dict[str, Any]:
    """Get system performance metrics"""
    try:
        metrics = local_monitoring.get_system_metrics(hours)
        
        return create_success_response(
            data={
                "metrics": metrics,
                "hours": hours,
                "count": len(metrics)
            },
            message="System metrics retrieved successfully"
        ).dict()
        
    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail=create_error_response(f"Failed to get system metrics: {str(e)}").dict()
        )

@router.get("/monitoring/metrics/ai")
async def get_ai_metrics(
    hours: int = Query(1, description="Hours of metrics to retrieve")
) -> Dict[str, Any]:
    """Get AI processing metrics"""
    try:
        metrics = local_monitoring.get_ai_metrics(hours)
        
        return create_success_response(
            data={
                "metrics": metrics,
                "hours": hours,
                "count": len(metrics)
            },
            message="AI metrics retrieved successfully"
        ).dict()
        
    except Exception as e:
        logger.error(f"Error getting AI metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail=create_error_response(f"Failed to get AI metrics: {str(e)}").dict()
        )

@router.get("/monitoring/cache/stats")
async def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics"""
    try:
        stats = local_monitoring.get_cache_stats()
        
        return create_success_response(
            data={
                "total_entries": stats.total_entries,
                "hit_rate": stats.hit_rate,
                "miss_rate": stats.miss_rate,
                "memory_usage_mb": stats.memory_usage_mb,
                "oldest_entry": stats.oldest_entry.isoformat(),
                "newest_entry": stats.newest_entry.isoformat(),
                "eviction_count": stats.eviction_count
            },
            message="Cache statistics retrieved successfully"
        ).dict()
        
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=create_error_response(f"Failed to get cache stats: {str(e)}").dict()
        )

@router.get("/monitoring/alerts")
async def get_alerts(
    level: Optional[str] = Query(None, description="Filter alerts by level")
) -> Dict[str, Any]:
    """Get recent alerts"""
    try:
        alerts = local_monitoring.get_alerts(level)
        
        return create_success_response(
            data={
                "alerts": alerts,
                "count": len(alerts),
                "level_filter": level
            },
            message="Alerts retrieved successfully"
        ).dict()
        
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        raise HTTPException(
            status_code=500,
            detail=create_error_response(f"Failed to get alerts: {str(e)}").dict()
        )

@router.post("/monitoring/cache/clear")
async def clear_cache() -> Dict[str, Any]:
    """Clear all cache entries"""
    try:
        local_monitoring.clear_cache()
        
        return create_success_response(
            data={"cache_cleared": True},
            message="Cache cleared successfully"
        ).dict()
        
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(
            status_code=500,
            detail=create_error_response(f"Failed to clear cache: {str(e)}").dict()
        )

@router.post("/monitoring/start")
async def start_monitoring() -> Dict[str, Any]:
    """Start the monitoring system"""
    try:
        local_monitoring.start_monitoring()
        
        return create_success_response(
            data={"monitoring_started": True},
            message="Monitoring system started"
        ).dict()
        
    except Exception as e:
        logger.error(f"Error starting monitoring: {e}")
        raise HTTPException(
            status_code=500,
            detail=create_error_response(f"Failed to start monitoring: {str(e)}").dict()
        )

@router.post("/monitoring/stop")
async def stop_monitoring() -> Dict[str, Any]:
    """Stop the monitoring system"""
    try:
        local_monitoring.stop_monitoring()
        
        return create_success_response(
            data={"monitoring_stopped": True},
            message="Monitoring system stopped"
        ).dict()
        
    except Exception as e:
        logger.error(f"Error stopping monitoring: {e}")
        raise HTTPException(
            status_code=500,
            detail=create_error_response(f"Failed to stop monitoring: {str(e)}").dict()
        )

# Health Check
@router.get("/health")
async def advanced_ml_health_check() -> Dict[str, Any]:
    """Health check for advanced ML services"""
    try:
        # Test each service
        services_status = {}
        
        # Test readability analyzer
        try:
            test_result = readability_analyzer.analyze_content(
                text="This is a test for health check.",
                use_cache=False
            )
            services_status["readability"] = "healthy"
        except Exception as e:
            services_status["readability"] = f"unhealthy: {str(e)}"
        
        # Test clustering
        try:
            test_articles = [
                {"title": "Test Article 1", "content": "This is a test article about technology."},
                {"title": "Test Article 2", "content": "This is another test article about science."}
            ]
            test_result = advanced_clustering.cluster_articles(
                articles=test_articles,
                use_cache=False
            )
            services_status["clustering"] = "healthy"
        except Exception as e:
            services_status["clustering"] = f"unhealthy: {str(e)}"
        
        # Test trend analyzer
        try:
            test_articles = [
                {"created_at": datetime.now().timestamp(), "sentiment_score": 0.5},
                {"created_at": (datetime.now().timestamp() - 3600), "sentiment_score": 0.6},
                {"created_at": (datetime.now().timestamp() - 7200), "sentiment_score": 0.7}
            ]
            test_result = trend_analyzer.analyze_trends(
                articles=test_articles,
                use_cache=False
            )
            services_status["trends"] = "healthy"
        except Exception as e:
            services_status["trends"] = f"unhealthy: {str(e)}"
        
        # Test monitoring
        try:
            performance_summary = local_monitoring.get_performance_summary()
            services_status["monitoring"] = "healthy"
        except Exception as e:
            services_status["monitoring"] = f"unhealthy: {str(e)}"
        
        overall_status = "healthy" if all("healthy" in status for status in services_status.values()) else "degraded"
        
        return create_success_response(
            data={
                "status": overall_status,
                "services": services_status,
                "timestamp": datetime.now().isoformat()
            },
            message="Advanced ML services health check completed"
        ).dict()
        
    except Exception as e:
        logger.error(f"Advanced ML health check failed: {e}")
        return create_success_response(
            data={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            },
            message="Advanced ML services health check failed"
        ).dict()
