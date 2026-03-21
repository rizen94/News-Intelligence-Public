#!/usr/bin/env python3
"""
Storyline Analysis Routes
RAG analysis, proactive detection, and advanced analysis features
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Path, Query, Depends
from typing import Optional
from shared.domain_registry import DOMAIN_PATH_PATTERN
import logging

from shared.services.domain_aware_service import validate_domain
from ..services.rag_analysis_service import RAGAnalysisService
from ..services.proactive_detection_service import ProactiveDetectionService
from ..schemas.storyline_schemas import EmergingStorylinesResponse, EmergingStoryline

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Storyline Analysis"],
    responses={404: {"description": "Not found"}}
)


async def validate_domain_dependency(domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN)) -> str:
    """Dependency to validate domain"""
    if not validate_domain(domain):
        raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
    return domain


# ============================================================================
# Emerging Storylines (must be before {storyline_id} routes)
# ============================================================================

@router.get("/{domain}/storylines/emerging", response_model=EmergingStorylinesResponse)
async def get_domain_emerging_storylines(
    domain: str = Depends(validate_domain_dependency),
    hours: int = Query(24, ge=1, le=168, description="Hours to look back"),
    min_articles: int = Query(3, ge=2, le=20, description="Minimum articles for storyline")
):
    """Get emerging storylines - Route order critical: must be before {storyline_id} routes"""
    try:
        detection_service = ProactiveDetectionService(domain=domain)
        result = await detection_service.detect_emerging_storylines(hours, min_articles)
        
        if result.get("success"):
            data = result.get("data", {})
            emerging_list = []
            for es in data.get("emerging_storylines", []):
                emerging_list.append(EmergingStoryline(
                    title=es.get("title", ""),
                    description=es.get("description", ""),
                    article_count=es.get("article_count", 0),
                    confidence_score=es.get("confidence_score", 0.0),
                    keywords=es.get("keywords", []),
                    article_ids=es.get("article_ids", [])
                ))
            
            return EmergingStorylinesResponse(
                emerging_storylines=emerging_list,
                articles_analyzed=data.get("articles_analyzed", 0),
                clusters_found=data.get("clusters_found", 0)
            )
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Detection failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error detecting emerging storylines: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{domain}/storylines/detect")
async def detect_domain_storylines(
    domain: str = Depends(validate_domain_dependency),
    hours: int = Query(24, ge=1, le=168),
    min_articles: int = Query(3, ge=2, le=20)
):
    """Detect and create new storylines from recent articles"""
    try:
        detection_service = ProactiveDetectionService(domain=domain)
        result = await detection_service.detect_emerging_storylines(hours, min_articles)
        
        if result.get("success"):
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Detection failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error detecting storylines: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# RAG Analysis
# ============================================================================

@router.get("/{domain}/storylines/{storyline_id}/report")
async def get_domain_storyline_report(
    domain: str = Depends(validate_domain_dependency),
    storyline_id: int = Path(..., description="Storyline ID", ge=1),
    report_type: str = Query("comprehensive", pattern="^(comprehensive|executive|summary)$")
):
    """Get comprehensive storyline report"""
    try:
        rag_service = RAGAnalysisService(domain=domain)
        result = await rag_service.generate_storyline_report(storyline_id, report_type)
        
        if result.get("success"):
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Report generation failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{domain}/storylines/{storyline_id}/analyze")
async def analyze_domain_storyline(
    domain: str = Depends(validate_domain_dependency),
    storyline_id: int = Path(..., description="Storyline ID", ge=1),
    background_tasks: BackgroundTasks = None,
):
    """Queue comprehensive storyline analysis (RAG-style pipeline); workers process the queue — not ad-hoc HTTP LLM."""
    try:
        from datetime import datetime
        from shared.database.connection import get_db_connection
        from services.content_refinement_queue_service import (
            enqueue_content_refinement,
            JOB_COMPREHENSIVE_RAG,
        )

        schema = domain.replace("-", "_")

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT 1 FROM {schema}.storylines WHERE id = %s",
                    (storyline_id,),
                )
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Storyline not found")
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.storyline_articles sa
                    JOIN {schema}.articles a ON a.id = sa.article_id
                    WHERE sa.storyline_id = %s
                      AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                    """,
                    (storyline_id,),
                )
                article_count = int(cur.fetchone()[0] or 0)
                if article_count == 0:
                    raise HTTPException(status_code=400, detail="No articles in storyline")
        finally:
            conn.close()

        enq = enqueue_content_refinement(
            domain, storyline_id, JOB_COMPREHENSIVE_RAG, priority="medium"
        )
        if not enq.get("success"):
            raise HTTPException(
                status_code=500,
                detail=enq.get("error", "Failed to queue analysis"),
            )

        _ = background_tasks  # legacy param; queue replaces FastAPI BackgroundTasks

        return {
            "success": True,
            "message": enq.get("message", "Queued for background processing"),
            "storyline_id": storyline_id,
            "articles_count": article_count,
            "queue_id": enq.get("queue_id"),
            "already_queued": enq.get("already_queued", False),
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting storyline analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{domain}/storylines/{storyline_id}/rag_analysis")
async def perform_domain_rag_analysis(
    domain: str = Depends(validate_domain_dependency),
    storyline_id: int = Path(..., description="Storyline ID", ge=1),
    background_tasks: BackgroundTasks = None,
):
    """Queue comprehensive storyline analysis (same worker job as POST .../analyze)."""
    try:
        from shared.database.connection import get_db_connection
        from services.content_refinement_queue_service import (
            enqueue_content_refinement,
            JOB_COMPREHENSIVE_RAG,
        )

        schema = domain.replace("-", "_")
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT 1 FROM {schema}.storylines WHERE id = %s",
                    (storyline_id,),
                )
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Storyline not found")
        finally:
            conn.close()

        enq = enqueue_content_refinement(
            domain, storyline_id, JOB_COMPREHENSIVE_RAG, priority="medium"
        )
        if not enq.get("success"):
            raise HTTPException(
                status_code=500,
                detail=enq.get("error", "Failed to queue analysis"),
            )
        _ = background_tasks
        return {
            "success": True,
            "message": enq.get("message", "Queued for background processing"),
            "storyline_id": storyline_id,
            "queue_id": enq.get("queue_id"),
            "already_queued": enq.get("already_queued", False),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error performing RAG analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/storylines/{storyline_id}/correlations")
async def get_domain_storyline_correlations(
    domain: str = Depends(validate_domain_dependency),
    storyline_id: int = Path(..., description="Storyline ID", ge=1)
):
    """Get correlations with other storylines"""
    try:
        rag_service = RAGAnalysisService(domain=domain)
        result = await rag_service.find_storyline_correlations(storyline_id)
        
        if result.get("success"):
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Correlation analysis failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finding correlations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/storylines/{storyline_id}/predict")
async def predict_domain_storyline_developments(
    domain: str = Depends(validate_domain_dependency),
    storyline_id: int = Path(..., description="Storyline ID", ge=1)
):
    """Predict potential future developments in storyline"""
    try:
        detection_service = ProactiveDetectionService(domain=domain)
        result = await detection_service.predict_story_developments(storyline_id)
        
        if result.get("success"):
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Prediction failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error predicting developments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/storylines/correlations")
async def get_domain_storyline_correlations_all(
    domain: str = Depends(validate_domain_dependency)
):
    """Get correlations between all storylines in domain"""
    try:
        detection_service = ProactiveDetectionService(domain=domain)
        result = await detection_service.identify_story_correlations()
        
        if result.get("success"):
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Correlation analysis failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finding correlations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

