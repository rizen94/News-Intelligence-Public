#!/usr/bin/env python3
"""
Storyline Helper Routes
Supporting endpoints (suggestions, timeline, validation, improvements)
"""

from fastapi import APIRouter, HTTPException, Path, Query, Depends
from typing import Optional
from shared.domain_registry import DOMAIN_PATH_PATTERN
from datetime import datetime, timedelta
import logging

from shared.database.connection import get_db_connection
from shared.services.domain_aware_service import validate_domain
from ..services.quality_assessment_service import QualityAssessmentService

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Storyline Helpers"],
    responses={404: {"description": "Not found"}}
)


async def validate_domain_dependency(domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN)) -> str:
    """Dependency to validate domain"""
    if not validate_domain(domain):
        raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
    return domain


def _parse_json_col(val):
    """Parse JSON/JSONB column to dict or list."""
    if val is None:
        return {} if isinstance(val, dict) else []
    if isinstance(val, (dict, list)):
        return val
    try:
        import json
        return json.loads(val) if isinstance(val, str) else val
    except (TypeError, ValueError):
        return {} if isinstance(val, dict) else []


# NOTE: GET .../timeline is implemented in storyline_timeline.py (public.chronological_events).


@router.get("/{domain}/storylines/{storyline_id}/suggestions")
async def get_domain_storyline_suggestions(
    domain: str = Depends(validate_domain_dependency),
    storyline_id: int = Path(..., description="Storyline ID", ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """Get article suggestions for a storyline"""
    try:
        schema = domain.replace('-', '_')
        
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Get storyline
                cur.execute(f"SELECT id, title FROM {schema}.storylines WHERE id = %s", (storyline_id,))
                storyline = cur.fetchone()
                if not storyline:
                    raise HTTPException(status_code=404, detail="Storyline not found")
                
                # Get recent articles not in storyline
                cur.execute(f"""
                    SELECT a.id, a.title, a.summary, a.published_at, a.source_domain
                    FROM {schema}.articles a
                    WHERE a.id NOT IN (
                        SELECT sa.article_id 
                        FROM {schema}.storyline_articles sa 
                        WHERE sa.storyline_id = %s
                    )
                    AND a.published_at >= %s
                    ORDER BY a.published_at DESC
                    LIMIT %s
                """, (storyline_id, datetime.now() - timedelta(days=7), limit))
                
                related_articles = cur.fetchall()
                
                return {
                    "success": True,
                    "data": {
                        "storyline_title": storyline[1],
                        "suggested_articles": [
                            {
                                "id": row[0],
                                "title": row[1],
                                "summary": row[2],
                                "published_at": row[3].isoformat() if row[3] else None,
                                "source_domain": row[4]
                            }
                            for row in related_articles
                        ]
                    },
                    "storyline_id": storyline_id,
                    "suggestions_count": len(related_articles),
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/storylines/{storyline_id}/validate_accuracy")
async def validate_domain_storyline_accuracy(
    domain: str = Depends(validate_domain_dependency),
    storyline_id: int = Path(..., description="Storyline ID", ge=1)
):
    """Validate factual accuracy of storyline"""
    try:
        quality_service = QualityAssessmentService(domain=domain)
        result = await quality_service.validate_factual_accuracy(storyline_id)
        
        if result.get("success"):
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Validation failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating accuracy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/storylines/{storyline_id}/suggestions_improvements")
async def get_domain_storyline_improvements(
    domain: str = Depends(validate_domain_dependency),
    storyline_id: int = Path(..., description="Storyline ID", ge=1)
):
    """Get suggestions for improving storyline"""
    try:
        quality_service = QualityAssessmentService(domain=domain)
        result = await quality_service.suggest_improvements(storyline_id)
        
        if result.get("success"):
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to get suggestions"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting improvement suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

