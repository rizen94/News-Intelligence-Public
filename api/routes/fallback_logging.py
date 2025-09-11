"""
Fallback Logging Routes
Tracks when HTML fallback interfaces are used instead of React
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
import logging
import json

router = APIRouter(prefix="/api/fallback", tags=["Fallback Logging"])

# Set up logging for fallback events
fallback_logger = logging.getLogger("fallback_usage")
fallback_logger.setLevel(logging.WARNING)

# Create file handler for fallback logs
import os
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir, exist_ok=True)

try:
    file_handler = logging.FileHandler(os.path.join(log_dir, "fallback_usage.log"))
    file_handler.setLevel(logging.WARNING)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    
    # Add handler to logger
    fallback_logger.addHandler(file_handler)
except PermissionError:
    # Fall back to console logging if file logging fails
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    fallback_logger.addHandler(console_handler)

class FallbackEvent(BaseModel):
    timestamp: str
    user_agent: str
    url: str
    reason: str
    api_available: bool = False

@router.post("/log")
async def log_fallback_usage(event: FallbackEvent):
    """
    Log when HTML fallback interface is used
    """
    try:
        # Log to file
        fallback_logger.warning(
            f"FALLBACK USED - URL: {event.url}, "
            f"User Agent: {event.user_agent}, "
            f"Reason: {event.reason}, "
            f"API Available: {event.api_available}"
        )
        
        # Also log to console for immediate visibility
        print(f"🚨 FALLBACK USAGE DETECTED:")
        print(f"   Time: {event.timestamp}")
        print(f"   URL: {event.url}")
        print(f"   Reason: {event.reason}")
        print(f"   API Available: {event.api_available}")
        print(f"   User Agent: {event.user_agent[:100]}...")
        print("-" * 50)
        
        return {"success": True, "message": "Fallback usage logged"}
        
    except Exception as e:
        print(f"Error logging fallback usage: {e}")
        raise HTTPException(status_code=500, detail="Failed to log fallback usage")

@router.get("/stats")
async def get_fallback_stats():
    """
    Get statistics about fallback usage
    """
    try:
        # This would typically read from a database or log file
        # For now, return a simple response
        return {
            "success": True,
            "message": "Fallback stats endpoint ready",
            "note": "Check logs/fallback_usage.log for detailed usage"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to get fallback stats")
