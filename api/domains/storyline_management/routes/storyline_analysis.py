#!/usr/bin/env python3
"""
Storyline Analysis Routes
RAG analysis, proactive detection, and advanced analysis features
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Path, Query, Depends
from typing import Optional
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


async def validate_domain_dependency(domain: str = Path(..., pattern="^(politics|finance|science-tech)$")) -> str:
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
    background_tasks: BackgroundTasks = None
):
    """Generate comprehensive storyline analysis using RAG in a specific domain"""
    try:
        from shared.database.connection import get_db_connection
        from datetime import datetime
        
        schema = domain.replace('-', '_')
        
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Get storyline and articles from domain schema
                cur.execute(f"""
                    SELECT s.title, s.description, s.analysis_summary
                    FROM {schema}.storylines s
                    WHERE s.id = %s
                """, (storyline_id,))
                
                storyline = cur.fetchone()
                if not storyline:
                    raise HTTPException(status_code=404, detail="Storyline not found")
                
                cur.execute(f"""
                    SELECT a.id, a.title, a.content, a.summary, a.published_at, a.source_domain, a.url
                    FROM {schema}.articles a
                    JOIN {schema}.storyline_articles sa ON a.id = sa.article_id
                    WHERE sa.storyline_id = %s
                      AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                    ORDER BY a.published_at ASC
                """, (storyline_id,))
                
                articles = cur.fetchall()
                
                if not articles:
                    raise HTTPException(status_code=400, detail="No articles in storyline")
                
                # Start comprehensive analysis in background
                if background_tasks:
                    # Import the background task function
                    from ..routes.storyline_management import process_storyline_rag_analysis
                    
                    # Trigger comprehensive processing (summary + timeline + breakdown)
                    background_tasks.add_task(
                        process_storyline_rag_analysis,
                        domain,
                        storyline_id,
                        storyline,
                        articles
                    )
                else:
                    # Run synchronously if no background tasks
                    rag_service = RAGAnalysisService(domain=domain)
                    result = await rag_service.perform_comprehensive_analysis(storyline_id)
                    if not result.get("success"):
                        raise HTTPException(status_code=500, detail=result.get("error", "Analysis failed"))
                
                return {
                    "success": True,
                    "message": "Storyline RAG analysis started",
                    "storyline_id": storyline_id,
                    "articles_count": len(articles),
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting storyline analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{domain}/storylines/{storyline_id}/rag_analysis")
async def perform_domain_rag_analysis(
    domain: str = Depends(validate_domain_dependency),
    storyline_id: int = Path(..., description="Storyline ID", ge=1),
    background_tasks: BackgroundTasks = None
):
    """Perform comprehensive RAG analysis"""
    try:
        rag_service = RAGAnalysisService(domain=domain)
        
        # Run in background for long-running analysis
        if background_tasks:
            from ..routes.storyline_management import perform_rag_analysis_background
            background_tasks.add_task(perform_rag_analysis_background, domain, storyline_id)
            return {
                "success": True,
                "message": "RAG analysis started in background",
                "storyline_id": storyline_id
            }
        else:
            result = await rag_service.perform_comprehensive_analysis(storyline_id)
            if result.get("success"):
                return result
            else:
                raise HTTPException(status_code=500, detail=result.get("error", "RAG analysis failed"))
            
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

