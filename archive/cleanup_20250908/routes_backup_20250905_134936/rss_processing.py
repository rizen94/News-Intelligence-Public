"""
News Intelligence System v3.1.0 - RSS Processing API
Real-time RSS feed processing endpoints
"""

import logging
from fastapi import APIRouter, HTTPException
from services.rss_processing_service import get_rss_processor
from schemas.response_schemas import APIResponse

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/process", response_model=APIResponse)
async def process_rss_feeds():
    """Process all RSS feeds and fetch new articles"""
    try:
        rss_processor = get_rss_processor()
        await rss_processor.process_all_feeds()
        
        return APIResponse(
            success=True,
            data=None,
            message="RSS feeds processed successfully"
        )
        
    except Exception as e:
        logger.error(f"Error processing RSS feeds: {e}")
        return APIResponse(
            success=False,
            data=None,
            message=f"Failed to process RSS feeds: {str(e)}"
        )

@router.get("/status", response_model=APIResponse)
async def get_rss_processing_status():
    """Get RSS processing status"""
    try:
        rss_processor = get_rss_processor()
        
        return APIResponse(
            success=True,
            data={
                "is_running": rss_processor.is_running,
                "processing_interval": rss_processor.processing_interval,
                "next_processing": "Every 5 minutes" if rss_processor.is_running else "Not running"
            },
            message="RSS processing status retrieved"
        )
        
    except Exception as e:
        logger.error(f"Error getting RSS processing status: {e}")
        return APIResponse(
            success=False,
            data=None,
            message=f"Failed to get RSS processing status: {str(e)}"
        )
