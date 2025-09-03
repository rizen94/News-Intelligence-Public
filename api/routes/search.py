"""
Search API Routes for News Intelligence System v3.0
Provides advanced search capabilities including full-text and semantic search
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
class SearchType(str, Enum):
    """Search types"""
    FULL_TEXT = "full_text"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"

class SortField(str, Enum):
    """Sort fields"""
    RELEVANCE = "relevance"
    DATE = "date"
    TITLE = "title"
    SOURCE = "source"
    SENTIMENT = "sentiment"

# Pydantic models
class SearchFilters(BaseModel):
    """Search filters model"""
    sources: Optional[List[str]] = Field(None, description="Filter by sources")
    categories: Optional[List[str]] = Field(None, description="Filter by categories")
    date_from: Optional[datetime] = Field(None, description="Start date")
    date_to: Optional[datetime] = Field(None, description="End date")
    min_confidence: Optional[float] = Field(None, description="Minimum confidence score")
    sentiment: Optional[str] = Field(None, description="Sentiment filter")
    entities: Optional[List[str]] = Field(None, description="Filter by entities")
    clusters: Optional[List[int]] = Field(None, description="Filter by cluster IDs")

class SearchRequest(BaseModel):
    """Search request model"""
    query: str = Field(..., description="Search query")
    search_type: SearchType = Field(SearchType.FULL_TEXT, description="Search type")
    filters: Optional[SearchFilters] = Field(None, description="Search filters")
    page: int = Field(1, ge=1, description="Page number")
    per_page: int = Field(20, ge=1, le=100, description="Items per page")
    sort_by: SortField = Field(SortField.RELEVANCE, description="Sort field")
    sort_order: str = Field("desc", description="Sort order")

class SearchResult(BaseModel):
    """Search result model"""
    id: int = Field(..., description="Article ID")
    title: str = Field(..., description="Article title")
    content: str = Field(..., description="Article content")
    url: str = Field(..., description="Article URL")
    source: str = Field(..., description="Article source")
    published_at: datetime = Field(..., description="Publication date")
    summary: Optional[str] = Field(None, description="Article summary")
    sentiment: Optional[float] = Field(None, description="Sentiment score")
    relevance_score: float = Field(..., description="Relevance score")
    entities: List[Dict[str, Any]] = Field(default_factory=list, description="Extracted entities")
    tags: List[str] = Field(default_factory=list, description="Article tags")

class SearchResponse(BaseModel):
    """Search response model"""
    results: List[SearchResult] = Field(..., description="Search results")
    total: int = Field(..., description="Total results")
    page: int = Field(..., description="Current page")
    per_page: int = Field(..., description="Items per page")
    search_time: float = Field(..., description="Search execution time")
    suggestions: List[str] = Field(default_factory=list, description="Search suggestions")

class SearchStats(BaseModel):
    """Search statistics model"""
    total_searches: int = Field(..., description="Total searches performed")
    popular_queries: List[Dict[str, Any]] = Field(..., description="Popular search queries")
    search_trends: List[Dict[str, Any]] = Field(..., description="Search trends over time")
    avg_search_time: float = Field(..., description="Average search time")
    no_results_queries: List[str] = Field(..., description="Queries with no results")

# API Endpoints

@router.post("/", response_model=SearchResponse)
async def search_articles(search_request: SearchRequest):
    """Advanced article search with multiple search types and filters"""
    try:
        import time
        start_time = time.time()
        
        offset = (search_request.page - 1) * search_request.per_page
        
        # Build search query based on search type
        if search_request.search_type == SearchType.FULL_TEXT:
            results, total = await _full_text_search(search_request, offset, search_request.per_page)
        elif search_request.search_type == SearchType.SEMANTIC:
            results, total = await _semantic_search(search_request, offset, search_request.per_page)
        else:  # HYBRID
            results, total = await _hybrid_search(search_request, offset, search_request.per_page)
        
        # Get search suggestions
        suggestions = await _get_search_suggestions(search_request.query)
        
        # Log search for analytics
        await _log_search(search_request.query, total, time.time() - start_time)
        
        return SearchResponse(
            results=results,
            total=total,
            page=search_request.page,
            per_page=search_request.per_page,
            search_time=time.time() - start_time,
            suggestions=suggestions
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )

@router.get("/suggestions")
async def get_search_suggestions(
    query: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Number of suggestions")
):
    """Get search suggestions based on query"""
    try:
        suggestions = await _get_search_suggestions(query, limit)
        return {"suggestions": suggestions}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get suggestions: {str(e)}"
        )

@router.get("/trending")
async def get_trending_searches(
    limit: int = Query(10, ge=1, le=50, description="Number of trending searches"),
    period: str = Query("24h", description="Time period: 1h, 24h, 7d, 30d")
):
    """Get trending search queries"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Calculate time period
        if period == "1h":
            time_filter = datetime.utcnow() - timedelta(hours=1)
        elif period == "24h":
            time_filter = datetime.utcnow() - timedelta(days=1)
        elif period == "7d":
            time_filter = datetime.utcnow() - timedelta(days=7)
        else:  # 30d
            time_filter = datetime.utcnow() - timedelta(days=30)
        
        # Get trending searches
        cursor.execute("""
            SELECT query, COUNT(*) as search_count
            FROM search_logs 
            WHERE timestamp >= %s
            GROUP BY query
            ORDER BY search_count DESC
            LIMIT %s
        """, (time_filter, limit))
        
        trending = [
            {"query": row[0], "count": row[1]}
            for row in cursor.fetchall()
        ]
        
        cursor.close()
        conn.close()
        
        return {"trending": trending, "period": period}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get trending searches: {str(e)}"
        )

@router.get("/stats", response_model=SearchStats)
async def get_search_stats():
    """Get search statistics and analytics"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Get total searches
        cursor.execute("SELECT COUNT(*) FROM search_logs")
        total_searches = cursor.fetchone()[0]
        
        # Get popular queries
        cursor.execute("""
            SELECT query, COUNT(*) as search_count
            FROM search_logs 
            WHERE timestamp >= %s
            GROUP BY query
            ORDER BY search_count DESC
            LIMIT 10
        """, (datetime.utcnow() - timedelta(days=7),))
        
        popular_queries = [
            {"query": row[0], "count": row[1]}
            for row in cursor.fetchall()
        ]
        
        # Get search trends (daily for last 7 days)
        cursor.execute("""
            SELECT DATE(timestamp) as date, COUNT(*) as searches
            FROM search_logs 
            WHERE timestamp >= %s
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
        """, (datetime.utcnow() - timedelta(days=7),))
        
        search_trends = [
            {"date": row[0].isoformat(), "searches": row[1]}
            for row in cursor.fetchall()
        ]
        
        # Get average search time
        cursor.execute("SELECT AVG(search_time) FROM search_logs WHERE search_time IS NOT NULL")
        avg_search_time = float(cursor.fetchone()[0] or 0)
        
        # Get no results queries
        cursor.execute("""
            SELECT DISTINCT query
            FROM search_logs 
            WHERE results_count = 0
            ORDER BY timestamp DESC
            LIMIT 10
        """)
        
        no_results_queries = [row[0] for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return SearchStats(
            total_searches=total_searches,
            popular_queries=popular_queries,
            search_trends=search_trends,
            avg_search_time=avg_search_time,
            no_results_queries=no_results_queries
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch search statistics: {str(e)}"
        )

# Helper functions

async def _full_text_search(search_request: SearchRequest, offset: int, limit: int) -> tuple[List[SearchResult], int]:
    """Perform full-text search using PostgreSQL"""
    conn = await get_db_connection()
    cursor = conn.cursor()
    
    # Build search query
    where_conditions = []
    params = []
    
    # Full-text search
    where_conditions.append("to_tsvector('english', title || ' ' || content) @@ plainto_tsquery('english', %s)")
    params.append(search_request.query)
    
    # Apply filters
    if search_request.filters:
        if search_request.filters.sources:
            where_conditions.append("source = ANY(%s)")
            params.append(search_request.filters.sources)
        
        if search_request.filters.date_from:
            where_conditions.append("published_at >= %s")
            params.append(search_request.filters.date_from)
        
        if search_request.filters.date_to:
            where_conditions.append("published_at <= %s")
            params.append(search_request.filters.date_to)
        
        if search_request.filters.sentiment:
            where_conditions.append("sentiment = %s")
            params.append(search_request.filters.sentiment)
    
    where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
    
    # Get total count
    count_query = f"SELECT COUNT(*) FROM articles {where_clause}"
    cursor.execute(count_query, params)
    total = cursor.fetchone()[0]
    
    # Get results with ranking
    order_clause = f"ORDER BY ts_rank(to_tsvector('english', title || ' ' || content), plainto_tsquery('english', %s)) DESC"
    params.append(search_request.query)
    
    results_query = f"""
        SELECT 
            id, title, content, url, source, published_at, summary, sentiment,
            ts_rank(to_tsvector('english', title || ' ' || content), plainto_tsquery('english', %s)) as relevance_score,
            entities, tags
        FROM articles 
        {where_clause}
        {order_clause}
        LIMIT %s OFFSET %s
    """
    params.extend([search_request.query, limit, offset])
    cursor.execute(results_query, params)
    
    results = []
    for row in cursor.fetchall():
        result = SearchResult(
            id=row[0],
            title=row[1],
            content=row[2],
            url=row[3],
            source=row[4],
            published_at=row[5],
            summary=row[6],
            sentiment=row[7],
            relevance_score=float(row[8]),
            entities=row[9] or [],
            tags=row[10] or []
        )
        results.append(result)
    
    cursor.close()
    conn.close()
    
    return results, total

async def _semantic_search(search_request: SearchRequest, offset: int, limit: int) -> tuple[List[SearchResult], int]:
    """Perform semantic search using ML models"""
    # For now, fall back to full-text search
    # In production, this would use sentence transformers or similar
    return await _full_text_search(search_request, offset, limit)

async def _hybrid_search(search_request: SearchRequest, offset: int, limit: int) -> tuple[List[SearchResult], int]:
    """Perform hybrid search combining full-text and semantic"""
    # For now, use full-text search
    # In production, this would combine both approaches
    return await _full_text_search(search_request, offset, limit)

async def _get_search_suggestions(query: str, limit: int = 10) -> List[str]:
    """Get search suggestions based on query"""
    conn = await get_db_connection()
    cursor = conn.cursor()
    
    # Get suggestions from search history
    cursor.execute("""
        SELECT DISTINCT query
        FROM search_logs 
        WHERE query ILIKE %s
        ORDER BY COUNT(*) DESC
        LIMIT %s
    """, (f"%{query}%", limit))
    
    suggestions = [row[0] for row in cursor.fetchall()]
    
    # If not enough suggestions, get from article titles
    if len(suggestions) < limit:
        cursor.execute("""
            SELECT DISTINCT title
            FROM articles 
            WHERE title ILIKE %s
            ORDER BY published_at DESC
            LIMIT %s
        """, (f"%{query}%", limit - len(suggestions)))
        
        suggestions.extend([row[0] for row in cursor.fetchall()])
    
    cursor.close()
    conn.close()
    
    return suggestions[:limit]

async def _log_search(query: str, results_count: int, search_time: float):
    """Log search for analytics"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO search_logs (query, results_count, search_time, timestamp)
            VALUES (%s, %s, %s, %s)
        """, (query, results_count, search_time, datetime.utcnow()))
        
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        # Don't fail the search if logging fails
        print(f"Failed to log search: {e}")
