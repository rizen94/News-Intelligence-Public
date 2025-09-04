"""
Articles API Routes for News Intelligence System v3.0
Provides article management, analysis, and search capabilities
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from enum import Enum

from fastapi import APIRouter, HTTPException, Query, Path
from pydantic import BaseModel, Field

from config.database import get_db_connection

router = APIRouter()

# Enums
class ArticleStatus(str, Enum):
    """Article processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"

class SortOrder(str, Enum):
    """Sort order options"""
    ASC = "asc"
    DESC = "desc"

class SortField(str, Enum):
    """Sort field options"""
    CREATED_AT = "created_at"
    TITLE = "title"
    SOURCE = "source"
    SENTIMENT = "sentiment"
    RELEVANCE = "relevance"

# Pydantic models
class ArticleBase(BaseModel):
    """Base article model"""
    title: str = Field(..., description="Article title")
    content: str = Field(..., description="Article content")
    url: str = Field(..., description="Article URL")
    source: str = Field(..., description="Article source")
    published_date: Optional[datetime] = Field(None, description="Publication timestamp")

class ArticleCreate(ArticleBase):
    """Article creation model"""
    pass

class ArticleUpdate(BaseModel):
    """Article update model"""
    title: Optional[str] = Field(None, description="Article title")
    content: Optional[str] = Field(None, description="Article content")
    status: Optional[ArticleStatus] = Field(None, description="Processing status")
    tags: Optional[List[str]] = Field(None, description="Article tags")

class Article(ArticleBase):
    """Full article model"""
    id: int = Field(..., description="Article ID")
    processing_status: str = Field(..., description="Processing status")
    created_at: datetime = Field(..., description="Creation timestamp")
    processing_completed_at: Optional[datetime] = Field(None, description="Processing timestamp")
    
    # Analysis results
    summary: Optional[str] = Field(None, description="AI-generated summary")
    quality_score: Optional[float] = Field(None, description="Quality score")
    ml_data: Optional[Dict[str, Any]] = Field(None, description="ML analysis data")
    
    class Config:
        from_attributes = True

class ArticleList(BaseModel):
    """Article list response model"""
    articles: List[Article] = Field(..., description="List of articles")
    total: int = Field(..., description="Total number of articles")
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Articles per page")
    has_next: bool = Field(..., description="Has next page")
    has_prev: bool = Field(..., description="Has previous page")

class ArticleSearch(BaseModel):
    """Article search model"""
    query: str = Field(..., description="Search query")
    filters: Optional[Dict[str, Any]] = Field(None, description="Search filters")
    sort_by: Optional[SortField] = Field(SortField.CREATED_AT, description="Sort field")
    sort_order: Optional[SortOrder] = Field(SortOrder.DESC, description="Sort order")
    page: int = Field(1, description="Page number")
    per_page: int = Field(20, description="Items per page")

class ArticleAnalysis(BaseModel):
    """Article analysis model"""
    article_id: int = Field(..., description="Article ID")
    summary: str = Field(..., description="AI-generated summary")
    sentiment: float = Field(..., description="Sentiment score")
    entities: List[Dict[str, Any]] = Field(..., description="Extracted entities")
    tags: List[str] = Field(..., description="Generated tags")
    relevance_score: float = Field(..., description="Relevance score")
    processing_time: float = Field(..., description="Processing time in seconds")

@router.get("/", response_model=ArticleList)
async def get_articles(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Articles per page"),
    status: Optional[ArticleStatus] = Query(None, description="Filter by status"),
    source: Optional[str] = Query(None, description="Filter by source"),
    sort_by: SortField = Query(SortField.CREATED_AT, description="Sort field"),
    sort_order: SortOrder = Query(SortOrder.DESC, description="Sort order"),
    search: Optional[str] = Query(None, description="Search query")
):
    """
    Get articles with filtering, sorting, and pagination
    
    Returns a paginated list of articles with optional filtering and sorting
    """
    try:
        offset = (page - 1) * per_page
        
        # Build query
        where_conditions = []
        params = []
        
        if status:
            where_conditions.append("status = %s")
            params.append(status.value)
        
        if source:
            where_conditions.append("source ILIKE %s")
            params.append(f"%{source}%")
        
        if search:
            where_conditions.append("(title ILIKE %s OR content ILIKE %s)")
            params.extend([f"%{search}%", f"%{search}%"])
        
        where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        # Get total count
        count_query = f"SELECT COUNT(*) FROM articles {where_clause}"
        conn = await get_db_connection()
        cursor = conn.cursor()
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]
        
        # Get articles
        order_clause = f"ORDER BY {sort_by.value} {sort_order.value.upper()}"
        articles_query = f"""
            SELECT 
                id, title, content, url, source, published_date,
                processing_status, created_at, processing_completed_at, processing_completed_at,
                summary, quality_score, ml_data, ml_data, quality_score
            FROM articles 
            {where_clause}
            {order_clause}
            LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        cursor.execute(articles_query, params)
        
        articles = []
        for row in cursor.fetchall():
            articles.append(Article(
                id=row[0],
                title=row[1],
                content=row[2],
                url=row[3],
                source=row[4],
                published_date=row[5],
                processing_status=row[6],
                created_at=row[7],
                processing_completed_at=row[8],
                summary=row[10],
                quality_score=row[11],
                ml_data=row[12] if row[12] else {}
            ))
        
        cursor.close()
        conn.close()
        
        return ArticleList(
            articles=articles,
            total=total,
            page=page,
            per_page=per_page,
            has_next=offset + per_page < total,
            has_prev=page > 1
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get articles: {str(e)}"
        )

@router.get("/{article_id}", response_model=Article)
async def get_article(
    article_id: int = Path(..., description="Article ID")
):
    """
    Get a specific article by ID
    
    Returns detailed information about a single article
    """
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                id, title, content, url, source, published_date,
                status, created_at, processed_at, ml_processed_at,
                summary, sentiment, entities, tags, relevance_score
            FROM articles 
            WHERE id = %s
        """, (article_id,))
        
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not row:
            raise HTTPException(
                status_code=404,
                detail="Article not found"
            )
        
        return Article(
            id=row[0],
            title=row[1],
            content=row[2],
            url=row[3],
            source=row[4],
            published_date=row[5],
            status=ArticleStatus(row[6]),
            created_at=row[7],
            processed_at=row[8],
            ml_processed_at=row[9],
            summary=row[10],
            sentiment=row[11],
            entities=row[12] if row[12] else [],
            tags=row[13] if row[13] else [],
            relevance_score=row[14]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get article: {str(e)}"
        )

@router.post("/", response_model=Article)
async def create_article(article: ArticleCreate):
    """
    Create a new article
    
    Adds a new article to the system for processing
    """
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO articles (
                title, content, url, source, published_date, status, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            article.title,
            article.content,
            article.url,
            article.source,
            article.published_date,
            ArticleStatus.PENDING.value,
            datetime.utcnow()
        ))
        
        article_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        
        # Return the created article
        return await get_article(article_id)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create article: {str(e)}"
        )

@router.put("/{article_id}", response_model=Article)
async def update_article(
    article_id: int = Path(..., description="Article ID"),
    article_update: ArticleUpdate = None
):
    """
    Update an existing article
    
    Updates article information and processing status
    """
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Check if article exists
        cursor.execute("SELECT id FROM articles WHERE id = %s", (article_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=404,
                detail="Article not found"
            )
        
        # Build update query
        update_fields = []
        params = []
        
        if article_update.title is not None:
            update_fields.append("title = %s")
            params.append(article_update.title)
        
        if article_update.content is not None:
            update_fields.append("content = %s")
            params.append(article_update.content)
        
        if article_update.status is not None:
            update_fields.append("status = %s")
            params.append(article_update.status.value)
        
        if article_update.tags is not None:
            update_fields.append("tags = %s")
            params.append(article_update.tags)
        
        if update_fields:
            update_fields.append("updated_at = %s")
            params.append(datetime.utcnow())
            params.append(article_id)
            
            cursor.execute(f"""
                UPDATE articles 
                SET {', '.join(update_fields)}
                WHERE id = %s
            """, params)
            
            conn.commit()
        
        cursor.close()
        conn.close()
        
        # Return updated article
        return await get_article(article_id)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update article: {str(e)}"
        )

@router.delete("/{article_id}")
async def delete_article(
    article_id: int = Path(..., description="Article ID")
):
    """
    Delete an article
    
    Removes an article from the system
    """
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM articles WHERE id = %s", (article_id,))
        
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Article not found"
            )
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {"message": "Article deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete article: {str(e)}"
        )

@router.post("/search", response_model=ArticleList)
async def search_articles(search: ArticleSearch):
    """
    Advanced article search with RAG enhancement
    
    Performs semantic search with optional filters and sorting
    """
    try:
        # This would integrate with RAG search capabilities
        # For now, implement basic text search
        
        offset = (search.page - 1) * search.per_page
        
        # Build search query
        where_conditions = []
        params = []
        
        if search.query:
            where_conditions.append("(title ILIKE %s OR content ILIKE %s OR summary ILIKE %s)")
            params.extend([f"%{search.query}%", f"%{search.query}%", f"%{search.query}%"])
        
        if search.filters:
            if "status" in search.filters:
                where_conditions.append("status = %s")
                params.append(search.filters["status"])
            
            if "source" in search.filters:
                where_conditions.append("source ILIKE %s")
                params.append(f"%{search.filters['source']}%")
            
            if "date_from" in search.filters:
                where_conditions.append("created_at >= %s")
                params.append(search.filters["date_from"])
            
            if "date_to" in search.filters:
                where_conditions.append("created_at <= %s")
                params.append(search.filters["date_to"])
        
        where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        # Get total count
        count_query = f"SELECT COUNT(*) FROM articles {where_clause}"
        conn = await get_db_connection()
        cursor = conn.cursor()
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]
        
        # Get articles
        order_clause = f"ORDER BY {search.sort_by.value} {search.sort_order.value.upper()}"
        articles_query = f"""
            SELECT 
                id, title, content, url, source, published_date,
                status, created_at, processed_at, ml_processed_at,
                summary, sentiment, entities, tags, relevance_score
            FROM articles 
            {where_clause}
            {order_clause}
            LIMIT %s OFFSET %s
        """
        params.extend([search.per_page, offset])
        cursor.execute(articles_query, params)
        
        articles = []
        for row in cursor.fetchall():
            articles.append(Article(
                id=row[0],
                title=row[1],
                content=row[2],
                url=row[3],
                source=row[4],
                published_date=row[5],
                processing_status=row[6],
                created_at=row[7],
                processing_completed_at=row[8],
                summary=row[10],
                quality_score=row[11],
                ml_data=row[12] if row[12] else {}
            ))
        
        cursor.close()
        conn.close()
        
        return ArticleList(
            articles=articles,
            total=total,
            page=search.page,
            per_page=search.per_page,
            has_next=offset + search.per_page < total,
            has_prev=search.page > 1
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to search articles: {str(e)}"
        )

@router.post("/{article_id}/analyze", response_model=ArticleAnalysis)
async def analyze_article(
    article_id: int = Path(..., description="Article ID")
):
    """
    Trigger AI analysis for an article
    
    Processes an article through the ML pipeline for analysis
    """
    try:
        # Get article
        article = await get_article(article_id)
        
        # Trigger ML analysis
        from modules.ml.ml_pipeline import MLPipeline
        pipeline = MLPipeline()
        
        start_time = time.time()
        analysis_result = await pipeline.analyze_article(article)
        processing_time = time.time() - start_time
        
        # Update article with analysis results
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE articles 
            SET 
                summary = %s,
                sentiment = %s,
                entities = %s,
                tags = %s,
                relevance_score = %s,
                ml_processed_at = %s,
                status = %s
            WHERE id = %s
        """, (
            analysis_result.get("summary"),
            analysis_result.get("sentiment"),
            analysis_result.get("entities"),
            analysis_result.get("tags"),
            analysis_result.get("relevance_score"),
            datetime.utcnow(),
            ArticleStatus.PROCESSED.value,
            article_id
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return ArticleAnalysis(
            article_id=article_id,
            summary=analysis_result.get("summary", ""),
            sentiment=analysis_result.get("sentiment", 0.0),
            entities=analysis_result.get("entities", []),
            tags=analysis_result.get("tags", []),
            relevance_score=analysis_result.get("relevance_score", 0.0),
            processing_time=processing_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze article: {str(e)}"
        )

@router.get("/{article_id}/related")
async def get_related_articles(
    article_id: int = Path(..., description="Article ID"),
    limit: int = Query(10, ge=1, le=50, description="Number of related articles")
):
    """
    Get related articles
    
    Returns articles related to the specified article
    """
    try:
        # Get the target article
        article = await get_article(article_id)
        
        # Find related articles based on tags, entities, or content similarity
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Simple implementation: find articles with similar tags
        if article.tags:
            tag_conditions = " OR ".join(["tags @> %s" for _ in article.tags])
            tag_params = [f'["{tag}"]' for tag in article.tags]
            
            cursor.execute(f"""
                SELECT 
                    id, title, content, url, source, published_date,
                    status, created_at, processed_at, ml_processed_at,
                    summary, sentiment, entities, tags, relevance_score
                FROM articles 
                WHERE id != %s AND ({tag_conditions})
                ORDER BY created_at DESC
                LIMIT %s
            """, [article_id] + tag_params + [limit])
        else:
            # Fallback: get recent articles from same source
            cursor.execute("""
                SELECT 
                    id, title, content, url, source, published_date,
                    status, created_at, processed_at, ml_processed_at,
                    summary, sentiment, entities, tags, relevance_score
                FROM articles 
                WHERE id != %s AND source = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (article_id, article.source, limit))
        
        related_articles = []
        for row in cursor.fetchall():
            related_articles.append(Article(
                id=row[0],
                title=row[1],
                content=row[2],
                url=row[3],
                source=row[4],
                published_date=row[5],
                processing_status=row[6],
                created_at=row[7],
                processing_completed_at=row[8],
                summary=row[10],
                quality_score=row[11],
                ml_data=row[12] if row[12] else {}
            ))
        
        cursor.close()
        conn.close()
        
        return {"related_articles": related_articles}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get related articles: {str(e)}"
        )

@router.get("/stats/overview")
async def get_article_stats():
    """
    Get article statistics overview
    
    Returns comprehensive statistics about articles
    """
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Get various statistics
        stats = {}
        
        # Total articles
        cursor.execute("SELECT COUNT(*) FROM articles")
        stats["total_articles"] = cursor.fetchone()[0]
        
        # Articles by status
        cursor.execute("""
            SELECT status, COUNT(*) 
            FROM articles 
            GROUP BY status
        """)
        stats["by_status"] = dict(cursor.fetchall())
        
        # Articles by source
        cursor.execute("""
            SELECT source, COUNT(*) 
            FROM articles 
            GROUP BY source 
            ORDER BY COUNT(*) DESC 
            LIMIT 10
        """)
        stats["top_sources"] = dict(cursor.fetchall())
        
        # Articles by day (last 7 days)
        cursor.execute("""
            SELECT DATE(created_at) as date, COUNT(*) 
            FROM articles 
            WHERE created_at >= NOW() - INTERVAL '7 days'
            GROUP BY DATE(created_at)
            ORDER BY date
        """)
        stats["daily_counts"] = dict(cursor.fetchall())
        
        # Average sentiment
        cursor.execute("""
            SELECT AVG(sentiment) 
            FROM articles 
            WHERE sentiment IS NOT NULL
        """)
        result = cursor.fetchone()[0]
        stats["avg_sentiment"] = float(result) if result else 0.0
        
        cursor.close()
        conn.close()
        
        return stats
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get article stats: {str(e)}"
        )
