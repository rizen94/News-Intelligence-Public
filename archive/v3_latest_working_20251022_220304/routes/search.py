"""
News Intelligence System v3.0 - Search API
Search functionality for articles, storylines, and content
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from schemas.robust_schemas import APIResponse
from config.database import get_db_cursor
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["Search"])

@router.get("/", response_model=APIResponse)
async def search_content(
    q: str = Query(..., description="Search query"),
    type: str = Query("all", description="Search type: articles, storylines, all"),
    limit: int = Query(10, description="Maximum results to return"),
    offset: int = Query(0, description="Results offset")
):
    """Search across articles and storylines"""
    try:
        cursor = get_db_cursor()
        
        if type == "articles" or type == "all":
            # Search articles
            cursor.execute("""
                SELECT id, title, content, source, published_at, quality_score
                FROM articles 
                WHERE title ILIKE %s OR content ILIKE %s
                ORDER BY published_at DESC
                LIMIT %s OFFSET %s
            """, (f"%{q}%", f"%{q}%", limit, offset))
            articles = cursor.fetchall()
        else:
            articles = []
            
        if type == "storylines" or type == "all":
            # Search storylines
            cursor.execute("""
                SELECT id, title, summary, created_at, updated_at
                FROM storylines 
                WHERE title ILIKE %s OR summary ILIKE %s
                ORDER BY updated_at DESC
                LIMIT %s OFFSET %s
            """, (f"%{q}%", f"%{q}%", limit, offset))
            storylines = cursor.fetchall()
        else:
            storylines = []
            
        results = {
            "query": q,
            "type": type,
            "articles": [dict(row) for row in articles],
            "storylines": [dict(row) for row in storylines],
            "total_results": len(articles) + len(storylines)
        }
        
        cursor.close()
        
        return APIResponse(
            success=True,
            data=results,
            message=f"Found {results['total_results']} results for '{q}'"
        )
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
