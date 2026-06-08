"""
Database health check utilities for the News Intelligence system.

This module provides functions to check database health and manage
the automation phases of the system.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from .connection import check_database_health, probe_database_server_reachable
from .db_availability import is_automation_db_ready

logger = logging.getLogger(__name__)

def check_system_health() -> Dict[str, Any]:
    """
    Check overall system health including database and other components.
    
    Returns:
        Dict containing system health status information
    """
    try:
        # Check database health
        db_health = check_database_health()
        
        # Check if database is ready for automation
        automation_ready = is_automation_db_ready()
        
        # Check if database server is reachable
        server_reachable = probe_database_server_reachable()
        
        return {
            "success": True,
            "database": db_health,
            "automation_ready": automation_ready,
            "server_reachable": server_reachable,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"System health check failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

def check_automation_phase_health(phase_name: str) -> Dict[str, Any]:
    """
    Check health for a specific automation phase.
    
    Args:
        phase_name (str): Name of the automation phase to check
        
    Returns:
        Dict containing phase health status information
    """
    try:
        # Check database health
        db_health = check_database_health()
        
        # Check if database is ready for automation
        automation_ready = is_automation_db_ready()
        
        # Check if database server is reachable
        server_reachable = probe_database_server_reachable()
        
        return {
            "success": True,
            "phase": phase_name,
            "database": db_health,
            "automation_ready": automation_ready,
            "server_reachable": server_reachable,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Automation phase health check failed for {phase_name}: {e}")
        return {
            "success": False,
            "phase": phase_name,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

def is_database_healthy() -> bool:
    """
    Simple check if database is healthy.
    
    Returns:
        bool: True if database is healthy, False otherwise
    """
    try:
        health = check_database_health()
        return health.get("success", False)
    except Exception:
        return False

def wait_for_database_ready(timeout_seconds: int = 60, check_interval: int = 5) -> bool:
    """
    Wait for database to become ready for automation.
    
    Args:
        timeout_seconds (int): Maximum time to wait in seconds
        check_interval (int): Time between checks in seconds
        
    Returns:
        bool: True if database became ready within timeout, False otherwise
    """
    start_time = time.time()
    
    while time.time() - start_time < timeout_seconds:
        try:
            if is_automation_db_ready():
                logger.info("Database is ready for automation")
                return True
        except Exception as e:
            logger.warning(f"Database readiness check failed: {e}")
        
        logger.info(f"Database not ready yet, waiting {check_interval} seconds...")
        time.sleep(check_interval)
    
    logger.warning("Database did not become ready within timeout")
    return False