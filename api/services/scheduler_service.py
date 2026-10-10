"""
Scheduler Service for News Intelligence System
Handles scheduled tasks including USD Purchasing Power Tracker updates.
"""

import logging
from datetime import datetime
from typing import Optional

try:
    from config.logging_config import get_component_logger
    logger = get_component_logger("scheduler")
except Exception:
    logger = logging.getLogger(__name__)

from api.services.usd_purchasing_power_tracker_service import update_usd_purchasing_power_tracker


class SchedulerService:
    """Service to handle scheduled tasks for the News Intelligence system."""
    
    def __init__(self):
        """Initialize the scheduler service."""
        self.logger = logger
    
    def run_usd_purchasing_power_tracker_update(self) -> bool:
        """
        Run the USD Purchasing Power Tracker update.
        
        Returns:
            bool: True if update successful, False otherwise
        """
        try:
            self.logger.info("Starting scheduled USD Purchasing Power Tracker update")
            success = update_usd_purchasing_power_tracker()
            if success:
                self.logger.info("USD Purchasing Power Tracker update completed successfully")
            else:
                self.logger.error("USD Purchasing Power Tracker update failed")
            return success
        except Exception as e:
            self.logger.error(f"Error running USD Purchasing Power Tracker update: {e}")
            return False
    
    def run_daily_maintenance_tasks(self) -> bool:
        """
        Run daily maintenance tasks.
        This can be expanded to include other daily tasks.
        
        Returns:
            bool: True if all tasks successful, False otherwise
        """
        self.logger.info("Starting daily maintenance tasks")
        
        success = True
        
        # Run USD Purchasing Power Tracker update
        if not self.run_usd_purchasing_power_tracker_update():
            success = False
        
        # Add other daily maintenance tasks here as needed
        
        if success:
            self.logger.info("Daily maintenance tasks completed successfully")
        else:
            self.logger.error("Some daily maintenance tasks failed")
        
        return success


# Global scheduler instance
scheduler_service = SchedulerService()


def run_usd_purchasing_power_tracker_update() -> bool:
    """
    Convenience function to run USD Purchasing Power Tracker update.
    
    Returns:
        bool: True if update successful, False otherwise
    """
    return scheduler_service.run_usd_purchasing_power_tracker_update()


def run_daily_maintenance_tasks() -> bool:
    """
    Convenience function to run daily maintenance tasks.
    
    Returns:
        bool: True if all tasks successful, False otherwise
    """
    return scheduler_service.run_daily_maintenance_tasks()


if __name__ == "__main__":
    # Allow running directly for testing
    success = run_daily_maintenance_tasks()
    exit(0 if success else 1)