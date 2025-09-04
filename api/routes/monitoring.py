"""
Monitoring API Routes for News Intelligence System v3.0
Provides system monitoring and metrics
"""

from datetime import datetime
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from middleware.metrics import MetricsMiddleware

router = APIRouter()

# Pydantic models
class SystemMetrics(BaseModel):
    """System metrics model"""
    cpu_percent: float = Field(..., description="CPU usage percentage")
    memory_percent: float = Field(..., description="Memory usage percentage")
    disk_percent: float = Field(..., description="Disk usage percentage")
    active_connections: int = Field(..., description="Active connections")

@router.get("/metrics")
async def get_prometheus_metrics():
    """Get Prometheus metrics"""
    metrics = MetricsMiddleware.get_metrics()
    return Response(content=metrics, media_type="text/plain")

@router.get("/system", response_model=SystemMetrics)
async def get_system_metrics():
    """Get system metrics"""
    import psutil
    
    return SystemMetrics(
        cpu_percent=psutil.cpu_percent(),
        memory_percent=psutil.virtual_memory().percent,
        disk_percent=psutil.disk_usage('/').percent,
        active_connections=0
    )

@router.get("/health")
async def get_monitoring_health():
    """Get monitoring system health"""
    return {"status": "healthy", "timestamp": datetime.utcnow()}
