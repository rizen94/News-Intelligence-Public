"""
Dashboard API Routes for News Intelligence System v3.0
Provides real-time dashboard data and statistics
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from api.config.database import get_db_connection

router = APIRouter()

# Pydantic models
class DashboardStats(BaseModel):
    """Dashboard statistics model"""
    total_articles: int = Field(..., description="Total number of articles")
    articles_today: int = Field(..., description="Articles collected today")
    articles_this_hour: int = Field(..., description="Articles collected this hour")
    active_stories: int = Field(..., description="Number of active stories")
    ml_processing_queue: int = Field(..., description="ML processing queue size")
    system_uptime_hours: float = Field(..., description="System uptime in hours")
    last_update: datetime = Field(..., description="Last data update timestamp")

class IngestionStats(BaseModel):
    """Article ingestion statistics model"""
    period: str = Field(..., description="Time period (hour, day, week)")
    articles_count: int = Field(..., description="Number of articles")
    sources_count: int = Field(..., description="Number of active sources")
    avg_processing_time: float = Field(..., description="Average processing time in seconds")
    success_rate: float = Field(..., description="Success rate percentage")

class MLPipelineStats(BaseModel):
    """ML pipeline statistics model"""
    queue_size: int = Field(..., description="Current queue size")
    processing_rate: float = Field(..., description="Articles processed per hour")
    avg_processing_time: float = Field(..., description="Average processing time")
    models_status: Dict[str, str] = Field(..., description="Model status")
    last_processed: Optional[datetime] = Field(None, description="Last processing timestamp")

class StoryEvolutionStats(BaseModel):
    """Story evolution statistics model"""
    total_stories: int = Field(..., description="Total number of stories")
    active_stories: int = Field(..., description="Currently active stories")
    stories_today: int = Field(..., description="New stories today")
    avg_articles_per_story: float = Field(..., description="Average articles per story")
    top_categories: List[Dict[str, Any]] = Field(..., description="Top story categories")

class SystemAlerts(BaseModel):
    """System alerts model"""
    alerts: List[Dict[str, Any]] = Field(..., description="List of active alerts")
    critical_count: int = Field(..., description="Number of critical alerts")
    warning_count: int = Field(..., description="Number of warning alerts")
    info_count: int = Field(..., description="Number of info alerts")

@router.get("/", response_model=DashboardStats)
async def get_dashboard_stats():
    """
    Get comprehensive dashboard statistics
    
    Returns real-time statistics for the main dashboard including:
    - Article counts and ingestion rates
    - Story tracking statistics
    - ML pipeline status
    - System health indicators
    """
    try:
        # Get basic statistics
        total_articles = await get_total_articles()
        articles_today = await get_articles_today()
        articles_this_hour = await get_articles_this_hour()
        active_stories = await get_active_stories()
        ml_queue_size = await get_ml_queue_size()
        uptime_hours = await get_system_uptime_hours()
        
        return DashboardStats(
            total_articles=total_articles,
            articles_today=articles_today,
            articles_this_hour=articles_this_hour,
            active_stories=active_stories,
            ml_processing_queue=ml_queue_size,
            system_uptime_hours=uptime_hours,
            last_update=datetime.utcnow()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get dashboard stats: {str(e)}"
        )

@router.get("/ingestion", response_model=IngestionStats)
async def get_ingestion_stats(
    period: str = Query("hour", description="Time period: hour, day, week")
):
    """
    Get article ingestion statistics
    
    Returns detailed statistics about article ingestion for the specified period
    """
    try:
        if period not in ["hour", "day", "week"]:
            raise HTTPException(
                status_code=400,
                detail="Period must be one of: hour, day, week"
            )
        
        # Get ingestion data for the period
        articles_count = await get_articles_count_for_period(period)
        sources_count = await get_active_sources_count(period)
        avg_processing_time = await get_avg_processing_time(period)
        success_rate = await get_ingestion_success_rate(period)
        
        return IngestionStats(
            period=period,
            articles_count=articles_count,
            sources_count=sources_count,
            avg_processing_time=avg_processing_time,
            success_rate=success_rate
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get ingestion stats: {str(e)}"
        )

@router.get("/ml-pipeline", response_model=MLPipelineStats)
async def get_ml_pipeline_stats():
    """
    Get ML pipeline statistics
    
    Returns detailed statistics about the ML processing pipeline
    """
    try:
        queue_size = await get_ml_queue_size()
        processing_rate = await get_ml_processing_rate()
        avg_processing_time = await get_ml_avg_processing_time()
        models_status = await get_models_status()
        last_processed = await get_last_ml_processing_time()
        
        return MLPipelineStats(
            queue_size=queue_size,
            processing_rate=processing_rate,
            avg_processing_time=avg_processing_time,
            models_status=models_status,
            last_processed=last_processed
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get ML pipeline stats: {str(e)}"
        )

@router.get("/story-evolution", response_model=StoryEvolutionStats)
async def get_story_evolution_stats():
    """
    Get story evolution statistics
    
    Returns statistics about story tracking and evolution
    """
    try:
        total_stories = await get_total_stories()
        active_stories = await get_active_stories()
        stories_today = await get_stories_today()
        avg_articles_per_story = await get_avg_articles_per_story()
        top_categories = await get_top_story_categories()
        
        return StoryEvolutionStats(
            total_stories=total_stories,
            active_stories=active_stories,
            stories_today=stories_today,
            avg_articles_per_story=avg_articles_per_story,
            top_categories=top_categories
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get story evolution stats: {str(e)}"
        )

@router.get("/alerts", response_model=SystemAlerts)
async def get_system_alerts():
    """
    Get system alerts and notifications
    
    Returns current system alerts categorized by severity
    """
    try:
        alerts = await get_active_alerts()
        
        critical_count = sum(1 for alert in alerts if alert.get("severity") == "critical")
        warning_count = sum(1 for alert in alerts if alert.get("severity") == "warning")
        info_count = sum(1 for alert in alerts if alert.get("severity") == "info")
        
        return SystemAlerts(
            alerts=alerts,
            critical_count=critical_count,
            warning_count=warning_count,
            info_count=info_count
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get system alerts: {str(e)}"
        )

@router.get("/recent-activity")
async def get_recent_activity(
    limit: int = Query(10, description="Number of recent activities to return")
):
    """
    Get recent system activity
    
    Returns a list of recent activities and events
    """
    try:
        if limit > 100:
            limit = 100
        
        activities = await get_recent_activities(limit)
        return {"activities": activities}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get recent activity: {str(e)}"
        )

# Helper functions
async def get_total_articles() -> int:
    """Get total number of articles"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM articles")
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count
    except:
        return 0

async def get_articles_today() -> int:
    """Get articles collected today"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM articles 
            WHERE DATE(created_at) = CURRENT_DATE
        """)
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count
    except:
        return 0

async def get_articles_this_hour() -> int:
    """Get articles collected this hour"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM articles 
            WHERE created_at >= NOW() - INTERVAL '1 hour'
        """)
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count
    except:
        return 0

async def get_active_stories() -> int:
    """Get number of active stories"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM stories 
            WHERE status = 'active'
        """)
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count
    except:
        return 0

async def get_ml_queue_size() -> int:
    """Get ML processing queue size"""
    try:
        from api.modules.ml.ml_pipeline import MLPipeline
        pipeline = MLPipeline()
        return pipeline.get_queue_size()
    except:
        return 0

async def get_system_uptime_hours() -> float:
    """Get system uptime in hours"""
    try:
        # This would typically come from system monitoring
        # For now, return a placeholder
        return 24.0
    except:
        return 0.0

async def get_articles_count_for_period(period: str) -> int:
    """Get article count for specified period"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        if period == "hour":
            cursor.execute("""
                SELECT COUNT(*) FROM articles 
                WHERE created_at >= NOW() - INTERVAL '1 hour'
            """)
        elif period == "day":
            cursor.execute("""
                SELECT COUNT(*) FROM articles 
                WHERE created_at >= NOW() - INTERVAL '1 day'
            """)
        elif period == "week":
            cursor.execute("""
                SELECT COUNT(*) FROM articles 
                WHERE created_at >= NOW() - INTERVAL '1 week'
            """)
        
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count
    except:
        return 0

async def get_active_sources_count(period: str) -> int:
    """Get count of active sources for period"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        if period == "hour":
            cursor.execute("""
                SELECT COUNT(DISTINCT source) FROM articles 
                WHERE created_at >= NOW() - INTERVAL '1 hour'
            """)
        elif period == "day":
            cursor.execute("""
                SELECT COUNT(DISTINCT source) FROM articles 
                WHERE created_at >= NOW() - INTERVAL '1 day'
            """)
        elif period == "week":
            cursor.execute("""
                SELECT COUNT(DISTINCT source) FROM articles 
                WHERE created_at >= NOW() - INTERVAL '1 week'
            """)
        
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count
    except:
        return 0

async def get_avg_processing_time(period: str) -> float:
    """Get average processing time for period"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        if period == "hour":
            cursor.execute("""
                SELECT AVG(EXTRACT(EPOCH FROM (processed_at - created_at))) 
                FROM articles 
                WHERE created_at >= NOW() - INTERVAL '1 hour' 
                AND processed_at IS NOT NULL
            """)
        elif period == "day":
            cursor.execute("""
                SELECT AVG(EXTRACT(EPOCH FROM (processed_at - created_at))) 
                FROM articles 
                WHERE created_at >= NOW() - INTERVAL '1 day' 
                AND processed_at IS NOT NULL
            """)
        elif period == "week":
            cursor.execute("""
                SELECT AVG(EXTRACT(EPOCH FROM (processed_at - created_at))) 
                FROM articles 
                WHERE created_at >= NOW() - INTERVAL '1 week' 
                AND processed_at IS NOT NULL
            """)
        
        result = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return float(result) if result else 0.0
    except:
        return 0.0

async def get_ingestion_success_rate(period: str) -> float:
    """Get ingestion success rate for period"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        if period == "hour":
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN status = 'processed' THEN 1 END) as successful
                FROM articles 
                WHERE created_at >= NOW() - INTERVAL '1 hour'
            """)
        elif period == "day":
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN status = 'processed' THEN 1 END) as successful
                FROM articles 
                WHERE created_at >= NOW() - INTERVAL '1 day'
            """)
        elif period == "week":
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN status = 'processed' THEN 1 END) as successful
                FROM articles 
                WHERE created_at >= NOW() - INTERVAL '1 week'
            """)
        
        total, successful = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if total == 0:
            return 0.0
        return (successful / total) * 100
    except:
        return 0.0

async def get_ml_processing_rate() -> float:
    """Get ML processing rate (articles per hour)"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM articles 
            WHERE ml_processed_at >= NOW() - INTERVAL '1 hour'
        """)
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return float(count)
    except:
        return 0.0

async def get_ml_avg_processing_time() -> float:
    """Get average ML processing time"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT AVG(EXTRACT(EPOCH FROM (ml_processed_at - created_at))) 
            FROM articles 
            WHERE ml_processed_at IS NOT NULL
        """)
        result = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return float(result) if result else 0.0
    except:
        return 0.0

async def get_models_status() -> Dict[str, str]:
    """Get status of ML models"""
    try:
        from api.modules.ml.ml_pipeline import MLPipeline
        pipeline = MLPipeline()
        return pipeline.get_models_status()
    except:
        return {"default": "unknown"}

async def get_last_ml_processing_time() -> Optional[datetime]:
    """Get last ML processing timestamp"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT MAX(ml_processed_at) FROM articles 
            WHERE ml_processed_at IS NOT NULL
        """)
        result = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return result
    except:
        return None

async def get_total_stories() -> int:
    """Get total number of stories"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM stories")
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count
    except:
        return 0

async def get_stories_today() -> int:
    """Get new stories today"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM stories 
            WHERE DATE(created_at) = CURRENT_DATE
        """)
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count
    except:
        return 0

async def get_avg_articles_per_story() -> float:
    """Get average articles per story"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT AVG(article_count) FROM (
                SELECT COUNT(*) as article_count 
                FROM story_articles 
                GROUP BY story_id
            ) as story_counts
        """)
        result = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return float(result) if result else 0.0
    except:
        return 0.0

async def get_top_story_categories(limit: int = 5) -> List[Dict[str, Any]]:
    """Get top story categories"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT category, COUNT(*) as count 
            FROM stories 
            GROUP BY category 
            ORDER BY count DESC 
            LIMIT %s
        """, (limit,))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "category": row[0],
                "count": row[1]
            })
        
        cursor.close()
        conn.close()
        return results
    except:
        return []

async def get_active_alerts() -> List[Dict[str, Any]]:
    """Get active system alerts"""
    try:
        # This would typically come from a monitoring system
        # For now, return some example alerts
        return [
            {
                "id": "alert_1",
                "severity": "info",
                "message": "System running normally",
                "timestamp": datetime.utcnow(),
                "category": "system"
            }
        ]
    except:
        return []

async def get_recent_activities(limit: int) -> List[Dict[str, Any]]:
    """Get recent system activities"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                'article_processed' as type,
                title,
                created_at as timestamp,
                source
            FROM articles 
            ORDER BY created_at DESC 
            LIMIT %s
        """, (limit,))
        
        activities = []
        for row in cursor.fetchall():
            activities.append({
                "type": row[0],
                "title": row[1],
                "timestamp": row[2],
                "source": row[3]
            })
        
        cursor.close()
        conn.close()
        return activities
    except:
        return []
