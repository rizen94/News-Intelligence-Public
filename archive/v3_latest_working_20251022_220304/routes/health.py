"""
News Intelligence System v3.0 - Production Health API
Robust health monitoring and system status endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from sqlalchemy.orm import Session
from schemas.robust_schemas import APIResponse, HealthCheck, HealthStatus
from services.health_service import HealthService
from config.database import get_db, check_database_health
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Health"])

@router.get("/", response_model=APIResponse)
async def get_system_health(db: Session = Depends(get_db)):
    """Get overall system health status"""
    try:
        service = HealthService(db)
        health = await service.get_system_health()
        return APIResponse(
            success=True,
            data=health,
            message="System health retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system health")

@router.get("/database", response_model=APIResponse)
async def get_database_health():
    """Get database health status using unified database manager"""
    try:
        health_status = check_database_health()
        return APIResponse(
            success=True,
            data=health_status,
            message="Database health retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error getting database health: {e}")
        return APIResponse(
            success=False,
            data={"status": "error", "error": str(e)},
            message="Failed to retrieve database health"
        )

@router.get("/ready", response_model=APIResponse)
async def get_readiness_status(db: Session = Depends(get_db)):
    """Get system readiness status"""
    try:
        service = HealthService(db)
        ready = await service.is_system_ready()
        return APIResponse(
            success=True,
            data={"ready": ready},
            message="Readiness status retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error getting readiness status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve readiness status")

@router.get("/live", response_model=APIResponse)
async def get_liveness_status(db: Session = Depends(get_db)):
    """Get system liveness status"""
    try:
        service = HealthService(db)
        live = await service.is_system_live()
        return APIResponse(
            success=True,
            data={"live": live},
            message="Liveness status retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error getting liveness status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve liveness status")
