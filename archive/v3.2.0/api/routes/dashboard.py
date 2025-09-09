"""
Dashboard Routes for News Intelligence System v3.1.0
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from services.dashboard_service import DashboardService
from schemas.response_schemas import APIResponse
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/", response_model=APIResponse)
async def get_dashboard_data():
    """Get comprehensive dashboard data"""
    try:
        service = DashboardService()
        data = await service.get_dashboard_data()
        
        if "error" in data:
            raise HTTPException(status_code=500, detail=data["error"])
        
        return APIResponse(
            success=True,
            data=data,
            message="Dashboard data retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve dashboard data: {str(e)}")

@router.get("/stats", response_model=APIResponse)
async def get_dashboard_stats():
    """Get dashboard statistics"""
    try:
        service = DashboardService()
        data = await service.get_dashboard_data()
        
        if "error" in data:
            raise HTTPException(status_code=500, detail=data["error"])
        
        # Extract just the stats
        stats = {
            "article_stats": data.get("article_stats", {}),
            "rss_stats": data.get("rss_stats", {}),
            "system_health": data.get("system_health", {})
        }
        
        return APIResponse(
            success=True,
            data=stats,
            message="Dashboard stats retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve dashboard stats: {str(e)}")
