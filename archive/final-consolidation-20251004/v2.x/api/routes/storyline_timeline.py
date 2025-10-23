#!/usr/bin/env python3
"""
Storyline Timeline API Routes
Provides timeline data for storyline events and story evolution
Uses ML/LLM to generate intelligent timeline events
"""

from fastapi import APIRouter, HTTPException, Query, Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import psycopg2
import json
import logging
import sys
import os

# Add the modules directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'modules', 'ml'))

try:
    from timeline_generator import TimelineGenerator, TimelineEvent
except ImportError:
    # Fallback if timeline_generator is not available
    TimelineGenerator = None
    TimelineEvent = None

logger = logging.getLogger(__name__)

router = APIRouter(tags=["storyline-timeline"])

# Import database configuration
from config.database import get_db_config

# Get database configuration
DB_CONFIG = get_db_config()

class TimelineEvent(BaseModel):
    """Model for a timeline event"""
    event_id: str = Field(..., description="Unique event identifier")
    title: str = Field(..., description="Event title")
    description: str = Field(..., description="Event description")
    event_date: str = Field(..., description="Date of the event (YYYY-MM-DD)")
    event_time: Optional[str] = Field(None, description="Time of the event (HH:MM)")
    source: str = Field(..., description="Source of the event")
    url: Optional[str] = Field(None, description="URL to source article")
    importance_score: float = Field(..., ge=0.0, le=1.0, description="Importance score (0-1)")
    event_type: str = Field(..., description="Type of event (military, diplomatic, humanitarian, etc.)")
    location: Optional[str] = Field(None, description="Location of the event")
    entities: List[str] = Field(default=[], description="Key entities involved")
    tags: List[str] = Field(default=[], description="Event tags")
    created_at: str = Field(..., description="When this event was added to timeline")

class TimelinePeriod(BaseModel):
    """Model for a time period in the timeline"""
    period: str = Field(..., description="Time period (e.g., '2024-01', '2024-Q1')")
    start_date: str = Field(..., description="Start date of period")
    end_date: str = Field(..., description="End date of period")
    event_count: int = Field(..., description="Number of events in this period")
    key_events: List[TimelineEvent] = Field(default=[], description="Key events in this period")
    summary: str = Field(..., description="Summary of events in this period")

class StorylineTimeline(BaseModel):
    """Model for complete storyline timeline"""
    storyline_id: str = Field(..., description="Storyline identifier")
    storyline_name: str = Field(..., description="Storyline name")
    total_events: int = Field(..., description="Total number of events")
    time_range: Dict[str, str] = Field(..., description="Start and end dates of timeline")
    periods: List[TimelinePeriod] = Field(default=[], description="Timeline periods")
    key_milestones: List[TimelineEvent] = Field(default=[], description="Key milestone events")
    recent_events: List[TimelineEvent] = Field(default=[], description="Most recent events")
    created_at: str = Field(..., description="When timeline was created")
    updated_at: str = Field(..., description="When timeline was last updated")

@router.get("/{storyline_id}")
async def get_storyline_timeline(
    storyline_id: str = Path(..., description="Storyline ID"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    event_types: Optional[str] = Query(None, description="Comma-separated event types to filter"),
    min_importance: float = Query(0.0, ge=0.0, le=1.0, description="Minimum importance score")
):
    """
    Get timeline of events for a specific storyline
    
    Returns a comprehensive timeline of events related to the storyline,
    including key milestones, recent events, and period summaries.
    """
    try:
        # Get storyline information
        storyline = await _get_storyline_info(storyline_id)
        if not storyline:
            raise HTTPException(status_code=404, detail="Storyline not found")
        
        # Set default date range if not provided
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        # Parse event types filter
        event_type_filter = []
        if event_types:
            event_type_filter = [t.strip() for t in event_types.split(',')]
        
        # Get timeline events
        events = await _get_timeline_events(
            storyline_id, start_date, end_date, event_type_filter, min_importance
        )
        
        # Group events by time periods
        periods = await _group_events_by_periods(events)
        
        # Get key milestones (high importance events)
        key_milestones = [e for e in events if e['importance_score'] >= 0.8][:10]
        
        # Get recent events (last 30 days)
        recent_cutoff = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        recent_events = [e for e in events if e['event_date'] >= recent_cutoff][:20]
        
        timeline_data = {
            'storyline_id': storyline_id,
            'storyline_name': storyline['name'],
            'total_events': len(events),
            'time_range': {
                'start': start_date,
                'end': end_date
            },
            'periods': periods,
            'key_milestones': key_milestones,
            'recent_events': recent_events,
            'created_at': storyline['created_at'],
            'updated_at': storyline['updated_at']
        }
        
        return {
            "success": True,
            "data": timeline_data,
            "message": f"Timeline retrieved for storyline {storyline_id}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting storyline timeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{storyline_id}/events", response_model=List[TimelineEvent])
async def get_storyline_events(
    storyline_id: str = Path(..., description="Storyline ID"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of events to return"),
    offset: int = Query(0, ge=0, description="Number of events to skip"),
    sort_by: str = Query("event_date", description="Sort field: event_date, importance_score"),
    sort_order: str = Query("desc", description="Sort order: asc, desc"),
    event_types: Optional[str] = Query(None, description="Comma-separated event types to filter"),
    min_importance: float = Query(0.0, ge=0.0, le=1.0, description="Minimum importance score")
):
    """
    Get paginated list of events for a storyline
    
    Returns a paginated list of timeline events with filtering and sorting options.
    """
    try:
        # Parse event types filter
        event_type_filter = []
        if event_types:
            event_type_filter = [t.strip() for t in event_types.split(',')]
        
        # Get events
        events = await _get_timeline_events(
            storyline_id, None, None, event_type_filter, min_importance, 
            limit, offset, sort_by, sort_order
        )
        
        return events
        
    except Exception as e:
        logger.error(f"Error getting storyline events: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{storyline_id}/milestones", response_model=List[TimelineEvent])
async def get_storyline_milestones(
    storyline_id: str = Path(..., description="Storyline ID"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of milestones to return")
):
    """
    Get key milestone events for a storyline
    
    Returns the most important events that represent key milestones in the storyline.
    """
    try:
        # Get high-importance events
        events = await _get_timeline_events(
            storyline_id, None, None, [], 0.7, limit, 0, "importance_score", "desc"
        )
        
        return events
        
    except Exception as e:
        logger.error(f"Error getting storyline milestones: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def _get_storyline_info(storyline_id: str) -> Optional[Dict[str, Any]]:
    """Get basic storyline information"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT story_id, name, description, created_at, updated_at
            FROM story_expectations 
            WHERE story_id = %s AND is_active = true
        """, (storyline_id,))
        
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if row:
            return {
                "story_id": row[0],
                "name": row[1],
                "description": row[2],
                "created_at": row[3].isoformat() if row[3] else None,
                "updated_at": row[4].isoformat() if row[4] else None
            }
        return None
        
    except Exception as e:
        logger.error(f"Error getting storyline info: {e}")
        return None

def _get_stored_timeline_events(
    storyline_id: str, 
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    event_types: List[str] = None,
    min_importance: float = 0.0,
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "event_date",
    sort_order: str = "desc"
) -> List[Dict[str, Any]]:
    """Get stored timeline events from database"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        where_conditions = ["storyline_id = %s"]
        params = [storyline_id]
        
        if start_date:
            where_conditions.append("event_date >= %s")
            params.append(start_date)
        
        if end_date:
            where_conditions.append("event_date <= %s")
            params.append(end_date)
        
        if event_types:
            placeholders = ','.join(['%s'] * len(event_types))
            where_conditions.append(f"event_type IN ({placeholders})")
            params.extend(event_types)
        
        if min_importance > 0:
            where_conditions.append("importance_score >= %s")
            params.append(min_importance)
        
        where_clause = " AND ".join(where_conditions)
        
        # Build ORDER BY clause
        order_direction = "DESC" if sort_order == "desc" else "ASC"
        if sort_by == "event_date":
            order_clause = f"event_date {order_direction}, importance_score DESC"
        elif sort_by == "importance_score":
            order_clause = f"importance_score {order_direction}, event_date DESC"
        else:
            order_clause = f"event_date DESC, importance_score DESC"
        
        query = f"""
            SELECT 
                te.event_id, te.title, te.description, te.event_date, te.event_time,
                te.source, te.url, te.importance_score, te.event_type, te.location,
                te.entities, te.tags, te.ml_generated, te.confidence_score, te.created_at,
                te.source_article_ids
            FROM timeline_events te
            WHERE {where_clause}
            ORDER BY {order_clause}
            LIMIT %s OFFSET %s
        """
        
        params.extend([limit, offset])
        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        events = []
        for row in rows:
            events.append({
                "event_id": row[0],
                "title": row[1],
                "description": row[2],
                "event_date": row[3].isoformat() if row[3] else None,
                "event_time": row[4].isoformat() if row[4] else None,
                "source": row[5],
                "url": row[6],
                "importance_score": float(row[7]) if row[7] else 0.0,
                "event_type": row[8],
                "location": row[9],
                "entities": row[10] if row[10] else [],
                "tags": row[11] if row[11] else [],
                "ml_generated": row[12],
                "confidence_score": float(row[13]) if row[13] else 0.0,
                "created_at": row[14].isoformat() if row[14] else None,
                "source_article_ids": row[15] if row[15] else []
            })
        
        return events
        
    except Exception as e:
        logger.error(f"Error getting stored timeline events: {e}")
        return []

async def _get_timeline_events(
    storyline_id: str, 
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    event_types: List[str] = None,
    min_importance: float = 0.0,
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "event_date",
    sort_order: str = "desc"
) -> List[Dict[str, Any]]:
    """Get timeline events for a storyline from database, generate if needed"""
    try:
        # First, try to get existing events from database
        existing_events = _get_stored_timeline_events(
            storyline_id, start_date, end_date, event_types, min_importance, limit, offset, sort_by, sort_order
        )
        
        # If we have events, return them (prioritize stored events)
        if existing_events:
            logger.info(f"Retrieved {len(existing_events)} stored timeline events for storyline {storyline_id}")
            return existing_events
        
        # Only generate new events if none exist and we have ML capability
        logger.info(f"No stored events found for storyline {storyline_id}, attempting to generate new ones")
        storyline_data = await _get_storyline_data(storyline_id)
        if not storyline_data:
            logger.warning(f"Storyline {storyline_id} not found")
            return []
        
        # Initialize timeline generator if available
        if TimelineGenerator:
            timeline_generator = TimelineGenerator(DB_CONFIG)
            
            # Generate intelligent timeline events using ML/LLM
            timeline_events = timeline_generator.generate_timeline_events(
                storyline_id=storyline_id,
                storyline_data=storyline_data,
                start_date=start_date,
                end_date=end_date,
                max_events=limit + offset
            )
        else:
            # Fallback to simple article-based approach
            timeline_events = []
        
        # Apply filters
        filtered_events = []
        for event in timeline_events:
            # Filter by event types
            if event_types and event.event_type not in event_types:
                continue
            
            # Filter by minimum importance
            if event.importance_score < min_importance:
                continue
            
            # Convert to dict format
            event_dict = {
                "event_id": event.event_id,
                "title": event.title,
                "description": event.description,
                "event_date": event.event_date,
                "event_time": event.event_time,
                "source": event.source,
                "url": event.url,
                "importance_score": event.importance_score,
                "event_type": event.event_type,
                "location": event.location,
                "entities": event.entities,
                "tags": event.tags,
                "created_at": event.created_at
            }
            filtered_events.append(event_dict)
        
        # Apply sorting
        if sort_by == "event_date":
            filtered_events.sort(key=lambda x: x["event_date"], reverse=(sort_order == "desc"))
        elif sort_by == "importance_score":
            filtered_events.sort(key=lambda x: x["importance_score"], reverse=(sort_order == "desc"))
        
        # Apply pagination
        return filtered_events[offset:offset + limit]
        
    except Exception as e:
        logger.error(f"Error getting timeline events: {e}")
        # Fallback to simple article-based approach if ML fails
        return await _get_timeline_events_fallback(
            storyline_id, start_date, end_date, event_types, 
            min_importance, limit, offset, sort_by, sort_order
        )

async def _get_storyline_data(storyline_id: str) -> Optional[Dict[str, Any]]:
    """Get storyline data for ML analysis"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT story_id, name, description, priority_level, keywords, 
                   entities, geographic_regions, quality_threshold, 
                   max_articles_per_day, auto_enhance, is_active
            FROM story_expectations 
            WHERE story_id = %s AND is_active = true
        """, (storyline_id,))
        
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if row:
            return {
                "story_id": row[0],
                "name": row[1],
                "description": row[2],
                "priority_level": row[3],
                "keywords": row[4] if isinstance(row[4], list) else json.loads(row[4]) if row[4] else [],
                "entities": row[5] if isinstance(row[5], list) else json.loads(row[5]) if row[5] else [],
                "geographic_regions": row[6] if isinstance(row[6], list) else json.loads(row[6]) if row[6] else [],
                "quality_threshold": row[7],
                "max_articles_per_day": row[8],
                "auto_enhance": row[9],
                "is_active": row[10]
            }
        return None
        
    except Exception as e:
        logger.error(f"Error getting storyline data: {e}")
        return None

async def _get_timeline_events_fallback(
    storyline_id: str, 
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    event_types: List[str] = None,
    min_importance: float = 0.0,
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "event_date",
    sort_order: str = "desc"
) -> List[Dict[str, Any]]:
    """Fallback method using simple article matching"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Build WHERE clause
        where_conditions = ["a.processing_status = 'completed'"]
        params = []
        
        if start_date:
            where_conditions.append(f"DATE(a.published_date) >= %s")
            params.append(start_date)
        
        if end_date:
            where_conditions.append(f"DATE(a.published_date) <= %s")
            params.append(end_date)
        
        if event_types:
            placeholders = ','.join(['%s'] * len(event_types))
            where_conditions.append(f"a.category IN ({placeholders})")
            params.extend(event_types)
        
        if min_importance > 0:
            where_conditions.append(f"COALESCE(a.engagement_score, 0) >= %s")
            params.append(min_importance)
        
        where_clause = " AND ".join(where_conditions)
        
        # Build ORDER BY clause
        valid_sort_fields = {
            "event_date": "a.published_date",
            "importance_score": "COALESCE(a.engagement_score, 0)",
            "created_at": "a.created_at"
        }
        sort_field = valid_sort_fields.get(sort_by, "a.published_date")
        sort_direction = "ASC" if sort_order.lower() == "asc" else "DESC"
        order_clause = f"{sort_field} {sort_direction}"
        
        # Simple keyword matching as fallback
        query = f"""
            SELECT 
                a.id as event_id,
                a.title,
                COALESCE(a.summary, a.content) as description,
                DATE(a.published_date) as event_date,
                TO_CHAR(a.published_date, 'HH24:MI') as event_time,
                a.source,
                a.url,
                COALESCE(a.engagement_score, 0) as importance_score,
                COALESCE(a.category, 'general') as event_type,
                COALESCE(a.entities_extracted, '[]'::jsonb) as entities,
                COALESCE(a.topics_extracted, '[]'::jsonb) as tags,
                a.created_at
            FROM articles a
            WHERE a.processing_status = 'completed'
            AND (
                a.title ILIKE %s OR 
                a.content ILIKE %s OR
                a.summary ILIKE %s
            )
            AND {where_clause}
            ORDER BY {order_clause}
            LIMIT %s OFFSET %s
        """
        
        # Add storyline search terms
        storyline_terms = storyline_id.replace('_', ' ').replace('-', ' ')
        search_term = f"%{storyline_terms}%"
        params = [search_term, search_term, search_term] + params + [limit, offset]
        
        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        events = []
        for row in rows:
            # Parse JSON fields
            entities = row[9] if isinstance(row[9], list) else json.loads(row[9]) if row[9] else []
            tags = row[10] if isinstance(row[10], list) else json.loads(row[10]) if row[10] else []
            
            events.append({
                "event_id": str(row[0]),
                "title": row[1],
                "description": row[2][:500] + "..." if len(row[2]) > 500 else row[2],
                "event_date": row[3].strftime('%Y-%m-%d') if row[3] else None,
                "event_time": row[4],
                "source": row[5],
                "url": row[6],
                "importance_score": float(row[7]),
                "event_type": row[8],
                "location": None,
                "entities": entities,
                "tags": tags,
                "created_at": row[11].isoformat() if row[11] else None
            })
        
        return events
        
    except Exception as e:
        logger.error(f"Error in fallback timeline events: {e}")
        return []

async def _group_events_by_periods(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group events by time periods (monthly)"""
    try:
        from collections import defaultdict
        
        # Group by month
        monthly_groups = defaultdict(list)
        for event in events:
            if event['event_date']:
                year_month = event['event_date'][:7]  # YYYY-MM
                monthly_groups[year_month].append(event)
        
        periods = []
        for period, period_events in sorted(monthly_groups.items()):
            # Get key events (top 3 by importance)
            key_events = sorted(period_events, key=lambda x: x['importance_score'], reverse=True)[:3]
            
            # Generate summary
            event_count = len(period_events)
            avg_importance = sum(e['importance_score'] for e in period_events) / event_count if event_count > 0 else 0
            
            summary = f"{event_count} events in {period}"
            if avg_importance > 0.7:
                summary += " (high importance period)"
            elif avg_importance > 0.4:
                summary += " (moderate activity)"
            else:
                summary += " (low activity)"
            
            periods.append({
                "period": period,
                "start_date": f"{period}-01",
                "end_date": f"{period}-31",
                "event_count": event_count,
                "key_events": key_events,
                "summary": summary
            })
        
        return periods
        
    except Exception as e:
        logger.error(f"Error grouping events by periods: {e}")
        return []
