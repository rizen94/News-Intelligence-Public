"""
Bias Detection API Routes - Fixed with text() wrapper
Provides political bias analysis for articles and sources
"""

from fastapi import APIRouter, HTTPException, Query, Path, Depends
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
from schemas.robust_schemas import APIResponse
from config.database import get_db
from services.bias_detection_service import BiasDetectionService
from datetime import datetime, timedelta
import logging
import json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bias-detection", tags=["Bias Detection"])

@router.get("/sources", response_model=APIResponse)
async def get_source_bias_ratings(
    political_bias: Optional[str] = Query(None, description="Filter by political bias"),
    country: Optional[str] = Query(None, description="Filter by country"),
    db: Session = Depends(get_db)
):
    """Get source bias ratings"""
    try:
        # Get database connection using the correct pattern
        db_gen = get_db()
        db = next(db_gen)
        
        try:
            # Build query based on filters
            query = "SELECT * FROM source_bias_ratings WHERE 1=1"
            params = {}
            
            if political_bias:
                query += " AND political_bias = :political_bias"
                params['political_bias'] = political_bias
            
            if country:
                query += " AND country = :country"
                params['country'] = country
            
            query += " ORDER BY source_name"
            
            result = db.execute(text(query), params).fetchall()
            
            sources = []
            for row in result:
                sources.append({
                    "id": row[0],
                    "source_name": row[1],
                    "political_bias": row[2],
                    "bias_score": float(row[3]),
                    "credibility_score": float(row[4]),
                    "factuality_score": float(row[5]),
                    "source_type": row[6],
                    "country": row[7],
                    "description": row[8],
                    "created_at": row[9].isoformat() if row[9] else None,
                    "updated_at": row[10].isoformat() if row[10] else None
                })
            
            return APIResponse(
                success=True,
                data=sources,
                message=f"Retrieved {len(sources)} source bias ratings"
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error getting source bias ratings: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve source bias ratings")

@router.get("/summary", response_model=APIResponse)
async def get_bias_summary(
    days_back: int = Query(7, ge=1, le=30, description="Days back to analyze"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum articles to analyze"),
    db: Session = Depends(get_db)
):
    """Get bias summary for recent articles"""
    try:
        # Get database connection using the correct pattern
        db_gen = get_db()
        db = next(db_gen)
        
        try:
            cutoff_date = datetime.now() - timedelta(days=days_back)
            
            # Get recent articles
            articles_query = text("""
                SELECT id FROM articles 
                WHERE created_at >= :cutoff_date 
                ORDER BY created_at DESC 
                LIMIT :limit
            """)
            
            articles = db.execute(articles_query, {
                "cutoff_date": cutoff_date,
                "limit": limit
            }).fetchall()
            
            article_ids = [row[0] for row in articles]
            
            if not article_ids:
                return APIResponse(
                    success=True,
                    data={
                        "total_articles": 0,
                        "bias_distribution": {},
                        "average_bias_score": 0.0,
                        "sources_analyzed": {}
                    },
                    message="No articles found for analysis"
                )
            
            # Get bias summary
            service = BiasDetectionService(db)
            bias_summary = service.get_bias_summary(article_ids)
            
            # Get source distribution
            sources_query = text("""
                SELECT sbr.source_name, sbr.political_bias, COUNT(*) as count
                FROM article_bias_analysis aba
                JOIN source_bias_ratings sbr ON aba.source_bias_id = sbr.id
                WHERE aba.article_id = ANY(:article_ids)
                GROUP BY sbr.source_name, sbr.political_bias
                ORDER BY count DESC
            """)
            
            sources_result = db.execute(sources_query, {"article_ids": article_ids}).fetchall()
            
            sources_analyzed = {}
            for row in sources_result:
                source_name = row[0]
                political_bias = row[1]
                count = row[2]
                
                if source_name not in sources_analyzed:
                    sources_analyzed[source_name] = {
                        "political_bias": political_bias,
                        "article_count": count
                    }
                else:
                    sources_analyzed[source_name]["article_count"] += count
            
            bias_summary["sources_analyzed"] = sources_analyzed
            
            return APIResponse(
                success=True,
                data=bias_summary,
                message=f"Bias summary for {len(article_ids)} articles"
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error getting bias summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve bias summary")
