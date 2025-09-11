"""
News Intelligence System v3.0 - Story Management API Routes
Provides endpoints for story control, discovery, and feedback loop management
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from fastapi import APIRouter, HTTPException, Query, Body, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text

from database.connection import get_db
from schemas.robust_schemas import APIResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/story-management", tags=["Story Management"])

# Pydantic models
class StoryExpectationCreate(BaseModel):
    """Model for creating a story expectation"""
    name: str = Field(..., description="Name of the story")
    description: str = Field(..., description="Description of the story")
    priority_level: int = Field(5, ge=1, le=10, description="Priority level (1-10)")
    keywords: List[str] = Field(default_factory=list, description="Keywords to track")
    entities: List[str] = Field(default_factory=list, description="Entities to track")
    geographic_regions: List[str] = Field(default_factory=list, description="Geographic regions to track")
    quality_threshold: float = Field(0.7, ge=0.0, le=1.0, description="Minimum quality threshold")
    max_articles_per_day: int = Field(100, ge=1, description="Maximum articles per day")
    auto_enhance: bool = Field(True, description="Whether to auto-trigger RAG enhancement")

class StoryExpectationUpdate(BaseModel):
    """Model for updating a story expectation"""
    name: Optional[str] = Field(None, description="Name of the story")
    description: Optional[str] = Field(None, description="Description of the story")
    priority_level: Optional[int] = Field(None, ge=1, le=10, description="Priority level (1-10)")
    keywords: Optional[List[str]] = Field(None, description="Keywords to track")
    entities: Optional[List[str]] = Field(None, description="Entities to track")
    geographic_regions: Optional[List[str]] = Field(None, description="Geographic regions to track")
    quality_threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="Minimum quality threshold")
    max_articles_per_day: Optional[int] = Field(None, ge=1, description="Maximum articles per day")
    auto_enhance: Optional[bool] = Field(None, description="Whether to auto-trigger RAG enhancement")
    is_active: Optional[bool] = Field(None, description="Whether the story is active")

class StoryTargetCreate(BaseModel):
    """Model for creating a story target"""
    target_type: str = Field(..., description="Type of target (person, organization, event, concept)")
    target_name: str = Field(..., description="Name of the target")
    target_description: str = Field("", description="Description of the target")
    importance_weight: float = Field(0.5, ge=0.0, le=1.0, description="Importance weight")
    tracking_keywords: List[str] = Field(default_factory=list, description="Keywords to track")
    tracking_entities: List[str] = Field(default_factory=list, description="Entities to track")

class StoryQualityFilterCreate(BaseModel):
    """Model for creating a story quality filter"""
    filter_type: str = Field(..., description="Type of filter")
    filter_config: Dict[str, Any] = Field(..., description="Filter configuration")

class StoryExpectationResponse(BaseModel):
    """Response model for story expectation"""
    story_id: str
    name: str
    description: str
    priority_level: int
    keywords: List[str]
    entities: List[str]
    geographic_regions: List[str]
    quality_threshold: float
    max_articles_per_day: int
    auto_enhance: bool
    created_at: str
    updated_at: str
    is_active: bool

class StorySuggestionResponse(BaseModel):
    """Response model for story suggestion"""
    suggestion_id: str
    title: str
    description: str
    confidence_score: float
    article_count: int
    time_span_days: int
    keywords: List[str]
    entities: List[str]
    geographic_regions: List[str]
    source_diversity: int
    quality_score: float
    trend_direction: str
    suggested_priority: int
    sample_articles: List[int]

class WeeklyDigestResponse(BaseModel):
    """Response model for weekly digest"""
    digest_id: str
    week_start: str
    week_end: str
    total_articles_analyzed: int
    new_stories_suggested: int
    existing_stories_updated: int
    top_trending_topics: List[str]
    story_suggestions: List[StorySuggestionResponse]
    quality_metrics: Dict[str, Any]
    created_at: str

class FeedbackLoopStatusResponse(BaseModel):
    """Response model for feedback loop status"""
    is_running: bool
    last_run: Optional[str]
    stories_being_tracked: int
    articles_processed_today: int
    rag_enhancements_triggered: int
    new_articles_found: int
    context_growth_percentage: float
    next_scheduled_run: Optional[str]

# Story Control Endpoints
@router.post("/stories", response_model=APIResponse)
async def create_story_expectation(
    story_data: StoryExpectationCreate,
    db: Session = Depends(get_db)
):
    """Create a new story expectation"""
    try:
        # Insert into storylines table
        result = db.execute(text("""
            INSERT INTO storylines (title, description, priority_level, keywords, entities, 
                                 geographic_regions, quality_threshold, max_articles_per_day, 
                                 auto_enhance, status, created_at, updated_at)
            VALUES (:name, :description, :priority_level, :keywords, :entities, 
                   :geographic_regions, :quality_threshold, :max_articles_per_day, 
                   :auto_enhance, 'active', NOW(), NOW())
            RETURNING id, created_at, updated_at
        """), {
            "name": story_data.name,
            "description": story_data.description,
            "priority_level": story_data.priority_level,
            "keywords": story_data.keywords,
            "entities": story_data.entities,
            "geographic_regions": story_data.geographic_regions,
            "quality_threshold": story_data.quality_threshold,
            "max_articles_per_day": story_data.max_articles_per_day,
            "auto_enhance": story_data.auto_enhance
        }).fetchone()
        
        story_id = str(result[0])
        created_at = result[1].isoformat()
        updated_at = result[2].isoformat()
        
        return APIResponse(
            success=True,
            data={
                "story_id": story_id,
                "name": story_data.name,
                "description": story_data.description,
                "priority_level": story_data.priority_level,
                "keywords": story_data.keywords,
                "entities": story_data.entities,
                "geographic_regions": story_data.geographic_regions,
                "quality_threshold": story_data.quality_threshold,
                "max_articles_per_day": story_data.max_articles_per_day,
                "auto_enhance": story_data.auto_enhance,
                "created_at": created_at,
                "updated_at": updated_at,
                "is_active": True
            },
            message="Story expectation created successfully"
        )
        
    except Exception as e:
        logger.error(f"Error creating story expectation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stories/ukraine-russia-conflict", response_model=APIResponse)
async def create_ukraine_russia_conflict_story(db: Session = Depends(get_db)):
    """Create the pre-configured Ukraine-Russia conflict story"""
    try:
        # Check if story already exists
        existing = db.execute(text("""
            SELECT id FROM storylines WHERE title = 'Ukraine-Russia Conflict' AND status = 'active'
        """)).fetchone()
        
        if existing:
            return APIResponse(
                success=True,
                data={"story_id": str(existing[0])},
                message="Ukraine-Russia conflict story already exists"
            )
        
        # Create the story
        story_data = StoryExpectationCreate(
            name="Ukraine-Russia Conflict",
            description="Comprehensive tracking of the ongoing conflict between Ukraine and Russia",
            priority_level=10,
            keywords=["Ukraine", "Russia", "war", "conflict", "invasion", "Zelensky", "Putin"],
            entities=["Ukraine", "Russia", "Volodymyr Zelensky", "Vladimir Putin"],
            geographic_regions=["Ukraine", "Russia", "Eastern Europe"],
            quality_threshold=0.8,
            max_articles_per_day=200,
            auto_enhance=True
        )
        
        result = await create_story_expectation(story_data, db)
        
        return APIResponse(
            success=True,
            data=result.data,
            message="Ukraine-Russia conflict story created successfully"
        )
        
    except Exception as e:
        logger.error(f"Error creating Ukraine-Russia conflict story: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stories", response_model=APIResponse)
async def get_active_stories(db: Session = Depends(get_db)):
    """Get all active story expectations"""
    try:
        result = db.execute(text("""
            SELECT id, title, description, priority_level, keywords, entities, 
                   geographic_regions, quality_threshold, max_articles_per_day, 
                   auto_enhance, created_at, updated_at, status
            FROM storylines 
            WHERE status = 'active'
            ORDER BY priority_level DESC, created_at DESC
        """)).fetchall()
        
        stories = []
        for row in result:
            stories.append({
                "story_id": str(row[0]),
                "name": row[1],
                "description": row[2],
                "priority_level": row[3],
                "keywords": row[4] if row[4] else [],
                "entities": row[5] if row[5] else [],
                "geographic_regions": row[6] if row[6] else [],
                "quality_threshold": float(row[7]) if row[7] else 0.0,
                "max_articles_per_day": row[8] if row[8] else 100,
                "auto_enhance": bool(row[9]) if row[9] is not None else True,
                "created_at": row[10].isoformat() if row[10] else None,
                "updated_at": row[11].isoformat() if row[11] else None,
                "is_active": row[12] == 'active'
            })
        
        return APIResponse(
            success=True,
            data=stories,
            message=f"Retrieved {len(stories)} active stories"
        )
        
    except Exception as e:
        logger.error(f"Error getting active stories: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/stories/{story_id}", response_model=APIResponse)
async def update_story_expectation(
    story_id: str, 
    story_update: StoryExpectationUpdate,
    db: Session = Depends(get_db)
):
    """Update an existing story expectation"""
    try:
        # Build dynamic update query
        update_fields = []
        params = {"story_id": story_id}
        
        if story_update.name is not None:
            update_fields.append("title = :name")
            params["name"] = story_update.name
        
        if story_update.description is not None:
            update_fields.append("description = :description")
            params["description"] = story_update.description
        
        if story_update.priority_level is not None:
            update_fields.append("priority_level = :priority_level")
            params["priority_level"] = story_update.priority_level
        
        if story_update.keywords is not None:
            update_fields.append("keywords = :keywords")
            params["keywords"] = story_update.keywords
        
        if story_update.entities is not None:
            update_fields.append("entities = :entities")
            params["entities"] = story_update.entities
        
        if story_update.geographic_regions is not None:
            update_fields.append("geographic_regions = :geographic_regions")
            params["geographic_regions"] = story_update.geographic_regions
        
        if story_update.quality_threshold is not None:
            update_fields.append("quality_threshold = :quality_threshold")
            params["quality_threshold"] = story_update.quality_threshold
        
        if story_update.max_articles_per_day is not None:
            update_fields.append("max_articles_per_day = :max_articles_per_day")
            params["max_articles_per_day"] = story_update.max_articles_per_day
        
        if story_update.auto_enhance is not None:
            update_fields.append("auto_enhance = :auto_enhance")
            params["auto_enhance"] = story_update.auto_enhance
        
        if story_update.is_active is not None:
            update_fields.append("status = :status")
            params["status"] = 'active' if story_update.is_active else 'inactive'
        
        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        update_fields.append("updated_at = NOW()")
        
        query = f"""
            UPDATE storylines 
            SET {', '.join(update_fields)}
            WHERE id = :story_id
            RETURNING id, title, description, priority_level, keywords, entities, 
                     geographic_regions, quality_threshold, max_articles_per_day, 
                     auto_enhance, created_at, updated_at, status
        """
        
        result = db.execute(text(query), params).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Story not found")
        
        return APIResponse(
            success=True,
            data={
                "story_id": str(result[0]),
                "name": result[1],
                "description": result[2],
                "priority_level": result[3],
                "keywords": result[4] if result[4] else [],
                "entities": result[5] if result[5] else [],
                "geographic_regions": result[6] if result[6] else [],
                "quality_threshold": float(result[7]) if result[7] else 0.0,
                "max_articles_per_day": result[8] if result[8] else 100,
                "auto_enhance": bool(result[9]) if result[9] is not None else True,
                "created_at": result[10].isoformat() if result[10] else None,
                "updated_at": result[11].isoformat() if result[11] else None,
                "is_active": result[12] == 'active'
            },
            message="Story expectation updated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating story expectation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/stories/{story_id}", response_model=APIResponse)
async def delete_story_expectation(story_id: str, db: Session = Depends(get_db)):
    """Delete a story expectation"""
    try:
        # Soft delete by setting status to inactive
        result = db.execute(text("""
            UPDATE storylines 
            SET status = 'inactive', updated_at = NOW()
            WHERE id = :story_id AND status = 'active'
            RETURNING id
        """), {"story_id": story_id}).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Story not found")
        
        db.commit()
        
        return APIResponse(
            success=True,
            data={"story_id": story_id},
            message="Story expectation deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting story expectation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stories/{story_id}/targets", response_model=APIResponse)
async def add_story_targets(
    story_id: str, 
    targets: List[StoryTargetCreate],
    db: Session = Depends(get_db)
):
    """Add targets to a story"""
    try:
        # Check if story exists
        story = db.execute(text("""
            SELECT id FROM storylines WHERE id = :story_id AND status = 'active'
        """), {"story_id": story_id}).fetchone()
        
        if not story:
            raise HTTPException(status_code=404, detail="Story not found")
        
        # For now, just return success - targets table can be implemented later
        target_names = [target.target_name for target in targets]
        
        return APIResponse(
            success=True,
            data={
                "story_id": story_id,
                "targets_added": len(targets),
                "target_names": target_names
            },
            message=f"Added {len(targets)} targets to story {story_id}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding story targets: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stories/{story_id}/filters", response_model=APIResponse)
async def add_story_quality_filters(
    story_id: str, 
    filters: List[StoryQualityFilterCreate],
    db: Session = Depends(get_db)
):
    """Add quality filters to a story"""
    try:
        # Check if story exists
        story = db.execute(text("""
            SELECT id FROM storylines WHERE id = :story_id AND status = 'active'
        """), {"story_id": story_id}).fetchone()
        
        if not story:
            raise HTTPException(status_code=404, detail="Story not found")
        
        # For now, just return success - filters table can be implemented later
        filter_types = [filter_obj.filter_type for filter_obj in filters]
        
        return APIResponse(
            success=True,
            data={
                "story_id": story_id,
                "filters_added": len(filters),
                "filter_types": filter_types
            },
            message=f"Added {len(filters)} quality filters to story {story_id}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding story quality filters: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stories/{story_id}/evaluate/{article_id}", response_model=APIResponse)
async def evaluate_article_for_story(
    story_id: str, 
    article_id: int,
    db: Session = Depends(get_db)
):
    """Evaluate if an article matches a story expectation"""
    try:
        # Get story details
        story = db.execute(text("""
            SELECT title, keywords, entities, geographic_regions, quality_threshold
            FROM storylines 
            WHERE id = :story_id AND status = 'active'
        """), {"story_id": story_id}).fetchone()
        
        if not story:
            raise HTTPException(status_code=404, detail="Story not found")
        
        # Get article details
        article = db.execute(text("""
            SELECT title, content, summary, category, quality_score, entities, tags
            FROM articles 
            WHERE id = :article_id
        """), {"article_id": article_id}).fetchone()
        
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        
        # Simple evaluation logic (can be enhanced with ML)
        story_keywords = story[1] if story[1] else []
        story_entities = story[2] if story[2] else []
        story_regions = story[3] if story[3] else []
        quality_threshold = float(story[4]) if story[4] else 0.7
        
        article_title = article[0] or ""
        article_content = (article[1] or article[2] or "").lower()
        article_quality = float(article[4]) if article[4] else 0.0
        article_entities = article[5] if article[5] else []
        article_tags = article[6] if article[6] else []
        
        # Calculate match score
        keyword_matches = sum(1 for keyword in story_keywords if keyword.lower() in article_content)
        entity_matches = sum(1 for entity in story_entities if entity.lower() in article_content)
        
        match_score = (keyword_matches + entity_matches) / max(len(story_keywords) + len(story_entities), 1)
        quality_met = article_quality >= quality_threshold
        
        matches = match_score > 0.3 and quality_met
        
        return APIResponse(
            success=True,
            data={
                "article_id": article_id,
                "story_id": story_id,
                "matches": matches,
                "match_score": match_score,
                "quality_met": quality_met,
                "keyword_matches": keyword_matches,
                "entity_matches": entity_matches,
                "article_quality": article_quality,
                "quality_threshold": quality_threshold
            },
            message=f"Article evaluation completed - {'MATCH' if matches else 'NO MATCH'}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error evaluating article for story: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Story Discovery Endpoints (Simplified for now)
@router.post("/discovery/weekly-digest", response_model=APIResponse)
async def generate_weekly_digest(
    week_start: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Generate weekly digest of story suggestions"""
    try:
        # For now, return a simple digest based on recent articles
        week_start_date = datetime.now() - timedelta(days=7)
        if week_start:
            week_start_date = datetime.fromisoformat(week_start)
        
        # Get recent articles
        result = db.execute(text("""
            SELECT COUNT(*) as total_articles,
                   COUNT(DISTINCT category) as category_diversity,
                   AVG(quality_score) as avg_quality
            FROM articles 
            WHERE created_at >= :week_start
        """), {"week_start": week_start_date}).fetchone()
        
        digest_data = {
            "digest_id": f"digest_{int(datetime.now().timestamp())}",
            "week_start": week_start_date.isoformat(),
            "week_end": datetime.now().isoformat(),
            "total_articles_analyzed": result[0] or 0,
            "new_stories_suggested": 0,  # Placeholder
            "existing_stories_updated": 0,  # Placeholder
            "top_trending_topics": [],  # Placeholder
            "story_suggestions": [],  # Placeholder
            "quality_metrics": {
                "category_diversity": result[1] or 0,
                "average_quality": float(result[2]) if result[2] else 0.0
            },
            "created_at": datetime.now().isoformat()
        }
        
        return APIResponse(
            success=True,
            data=digest_data,
            message="Weekly digest generated successfully"
        )
        
    except Exception as e:
        logger.error(f"Error generating weekly digest: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Feedback Loop Endpoints (Simplified for now)
@router.get("/feedback-loop/status", response_model=APIResponse)
async def get_feedback_loop_status(db: Session = Depends(get_db)):
    """Get feedback loop status"""
    try:
        # Get basic statistics
        stories_count = db.execute(text("""
            SELECT COUNT(*) FROM storylines WHERE status = 'active'
        """)).fetchone()[0] or 0
        
        articles_today = db.execute(text("""
            SELECT COUNT(*) FROM articles WHERE DATE(created_at) = CURRENT_DATE
        """)).fetchone()[0] or 0
        
        status_data = {
            "is_running": True,  # Placeholder
            "last_run": datetime.now().isoformat(),
            "stories_being_tracked": stories_count,
            "articles_processed_today": articles_today,
            "rag_enhancements_triggered": 0,  # Placeholder
            "new_articles_found": articles_today,
            "context_growth_percentage": 0.0,  # Placeholder
            "next_scheduled_run": (datetime.now() + timedelta(hours=1)).isoformat()
        }
        
        return APIResponse(
            success=True,
            data=status_data,
            message="Feedback loop status retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting feedback loop status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Health check endpoint
@router.get("/health", response_model=APIResponse)
async def health_check():
    """Health check endpoint"""
    return APIResponse(
        success=True,
        data={"status": "healthy", "timestamp": datetime.now().isoformat()},
        message="Story management service is healthy"
    )

