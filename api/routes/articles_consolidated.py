
"""
News Intelligence System v3.1.0 - Articles API
Consolidated articles management endpoints
"""

from fastapi import APIRouter, HTTPException, Query, Path
from typing import List, Optional, Dict, Any
from schemas.response_schemas import APIResponse
from schemas.article_schemas import Article, ArticleCreate, ArticleUpdate, ArticleSearch
from services.article_service import ArticleService
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/", response_model=APIResponse)
async def get_articles(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    source: Optional[str] = Query(None, description="Filter by source"),
    category: Optional[str] = Query(None, description="Filter by category"),
    status: Optional[str] = Query(None, description="Filter by status")
):
    """Get paginated list of articles with filters"""
    try:
        service = ArticleService()
        articles = await service.get_articles(
            page=page, limit=limit, source=source, 
            category=category, status=status
        )
        return APIResponse(
            success=True,
            data=articles,
            message=f"Retrieved {len(articles.get('items', []))} articles"
        )
    except Exception as e:
        logger.error(f"Error getting articles: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sources", response_model=APIResponse)
async def get_article_sources():
    """Get list of article sources"""
    try:
        service = ArticleService()
        sources = await service.get_sources()
        return APIResponse(
            success=True,
            data=sources,
            message="Article sources retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error getting sources: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/categories", response_model=APIResponse)
async def get_article_categories():
    """Get list of article categories"""
    try:
        service = ArticleService()
        categories = await service.get_categories()
        return APIResponse(
            success=True,
            data=categories,
            message="Article categories retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error getting categories: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{article_id}", response_model=APIResponse)
async def get_article(article_id: str = Path(..., description="Article ID")):
    """Get specific article by ID"""
    try:
        service = ArticleService()
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
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=APIResponse)
async def create_article(article_data: ArticleCreate):
    """Create new article"""
    try:
        service = ArticleService()
        article = await service.create_article(article_data)
        return APIResponse(
            success=True,
            data=article,
            message="Article created successfully"
        )
    except Exception as e:
        logger.error(f"Error creating article: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{article_id}", response_model=APIResponse)
async def update_article(
    article_id: str = Path(..., description="Article ID"),
    article_data: ArticleUpdate = None
):
    """Update existing article"""
    try:
        service = ArticleService()
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
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{article_id}", response_model=APIResponse)
async def delete_article(article_id: str = Path(..., description="Article ID")):
    """Delete article"""
    try:
        service = ArticleService()
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
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/search", response_model=APIResponse)
async def search_articles(search_data: ArticleSearch):
    """Search articles with advanced filters"""
    try:
        service = ArticleService()
        results = await service.search_articles(search_data)
        return APIResponse(
            success=True,
            data=results,
            message=f"Found {len(results.get('items', []))} articles"
        )
    except Exception as e:
        logger.error(f"Error searching articles: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{article_id}/analyze", response_model=APIResponse)
async def analyze_article(article_id: str = Path(..., description="Article ID")):
    """Trigger AI analysis for article"""
    try:
        service = ArticleService()
        analysis = await service.analyze_article(article_id)
        return APIResponse(
            success=True,
            data=analysis,
            message="Article analysis completed"
        )
    except Exception as e:
        logger.error(f"Error analyzing article {article_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{article_id}/related", response_model=APIResponse)
async def get_related_articles(article_id: str = Path(..., description="Article ID")):
    """Get related articles"""
    try:
        service = ArticleService()
        related = await service.get_related_articles(article_id)
        return APIResponse(
            success=True,
            data=related,
            message="Related articles retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error getting related articles for {article_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats/overview", response_model=APIResponse)
async def get_article_stats():
    """Get article statistics overview"""
    try:
        service = ArticleService()
        stats = await service.get_stats()
        return APIResponse(
            success=True,
            data=stats,
            message="Article statistics retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error getting article stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
