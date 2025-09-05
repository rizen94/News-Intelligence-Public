"""
News Intelligence System v3.1.0 - Production Articles API
Robust, fully functional articles management endpoints
"""

from fastapi import APIRouter, HTTPException, Query, Path, Depends
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from schemas.robust_schemas import (
    APIResponse, Article, ArticleCreate, ArticleUpdate, ArticleSearch,
    ArticleList, ArticleStats, SearchRequest, SearchResult
)
from services.article_service import ArticleService
from database.connection import get_db
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/articles", tags=["Articles"])

@router.get("/", response_model=APIResponse)
async def get_articles(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    source: Optional[str] = Query(None, description="Filter by source"),
    category: Optional[str] = Query(None, description="Filter by category"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db)
):
    """Get paginated list of articles with filters"""
    try:
        service = ArticleService(db)
        result = await service.get_articles(
            page=page, limit=limit, source=source, 
            category=category, status=status
        )
        return APIResponse(
            success=True,
            data=result,
            message=f"Retrieved {result.total} articles"
        )
    except Exception as e:
        logger.error(f"Error getting articles: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve articles")

@router.get("/sources", response_model=APIResponse)
async def get_article_sources(db: Session = Depends(get_db)):
    """Get list of article sources"""
    try:
        service = ArticleService(db)
        sources = await service.get_sources()
        return APIResponse(
            success=True,
            data=sources,
            message="Article sources retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error getting sources: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve sources")

@router.get("/categories", response_model=APIResponse)
async def get_article_categories(db: Session = Depends(get_db)):
    """Get list of article categories"""
    try:
        service = ArticleService(db)
        categories = await service.get_categories()
        return APIResponse(
            success=True,
            data=categories,
            message="Article categories retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error getting categories: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve categories")

@router.get("/{article_id}", response_model=APIResponse)
async def get_article(
    article_id: str = Path(..., description="Article ID"),
    db: Session = Depends(get_db)
):
    """Get specific article by ID"""
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
    article_data: ArticleCreate,
    db: Session = Depends(get_db)
):
    """Create new article"""
    try:
        service = ArticleService(db)
        article = await service.create_article(article_data)
        return APIResponse(
            success=True,
            data=article,
            message="Article created successfully"
        )
    except Exception as e:
        logger.error(f"Error creating article: {e}")
        raise HTTPException(status_code=500, detail="Failed to create article")

@router.put("/{article_id}", response_model=APIResponse)
async def update_article(
    article_id: str = Path(..., description="Article ID"),
    article_data: ArticleUpdate = None,
    db: Session = Depends(get_db)
):
    """Update existing article"""
    try:
        service = ArticleService(db)
        article = await service.update_article(article_id, article_data)
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        return APIResponse(
            success=True,
            data=article,
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
        success = await service.delete_article(article_id)
        if not success:
            raise HTTPException(status_code=404, detail="Article not found")
        return APIResponse(
            success=True,
            data=None,
            message="Article deleted successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting article {article_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete article")

@router.post("/search", response_model=APIResponse)
async def search_articles(
    search_data: ArticleSearch,
    db: Session = Depends(get_db)
):
    """Search articles with advanced filters"""
    try:
        service = ArticleService(db)
        results = await service.search_articles(search_data)
        return APIResponse(
            success=True,
            data=results,
            message=f"Found {results.total} articles"
        )
    except Exception as e:
        logger.error(f"Error searching articles: {e}")
        raise HTTPException(status_code=500, detail="Failed to search articles")

@router.post("/{article_id}/analyze", response_model=APIResponse)
async def analyze_article(
    article_id: str = Path(..., description="Article ID"),
    db: Session = Depends(get_db)
):
    """Trigger AI analysis for article"""
    try:
        service = ArticleService(db)
        analysis = await service.analyze_article(article_id)
        return APIResponse(
            success=True,
            data=analysis,
            message="Article analysis completed"
        )
    except Exception as e:
        logger.error(f"Error analyzing article {article_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to analyze article")

@router.get("/{article_id}/related", response_model=APIResponse)
async def get_related_articles(
    article_id: str = Path(..., description="Article ID"),
    limit: int = Query(10, ge=1, le=50, description="Number of related articles"),
    db: Session = Depends(get_db)
):
    """Get related articles"""
    try:
        service = ArticleService(db)
        related = await service.get_related_articles(article_id, limit)
        return APIResponse(
            success=True,
            data=related,
            message=f"Retrieved {len(related)} related articles"
        )
    except Exception as e:
        logger.error(f"Error getting related articles for {article_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get related articles")

@router.get("/stats/overview", response_model=APIResponse)
async def get_article_stats(db: Session = Depends(get_db)):
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
        raise HTTPException(status_code=500, detail="Failed to get article statistics")
