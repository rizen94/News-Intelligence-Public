#!/usr/bin/env python3
"""
Story Management API Routes for News Intelligence System v3.0
Provides endpoints for story control, discovery, and feedback loop management
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from config.database import get_db_connection
from modules.intelligence.story_control_system import StoryControlSystem, StoryExpectation
from modules.intelligence.story_discovery_system import StoryDiscoverySystem, WeeklyDigest
from modules.intelligence.feedback_loop_system import FeedbackLoopSystem, FeedbackLoopStatus

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize systems
db_config = {
    'host': os.getenv('DB_HOST', 'postgres'),
    'database': os.getenv('DB_NAME', 'news_system'),
    'user': os.getenv('DB_USER', 'newsapp'),
    'password': os.getenv('DB_PASSWORD', ''),
    'port': os.getenv('DB_PORT', '5432')
}

story_control = StoryControlSystem(db_config)
story_discovery = StoryDiscoverySystem(db_config)
feedback_loop = FeedbackLoopSystem(db_config)

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
@router.post("/stories", response_model=StoryExpectationResponse)
async def create_story_expectation(story_data: StoryExpectationCreate):
    """Create a new story expectation"""
    try:
        story_dict = story_data.dict()
        story = story_control.create_story_expectation(story_dict)
        
        return StoryExpectationResponse(
            story_id=story.story_id,
            name=story.name,
            description=story.description,
            priority_level=story.priority_level,
            keywords=story.keywords,
            entities=story.entities,
            geographic_regions=story.geographic_regions,
            quality_threshold=story.quality_threshold,
            max_articles_per_day=story.max_articles_per_day,
            auto_enhance=story.auto_enhance,
            created_at=story.created_at,
            updated_at=story.updated_at,
            is_active=story.is_active
        )
    except Exception as e:
        logger.error(f"Error creating story expectation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stories/ukraine-russia-conflict")
async def create_ukraine_russia_conflict_story():
    """Create the pre-configured Ukraine-Russia conflict story"""
    try:
        story = story_control.create_ukraine_russia_conflict_story()
        
        # Add targets
        targets = story_control.add_ukraine_russia_targets(story.story_id)
        
        # Add quality filters
        filters = story_control.add_ukraine_russia_quality_filters(story.story_id)
        
        return {
            "message": "Ukraine-Russia conflict story created successfully",
            "story_id": story.story_id,
            "targets_added": len(targets),
            "filters_added": len(filters)
        }
    except Exception as e:
        logger.error(f"Error creating Ukraine-Russia conflict story: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stories", response_model=List[StoryExpectationResponse])
async def get_active_stories():
    """Get all active story expectations"""
    try:
        stories = story_control.get_active_stories()
        
        return [
            StoryExpectationResponse(
                story_id=story.story_id,
                name=story.name,
                description=story.description,
                priority_level=story.priority_level,
                keywords=story.keywords,
                entities=story.entities,
                geographic_regions=story.geographic_regions,
                quality_threshold=story.quality_threshold,
                max_articles_per_day=story.max_articles_per_day,
                auto_enhance=story.auto_enhance,
                created_at=story.created_at,
                updated_at=story.updated_at,
                is_active=story.is_active
            )
            for story in stories
        ]
    except Exception as e:
        logger.error(f"Error getting active stories: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stories/{story_id}/targets")
async def add_story_targets(story_id: str, targets: List[StoryTargetCreate]):
    """Add targets to a story"""
    try:
        targets_data = [target.dict() for target in targets]
        added_targets = story_control.add_story_targets(story_id, targets_data)
        
        return {
            "message": f"Added {len(added_targets)} targets to story {story_id}",
            "targets": [target.target_name for target in added_targets]
        }
    except Exception as e:
        logger.error(f"Error adding story targets: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stories/{story_id}/filters")
async def add_story_quality_filters(story_id: str, filters: List[StoryQualityFilterCreate]):
    """Add quality filters to a story"""
    try:
        filters_data = [filter_obj.dict() for filter_obj in filters]
        added_filters = story_control.add_quality_filters(story_id, filters_data)
        
        return {
            "message": f"Added {len(added_filters)} quality filters to story {story_id}",
            "filters": [filter_obj.filter_type for filter_obj in added_filters]
        }
    except Exception as e:
        logger.error(f"Error adding story quality filters: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stories/{story_id}/evaluate/{article_id}")
async def evaluate_article_for_story(story_id: str, article_id: int):
    """Evaluate if an article matches a story expectation"""
    try:
        result = story_control.evaluate_article_for_story(article_id, story_id)
        return result
    except Exception as e:
        logger.error(f"Error evaluating article for story: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Story Discovery Endpoints
@router.post("/discovery/weekly-digest")
async def generate_weekly_digest(week_start: Optional[str] = None):
    """Generate weekly digest of story suggestions"""
    try:
        week_start_date = None
        if week_start:
            week_start_date = datetime.fromisoformat(week_start)
        
        digest = story_discovery.generate_weekly_digest(week_start_date)
        
        return WeeklyDigestResponse(
            digest_id=digest.digest_id,
            week_start=digest.week_start,
            week_end=digest.week_end,
            total_articles_analyzed=digest.total_articles_analyzed,
            new_stories_suggested=digest.new_stories_suggested,
            existing_stories_updated=digest.existing_stories_updated,
            top_trending_topics=digest.top_trending_topics,
            story_suggestions=[
                StorySuggestionResponse(
                    suggestion_id=suggestion.suggestion_id,
                    title=suggestion.title,
                    description=suggestion.description,
                    confidence_score=suggestion.confidence_score,
                    article_count=suggestion.article_count,
                    time_span_days=suggestion.time_span_days,
                    keywords=suggestion.keywords,
                    entities=suggestion.entities,
                    geographic_regions=suggestion.geographic_regions,
                    source_diversity=suggestion.source_diversity,
                    quality_score=suggestion.quality_score,
                    trend_direction=suggestion.trend_direction,
                    suggested_priority=suggestion.suggested_priority,
                    sample_articles=suggestion.sample_articles
                )
                for suggestion in digest.story_suggestions
            ],
            quality_metrics=digest.quality_metrics,
            created_at=digest.created_at
        )
    except Exception as e:
        logger.error(f"Error generating weekly digest: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/discovery/weekly-digests", response_model=List[WeeklyDigestResponse])
async def get_recent_digests(limit: int = Query(5, ge=1, le=20)):
    """Get recent weekly digests"""
    try:
        digests = story_discovery.get_recent_digests(limit)
        
        return [
            WeeklyDigestResponse(
                digest_id=digest.digest_id,
                week_start=digest.week_start,
                week_end=digest.week_end,
                total_articles_analyzed=digest.total_articles_analyzed,
                new_stories_suggested=digest.new_stories_suggested,
                existing_stories_updated=digest.existing_stories_updated,
                top_trending_topics=digest.top_trending_topics,
                story_suggestions=[
                    StorySuggestionResponse(
                        suggestion_id=suggestion.suggestion_id,
                        title=suggestion.title,
                        description=suggestion.description,
                        confidence_score=suggestion.confidence_score,
                        article_count=suggestion.article_count,
                        time_span_days=suggestion.time_span_days,
                        keywords=suggestion.keywords,
                        entities=suggestion.entities,
                        geographic_regions=suggestion.geographic_regions,
                        source_diversity=suggestion.source_diversity,
                        quality_score=suggestion.quality_score,
                        trend_direction=suggestion.trend_direction,
                        suggested_priority=suggestion.suggested_priority,
                        sample_articles=suggestion.sample_articles
                    )
                    for suggestion in digest.story_suggestions
                ],
                quality_metrics=digest.quality_metrics,
                created_at=digest.created_at
            )
            for digest in digests
        ]
    except Exception as e:
        logger.error(f"Error getting recent digests: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/discovery/weekly-digests/{digest_id}", response_model=WeeklyDigestResponse)
async def get_weekly_digest(digest_id: str):
    """Get a specific weekly digest"""
    try:
        digest = story_discovery.get_weekly_digest(digest_id)
        
        if not digest:
            raise HTTPException(status_code=404, detail="Digest not found")
        
        return WeeklyDigestResponse(
            digest_id=digest.digest_id,
            week_start=digest.week_start,
            week_end=digest.week_end,
            total_articles_analyzed=digest.total_articles_analyzed,
            new_stories_suggested=digest.new_stories_suggested,
            existing_stories_updated=digest.existing_stories_updated,
            top_trending_topics=digest.top_trending_topics,
            story_suggestions=[
                StorySuggestionResponse(
                    suggestion_id=suggestion.suggestion_id,
                    title=suggestion.title,
                    description=suggestion.description,
                    confidence_score=suggestion.confidence_score,
                    article_count=suggestion.article_count,
                    time_span_days=suggestion.time_span_days,
                    keywords=suggestion.keywords,
                    entities=suggestion.entities,
                    geographic_regions=suggestion.geographic_regions,
                    source_diversity=suggestion.source_diversity,
                    quality_score=suggestion.quality_score,
                    trend_direction=suggestion.trend_direction,
                    suggested_priority=suggestion.suggested_priority,
                    sample_articles=suggestion.sample_articles
                )
                for suggestion in digest.story_suggestions
            ],
            quality_metrics=digest.quality_metrics,
            created_at=digest.created_at
        )
    except Exception as e:
        logger.error(f"Error getting weekly digest: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Feedback Loop Endpoints
@router.post("/feedback-loop/start")
async def start_feedback_loop():
    """Start the feedback loop system"""
    try:
        feedback_loop.start_feedback_loop()
        return {"message": "Feedback loop started successfully"}
    except Exception as e:
        logger.error(f"Error starting feedback loop: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/feedback-loop/stop")
async def stop_feedback_loop():
    """Stop the feedback loop system"""
    try:
        feedback_loop.stop_feedback_loop()
        return {"message": "Feedback loop stopped successfully"}
    except Exception as e:
        logger.error(f"Error stopping feedback loop: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/feedback-loop/status", response_model=FeedbackLoopStatusResponse)
async def get_feedback_loop_status():
    """Get feedback loop status"""
    try:
        status = feedback_loop.get_feedback_loop_status()
        
        return FeedbackLoopStatusResponse(
            is_running=status.is_running,
            last_run=status.last_run,
            stories_being_tracked=status.stories_being_tracked,
            articles_processed_today=status.articles_processed_today,
            rag_enhancements_triggered=status.rag_enhancements_triggered,
            new_articles_found=status.new_articles_found,
            context_growth_percentage=status.context_growth_percentage,
            next_scheduled_run=status.next_scheduled_run
        )
    except Exception as e:
        logger.error(f"Error getting feedback loop status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Health check endpoint
@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
