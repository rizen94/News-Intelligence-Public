"""
Enhanced Storylines API for News Intelligence System v3.3.0
Provides comprehensive storyline reports with ML processing
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional
from pydantic import BaseModel
import logging
from services.storyline_service import StorylineService
from services.enhanced_storyline_service import EnhancedStorylineService
from config.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/storylines", tags=["Enhanced Storylines"])

# Pydantic models
class StorylineReportResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class MLProcessingResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# Initialize storyline services
storyline_service = StorylineService()
enhanced_storyline_service = EnhancedStorylineService()

@router.get("/{storyline_id}/report", response_model=StorylineReportResponse)
async def get_storyline_report(storyline_id: int):
    """Get comprehensive storyline report with all data"""
    try:
        # Get storyline basic info
        storyline_result = await storyline_service.get_storyline_articles(storyline_id)
        
        if "error" in storyline_result:
            return StorylineReportResponse(
                success=False,
                message="Failed to retrieve storyline",
                error=storyline_result["error"]
            )
        
        # Get articles for this storyline
        articles_result = await storyline_service.get_storyline_articles(storyline_id)
        
        # Get timeline events from database
        events = await storyline_service.get_storyline_events(storyline_id)
        
        # Get source analysis from database
        sources = await storyline_service.get_storyline_sources(storyline_id)
        
        # Get edit log from database
        edit_log = await storyline_service.get_storyline_edit_log(storyline_id)
        
        return StorylineReportResponse(
            success=True,
            message="Storyline report retrieved successfully",
            data={
                "storyline": storyline_result.get("storyline", {}),
                "articles": storyline_result.get("articles", []),
                "events": events,
                "sources": sources,
                "edit_log": edit_log,
                "summary": {
                    "total_articles": len(storyline_result.get("articles", [])),
                    "total_events": len(events),
                    "total_sources": len(sources),
                    "ml_processed": storyline_result.get("storyline", {}).get("ml_processed", False)
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting storyline report: {e}")
        return StorylineReportResponse(
            success=False,
            message="Failed to retrieve storyline report",
            error=str(e)
        )

@router.post("/{storyline_id}/process-ml", response_model=MLProcessingResponse)
async def process_storyline_ml(storyline_id: int):
    """Process storyline with ML to generate summary and timeline"""
    try:
        # Use enhanced storyline service for ML processing
        result = await enhanced_storyline_service.process_storyline_ml(storyline_id)
        
        if "error" in result:
            return MLProcessingResponse(
                success=False,
                message="Failed to process storyline with ML",
                error=result["error"]
            )
        
        return MLProcessingResponse(
            success=True,
            message="ML processing completed",
            data=result.get("data", {})
        )
        
    except Exception as e:
        logger.error(f"Error processing storyline ML: {e}")
        return MLProcessingResponse(
            success=False,
            message="Failed to process storyline with ML",
            error=str(e)
        )

@router.get("/{storyline_id}/timeline", response_model=StorylineReportResponse)
async def get_storyline_timeline(storyline_id: int):
    """Get timeline events for storyline"""
    try:
        # TODO: Implement actual timeline extraction
        # For now, return mock data
        
        events = [
            {
                "id": 1,
                "event_title": "Initial Report",
                "event_description": "First reports of the incident emerge",
                "event_date": "2024-01-15T10:00:00Z",
                "event_source": "CNN",
                "event_type": "announcement",
                "confidence_score": 0.95,
                "sentiment_score": -0.3
            },
            {
                "id": 2,
                "event_title": "Official Response",
                "event_description": "Authorities provide official statement",
                "event_date": "2024-01-15T14:30:00Z",
                "event_source": "Reuters",
                "event_type": "response",
                "confidence_score": 0.98,
                "sentiment_score": 0.1
            }
        ]
        
        return StorylineReportResponse(
            success=True,
            message="Timeline retrieved successfully",
            data={"events": events}
        )
        
    except Exception as e:
        logger.error(f"Error getting storyline timeline: {e}")
        return StorylineReportResponse(
            success=False,
            message="Failed to retrieve timeline",
            error=str(e)
        )
