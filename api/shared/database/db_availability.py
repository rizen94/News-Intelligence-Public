"""
Database availability utilities for the News Intelligence system.

This module provides functions to check database availability and readiness
for automation phases.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from .connection import get_db_connection, get_health_db_connection, check_database_health

logger = logging.getLogger(__name__)

def is_database_ready() -> bool:
    """
    Check if database is ready for general use.
    
    Returns:
        bool: True if database is ready, False otherwise
    """
    try:
        # Quick health check
        health = check_database_health()
        if not health.get("success", False):
            return False
            
        # Try to get a connection
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
                
        return True
    except Exception as e:
        logger.warning(f"Database readiness check failed: {e}")
        return False

def is_automation_db_ready() -> bool:
    """
    Check if database is ready for automation phases.
    
    Returns:
        bool: True if database is ready for automation, False otherwise
    """
    try:
        # Check database health first
        health = check_database_health()
        if not health.get("success", False):
            return False
            
        # Try to get a connection from the health pool (reserved for automation)
        with get_health_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
                
        return True
    except Exception as e:
        logger.warning(f"Automation database readiness check failed: {e}")
        return False

def schema_has_table(schema_name: str, table_name: str = "articles") -> bool:
    """Return True when ``{schema_name}.{table_name}`` exists (pipeline safety guard)."""
    if not schema_name or not table_name:
        return False
    if not schema_name.replace("_", "").isalnum() or not schema_name.islower():
        return False
    if not table_name.replace("_", "").isalnum() or not table_name.islower():
        return False
    try:
        from .connection import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = %s AND table_name = %s
                    LIMIT 1
                    """,
                    (schema_name, table_name),
                )
                return cur.fetchone() is not None
    except Exception as e:
        logger.debug("schema_has_table(%s.%s): %s", schema_name, table_name, e)
        return False


def is_database_available() -> bool:
    """
    Check if database is available (connection can be established).
    
    Returns:
        bool: True if database is available, False otherwise
    """
    try:
        # Try to get a connection
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
                
        return True
    except Exception as e:
        logger.warning(f"Database availability check failed: {e}")
        return False

def wait_for_database_availability(timeout_seconds: int = 60, check_interval: int = 2) -> bool:
    """
    Wait for database to become available.
    
    Args:
        timeout_seconds (int): Maximum time to wait in seconds
        check_interval (int): Time between checks in seconds
        
    Returns:
        bool: True if database became available within timeout, False otherwise
    """
    start_time = time.time()
    
    while time.time() - start_time < timeout_seconds:
        try:
            if is_database_available():
                logger.info("Database is available")
                return True
        except Exception as e:
            logger.warning(f"Database availability check failed: {e}")
        
        logger.info(f"Database not available yet, waiting {check_interval} seconds...")
        time.sleep(check_interval)
    
    logger.warning("Database did not become available within timeout")
    return False

def get_database_status() -> Dict[str, Any]:
    """
    Get comprehensive database status information.
    
    Returns:
        Dict containing database status information
    """
    try:
        # Check basic database health
        health = check_database_health()
        
        # Check if database is ready for automation
        automation_ready = is_automation_db_ready()
        
        # Check if database is available
        available = is_database_available()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "health": health,
            "automation_ready": automation_ready,
            "available": available,
            "status": "healthy" if health.get("success", False) else "unhealthy"
        }
    except Exception as e:
        logger.error(f"Failed to get database status: {e}")
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "health": {"success": False, "error": str(e)},
            "automation_ready": False,
            "available": False,
            "status": "error"
        }