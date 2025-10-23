"""
Story Timeline API Routes - Fixed with text() wrapper
Tracks story evolution over time, similar to Ground News
"""

from fastapi import APIRouter, HTTPException, Query, Path, Depends
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
from schemas.robust_schemas import APIResponse
from config.database import get_db
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/story-timeline", tags=["Story Timeline"])

@router.get("/", response_model=APIResponse)
async def get_story_timelines(
    limit: int = Query(20, ge=1, le=100, description="Number of timelines to return"),
    offset: int = Query(0, ge=0, description="Number of timelines to skip"),
    days_back: int = Query(7, ge=1, le=30, description="Days back to look for stories"),
    db: Session = Depends(get_db)
):
    """Get story timelines with recent activity"""
    try:
        # Get database connection using the correct pattern
        db_gen = get_db()
        db = next(db_gen)
        
        try:
            cutoff_date = datetime.now() - timedelta(days=days_back)
            
            # Simple query to get story timelines
            query = text("""
                SELECT 
                    id, story_id, title, summary, first_seen, last_updated,
                    article_count, source_count, sentiment_trend, key_events, related_stories
                FROM story_timelines 
                WHERE last_updated >= :cutoff_date
                ORDER BY last_updated DESC
                LIMIT :limit OFFSET :offset
            """)
            
            result = db.execute(query, {
                "cutoff_date": cutoff_date,
                "limit": limit,
                "offset": offset
            }).fetchall()
            
            timelines = []
            for row in result:
                timelines.append({
                    "id": row[0],
                    "story_id": row[1],
                    "title": row[2],
                    "summary": row[3],
                    "first_seen": row[4].isoformat() if row[4] else None,
                    "last_updated": row[5].isoformat() if row[5] else None,
                    "article_count": row[6],
                    "source_count": row[7],
                    "sentiment_trend": row[8],
                    "key_events": row[9],
                    "related_stories": row[10]
                })
            
            return APIResponse(
                success=True,
                data=timelines,
                message=f"Retrieved {len(timelines)} story timelines"
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error getting story timelines: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve story timelines")

@router.get("/{story_id}", response_model=APIResponse)
async def get_story_timeline(
    story_id: str = Path(..., description="Story ID"),
    db: Session = Depends(get_db)
):
    """Get detailed timeline for a specific story"""
    try:
        # Get database connection using the correct pattern
        db_gen = get_db()
        db = next(db_gen)
        
        try:
            # Get story timeline
            timeline_query = text("SELECT * FROM story_timelines WHERE story_id = :story_id")
            timeline = db.execute(timeline_query, {"story_id": story_id}).fetchone()
            
            if not timeline:
                raise HTTPException(status_code=404, detail="Story timeline not found")
            
            # Get story events
            events_query = text("SELECT * FROM story_events WHERE story_id = :story_id ORDER BY event_timestamp DESC")
            events = db.execute(events_query, {"story_id": story_id}).fetchall()
            
            events_list = []
            for event in events:
                events_list.append({
                    "id": event[0],
                    "event_type": event[2],
                    "event_title": event[3],
                    "event_description": event[4],
                    "event_timestamp": event[7].isoformat() if event[7] else None,
                    "source_url": event[5],
                    "source_name": event[6],
                    "significance_score": float(event[8]) if event[8] else 0.0
                })
            
            timeline_data = {
                "id": timeline[0],
                "story_id": timeline[1],
                "title": timeline[2],
                "summary": timeline[3],
                "first_seen": timeline[4].isoformat() if timeline[4] else None,
                "last_updated": timeline[5].isoformat() if timeline[5] else None,
                "article_count": timeline[6],
                "source_count": timeline[7],
                "sentiment_trend": timeline[8],
                "key_events": timeline[9],
                "related_stories": timeline[10],
                "events": events_list
            }
            
            return APIResponse(
                success=True,
                data=timeline_data,
                message="Story timeline retrieved successfully"
            )
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting story timeline: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve story timeline")

@router.post("/create", response_model=APIResponse)
async def create_story_timeline(
    story_id: str,
    title: str,
    summary: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Create a new story timeline"""
    try:
        # Get database connection using the correct pattern
        db_gen = get_db()
        db = next(db_gen)
        
        try:
            # Check if timeline already exists
            existing_query = text("SELECT id FROM story_timelines WHERE story_id = :story_id")
            existing = db.execute(existing_query, {"story_id": story_id}).fetchone()
            
            if existing:
                return APIResponse(
                    success=False,
                    data=None,
                    message="Story timeline already exists"
                )
            
            # Create new timeline
            insert_query = text("""
                INSERT INTO story_timelines (story_id, title, summary)
                VALUES (:story_id, :title, :summary)
                RETURNING id
            """)
            
            result = db.execute(insert_query, {
                "story_id": story_id,
                "title": title,
                "summary": summary
            })
            
            timeline_id = result.fetchone()[0]
            db.commit()
            
            return APIResponse(
                success=True,
                data={"timeline_id": timeline_id},
                message="Story timeline created successfully"
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error creating story timeline: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create story timeline")
