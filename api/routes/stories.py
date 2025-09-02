"""
Stories API Routes for News Intelligence System v3.0
Provides story tracking, evolution, and dossier management
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from enum import Enum

from fastapi import APIRouter, HTTPException, Query, Path
from pydantic import BaseModel, Field

from api.config.database import get_db_connection

router = APIRouter()

# Enums
class StoryStatus(str, Enum):
    """Story status"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    RESOLVED = "resolved"

class StoryPriority(str, Enum):
    """Story priority"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

# Pydantic models
class StoryBase(BaseModel):
    """Base story model"""
    title: str = Field(..., description="Story title")
    description: Optional[str] = Field(None, description="Story description")
    category: Optional[str] = Field(None, description="Story category")
    priority: StoryPriority = Field(StoryPriority.MEDIUM, description="Story priority")

class StoryCreate(StoryBase):
    """Story creation model"""
    pass

class StoryUpdate(BaseModel):
    """Story update model"""
    title: Optional[str] = Field(None, description="Story title")
    description: Optional[str] = Field(None, description="Story description")
    category: Optional[str] = Field(None, description="Story category")
    priority: Optional[StoryPriority] = Field(None, description="Story priority")
    status: Optional[StoryStatus] = Field(None, description="Story status")

class Story(StoryBase):
    """Full story model"""
    id: int = Field(..., description="Story ID")
    status: StoryStatus = Field(..., description="Story status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    article_count: int = Field(0, description="Number of articles in story")
    last_activity: Optional[datetime] = Field(None, description="Last activity timestamp")
    
    # Analysis results
    summary: Optional[str] = Field(None, description="Story summary")
    sentiment_trend: Optional[List[float]] = Field(None, description="Sentiment trend over time")
    key_entities: Optional[List[Dict[str, Any]]] = Field(None, description="Key entities in story")
    timeline: Optional[List[Dict[str, Any]]] = Field(None, description="Story timeline")
    
    class Config:
        from_attributes = True

class StoryList(BaseModel):
    """Story list response model"""
    stories: List[Story] = Field(..., description="List of stories")
    total: int = Field(..., description="Total number of stories")
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Stories per page")
    has_next: bool = Field(..., description="Has next page")
    has_prev: bool = Field(..., description="Has previous page")

class StoryDossier(BaseModel):
    """Story dossier model"""
    story: Story = Field(..., description="Story information")
    articles: List[Dict[str, Any]] = Field(..., description="Related articles")
    timeline: List[Dict[str, Any]] = Field(..., description="Story timeline")
    entities: List[Dict[str, Any]] = Field(..., description="Key entities")
    sentiment_analysis: Dict[str, Any] = Field(..., description="Sentiment analysis")
    related_stories: List[Story] = Field(..., description="Related stories")

class StoryEvolution(BaseModel):
    """Story evolution model"""
    story_id: int = Field(..., description="Story ID")
    period: str = Field(..., description="Time period")
    article_count: int = Field(..., description="Articles in period")
    sentiment_avg: float = Field(..., description="Average sentiment")
    key_events: List[Dict[str, Any]] = Field(..., description="Key events")
    entity_changes: List[Dict[str, Any]] = Field(..., description="Entity changes")

@router.get("/", response_model=StoryList)
async def get_stories(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Stories per page"),
    status: Optional[StoryStatus] = Query(None, description="Filter by status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    priority: Optional[StoryPriority] = Query(None, description="Filter by priority"),
    search: Optional[str] = Query(None, description="Search query")
):
    """
    Get stories with filtering, sorting, and pagination
    
    Returns a paginated list of stories with optional filtering
    """
    try:
        offset = (page - 1) * per_page
        
        # Build query
        where_conditions = []
        params = []
        
        if status:
            where_conditions.append("status = %s")
            params.append(status.value)
        
        if category:
            where_conditions.append("category ILIKE %s")
            params.append(f"%{category}%")
        
        if priority:
            where_conditions.append("priority = %s")
            params.append(priority.value)
        
        if search:
            where_conditions.append("(title ILIKE %s OR description ILIKE %s)")
            params.extend([f"%{search}%", f"%{search}%"])
        
        where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        # Get total count
        count_query = f"SELECT COUNT(*) FROM stories {where_clause}"
        conn = await get_db_connection()
        cursor = conn.cursor()
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]
        
        # Get stories with article counts
        stories_query = f"""
            SELECT 
                s.id, s.title, s.description, s.category, s.priority, s.status,
                s.created_at, s.updated_at, s.last_activity,
                s.summary, s.sentiment_trend, s.key_entities, s.timeline,
                COUNT(sa.article_id) as article_count
            FROM stories s
            LEFT JOIN story_articles sa ON s.id = sa.story_id
            {where_clause}
            GROUP BY s.id, s.title, s.description, s.category, s.priority, s.status,
                     s.created_at, s.updated_at, s.last_activity,
                     s.summary, s.sentiment_trend, s.key_entities, s.timeline
            ORDER BY s.updated_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        cursor.execute(stories_query, params)
        
        stories = []
        for row in cursor.fetchall():
            stories.append(Story(
                id=row[0],
                title=row[1],
                description=row[2],
                category=row[3],
                priority=StoryPriority(row[4]),
                status=StoryStatus(row[5]),
                created_at=row[6],
                updated_at=row[7],
                last_activity=row[8],
                summary=row[9],
                sentiment_trend=row[10] if row[10] else [],
                key_entities=row[11] if row[11] else [],
                timeline=row[12] if row[12] else [],
                article_count=row[13]
            ))
        
        cursor.close()
        conn.close()
        
        return StoryList(
            stories=stories,
            total=total,
            page=page,
            per_page=per_page,
            has_next=offset + per_page < total,
            has_prev=page > 1
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get stories: {str(e)}"
        )

@router.get("/{story_id}", response_model=Story)
async def get_story(
    story_id: int = Path(..., description="Story ID")
):
    """
    Get a specific story by ID
    
    Returns detailed information about a single story
    """
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                s.id, s.title, s.description, s.category, s.priority, s.status,
                s.created_at, s.updated_at, s.last_activity,
                s.summary, s.sentiment_trend, s.key_entities, s.timeline,
                COUNT(sa.article_id) as article_count
            FROM stories s
            LEFT JOIN story_articles sa ON s.id = sa.story_id
            WHERE s.id = %s
            GROUP BY s.id, s.title, s.description, s.category, s.priority, s.status,
                     s.created_at, s.updated_at, s.last_activity,
                     s.summary, s.sentiment_trend, s.key_entities, s.timeline
        """, (story_id,))
        
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not row:
            raise HTTPException(
                status_code=404,
                detail="Story not found"
            )
        
        return Story(
            id=row[0],
            title=row[1],
            description=row[2],
            category=row[3],
            priority=StoryPriority(row[4]),
            status=StoryStatus(row[5]),
            created_at=row[6],
            updated_at=row[7],
            last_activity=row[8],
            summary=row[9],
            sentiment_trend=row[10] if row[10] else [],
            key_entities=row[11] if row[11] else [],
            timeline=row[12] if row[12] else [],
            article_count=row[13]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get story: {str(e)}"
        )

@router.get("/{story_id}/dossier", response_model=StoryDossier)
async def get_story_dossier(
    story_id: int = Path(..., description="Story ID")
):
    """
    Get comprehensive story dossier
    
    Returns a complete story dossier with all related information
    """
    try:
        # Get story
        story = await get_story(story_id)
        
        # Get related articles
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                a.id, a.title, a.url, a.source, a.published_at,
                a.summary, a.sentiment, a.tags, a.relevance_score
            FROM articles a
            JOIN story_articles sa ON a.id = sa.article_id
            WHERE sa.story_id = %s
            ORDER BY a.published_at DESC
        """, (story_id,))
        
        articles = []
        for row in cursor.fetchall():
            articles.append({
                "id": row[0],
                "title": row[1],
                "url": row[2],
                "source": row[3],
                "published_at": row[4],
                "summary": row[5],
                "sentiment": row[6],
                "tags": row[7] if row[7] else [],
                "relevance_score": row[8]
            })
        
        # Get timeline
        cursor.execute("""
            SELECT 
                DATE(a.published_at) as date,
                COUNT(*) as article_count,
                AVG(a.sentiment) as avg_sentiment
            FROM articles a
            JOIN story_articles sa ON a.id = sa.article_id
            WHERE sa.story_id = %s
            GROUP BY DATE(a.published_at)
            ORDER BY date
        """, (story_id,))
        
        timeline = []
        for row in cursor.fetchall():
            timeline.append({
                "date": row[0],
                "article_count": row[1],
                "avg_sentiment": float(row[2]) if row[2] else 0.0
            })
        
        # Get entities
        cursor.execute("""
            SELECT 
                entity_type, entity_name, COUNT(*) as frequency
            FROM (
                SELECT 
                    jsonb_array_elements(a.entities) as entity
                FROM articles a
                JOIN story_articles sa ON a.id = sa.article_id
                WHERE sa.story_id = %s AND a.entities IS NOT NULL
            ) as entity_data
            CROSS JOIN LATERAL (
                SELECT 
                    entity->>'type' as entity_type,
                    entity->>'name' as entity_name
            ) as entity_info
            GROUP BY entity_type, entity_name
            ORDER BY frequency DESC
            LIMIT 20
        """, (story_id,))
        
        entities = []
        for row in cursor.fetchall():
            entities.append({
                "type": row[0],
                "name": row[1],
                "frequency": row[2]
            })
        
        # Get sentiment analysis
        cursor.execute("""
            SELECT 
                AVG(sentiment) as avg_sentiment,
                MIN(sentiment) as min_sentiment,
                MAX(sentiment) as max_sentiment,
                COUNT(CASE WHEN sentiment > 0.1 THEN 1 END) as positive_count,
                COUNT(CASE WHEN sentiment < -0.1 THEN 1 END) as negative_count,
                COUNT(CASE WHEN sentiment BETWEEN -0.1 AND 0.1 THEN 1 END) as neutral_count
            FROM articles a
            JOIN story_articles sa ON a.id = sa.article_id
            WHERE sa.story_id = %s AND a.sentiment IS NOT NULL
        """, (story_id,))
        
        sentiment_row = cursor.fetchone()
        sentiment_analysis = {
            "avg_sentiment": float(sentiment_row[0]) if sentiment_row[0] else 0.0,
            "min_sentiment": float(sentiment_row[1]) if sentiment_row[1] else 0.0,
            "max_sentiment": float(sentiment_row[2]) if sentiment_row[2] else 0.0,
            "positive_count": sentiment_row[3] or 0,
            "negative_count": sentiment_row[4] or 0,
            "neutral_count": sentiment_row[5] or 0
        }
        
        # Get related stories
        cursor.execute("""
            SELECT DISTINCT s2.id
            FROM stories s1
            JOIN story_articles sa1 ON s1.id = sa1.story_id
            JOIN story_articles sa2 ON sa1.article_id = sa2.article_id
            JOIN stories s2 ON sa2.story_id = s2.id
            WHERE s1.id = %s AND s2.id != %s
            LIMIT 5
        """, (story_id, story_id))
        
        related_story_ids = [row[0] for row in cursor.fetchall()]
        related_stories = []
        for related_id in related_story_ids:
            related_stories.append(await get_story(related_id))
        
        cursor.close()
        conn.close()
        
        return StoryDossier(
            story=story,
            articles=articles,
            timeline=timeline,
            entities=entities,
            sentiment_analysis=sentiment_analysis,
            related_stories=related_stories
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get story dossier: {str(e)}"
        )

@router.get("/{story_id}/evolution", response_model=StoryEvolution)
async def get_story_evolution(
    story_id: int = Path(..., description="Story ID"),
    period: str = Query("week", description="Time period: day, week, month")
):
    """
    Get story evolution analysis
    
    Returns analysis of how the story has evolved over time
    """
    try:
        if period not in ["day", "week", "month"]:
            raise HTTPException(
                status_code=400,
                detail="Period must be one of: day, week, month"
            )
        
        # Get story
        story = await get_story(story_id)
        
        # Calculate time interval
        if period == "day":
            interval = "1 day"
        elif period == "week":
            interval = "1 week"
        else:  # month
            interval = "1 month"
        
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Get article count for period
        cursor.execute("""
            SELECT COUNT(*)
            FROM articles a
            JOIN story_articles sa ON a.id = sa.article_id
            WHERE sa.story_id = %s 
            AND a.published_at >= NOW() - INTERVAL %s
        """, (story_id, interval))
        article_count = cursor.fetchone()[0]
        
        # Get average sentiment for period
        cursor.execute("""
            SELECT AVG(a.sentiment)
            FROM articles a
            JOIN story_articles sa ON a.id = sa.article_id
            WHERE sa.story_id = %s 
            AND a.published_at >= NOW() - INTERVAL %s
            AND a.sentiment IS NOT NULL
        """, (story_id, interval))
        sentiment_avg = cursor.fetchone()[0]
        
        # Get key events (articles with high relevance)
        cursor.execute("""
            SELECT 
                a.id, a.title, a.published_at, a.relevance_score
            FROM articles a
            JOIN story_articles sa ON a.id = sa.article_id
            WHERE sa.story_id = %s 
            AND a.published_at >= NOW() - INTERVAL %s
            ORDER BY a.relevance_score DESC
            LIMIT 10
        """, (story_id, interval))
        
        key_events = []
        for row in cursor.fetchall():
            key_events.append({
                "article_id": row[0],
                "title": row[1],
                "published_at": row[2],
                "relevance_score": row[3]
            })
        
        # Get entity changes
        cursor.execute("""
            SELECT 
                entity_type, entity_name, COUNT(*) as frequency
            FROM (
                SELECT 
                    jsonb_array_elements(a.entities) as entity
                FROM articles a
                JOIN story_articles sa ON a.id = sa.article_id
                WHERE sa.story_id = %s 
                AND a.published_at >= NOW() - INTERVAL %s
                AND a.entities IS NOT NULL
            ) as entity_data
            CROSS JOIN LATERAL (
                SELECT 
                    entity->>'type' as entity_type,
                    entity->>'name' as entity_name
            ) as entity_info
            GROUP BY entity_type, entity_name
            ORDER BY frequency DESC
            LIMIT 10
        """, (story_id, interval))
        
        entity_changes = []
        for row in cursor.fetchall():
            entity_changes.append({
                "type": row[0],
                "name": row[1],
                "frequency": row[2]
            })
        
        cursor.close()
        conn.close()
        
        return StoryEvolution(
            story_id=story_id,
            period=period,
            article_count=article_count,
            sentiment_avg=float(sentiment_avg) if sentiment_avg else 0.0,
            key_events=key_events,
            entity_changes=entity_changes
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get story evolution: {str(e)}"
        )

@router.post("/", response_model=Story)
async def create_story(story: StoryCreate):
    """
    Create a new story
    
    Creates a new story for tracking
    """
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO stories (
                title, description, category, priority, status, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            story.title,
            story.description,
            story.category,
            story.priority.value,
            StoryStatus.ACTIVE.value,
            datetime.utcnow(),
            datetime.utcnow()
        ))
        
        story_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        
        # Return the created story
        return await get_story(story_id)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create story: {str(e)}"
        )

@router.put("/{story_id}", response_model=Story)
async def update_story(
    story_id: int = Path(..., description="Story ID"),
    story_update: StoryUpdate = None
):
    """
    Update an existing story
    
    Updates story information and status
    """
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Check if story exists
        cursor.execute("SELECT id FROM stories WHERE id = %s", (story_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=404,
                detail="Story not found"
            )
        
        # Build update query
        update_fields = []
        params = []
        
        if story_update.title is not None:
            update_fields.append("title = %s")
            params.append(story_update.title)
        
        if story_update.description is not None:
            update_fields.append("description = %s")
            params.append(story_update.description)
        
        if story_update.category is not None:
            update_fields.append("category = %s")
            params.append(story_update.category)
        
        if story_update.priority is not None:
            update_fields.append("priority = %s")
            params.append(story_update.priority.value)
        
        if story_update.status is not None:
            update_fields.append("status = %s")
            params.append(story_update.status.value)
        
        if update_fields:
            update_fields.append("updated_at = %s")
            params.append(datetime.utcnow())
            params.append(story_id)
            
            cursor.execute(f"""
                UPDATE stories 
                SET {', '.join(update_fields)}
                WHERE id = %s
            """, params)
            
            conn.commit()
        
        cursor.close()
        conn.close()
        
        # Return updated story
        return await get_story(story_id)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update story: {str(e)}"
        )

@router.post("/{story_id}/articles/{article_id}")
async def add_article_to_story(
    story_id: int = Path(..., description="Story ID"),
    article_id: int = Path(..., description="Article ID")
):
    """
    Add an article to a story
    
    Associates an article with a story for tracking
    """
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Check if story exists
        cursor.execute("SELECT id FROM stories WHERE id = %s", (story_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=404,
                detail="Story not found"
            )
        
        # Check if article exists
        cursor.execute("SELECT id FROM articles WHERE id = %s", (article_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=404,
                detail="Article not found"
            )
        
        # Add article to story
        cursor.execute("""
            INSERT INTO story_articles (story_id, article_id, added_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (story_id, article_id) DO NOTHING
        """, (story_id, article_id, datetime.utcnow()))
        
        # Update story last activity
        cursor.execute("""
            UPDATE stories 
            SET last_activity = %s, updated_at = %s
            WHERE id = %s
        """, (datetime.utcnow(), datetime.utcnow(), story_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {"message": "Article added to story successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add article to story: {str(e)}"
        )

@router.delete("/{story_id}/articles/{article_id}")
async def remove_article_from_story(
    story_id: int = Path(..., description="Story ID"),
    article_id: int = Path(..., description="Article ID")
):
    """
    Remove an article from a story
    
    Removes the association between an article and a story
    """
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM story_articles 
            WHERE story_id = %s AND article_id = %s
        """, (story_id, article_id))
        
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Article not found in story"
            )
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {"message": "Article removed from story successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to remove article from story: {str(e)}"
        )

@router.get("/stats/overview")
async def get_story_stats():
    """
    Get story statistics overview
    
    Returns comprehensive statistics about stories
    """
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Get various statistics
        stats = {}
        
        # Total stories
        cursor.execute("SELECT COUNT(*) FROM stories")
        stats["total_stories"] = cursor.fetchone()[0]
        
        # Stories by status
        cursor.execute("""
            SELECT status, COUNT(*) 
            FROM stories 
            GROUP BY status
        """)
        stats["by_status"] = dict(cursor.fetchall())
        
        # Stories by category
        cursor.execute("""
            SELECT category, COUNT(*) 
            FROM stories 
            WHERE category IS NOT NULL
            GROUP BY category 
            ORDER BY COUNT(*) DESC 
            LIMIT 10
        """)
        stats["by_category"] = dict(cursor.fetchall())
        
        # Stories by priority
        cursor.execute("""
            SELECT priority, COUNT(*) 
            FROM stories 
            GROUP BY priority
        """)
        stats["by_priority"] = dict(cursor.fetchall())
        
        # Average articles per story
        cursor.execute("""
            SELECT AVG(article_count) FROM (
                SELECT COUNT(*) as article_count 
                FROM story_articles 
                GROUP BY story_id
            ) as story_counts
        """)
        result = cursor.fetchone()[0]
        stats["avg_articles_per_story"] = float(result) if result else 0.0
        
        cursor.close()
        conn.close()
        
        return stats
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get story stats: {str(e)}"
        )
