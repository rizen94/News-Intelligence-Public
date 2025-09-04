"""
Health and Status API Routes for News Intelligence System v3.0
Provides system health checks and status information
"""

import os
import time
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any, List

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from config.database import get_db_connection
from middleware.metrics import MetricsMiddleware

router = APIRouter()

# Pydantic models for request/response
class HealthResponse(BaseModel):
    """Health check response model"""
    status: str = Field(..., description="Overall system status")
    timestamp: datetime = Field(..., description="Health check timestamp")
    version: str = Field(..., description="System version")
    uptime_seconds: float = Field(..., description="System uptime in seconds")
    services: Dict[str, Dict[str, Any]] = Field(..., description="Service status details")

class ServiceStatus(BaseModel):
    """Individual service status model"""
    status: str = Field(..., description="Service status (healthy/unhealthy)")
    message: str = Field(..., description="Status message")
    last_check: datetime = Field(..., description="Last check timestamp")
    response_time_ms: float = Field(..., description="Response time in milliseconds")

class SystemMetrics(BaseModel):
    """System metrics model"""
    cpu_percent: float = Field(..., description="CPU usage percentage")
    memory_percent: float = Field(..., description="Memory usage percentage")
    disk_percent: float = Field(..., description="Disk usage percentage")
    active_connections: int = Field(..., description="Active database connections")
    articles_processed_today: int = Field(..., description="Articles processed today")
    ml_processing_queue: int = Field(..., description="ML processing queue size")

# Global variables for tracking
startup_time = time.time()

@router.get("/", response_model=HealthResponse)
async def health_check():
    """
    Comprehensive health check endpoint
    
    Returns the overall system health status including:
    - Database connectivity
    - ML pipeline status
    - Monitoring system status
    - System metrics
    """
    try:
        current_time = datetime.utcnow()
        uptime = time.time() - startup_time
        
        # Check database
        db_status = await check_database_health()
        
        # Check ML pipeline
        ml_status = await check_ml_pipeline_health()
        
        # Check monitoring
        monitoring_status = await check_monitoring_health()
        
        # Check story management
        story_management_status = await check_story_management_health()
        
        # Check feedback loop
        feedback_loop_status = await check_feedback_loop_health()
        
        # Check RSS collection
        rss_status = await check_rss_collection_health()
        
        # Determine overall status
        critical_services = [db_status, ml_status]
        optional_services = [monitoring_status, story_management_status, feedback_loop_status, rss_status]
        
        critical_healthy = all(service["status"] == "healthy" for service in critical_services)
        optional_healthy = all(service["status"] in ["healthy", "degraded"] for service in optional_services)
        
        if critical_healthy and optional_healthy:
            overall_status = "healthy"
        elif critical_healthy:
            overall_status = "degraded"
        else:
            overall_status = "unhealthy"
        
        return HealthResponse(
            status=overall_status,
            timestamp=current_time,
            version="3.0.0",
            uptime_seconds=uptime,
            services={
                "database": db_status,
                "ml_pipeline": ml_status,
                "monitoring": monitoring_status,
                "story_management": story_management_status,
                "feedback_loop": feedback_loop_status,
                "rss_collection": rss_status
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Health check failed: {str(e)}"
        )

@router.get("/database", response_model=ServiceStatus)
async def database_health():
    """Check database connectivity and performance"""
    return await check_database_health()

@router.get("/ml", response_model=ServiceStatus)
async def ml_pipeline_health():
    """Check ML pipeline status and performance"""
    return await check_ml_pipeline_health()

@router.get("/monitoring", response_model=ServiceStatus)
async def monitoring_health():
    """Check monitoring system status"""
    return await check_monitoring_health()

@router.get("/story-management", response_model=ServiceStatus)
async def story_management_health():
    """Check story management system status"""
    return await check_story_management_health()

@router.get("/feedback-loop", response_model=ServiceStatus)
async def feedback_loop_health():
    """Check feedback loop system status"""
    return await check_feedback_loop_health()

@router.get("/rss", response_model=ServiceStatus)
async def rss_health():
    """Check RSS collection system status"""
    return await check_rss_collection_health()

@router.get("/metrics", response_model=SystemMetrics)
async def system_metrics():
    """
    Get system performance metrics
    
    Returns current system resource usage and performance indicators
    """
    try:
        # Get system metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Get database connection count
        active_connections = await get_database_connection_count()
        
        # Get articles processed today
        articles_today = await get_articles_processed_today()
        
        # Get ML queue size
        ml_queue_size = await get_ml_queue_size()
        
        return SystemMetrics(
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            disk_percent=disk.percent,
            active_connections=active_connections,
            articles_processed_today=articles_today,
            ml_processing_queue=ml_queue_size
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get system metrics: {str(e)}"
        )

@router.get("/ready")
async def readiness_check():
    """
    Kubernetes readiness probe endpoint
    
    Returns 200 if the system is ready to accept traffic
    """
    try:
        # Check critical services
        db_healthy = await check_database_health()
        ml_healthy = await check_ml_pipeline_health()
        
        if db_healthy["status"] != "healthy":
            raise HTTPException(status_code=503, detail="Database not ready")
        
        if ml_healthy["status"] != "healthy":
            raise HTTPException(status_code=503, detail="ML pipeline not ready")
        
        return {"status": "ready", "timestamp": datetime.utcnow()}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"System not ready: {str(e)}"
        )

@router.get("/live")
async def liveness_check():
    """
    Kubernetes liveness probe endpoint
    
    Returns 200 if the system is alive and responding
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow(),
        "uptime_seconds": time.time() - startup_time
    }

# Helper functions
async def check_database_health() -> Dict[str, Any]:
    """Check database health and performance"""
    start_time = time.time()
    
    try:
        # Test database connection
        conn = await get_db_connection()
        
        # Test a simple query
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()
        
        response_time = (time.time() - start_time) * 1000
        
        return {
            "status": "healthy",
            "message": "Database connection successful",
            "last_check": datetime.utcnow(),
            "response_time_ms": response_time
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"Database error: {str(e)}",
            "last_check": datetime.utcnow(),
            "response_time_ms": (time.time() - start_time) * 1000
        }

async def check_ml_pipeline_health() -> Dict[str, Any]:
    """Check ML pipeline health"""
    start_time = time.time()
    
    try:
        # Check if ML pipeline is available in app state
        from main import app_state
        
        if "ml_pipeline" not in app_state or not app_state.get("ml_available", False):
            return {
                "status": "unhealthy",
                "message": "ML pipeline not initialized",
                "last_check": datetime.utcnow(),
                "response_time_ms": (time.time() - start_time) * 1000
            }
        
        # Check if pipeline has is_healthy method
        pipeline = app_state["ml_pipeline"]
        if hasattr(pipeline, 'is_healthy'):
            is_healthy = pipeline.is_healthy()
        else:
            # Basic check - if pipeline exists and is initialized
            is_healthy = pipeline is not None
        
        response_time = (time.time() - start_time) * 1000
        
        if is_healthy:
            return {
                "status": "healthy",
                "message": "ML pipeline operational",
                "last_check": datetime.utcnow(),
                "response_time_ms": response_time
            }
        else:
            return {
                "status": "degraded",
                "message": "ML pipeline partially operational",
                "last_check": datetime.utcnow(),
                "response_time_ms": response_time
            }
            
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"ML pipeline error: {str(e)}",
            "last_check": datetime.utcnow(),
            "response_time_ms": (time.time() - start_time) * 1000
        }

async def check_monitoring_health() -> Dict[str, Any]:
    """Check monitoring system health"""
    start_time = time.time()
    
    try:
        # Check if monitoring is available in app state
        from main import app_state
        
        if "monitoring" not in app_state or not app_state.get("monitoring_available", False):
            return {
                "status": "unhealthy",
                "message": "Monitoring system not initialized",
                "last_check": datetime.utcnow(),
                "response_time_ms": (time.time() - start_time) * 1000
            }
        
        # Check if monitoring has is_healthy method
        monitor = app_state["monitoring"]
        if hasattr(monitor, 'is_healthy'):
            is_healthy = monitor.is_healthy()
        else:
            # Basic check - if monitor exists and is initialized
            is_healthy = monitor is not None
        
        response_time = (time.time() - start_time) * 1000
        
        if is_healthy:
            return {
                "status": "healthy",
                "message": "Monitoring system operational",
                "last_check": datetime.utcnow(),
                "response_time_ms": response_time
            }
        else:
            return {
                "status": "degraded",
                "message": "Monitoring system partially operational",
                "last_check": datetime.utcnow(),
                "response_time_ms": response_time
            }
            
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"Monitoring error: {str(e)}",
            "last_check": datetime.utcnow(),
            "response_time_ms": (time.time() - start_time) * 1000
        }

async def get_database_connection_count() -> int:
    """Get current database connection count"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count
    except:
        return 0

async def get_articles_processed_today() -> int:
    """Get count of articles processed today"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM articles 
            WHERE created_at >= CURRENT_DATE
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
        from main import app_state
        if "ml_pipeline" in app_state and app_state.get("ml_available", False):
            pipeline = app_state["ml_pipeline"]
            if hasattr(pipeline, 'get_queue_size'):
                return pipeline.get_queue_size()
        return 0
    except:
        return 0

async def check_story_management_health() -> Dict[str, Any]:
    """Check story management system health"""
    start_time = time.time()
    
    try:
        # Check if story management tables exist and are accessible
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Check story_expectations table
        cursor.execute("""
            SELECT COUNT(*) FROM story_expectations 
            WHERE is_active = true
        """)
        active_stories = cursor.fetchone()[0]
        
        # Check story_targets table
        cursor.execute("SELECT COUNT(*) FROM story_targets WHERE is_active = true")
        active_targets = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        response_time = (time.time() - start_time) * 1000
        
        return {
            "status": "healthy",
            "message": f"Story management operational - {active_stories} active stories, {active_targets} targets",
            "last_check": datetime.utcnow(),
            "response_time_ms": response_time,
            "active_stories": active_stories,
            "active_targets": active_targets
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"Story management error: {str(e)}",
            "last_check": datetime.utcnow(),
            "response_time_ms": (time.time() - start_time) * 1000
        }

async def check_feedback_loop_health() -> Dict[str, Any]:
    """Check feedback loop system health"""
    start_time = time.time()
    
    try:
        # Check feedback loop status table
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT is_running, last_run, stories_being_tracked, 
                   articles_processed_today, context_growth_percentage
            FROM feedback_loop_status 
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        response_time = (time.time() - start_time) * 1000
        
        if result:
            is_running, last_run, stories_tracked, articles_processed, growth = result
            status = "healthy" if is_running else "degraded"
            message = f"Feedback loop {'running' if is_running else 'stopped'} - {stories_tracked} stories tracked, {articles_processed} articles processed today"
        else:
            status = "unhealthy"
            message = "No feedback loop status found"
            is_running = False
            stories_tracked = 0
            articles_processed = 0
            growth = 0.0
        
        return {
            "status": status,
            "message": message,
            "last_check": datetime.utcnow(),
            "response_time_ms": response_time,
            "is_running": is_running,
            "stories_tracked": stories_tracked,
            "articles_processed_today": articles_processed,
            "context_growth_percentage": float(growth) if growth else 0.0
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"Feedback loop error: {str(e)}",
            "last_check": datetime.utcnow(),
            "response_time_ms": (time.time() - start_time) * 1000
        }

async def check_rss_collection_health() -> Dict[str, Any]:
    """Check RSS collection system health"""
    start_time = time.time()
    
    try:
        # Check RSS feeds table
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_feeds,
                COUNT(CASE WHEN is_active = true THEN 1 END) as active_feeds,
                COUNT(CASE WHEN last_success > NOW() - INTERVAL '24 hours' THEN 1 END) as recent_success,
                AVG(article_count) as avg_articles_per_feed
            FROM rss_feeds
        """)
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        response_time = (time.time() - start_time) * 1000
        
        if result:
            total_feeds, active_feeds, recent_success, avg_articles = result
            avg_articles = float(avg_articles) if avg_articles else 0.0
            
            if active_feeds > 0 and recent_success > 0:
                status = "healthy"
                message = f"RSS collection operational - {active_feeds}/{total_feeds} active feeds, {recent_success} recent successes"
            elif active_feeds > 0:
                status = "degraded"
                message = f"RSS collection partially operational - {active_feeds}/{total_feeds} active feeds, no recent successes"
            else:
                status = "unhealthy"
                message = "No active RSS feeds configured"
        else:
            status = "unhealthy"
            message = "No RSS feeds found"
            total_feeds = active_feeds = recent_success = 0
            avg_articles = 0.0
        
        return {
            "status": status,
            "message": message,
            "last_check": datetime.utcnow(),
            "response_time_ms": response_time,
            "total_feeds": total_feeds,
            "active_feeds": active_feeds,
            "recent_successes": recent_success,
            "avg_articles_per_feed": avg_articles
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"RSS collection error: {str(e)}",
            "last_check": datetime.utcnow(),
            "response_time_ms": (time.time() - start_time) * 1000
        }
