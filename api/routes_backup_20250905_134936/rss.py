"""
RSS Management API Routes for News Intelligence System v3.0
Provides RSS feed management, monitoring, and statistics
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from enum import Enum

from fastapi import APIRouter, HTTPException, Query, Path, Body
from pydantic import BaseModel, Field

from config.database import get_db_connection
from schemas.response_schemas import APIResponse, PaginatedResponse

router = APIRouter()

# Enums
class FeedStatus(str, Enum):
    """RSS feed status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    WARNING = "warning"

class FeedCategory(str, Enum):
    """RSS feed categories"""
    NEWS = "news"
    TECHNOLOGY = "technology"
    BUSINESS = "business"
    POLITICS = "politics"
    SPORTS = "sports"
    ENTERTAINMENT = "entertainment"
    SCIENCE = "science"
    HEALTH = "health"
    OTHER = "other"

# Pydantic models
class RSSFeedBase(BaseModel):
    """Base RSS feed model"""
    name: str = Field(..., description="Feed name")
    url: str = Field(..., description="Feed URL")
    category: Optional[str] = Field(None, description="Feed category")
    is_active: bool = Field(True, description="Whether feed is active")

class RSSFeedCreate(RSSFeedBase):
    """RSS feed creation model"""
    pass

class RSSFeedUpdate(BaseModel):
    """RSS feed update model"""
    name: Optional[str] = None
    url: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None

class RSSFeed(RSSFeedBase):
    """Complete RSS feed model"""
    id: int = Field(..., description="Feed ID")
    last_checked: Optional[datetime] = Field(None, description="Last check timestamp")
    last_success: Optional[datetime] = Field(None, description="Last successful update")
    failure_count: int = Field(0, description="Number of failures")
    article_count: int = Field(0, description="Total articles collected")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

class RSSFeedList(BaseModel):
    """RSS feed list response"""
    feeds: List[RSSFeed] = Field(..., description="List of RSS feeds")
    total: int = Field(..., description="Total number of feeds")
    page: int = Field(..., description="Current page")
    per_page: int = Field(..., description="Items per page")

class RSSStats(BaseModel):
    """RSS statistics model"""
    total_feeds: int = Field(..., description="Total number of feeds")
    active_feeds: int = Field(..., description="Number of active feeds")
    articles_today: int = Field(..., description="Articles collected today")
    articles_this_hour: int = Field(..., description="Articles collected this hour")
    articles_last_24h: int = Field(..., description="Articles collected in last 24 hours")
    articles_last_7d: int = Field(..., description="Articles collected in last 7 days")
    success_rate: float = Field(..., description="Overall success rate")
    avg_response_time: int = Field(..., description="Average response time")
    overall_health: float = Field(..., description="Overall system health")
    most_active_feed: Optional[Dict[str, Any]] = Field(None, description="Most active feed")
    fastest_feed: Optional[Dict[str, Any]] = Field(None, description="Fastest feed")
    most_reliable_feed: Optional[Dict[str, Any]] = Field(None, description="Most reliable feed")
    avg_articles_per_feed: float = Field(..., description="Average articles per feed")

class FeedTestResult(BaseModel):
    """Feed test result model"""
    success: bool = Field(..., description="Test success status")
    response_time: int = Field(..., description="Response time in ms")
    articles_found: int = Field(..., description="Number of articles found")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    last_article_date: Optional[datetime] = Field(None, description="Date of most recent article")

# API Endpoints

@router.get("/feeds/", response_model=APIResponse)
async def get_rss_feeds(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[FeedStatus] = Query(None, description="Filter by status"),
    category: Optional[FeedCategory] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search query")
):
    """Get list of RSS feeds with filtering and pagination"""
    try:
        offset = (page - 1) * per_page
        
        # Build query conditions
        where_conditions = []
        params = []
        
        if status:
            where_conditions.append("status = %s")
            params.append(status.value)
        
        if category:
            where_conditions.append("category = %s")
            params.append(category.value)
        
        if search:
            where_conditions.append("(name ILIKE %s OR url ILIKE %s)")
            params.extend([f"%{search}%", f"%{search}%"])
        
        where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        # Get total count
        count_query = f"SELECT COUNT(*) FROM rss_feeds {where_clause}"
        conn = await get_db_connection()
        cursor = conn.cursor()
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]
        
        # Get feeds
        feeds_query = f"""
            SELECT 
                id, name, url, category, is_active, last_checked, last_success,
                failure_count, article_count, created_at, updated_at
            FROM rss_feeds 
            {where_clause}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        cursor.execute(feeds_query, params)
        
        feeds = []
        for row in cursor.fetchall():
            feed = RSSFeed(
                id=row[0],
                name=row[1],
                url=row[2],
                category=row[3],
                is_active=row[4],
                last_checked=row[5],
                last_success=row[6],
                failure_count=row[7],
                article_count=row[8],
                created_at=row[9],
                updated_at=row[10]
            )
            feeds.append(feed)
        
        cursor.close()
        conn.close()
        
        return APIResponse(
            success=True,
            data={
                "feeds": feeds,
                "pagination": {
                    "total": total,
                    "page": page,
                    "per_page": per_page,
                    "total_pages": (total + per_page - 1) // per_page
                }
            },
            message=f"Retrieved {len(feeds)} RSS feeds"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch RSS feeds: {str(e)}"
        )

@router.get("/feeds/{feed_id}", response_model=RSSFeed)
async def get_rss_feed(feed_id: int = Path(..., description="Feed ID")):
    """Get specific RSS feed by ID"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                id, name, url, category, is_active, last_checked, last_success,
                failure_count, article_count, created_at, updated_at
            FROM rss_feeds 
            WHERE id = %s
        """, (feed_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="RSS feed not found")
        
        feed = RSSFeed(
            id=row[0],
            name=row[1],
            url=row[2],
            category=row[3],
            is_active=row[4],
            last_check=row[5],
            last_success=row[6],
            failure_count=row[7],
            article_count=row[8],
            created_at=row[9],
            updated_at=row[10]
        )
        
        cursor.close()
        conn.close()
        
        return feed
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch RSS feed: {str(e)}"
        )

@router.post("/feeds", response_model=RSSFeed)
async def create_rss_feed(feed_data: RSSFeedCreate):
    """Create new RSS feed"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Check if URL already exists
        cursor.execute("SELECT id FROM rss_feeds WHERE url = %s", (feed_data.url,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="RSS feed with this URL already exists")
        
        # Insert new feed
        cursor.execute("""
            INSERT INTO rss_feeds (
                name, url, category, is_active, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s
            ) RETURNING id
        """, (
            feed_data.name,
            feed_data.url,
            feed_data.category,
            feed_data.is_active,
            datetime.utcnow(),
            datetime.utcnow()
        ))
        
        feed_id = cursor.fetchone()[0]
        conn.commit()
        
        cursor.close()
        conn.close()
        
        # Return created feed
        return await get_rss_feed(feed_id)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create RSS feed: {str(e)}"
        )

@router.put("/feeds/{feed_id}", response_model=RSSFeed)
async def update_rss_feed(
    feed_id: int = Path(..., description="Feed ID"),
    feed_data: RSSFeedUpdate = Body(..., description="Feed update data")
):
    """Update RSS feed"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Check if feed exists
        cursor.execute("SELECT id FROM rss_feeds WHERE id = %s", (feed_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="RSS feed not found")
        
        # Build update query dynamically
        update_fields = []
        params = []
        
        if feed_data.name is not None:
            update_fields.append("name = %s")
            params.append(feed_data.name)
        
        if feed_data.url is not None:
            # Check if new URL already exists
            cursor.execute("SELECT id FROM rss_feeds WHERE url = %s AND id != %s", (feed_data.url, feed_id))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="RSS feed with this URL already exists")
            update_fields.append("url = %s")
            params.append(feed_data.url)
        

        
        if feed_data.category is not None:
            update_fields.append("category = %s")
            params.append(feed_data.category)
        
        if feed_data.is_active is not None:
            update_fields.append("is_active = %s")
            params.append(feed_data.is_active)
        
        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        update_fields.append("updated_at = %s")
        params.append(datetime.utcnow())
        params.append(feed_id)
        
        update_query = f"""
            UPDATE rss_feeds 
            SET {', '.join(update_fields)}
            WHERE id = %s
        """
        
        cursor.execute(update_query, params)
        conn.commit()
        
        cursor.close()
        conn.close()
        
        # Return updated feed
        return await get_rss_feed(feed_id)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update RSS feed: {str(e)}"
        )

@router.delete("/feeds/{feed_id}")
async def delete_rss_feed(feed_id: int = Path(..., description="Feed ID")):
    """Delete RSS feed"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Check if feed exists
        cursor.execute("SELECT id FROM rss_feeds WHERE id = %s", (feed_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="RSS feed not found")
        
        # Delete feed
        cursor.execute("DELETE FROM rss_feeds WHERE id = %s", (feed_id,))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return {"message": "RSS feed deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete RSS feed: {str(e)}"
        )

@router.post("/feeds/{feed_id}/test", response_model=FeedTestResult)
async def test_rss_feed(feed_id: int = Path(..., description="Feed ID")):
    """Test RSS feed connectivity and validity"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Get feed details
        cursor.execute("SELECT url, name FROM rss_feeds WHERE id = %s", (feed_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="RSS feed not found")
        
        feed_url, feed_name = row
        
        # Test feed (simplified - in production, use proper RSS parsing)
        import requests
        import time
        
        start_time = time.time()
        try:
            response = requests.get(feed_url, timeout=30)
            response_time = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                # Parse RSS content (simplified)
                import feedparser
                feed = feedparser.parse(response.content)
                
                articles_found = len(feed.entries) if hasattr(feed, 'entries') else 0
                last_article_date = None
                
                if articles_found > 0 and hasattr(feed.entries[0], 'published_parsed'):
                    last_article_date = datetime(*feed.entries[0].published_parsed[:6])
                
                return FeedTestResult(
                    success=True,
                    response_time=response_time,
                    articles_found=articles_found,
                    last_article_date=last_article_date
                )
            else:
                return FeedTestResult(
                    success=False,
                    response_time=response_time,
                    articles_found=0,
                    error_message=f"HTTP {response.status_code}: {response.reason}"
                )
                
        except requests.RequestException as e:
            response_time = int((time.time() - start_time) * 1000)
            return FeedTestResult(
                success=False,
                response_time=response_time,
                articles_found=0,
                error_message=str(e)
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to test RSS feed: {str(e)}"
        )

@router.post("/feeds/{feed_id}/refresh")
async def refresh_rss_feed(feed_id: int = Path(..., description="Feed ID")):
    """Force refresh RSS feed"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Check if feed exists
        cursor.execute("SELECT id FROM rss_feeds WHERE id = %s", (feed_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="RSS feed not found")
        
        # Update last_checked timestamp
        cursor.execute("""
            UPDATE rss_feeds 
            SET last_checked = %s, updated_at = %s
            WHERE id = %s
        """, (datetime.utcnow(), datetime.utcnow(), feed_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # In production, this would trigger the RSS collection process
        return {"message": "RSS feed refresh triggered successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh RSS feed: {str(e)}"
        )

@router.patch("/feeds/{feed_id}/toggle")
async def toggle_rss_feed(
    feed_id: int = Path(..., description="Feed ID"),
    is_active: bool = Body(..., description="Active status")
):
    """Toggle RSS feed active status"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Check if feed exists
        cursor.execute("SELECT id FROM rss_feeds WHERE id = %s", (feed_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="RSS feed not found")
        
        # Update active status
        cursor.execute("""
            UPDATE rss_feeds 
            SET is_active = %s, updated_at = %s
            WHERE id = %s
        """, (is_active, datetime.utcnow(), feed_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {"message": f"RSS feed {'activated' if is_active else 'deactivated'} successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to toggle RSS feed: {str(e)}"
        )

@router.get("/stats", response_model=RSSStats)
async def get_rss_stats():
    """Get RSS collection statistics"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Get basic stats
        cursor.execute("SELECT COUNT(*) FROM rss_feeds")
        total_feeds = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM rss_feeds WHERE is_active = true")
        active_feeds = cursor.fetchone()[0]
        
        # Get article counts
        today = datetime.utcnow().date()
        cursor.execute("""
            SELECT COUNT(*) FROM articles 
            WHERE DATE(created_at) = %s
        """, (today,))
        articles_today = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM articles 
            WHERE created_at >= %s
        """, (datetime.utcnow() - timedelta(hours=1),))
        articles_this_hour = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM articles 
            WHERE created_at >= %s
        """, (datetime.utcnow() - timedelta(days=1),))
        articles_last_24h = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM articles 
            WHERE created_at >= %s
        """, (datetime.utcnow() - timedelta(days=7),))
        articles_last_7d = cursor.fetchone()[0]
        
        # Get feed performance stats
        cursor.execute("""
            SELECT 
                AVG(success_rate) as avg_success_rate,
                AVG(avg_response_time) as avg_response_time
            FROM rss_feeds 
            WHERE is_active = true
        """)
        row = cursor.fetchone()
        success_rate = float(row[0]) if row[0] else 0.0
        avg_response_time = int(row[1]) if row[1] else 0
        
        # Get most active feed
        cursor.execute("""
            SELECT name, articles_today 
            FROM rss_feeds 
            WHERE is_active = true 
            ORDER BY articles_today DESC 
            LIMIT 1
        """)
        row = cursor.fetchone()
        most_active_feed = {"name": row[0], "articles_today": row[1]} if row else None
        
        # Get fastest feed
        cursor.execute("""
            SELECT name, avg_response_time 
            FROM rss_feeds 
            WHERE is_active = true AND avg_response_time > 0
            ORDER BY avg_response_time ASC 
            LIMIT 1
        """)
        row = cursor.fetchone()
        fastest_feed = {"name": row[0], "avg_response_time": row[1]} if row else None
        
        # Get most reliable feed
        cursor.execute("""
            SELECT name, success_rate 
            FROM rss_feeds 
            WHERE is_active = true 
            ORDER BY success_rate DESC 
            LIMIT 1
        """)
        row = cursor.fetchone()
        most_reliable_feed = {"name": row[0], "success_rate": row[1]} if row else None
        
        # Calculate overall health
        overall_health = (success_rate + (100 - min(avg_response_time / 10, 100))) / 2
        
        cursor.close()
        conn.close()
        
        return RSSStats(
            total_feeds=total_feeds,
            active_feeds=active_feeds,
            articles_today=articles_today,
            articles_this_hour=articles_this_hour,
            articles_last_24h=articles_last_24h,
            articles_last_7d=articles_last_7d,
            success_rate=success_rate,
            avg_response_time=avg_response_time,
            overall_health=overall_health,
            most_active_feed=most_active_feed,
            fastest_feed=fastest_feed,
            most_reliable_feed=most_reliable_feed,
            avg_articles_per_feed=articles_today / max(active_feeds, 1)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch RSS statistics: {str(e)}"
        )
