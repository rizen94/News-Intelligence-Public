"""
News Intelligence System v3.1.0 - Story Consolidation API
Handles story timeline management, consolidation, and AI analysis
"""

import os
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
import psycopg2
from psycopg2.extras import RealDictCursor
import json

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'news-system-postgres'),
    'database': os.getenv('DB_NAME', 'newsintelligence'),
    'user': os.getenv('DB_USER', 'newsapp'),
    'password': os.getenv('DB_PASSWORD', 'Database@NEWSINT2025'),
    'port': os.getenv('DB_PORT', '5432')
}

# Pydantic models
class TimelineEvent(BaseModel):
    id: Optional[int] = None
    event_id: str
    timestamp: datetime
    title: str
    description: str
    source: str
    confidence: float = Field(ge=0.0, le=1.0)
    event_type: str = Field(..., pattern="^(initial|development|update|conclusion)$")
    sentiment: Optional[str] = Field(None, pattern="^(positive|negative|neutral)$")
    entities: Optional[List[str]] = []

class StoryTimeline(BaseModel):
    id: Optional[int] = None
    story_id: str
    title: str
    summary: Optional[str] = None
    status: str = Field(default="developing", pattern="^(developing|breaking|concluded|monitoring)$")
    sentiment: str = Field(default="neutral", pattern="^(positive|negative|neutral|mixed)$")
    impact_level: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    sources_count: int = Field(default=0, ge=0)
    last_updated: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class StoryConsolidation(BaseModel):
    id: Optional[int] = None
    story_timeline_id: int
    headline: str
    consolidated_summary: str
    key_points: List[str] = []
    professional_report: Optional[str] = None
    executive_summary: Optional[str] = None
    recommendations: List[str] = []
    ai_analysis: Dict[str, Any] = {}
    sources: List[str] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class AIAnalysis(BaseModel):
    id: Optional[int] = None
    story_timeline_id: int
    analysis_type: str
    analysis_data: Dict[str, Any]
    confidence: float = Field(ge=0.0, le=1.0)
    model_used: Optional[str] = None
    processing_time_ms: Optional[int] = None
    created_at: Optional[datetime] = None

class StoryTimelineResponse(BaseModel):
    success: bool = True
    data: List[StoryTimeline]
    total: int
    page: int
    limit: int

class StoryConsolidationResponse(BaseModel):
    success: bool = True
    data: List[StoryConsolidation]
    total: int
    page: int
    limit: int

class TimelineEventsResponse(BaseModel):
    success: bool = True
    data: List[TimelineEvent]
    total: int

class AIAnalysisResponse(BaseModel):
    success: bool = True
    data: List[AIAnalysis]
    total: int

# Database connection helper
def get_db_connection():
    """Get database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")

# API Endpoints

@router.get("/timelines/", response_model=StoryTimelineResponse)
async def get_story_timelines(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = Query(None),
    sentiment: Optional[str] = Query(None),
    impact_level: Optional[str] = Query(None)
):
    """Get all story timelines with optional filtering"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Build query with filters
        where_conditions = []
        params = []
        
        if status:
            where_conditions.append("status = %s")
            params.append(status)
        if sentiment:
            where_conditions.append("sentiment = %s")
            params.append(sentiment)
        if impact_level:
            where_conditions.append("impact_level = %s")
            params.append(impact_level)
        
        where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        # Get total count
        count_query = f"SELECT COUNT(*) FROM story_timelines {where_clause}"
        cursor.execute(count_query, params)
        total = cursor.fetchone()['count']
        
        # Get paginated results
        offset = (page - 1) * limit
        query = f"""
            SELECT * FROM story_timelines 
            {where_clause}
            ORDER BY created_at DESC 
            LIMIT %s OFFSET %s
        """
        cursor.execute(query, params + [limit, offset])
        
        timelines = []
        for row in cursor.fetchall():
            timeline_data = dict(row)
            # Convert datetime objects to ISO format
            for key, value in timeline_data.items():
                if isinstance(value, datetime):
                    timeline_data[key] = value.isoformat()
            timelines.append(StoryTimeline(**timeline_data))
        
        cursor.close()
        conn.close()
        
        return StoryTimelineResponse(
            data=timelines,
            total=total,
            page=page,
            limit=limit
        )
        
    except Exception as e:
        logger.error(f"Error fetching story timelines: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/timelines/{story_id}/", response_model=StoryTimeline)
async def get_story_timeline(story_id: str):
    """Get a specific story timeline by story_id"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("SELECT * FROM story_timelines WHERE story_id = %s", (story_id,))
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Story timeline not found")
        
        timeline_data = dict(row)
        # Convert datetime objects to ISO format
        for key, value in timeline_data.items():
            if isinstance(value, datetime):
                timeline_data[key] = value.isoformat()
        
        cursor.close()
        conn.close()
        
        return StoryTimeline(**timeline_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching story timeline {story_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/timelines/{story_id}/events/", response_model=TimelineEventsResponse)
async def get_timeline_events(story_id: str):
    """Get timeline events for a specific story"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # First get the story timeline ID
        cursor.execute("SELECT id FROM story_timelines WHERE story_id = %s", (story_id,))
        timeline_row = cursor.fetchone()
        
        if not timeline_row:
            raise HTTPException(status_code=404, detail="Story timeline not found")
        
        timeline_id = timeline_row['id']
        
        # Get events
        cursor.execute("""
            SELECT * FROM timeline_events 
            WHERE story_timeline_id = %s 
            ORDER BY timestamp ASC
        """, (timeline_id,))
        
        events = []
        for row in cursor.fetchall():
            event_data = dict(row)
            # Convert datetime objects to ISO format
            for key, value in event_data.items():
                if isinstance(value, datetime):
                    event_data[key] = value.isoformat()
            events.append(TimelineEvent(**event_data))
        
        cursor.close()
        conn.close()
        
        return TimelineEventsResponse(
            data=events,
            total=len(events)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching timeline events for {story_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/consolidated/", response_model=StoryConsolidationResponse)
async def get_consolidated_stories(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100)
):
    """Get consolidated story reports"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get total count
        cursor.execute("SELECT COUNT(*) FROM story_consolidations")
        total = cursor.fetchone()['count']
        
        # Get paginated results
        offset = (page - 1) * limit
        cursor.execute("""
            SELECT sc.*, st.story_id, st.title as story_title
            FROM story_consolidations sc
            JOIN story_timelines st ON sc.story_timeline_id = st.id
            ORDER BY sc.created_at DESC 
            LIMIT %s OFFSET %s
        """, (limit, offset))
        
        consolidations = []
        for row in cursor.fetchall():
            consolidation_data = dict(row)
            # Convert datetime objects to ISO format
            for key, value in consolidation_data.items():
                if isinstance(value, datetime):
                    consolidation_data[key] = value.isoformat()
            consolidations.append(StoryConsolidation(**consolidation_data))
        
        cursor.close()
        conn.close()
        
        return StoryConsolidationResponse(
            data=consolidations,
            total=total,
            page=page,
            limit=limit
        )
        
    except Exception as e:
        logger.error(f"Error fetching consolidated stories: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/timelines/{story_id}/analysis/", response_model=AIAnalysisResponse)
async def get_story_analysis(story_id: str):
    """Get AI analysis for a specific story"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # First get the story timeline ID
        cursor.execute("SELECT id FROM story_timelines WHERE story_id = %s", (story_id,))
        timeline_row = cursor.fetchone()
        
        if not timeline_row:
            raise HTTPException(status_code=404, detail="Story timeline not found")
        
        timeline_id = timeline_row['id']
        
        # Get AI analysis
        cursor.execute("""
            SELECT * FROM ai_analysis 
            WHERE story_timeline_id = %s 
            ORDER BY created_at DESC
        """, (timeline_id,))
        
        analyses = []
        for row in cursor.fetchall():
            analysis_data = dict(row)
            # Convert datetime objects to ISO format
            for key, value in analysis_data.items():
                if isinstance(value, datetime):
                    analysis_data[key] = value.isoformat()
            analyses.append(AIAnalysis(**analysis_data))
        
        cursor.close()
        conn.close()
        
        return AIAnalysisResponse(
            data=analyses,
            total=len(analyses)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching story analysis for {story_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/consolidate/")
async def generate_consolidated_report(
    story_id: str,
    sources: List[str],
    timeframe: Optional[str] = None,
    focus: Optional[List[str]] = None,
    report_type: str = "comprehensive"
):
    """Generate a new consolidated story report"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get or create story timeline
        cursor.execute("SELECT id FROM story_timelines WHERE story_id = %s", (story_id,))
        timeline_row = cursor.fetchone()
        
        if not timeline_row:
            # Create new story timeline
            cursor.execute("""
                INSERT INTO story_timelines (story_id, title, summary, status, sentiment, impact_level, confidence_score, sources_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (story_id, f"Story {story_id}", "Generated story", "developing", "neutral", "medium", 0.0, len(sources)))
            timeline_id = cursor.fetchone()['id']
        else:
            timeline_id = timeline_row['id']
        
        # For now, create a mock consolidated report
        # In Phase 2, this will integrate with AI processing
        consolidated_data = {
            "headline": f"Consolidated Report for {story_id}",
            "consolidated_summary": f"Comprehensive analysis of {story_id} based on {len(sources)} sources",
            "key_points": [
                f"Story {story_id} is developing",
                f"Based on {len(sources)} verified sources",
                "AI analysis pending integration"
            ],
            "professional_report": f"Professional analysis of {story_id} will be generated once AI integration is complete.",
            "executive_summary": f"Story {story_id} requires further analysis",
            "recommendations": [
                "Monitor story development",
                "Update analysis as new information becomes available"
            ],
            "ai_analysis": {
                "sentiment": "neutral",
                "entities": [],
                "topics": [],
                "credibility": 0.5,
                "bias": "neutral",
                "factCheck": 0.5
            },
            "sources": sources
        }
        
        # Insert consolidated report
        cursor.execute("""
            INSERT INTO story_consolidations 
            (story_timeline_id, headline, consolidated_summary, key_points, professional_report, 
             executive_summary, recommendations, ai_analysis, sources)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            timeline_id,
            consolidated_data["headline"],
            consolidated_data["consolidated_summary"],
            json.dumps(consolidated_data["key_points"]),
            consolidated_data["professional_report"],
            consolidated_data["executive_summary"],
            json.dumps(consolidated_data["recommendations"]),
            json.dumps(consolidated_data["ai_analysis"]),
            json.dumps(consolidated_data["sources"])
        ))
        
        consolidation_id = cursor.fetchone()['id']
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "message": "Consolidated report generated successfully",
            "data": {
                "consolidation_id": consolidation_id,
                "story_id": story_id,
                "timeline_id": timeline_id
            }
        }
        
    except Exception as e:
        logger.error(f"Error generating consolidated report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/timelines/{story_id}/timeline/")
async def update_story_timeline(story_id: str, events: List[TimelineEvent]):
    """Update story timeline with new events"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get story timeline ID
        cursor.execute("SELECT id FROM story_timelines WHERE story_id = %s", (story_id,))
        timeline_row = cursor.fetchone()
        
        if not timeline_row:
            raise HTTPException(status_code=404, detail="Story timeline not found")
        
        timeline_id = timeline_row['id']
        
        # Insert new events
        for event in events:
            cursor.execute("""
                INSERT INTO timeline_events 
                (story_timeline_id, event_id, timestamp, title, description, source, 
                 confidence, event_type, sentiment, entities)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (event_id) DO UPDATE SET
                    timestamp = EXCLUDED.timestamp,
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    source = EXCLUDED.source,
                    confidence = EXCLUDED.confidence,
                    event_type = EXCLUDED.event_type,
                    sentiment = EXCLUDED.sentiment,
                    entities = EXCLUDED.entities
            """, (
                timeline_id,
                event.event_id,
                event.timestamp,
                event.title,
                event.description,
                event.source,
                event.confidence,
                event.event_type,
                event.sentiment,
                json.dumps(event.entities or [])
            ))
        
        # Update story timeline last_updated
        cursor.execute("""
            UPDATE story_timelines 
            SET last_updated = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (timeline_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "message": f"Timeline updated with {len(events)} events",
            "data": {
                "story_id": story_id,
                "events_added": len(events)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating story timeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/timelines/{story_id}/updates/", response_model=TimelineEventsResponse)
async def get_story_updates(story_id: str, since: Optional[datetime] = None):
    """Get real-time story updates"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get story timeline ID
        cursor.execute("SELECT id FROM story_timelines WHERE story_id = %s", (story_id,))
        timeline_row = cursor.fetchone()
        
        if not timeline_row:
            raise HTTPException(status_code=404, detail="Story timeline not found")
        
        timeline_id = timeline_row['id']
        
        # Get recent events
        if since:
            cursor.execute("""
                SELECT * FROM timeline_events 
                WHERE story_timeline_id = %s AND timestamp > %s
                ORDER BY timestamp DESC
            """, (timeline_id, since))
        else:
            cursor.execute("""
                SELECT * FROM timeline_events 
                WHERE story_timeline_id = %s 
                ORDER BY timestamp DESC 
                LIMIT 10
            """, (timeline_id,))
        
        events = []
        for row in cursor.fetchall():
            event_data = dict(row)
            # Convert datetime objects to ISO format
            for key, value in event_data.items():
                if isinstance(value, datetime):
                    event_data[key] = value.isoformat()
            events.append(TimelineEvent(**event_data))
        
        cursor.close()
        conn.close()
        
        return TimelineEventsResponse(
            data=events,
            total=len(events)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching story updates: {e}")
        raise HTTPException(status_code=500, detail=str(e))
