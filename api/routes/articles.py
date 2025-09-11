"""
News Intelligence System v3.0 - Production Articles API
Robust, fully functional articles management endpoints
"""

from fastapi import APIRouter, HTTPException, Query, Path, Depends
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from schemas.robust_schemas import APIResponse
from schemas.generated_models import Article, RSSFeed, ArticleCreate, ArticleUpdate
from config.database import get_db
from services.article_service import ArticleService
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/articles", tags=["Articles"])

# Simple response models
class ArticleListResponse(BaseModel):
    articles: List[Article]
    total_count: int
    page: int
    limit: int
    total_pages: int

class ArticleStatsResponse(BaseModel):
    total_articles: int
    articles_by_source: Dict[str, int]
    articles_by_category: Dict[str, int]
    articles_by_status: Dict[str, int]
    recent_articles: int
    avg_quality_score: float

@router.get("/", response_model=APIResponse)
async def get_articles(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search in title and content"),
    source: Optional[str] = Query(None, description="Filter by source"),
    category: Optional[str] = Query(None, description="Filter by category"),
    status: Optional[str] = Query(None, description="Filter by status"),
    sort: Optional[str] = Query("created_at", description="Sort field"),
    sort_order: Optional[str] = Query("desc", description="Sort order (asc/desc)")
):
    """Get paginated list of articles with filters"""
    try:
        db_gen = get_db()
        db = next(db_gen)
        try:
            offset = (page - 1) * limit
            
            # Build WHERE clause
            where_conditions = []
            params = {"limit": limit, "offset": offset}
            
            if search:
                where_conditions.append("(title ILIKE :search OR content ILIKE :search)")
                params["search"] = f"%{search}%"
            if source:
                where_conditions.append("source = :source")
                params["source"] = source
            if category:
                where_conditions.append("category = :category")
                params["category"] = category
            if status:
                where_conditions.append("status = :status")
                params["status"] = status
                
            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
            
            # Build ORDER BY clause
            valid_sort_fields = {
                "created_at": "created_at",
                "published_at": "published_at", 
                "title": "title",
                "quality_score": "quality_score",
                "source": "source",
                "category": "category"
            }
            
            sort_field = valid_sort_fields.get(sort, "created_at")
            sort_direction = "ASC" if sort_order.lower() == "asc" else "DESC"
            order_clause = f"{sort_field} {sort_direction}"
            
            # Get articles
            articles_query = text(f"""
                SELECT id, title, content, url, published_at, source, tags, created_at, updated_at,
                       sentiment_score, entities, readability_score, quality_score,
                       summary, ml_data, language, word_count, reading_time, feed_id
                FROM articles 
                WHERE {where_clause}
                ORDER BY {order_clause}
                LIMIT :limit OFFSET :offset
            """)
            
            articles_result = db.execute(articles_query, params).fetchall()
            
            # Get total count
            count_query = text(f"SELECT COUNT(*) FROM articles WHERE {where_clause}")
            count_result = db.execute(count_query, params).fetchone()
            total_count = count_result[0] if count_result else 0
            
            articles = []
            for row in articles_result:
                articles.append({
                    "id": row[0],
                    "title": row[1],
                    "content": row[2],
                    "url": row[3],
                    "published_at": row[4].isoformat() if row[4] else None,
                    "source": row[5],
                    "tags": row[6],
                    "created_at": row[7].isoformat() if row[7] else None,
                    "updated_at": row[8].isoformat() if row[8] else None,
                    "sentiment_score": float(row[9]) if row[9] is not None else None,
                    "entities": row[10] if row[10] else {},
                    "readability_score": float(row[11]) if row[11] is not None else None,
                    "quality_score": float(row[12]) if row[12] is not None else None,
                    "summary": row[13],
                    "ml_data": row[14] if row[14] else {},
                    "language": row[15],
                    "word_count": row[16] if row[16] else 0,
                    "reading_time": row[17] if row[17] else 0,
                    "feed_id": row[18]
                })
            
            return APIResponse(
                success=True,
                data={
                    "articles": articles,
                    "total_count": total_count,
                    "page": page,
                    "limit": limit,
                    "total_pages": (total_count + limit - 1) // limit
                },
                message=f"Retrieved {len(articles)} articles"
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error getting articles: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve articles: {str(e)}")

@router.get("/sources", response_model=APIResponse)
async def get_article_sources():
    """Get list of article sources"""
    try:
        db_gen = get_db()
        db = next(db_gen)
        try:
            result = db.execute(text("""
                SELECT DISTINCT source, COUNT(*) as count 
                FROM articles 
                WHERE source IS NOT NULL 
                GROUP BY source 
                ORDER BY count DESC
            """)).fetchall()
            
            sources = [{"source": row[0], "count": row[1]} for row in result]
            
            return APIResponse(
                success=True,
                data={"sources": sources},
                message="Article sources retrieved successfully"
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error getting article sources: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve article sources")

@router.get("/categories", response_model=APIResponse)
async def get_article_categories(db: Session = Depends(get_db)):
    """Get list of article categories"""
    try:
        # For now, return a static list of categories
        categories = [
            "Global Events", "Business", "Politics", "Technology", "Health",
            "Science", "Sports", "Entertainment", "World News", "Local News"
        ]
        return APIResponse(
            success=True,
            data={"categories": categories},
            message="Article categories retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error getting article categories: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve article categories")

@router.get("/stats/overview", response_model=APIResponse)
async def get_article_stats_overview(db: Session = Depends(get_db)):
    """Get article statistics overview"""
    try:
        service = ArticleService(db)
        stats = await service.get_stats()
        return APIResponse(
            success=True,
            data=stats,
            message="Article statistics retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error getting article stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve article statistics")

@router.get("/{article_id}", response_model=APIResponse)
async def get_article_by_id(
    article_id: str = Path(..., description="Article ID"),
    db: Session = Depends(get_db)
):
    """Get article by ID"""
    try:
        service = ArticleService(db)
        article = await service.get_article(article_id)
        
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        
        return APIResponse(
            success=True,
            data=article,
            message="Article retrieved successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting article {article_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve article")

@router.post("/", response_model=APIResponse)
async def create_article(
    article: ArticleCreate,
    db: Session = Depends(get_db)
):
    """Create new article"""
    try:
        service = ArticleService(db)
        result = await service.create_article(article.dict())
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return APIResponse(
            success=True,
            data=result,
            message="Article created successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating article: {e}")
        raise HTTPException(status_code=500, detail="Failed to create article")

@router.put("/{article_id}", response_model=APIResponse)
async def update_article(
    article_id: str = Path(..., description="Article ID"),
    article: ArticleUpdate = None,
    db: Session = Depends(get_db)
):
    """Update article"""
    try:
        service = ArticleService(db)
        result = await service.update_article(article_id, article.dict())
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return APIResponse(
            success=True,
            data=result,
            message="Article updated successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating article {article_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update article")

@router.delete("/{article_id}", response_model=APIResponse)
async def delete_article(
    article_id: str = Path(..., description="Article ID"),
    db: Session = Depends(get_db)
):
    """Delete article"""
    try:
        service = ArticleService(db)
        result = await service.delete_article(article_id)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return APIResponse(
            success=True,
            data=result,
            message="Article deleted successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting article {article_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete article")
