"""
Sources API Routes for News Intelligence System v3.0
Provides news source management and analytics
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from enum import Enum

from fastapi import APIRouter, HTTPException, Query, Path, Body
from pydantic import BaseModel, Field

from api.config.database import get_db_connection

router = APIRouter()

# Enums
class SourceCategory(str, Enum):
    """Source categories"""
    NEWS = "news"
    TECHNOLOGY = "technology"
    BUSINESS = "business"
    POLITICS = "politics"
    SPORTS = "sports"
    ENTERTAINMENT = "entertainment"
    SCIENCE = "science"
    HEALTH = "health"
    WORLD = "world"
    LOCAL = "local"
    OTHER = "other"

class SourceStatus(str, Enum):
    """Source status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    WARNING = "warning"

# Pydantic models
class SourceBase(BaseModel):
    """Base source model"""
    name: str = Field(..., description="Source name")
    url: str = Field(..., description="Source URL")
    category: SourceCategory = Field(..., description="Source category")
    description: Optional[str] = Field(None, description="Source description")
    language: str = Field("en", description="Source language")
    country: Optional[str] = Field(None, description="Source country")
    is_active: bool = Field(True, description="Whether source is active")

class SourceCreate(SourceBase):
    """Source creation model"""
    pass

class SourceUpdate(BaseModel):
    """Source update model"""
    name: Optional[str] = None
    url: Optional[str] = None
    category: Optional[SourceCategory] = None
    description: Optional[str] = None
    language: Optional[str] = None
    country: Optional[str] = None
    is_active: Optional[bool] = None

class Source(SourceBase):
    """Complete source model"""
    id: int = Field(..., description="Source ID")
    status: SourceStatus = Field(..., description="Current status")
    article_count: int = Field(0, description="Total articles from this source")
    articles_today: int = Field(0, description="Articles today")
    articles_this_week: int = Field(0, description="Articles this week")
    last_article_date: Optional[datetime] = Field(None, description="Last article date")
    success_rate: float = Field(0.0, description="Success rate percentage")
    avg_response_time: int = Field(0, description="Average response time in ms")
    reliability_score: float = Field(0.0, description="Reliability score")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

class SourceList(BaseModel):
    """Source list response"""
    sources: List[Source] = Field(..., description="List of sources")
    total: int = Field(..., description="Total number of sources")
    page: int = Field(..., description="Current page")
    per_page: int = Field(..., description="Items per page")

class SourceStats(BaseModel):
    """Source statistics model"""
    total_sources: int = Field(..., description="Total sources")
    active_sources: int = Field(..., description="Active sources")
    sources_by_category: Dict[str, int] = Field(..., description="Sources by category")
    most_productive: List[Dict[str, Any]] = Field(..., description="Most productive sources")
    most_reliable: List[Dict[str, Any]] = Field(..., description="Most reliable sources")
    recent_sources: List[Dict[str, Any]] = Field(..., description="Recently added sources")
    articles_by_source: Dict[str, int] = Field(..., description="Articles by source")

# API Endpoints

@router.get("/", response_model=SourceList)
async def get_sources(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    category: Optional[SourceCategory] = Query(None, description="Filter by category"),
    status: Optional[SourceStatus] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search query"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    sort_by: str = Query("article_count", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order")
):
    """Get list of sources with filtering and pagination"""
    try:
        offset = (page - 1) * per_page
        
        # Build query conditions
        where_conditions = []
        params = []
        
        if category:
            where_conditions.append("category = %s")
            params.append(category.value)
        
        if status:
            where_conditions.append("status = %s")
            params.append(status.value)
        
        if search:
            where_conditions.append("(name ILIKE %s OR url ILIKE %s OR description ILIKE %s)")
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
        
        if is_active is not None:
            where_conditions.append("is_active = %s")
            params.append(is_active)
        
        where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        # Get total count
        count_query = f"SELECT COUNT(*) FROM sources {where_clause}"
        conn = await get_db_connection()
        cursor = conn.cursor()
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]
        
        # Get sources
        order_clause = f"ORDER BY {sort_by} {sort_order.upper()}"
        sources_query = f"""
            SELECT 
                id, name, url, category, description, language, country, is_active,
                status, article_count, articles_today, articles_this_week, last_article_date,
                success_rate, avg_response_time, reliability_score, created_at, updated_at
            FROM sources 
            {where_clause}
            {order_clause}
            LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        cursor.execute(sources_query, params)
        
        sources = []
        for row in cursor.fetchall():
            source = Source(
                id=row[0],
                name=row[1],
                url=row[2],
                category=row[3],
                description=row[4],
                language=row[5],
                country=row[6],
                is_active=row[7],
                status=row[8],
                article_count=row[9],
                articles_today=row[10],
                articles_this_week=row[11],
                last_article_date=row[12],
                success_rate=row[13],
                avg_response_time=row[14],
                reliability_score=row[15],
                created_at=row[16],
                updated_at=row[17]
            )
            sources.append(source)
        
        cursor.close()
        conn.close()
        
        return SourceList(
            sources=sources,
            total=total,
            page=page,
            per_page=per_page
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch sources: {str(e)}"
        )

@router.get("/{source_id}", response_model=Source)
async def get_source(source_id: int = Path(..., description="Source ID")):
    """Get specific source by ID"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                id, name, url, category, description, language, country, is_active,
                status, article_count, articles_today, articles_this_week, last_article_date,
                success_rate, avg_response_time, reliability_score, created_at, updated_at
            FROM sources 
            WHERE id = %s
        """, (source_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Source not found")
        
        source = Source(
            id=row[0],
            name=row[1],
            url=row[2],
            category=row[3],
            description=row[4],
            language=row[5],
            country=row[6],
            is_active=row[7],
            status=row[8],
            article_count=row[9],
            articles_today=row[10],
            articles_this_week=row[11],
            last_article_date=row[12],
            success_rate=row[13],
            avg_response_time=row[14],
            reliability_score=row[15],
            created_at=row[16],
            updated_at=row[17]
        )
        
        cursor.close()
        conn.close()
        
        return source
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch source: {str(e)}"
        )

@router.post("/", response_model=Source)
async def create_source(source_data: SourceCreate):
    """Create new source"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Check if URL already exists
        cursor.execute("SELECT id FROM sources WHERE url = %s", (source_data.url,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Source with this URL already exists")
        
        # Insert new source
        cursor.execute("""
            INSERT INTO sources (
                name, url, category, description, language, country, is_active,
                status, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            ) RETURNING id
        """, (
            source_data.name,
            source_data.url,
            source_data.category.value,
            source_data.description,
            source_data.language,
            source_data.country,
            source_data.is_active,
            SourceStatus.ACTIVE.value,
            datetime.utcnow(),
            datetime.utcnow()
        ))
        
        source_id = cursor.fetchone()[0]
        conn.commit()
        
        cursor.close()
        conn.close()
        
        # Return created source
        return await get_source(source_id)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create source: {str(e)}"
        )

@router.put("/{source_id}", response_model=Source)
async def update_source(
    source_id: int = Path(..., description="Source ID"),
    source_data: SourceUpdate = Body(..., description="Source update data")
):
    """Update source"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Check if source exists
        cursor.execute("SELECT id FROM sources WHERE id = %s", (source_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Source not found")
        
        # Build update query dynamically
        update_fields = []
        params = []
        
        if source_data.name is not None:
            update_fields.append("name = %s")
            params.append(source_data.name)
        
        if source_data.url is not None:
            # Check if new URL already exists
            cursor.execute("SELECT id FROM sources WHERE url = %s AND id != %s", (source_data.url, source_id))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Source with this URL already exists")
            update_fields.append("url = %s")
            params.append(source_data.url)
        
        if source_data.category is not None:
            update_fields.append("category = %s")
            params.append(source_data.category.value)
        
        if source_data.description is not None:
            update_fields.append("description = %s")
            params.append(source_data.description)
        
        if source_data.language is not None:
            update_fields.append("language = %s")
            params.append(source_data.language)
        
        if source_data.country is not None:
            update_fields.append("country = %s")
            params.append(source_data.country)
        
        if source_data.is_active is not None:
            update_fields.append("is_active = %s")
            params.append(source_data.is_active)
        
        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        update_fields.append("updated_at = %s")
        params.append(datetime.utcnow())
        params.append(source_id)
        
        update_query = f"""
            UPDATE sources 
            SET {', '.join(update_fields)}
            WHERE id = %s
        """
        
        cursor.execute(update_query, params)
        conn.commit()
        
        cursor.close()
        conn.close()
        
        # Return updated source
        return await get_source(source_id)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update source: {str(e)}"
        )

@router.delete("/{source_id}")
async def delete_source(source_id: int = Path(..., description="Source ID")):
    """Delete source"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Check if source exists
        cursor.execute("SELECT id FROM sources WHERE id = %s", (source_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Source not found")
        
        # Delete source
        cursor.execute("DELETE FROM sources WHERE id = %s", (source_id,))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return {"message": "Source deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete source: {str(e)}"
        )

@router.get("/stats/overview", response_model=SourceStats)
async def get_source_stats():
    """Get source statistics"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Get total sources
        cursor.execute("SELECT COUNT(*) FROM sources")
        total_sources = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM sources WHERE is_active = true")
        active_sources = cursor.fetchone()[0]
        
        # Get sources by category
        cursor.execute("""
            SELECT category, COUNT(*) 
            FROM sources 
            GROUP BY category 
            ORDER BY COUNT(*) DESC
        """)
        sources_by_category = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Get most productive sources
        cursor.execute("""
            SELECT name, article_count, articles_today, success_rate
            FROM sources 
            WHERE is_active = true
            ORDER BY article_count DESC 
            LIMIT 10
        """)
        most_productive = [
            {
                "name": row[0],
                "article_count": row[1],
                "articles_today": row[2],
                "success_rate": row[3]
            }
            for row in cursor.fetchall()
        ]
        
        # Get most reliable sources
        cursor.execute("""
            SELECT name, reliability_score, success_rate, avg_response_time
            FROM sources 
            WHERE is_active = true
            ORDER BY reliability_score DESC 
            LIMIT 10
        """)
        most_reliable = [
            {
                "name": row[0],
                "reliability_score": row[1],
                "success_rate": row[2],
                "avg_response_time": row[3]
            }
            for row in cursor.fetchall()
        ]
        
        # Get recent sources
        cursor.execute("""
            SELECT name, category, created_at, article_count
            FROM sources 
            ORDER BY created_at DESC 
            LIMIT 10
        """)
        recent_sources = [
            {
                "name": row[0],
                "category": row[1],
                "created_at": row[2],
                "article_count": row[3]
            }
            for row in cursor.fetchall()
        ]
        
        # Get articles by source
        cursor.execute("""
            SELECT name, article_count
            FROM sources 
            WHERE is_active = true
            ORDER BY article_count DESC
        """)
        articles_by_source = {row[0]: row[1] for row in cursor.fetchall()}
        
        cursor.close()
        conn.close()
        
        return SourceStats(
            total_sources=total_sources,
            active_sources=active_sources,
            sources_by_category=sources_by_category,
            most_productive=most_productive,
            most_reliable=most_reliable,
            recent_sources=recent_sources,
            articles_by_source=articles_by_source
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch source statistics: {str(e)}"
        )
