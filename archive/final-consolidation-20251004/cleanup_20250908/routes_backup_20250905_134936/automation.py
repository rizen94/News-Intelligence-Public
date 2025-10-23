"""
News Intelligence System v3.1.0 - Automation API
Enterprise-grade automation management endpoints
"""

import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks
from services.automation_manager import get_automation_manager
from schemas.response_schemas import APIResponse
from typing import Dict, Any

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/status", response_model=APIResponse)
async def get_automation_status():
    """Get automation system status"""
    try:
        automation_manager = get_automation_manager()
        status = automation_manager.get_status()
        
        return APIResponse(
            success=True,
            data=status,
            message="Automation status retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting automation status: {e}")
        return APIResponse(
            success=False,
            data=None,
            message=f"Failed to get automation status: {str(e)}"
        )

@router.get("/metrics", response_model=APIResponse)
async def get_automation_metrics():
    """Get detailed automation metrics"""
    try:
        automation_manager = get_automation_manager()
        metrics = automation_manager.get_metrics()
        
        return APIResponse(
            success=True,
            data=metrics,
            message="Automation metrics retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting automation metrics: {e}")
        return APIResponse(
            success=False,
            data=None,
            message=f"Failed to get automation metrics: {str(e)}"
        )

@router.post("/start", response_model=APIResponse)
async def start_automation():
    """Start automation system"""
    try:
        automation_manager = get_automation_manager()
        
        if automation_manager.is_running:
            return APIResponse(
                success=True,
                data=None,
                message="Automation system is already running"
            )
        
        await automation_manager.start()
        
        return APIResponse(
            success=True,
            data=None,
            message="Automation system started successfully"
        )
        
    except Exception as e:
        logger.error(f"Error starting automation: {e}")
        return APIResponse(
            success=False,
            data=None,
            message=f"Failed to start automation: {str(e)}"
        )

@router.post("/stop", response_model=APIResponse)
async def stop_automation():
    """Stop automation system"""
    try:
        automation_manager = get_automation_manager()
        
        if not automation_manager.is_running:
            return APIResponse(
                success=True,
                data=None,
                message="Automation system is already stopped"
            )
        
        await automation_manager.stop()
        
        return APIResponse(
            success=True,
            data=None,
            message="Automation system stopped successfully"
        )
        
    except Exception as e:
        logger.error(f"Error stopping automation: {e}")
        return APIResponse(
            success=False,
            data=None,
            message=f"Failed to stop automation: {str(e)}"
        )

@router.post("/restart", response_model=APIResponse)
async def restart_automation():
    """Restart automation system"""
    try:
        automation_manager = get_automation_manager()
        
        if automation_manager.is_running:
            await automation_manager.stop()
            await asyncio.sleep(2)  # Wait for graceful shutdown
        
        await automation_manager.start()
        
        return APIResponse(
            success=True,
            data=None,
            message="Automation system restarted successfully"
        )
        
    except Exception as e:
        logger.error(f"Error restarting automation: {e}")
        return APIResponse(
            success=False,
            data=None,
            message=f"Failed to restart automation: {str(e)}"
        )

@router.get("/health", response_model=APIResponse)
async def get_automation_health():
    """Get automation system health"""
    try:
        automation_manager = get_automation_manager()
        status = automation_manager.get_status()
        
        # Determine health status
        health_status = "healthy"
        issues = []
        
        if not status['is_running']:
            health_status = "unhealthy"
            issues.append("Automation system not running")
        
        if status['active_workers'] < 3:
            health_status = "degraded"
            issues.append(f"Low worker count: {status['active_workers']}")
        
        if status['queue_size'] > 50:
            health_status = "degraded"
            issues.append(f"High queue size: {status['queue_size']}")
        
        health_data = {
            'status': health_status,
            'issues': issues,
            'details': status
        }
        
        return APIResponse(
            success=True,
            data=health_data,
            message=f"Automation health: {health_status}"
        )
        
    except Exception as e:
        logger.error(f"Error getting automation health: {e}")
        return APIResponse(
            success=False,
            data=None,
            message=f"Failed to get automation health: {str(e)}"
        )
