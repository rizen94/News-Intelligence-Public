#!/usr/bin/env python3
"""
Route Supervisor API Routes
Provides endpoints for route supervisor monitoring and reports
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Optional
from datetime import datetime
import logging

from shared.services.route_supervisor import (
    get_route_supervisor,
    RouteSupervisorReport
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v4/system_monitoring/route_supervisor",
    tags=["Route Supervisor"],
    responses={404: {"description": "Not found"}}
)


@router.get("/health")
async def get_route_supervisor_health():
    """Get route supervisor health summary"""
    try:
        supervisor = get_route_supervisor()
        
        route_summary = supervisor.get_route_health_summary()
        db_summary = supervisor.get_database_health_summary()
        
        frontend_summary = None
        if supervisor.frontend_health:
            frontend_summary = {
                "url": supervisor.frontend_health.url,
                "status": supervisor.frontend_health.status.value,
                "response_time_ms": supervisor.frontend_health.response_time_ms,
                "api_connection": supervisor.frontend_health.api_connection,
                "last_check": supervisor.frontend_health.last_check.isoformat()
            }
        
        return {
            "success": True,
            "route_health": route_summary,
            "database_health": db_summary,
            "frontend_health": frontend_summary,
            "is_monitoring": supervisor.is_running,
            "last_check": supervisor.last_full_check.isoformat() if supervisor.last_full_check else None
        }
    except Exception as e:
        logger.error(f"Error getting route supervisor health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report")
async def get_route_supervisor_report():
    """Get comprehensive route supervisor report"""
    try:
        supervisor = get_route_supervisor()
        report = await supervisor.generate_report()
        
        return {
            "success": True,
            "timestamp": report.timestamp.isoformat(),
            "summary": {
                "total_routes": report.total_routes,
                "healthy_routes": report.healthy_routes,
                "degraded_routes": report.degraded_routes,
                "unhealthy_routes": report.unhealthy_routes
            },
            "database_connections": [
                {
                    "domain": db.domain,
                    "schema": db.schema,
                    "status": db.status.value,
                    "response_time_ms": db.response_time_ms,
                    "error": db.error_message,
                    "last_check": db.last_check.isoformat()
                }
                for db in report.database_connections
            ],
            "frontend_health": {
                "url": report.frontend_health.url if report.frontend_health else None,
                "status": report.frontend_health.status.value if report.frontend_health else "unknown",
                "response_time_ms": report.frontend_health.response_time_ms if report.frontend_health else None,
                "error": report.frontend_health.error_message if report.frontend_health else None,
                "api_connection": report.frontend_health.api_connection if report.frontend_health else False,
                "consecutive_failures": report.frontend_health.consecutive_failures if report.frontend_health else 0,
                "last_check": report.frontend_health.last_check.isoformat() if report.frontend_health else None
            } if report.frontend_health else None,
            "route_health": [
                {
                    "route": route.route_path,
                    "method": route.method,
                    "status": route.status.value,
                    "response_time_ms": route.response_time_ms,
                    "error": route.error_message,
                    "database_connected": route.database_connected,
                    "schema_valid": route.schema_valid,
                    "consecutive_failures": route.consecutive_failures,
                    "last_check": route.last_check.isoformat()
                }
                for route in report.route_health
            ],
            "issues": report.issues,
            "warnings": report.warnings
        }
    except Exception as e:
        logger.error(f"Error generating route supervisor report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/issues")
async def get_recent_issues(hours: int = 24, limit: int = 100):
    """Get recent issues from route supervisor log"""
    try:
        supervisor = get_route_supervisor()
        issues = supervisor.get_recent_issues(hours=hours)
        
        return {
            "success": True,
            "count": len(issues),
            "hours": hours,
            "issues": issues[:limit]
        }
    except Exception as e:
        logger.error(f"Error getting recent issues: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check_now")
async def trigger_immediate_check(background_tasks: BackgroundTasks):
    """Trigger an immediate route supervisor check"""
    try:
        supervisor = get_route_supervisor()
        
        # Run check in background
        background_tasks.add_task(supervisor.generate_report)
        
        return {
            "success": True,
            "message": "Route supervisor check triggered",
            "is_monitoring": supervisor.is_running
        }
    except Exception as e:
        logger.error(f"Error triggering route supervisor check: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/routes/{route_path:path}")
async def get_route_health(route_path: str, method: str = "GET", domain: Optional[str] = None):
    """Get health status for a specific route"""
    try:
        supervisor = get_route_supervisor()
        
        # Ensure route_path starts with /
        if not route_path.startswith('/'):
            route_path = '/' + route_path
        
        health = await supervisor.check_route_health(route_path, method, domain)
        
        return {
            "success": True,
            "route": {
                "path": health.route_path,
                "method": health.method,
                "status": health.status.value,
                "response_time_ms": health.response_time_ms,
                "error": health.error_message,
                "database_connected": health.database_connected,
                "schema_valid": health.schema_valid,
                "consecutive_failures": health.consecutive_failures,
                "last_check": health.last_check.isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Error checking route health: {e}")
        raise HTTPException(status_code=500, detail=str(e))

