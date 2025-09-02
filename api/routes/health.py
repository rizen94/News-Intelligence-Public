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

from api.config.database import get_db_connection
from api.middleware.metrics import MetricsMiddleware

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
        
        # Determine overall status
        all_healthy = all([
            db_status["status"] == "healthy",
            ml_status["status"] == "healthy",
            monitoring_status["status"] == "healthy"
        ])
        
        overall_status = "healthy" if all_healthy else "degraded"
        
        return HealthResponse(
            status=overall_status,
            timestamp=current_time,
            version="3.0.0",
            uptime_seconds=uptime,
            services={
                "database": db_status,
                "ml_pipeline": ml_status,
                "monitoring": monitoring_status
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
        # Import ML pipeline
        from api.modules.ml.ml_pipeline import MLPipeline
        
        # Check if ML pipeline is available
        pipeline = MLPipeline()
        is_healthy = pipeline.is_healthy()
        
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
        # Import monitoring
        from api.modules.monitoring.resource_logger import ResourceLogger
        
        # Check if monitoring is available
        monitor = ResourceLogger()
        is_healthy = monitor.is_healthy()
        
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
        from api.modules.ml.ml_pipeline import MLPipeline
        pipeline = MLPipeline()
        return pipeline.get_queue_size()
    except:
        return 0
