"""
News Intelligence System v3.1.0 - Startup Automation Integration
Ensures automation starts with the application
"""

import asyncio
import logging
from services.automation_manager import get_automation_manager

logger = logging.getLogger(__name__)

async def start_automation_on_startup():
    """Start automation system on application startup"""
    try:
        automation_manager = get_automation_manager()
        await automation_manager.start()
        logger.info("Automation system started on application startup")
        return True
    except Exception as e:
        logger.error(f"Failed to start automation on startup: {e}")
        return False

async def stop_automation_on_shutdown():
    """Stop automation system on application shutdown"""
    try:
        automation_manager = get_automation_manager()
        await automation_manager.stop()
        logger.info("Automation system stopped on application shutdown")
        return True
    except Exception as e:
        logger.error(f"Failed to stop automation on shutdown: {e}")
        return False
