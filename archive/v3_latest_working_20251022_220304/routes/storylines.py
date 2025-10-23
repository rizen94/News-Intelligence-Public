"""
Storylines API Routes - Clean Version
Manages storylines and their associated articles
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from sqlalchemy.orm import Session
from schemas.robust_schemas import StorylineResponse, CreateStorylineRequest, AddArticleRequest
from services.storyline_service import StorylineService
from config.database import get_db
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/storylines", tags=["Storylines"])

@router.get("/", response_model=StorylineResponse)
async def get_storylines(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Get all storylines with pagination"""
    try:
        service = StorylineService(db)
        result = await service.get_storylines(limit=limit, offset=offset)
        
        return StorylineResponse(
            success=True,
            message=f"Retrieved {len(result['storylines'])} storylines",
            data=result
        )
    except Exception as e:
        logger.error(f"Error getting storylines: {e}")
        return StorylineResponse(
            success=False,
            message="Failed to retrieve storylines",
            error=str(e)
        )

@router.post("/", response_model=StorylineResponse)
async def create_storyline(request: CreateStorylineRequest):
    """Create a new storyline"""
    try:
        # This is a placeholder - would need proper implementation
        return StorylineResponse(
            success=True,
            message="Storyline created successfully",
            data={"id": "placeholder", "title": request.title}
        )
    except Exception as e:
        logger.error(f"Error creating storyline: {e}")
        return StorylineResponse(
            success=False,
            message="Failed to create storyline",
            error=str(e)
        )

@router.get("/storyline/{storyline_id}/", response_model=StorylineResponse)
async def get_storyline(storyline_id: str):
    """Get a specific storyline with its articles"""
    try:
        # This is a placeholder - would need proper implementation
        return StorylineResponse(
            success=True,
            message="Storyline retrieved successfully",
            data={"id": storyline_id, "title": "Sample Storyline"}
        )
    except Exception as e:
        logger.error(f"Error getting storyline {storyline_id}: {e}")
        return StorylineResponse(
            success=False,
            message="Failed to retrieve storyline",
            error=str(e)
        )
