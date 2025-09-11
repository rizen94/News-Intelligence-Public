"""
News Intelligence System v3.0 - Storylines API
Handles storyline management, article addition, and database operations
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional
from pydantic import BaseModel
import logging
from services.storyline_service import StorylineService
from config.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

# Pydantic models
class AddArticleRequest(BaseModel):
    article_id: str
    relevance_score: Optional[float] = None
    importance_score: Optional[float] = None

class CreateStorylineRequest(BaseModel):
    title: str
    description: Optional[str] = None

class StorylineResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# Initialize storyline service
storyline_service = StorylineService()

@router.get("/", response_model=StorylineResponse)
async def get_storylines():
    """Get all storylines"""
    try:
        result = await storyline_service.get_storylines()
        
        if "error" in result:
            return StorylineResponse(
                success=False,
                message="Failed to retrieve storylines",
                error=result["error"]
            )
        
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
        result = await storyline_service.create_storyline(
            title=request.title,
            description=request.description
        )
        
        if "error" in result:
            return StorylineResponse(
                success=False,
                message="Failed to create storyline",
                error=result["error"]
            )
        
        return StorylineResponse(
            success=True,
            message="Storyline created successfully",
            data={"storyline": result}
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
        result = await storyline_service.get_storyline_articles(storyline_id)
        
        if "error" in result:
            return StorylineResponse(
                success=False,
                message="Failed to retrieve storyline",
                error=result["error"]
            )
        
        return StorylineResponse(
            success=True,
            message="Storyline retrieved successfully",
            data=result
        )
        
    except Exception as e:
        logger.error(f"Error getting storyline {storyline_id}: {e}")
        return StorylineResponse(
            success=False,
            message="Failed to retrieve storyline",
            error=str(e)
        )

@router.post("/storyline/{storyline_id}/add-article/", response_model=StorylineResponse)
async def add_article_to_storyline(storyline_id: str, request: AddArticleRequest):
    """Add an article to a storyline"""
    try:
        result = await storyline_service.add_article_to_storyline(
            storyline_id=storyline_id,
            article_id=request.article_id,
            relevance_score=request.relevance_score,
            importance_score=request.importance_score
        )
        
        if "error" in result:
            return StorylineResponse(
                success=False,
                message="Failed to add article to storyline",
                error=result["error"]
            )
        
        return StorylineResponse(
            success=True,
            message="Article added to storyline successfully",
            data=result
        )
        
    except Exception as e:
        logger.error(f"Error adding article to storyline: {e}")
        return StorylineResponse(
            success=False,
            message="Failed to add article to storyline",
            error=str(e)
        )

@router.delete("/storyline/{storyline_id}/articles/{article_id}/", response_model=StorylineResponse)
async def remove_article_from_storyline(storyline_id: str, article_id: str):
    """Remove an article from a storyline"""
    try:
        result = await storyline_service.remove_article_from_storyline(
            storyline_id=storyline_id,
            article_id=article_id
        )
        
        if "error" in result:
            return StorylineResponse(
                success=False,
                message="Failed to remove article from storyline",
                error=result["error"]
            )
        
        return StorylineResponse(
            success=True,
            message="Article removed from storyline successfully",
            data=result
        )
        
    except Exception as e:
        logger.error(f"Error removing article from storyline: {e}")
        return StorylineResponse(
            success=False,
            message="Failed to remove article from storyline",
            error=str(e)
        )

@router.post("/storyline/{storyline_id}/generate-summary/", response_model=StorylineResponse)
async def generate_storyline_summary(storyline_id: str):
    """Generate AI-powered summary for a storyline"""
    try:
        result = await storyline_service.generate_storyline_summary(storyline_id)
        
        if "error" in result:
            return StorylineResponse(
                success=False,
                message="Failed to generate storyline summary",
                error=result["error"]
            )
        
        return StorylineResponse(
            success=True,
            message="Storyline summary generated successfully",
            data=result
        )
        
    except Exception as e:
        logger.error(f"Error generating storyline summary: {e}")
        return StorylineResponse(
            success=False,
            message="Failed to generate storyline summary",
            error=str(e)
        )

@router.get("/storyline/{storyline_id}/suggestions/", response_model=StorylineResponse)
async def get_storyline_suggestions(storyline_id: str):
    """Get suggested storylines for an article"""
    try:
        result = await storyline_service.get_storyline_suggestions(storyline_id)
        
        if "error" in result:
            return StorylineResponse(
                success=False,
                message="Failed to get storyline suggestions",
                error=result["error"]
            )
        
        return StorylineResponse(
            success=True,
            message="Storyline suggestions retrieved successfully",
            data=result
        )
        
    except Exception as e:
        logger.error(f"Error getting storyline suggestions: {e}")
        return StorylineResponse(
            success=False,
            message="Failed to get storyline suggestions",
            error=str(e)
        )

@router.delete("/storyline/{storyline_id}/", response_model=StorylineResponse)
async def delete_storyline(storyline_id: str):
    """Delete a storyline and all associated data"""
    try:
        result = await storyline_service.delete_storyline(storyline_id)
        
        if result.get('success'):
            return StorylineResponse(
                success=True,
                message="Storyline deleted successfully",
                data=result
            )
        else:
            return StorylineResponse(
                success=False,
                message="Failed to delete storyline",
                error=result.get('error', 'Unknown error')
            )
        
    except Exception as e:
        logger.error(f"Error deleting storyline: {e}")
        return StorylineResponse(
            success=False,
            message="Failed to delete storyline",
            error=str(e)
        )

@router.get("/health/")
async def health_check():
    """Health check for storylines API"""
    return {
        "status": "healthy",
        "service": "storylines",
        "message": "Storylines API is running"
    }

# Additional endpoints for frontend compatibility
@router.get("/storylines/", response_model=StorylineResponse)
async def get_storylines_alt():
    """Alternative endpoint for frontend compatibility - GET /storylines"""
    return await get_storylines()

@router.post("/storylines/", response_model=StorylineResponse)
async def create_storyline_alt(request: CreateStorylineRequest):
    """Alternative endpoint for frontend compatibility - POST /storylines"""
    return await create_storyline(request)
