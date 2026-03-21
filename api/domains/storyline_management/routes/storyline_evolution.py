#!/usr/bin/env python3
"""
Storyline Evolution Routes
Intelligent storyline evolution and quality assessment
"""

from fastapi import APIRouter, HTTPException, Path, Query, Depends
from typing import Optional
from shared.domain_registry import DOMAIN_PATH_PATTERN
import logging

from shared.services.domain_aware_service import validate_domain
from ..services.storyline_service import StorylineService
from ..services.quality_assessment_service import QualityAssessmentService
from ..schemas.storyline_schemas import (
    StorylineEvolutionRequest,
    EvolutionResult,
    QualityAssessmentResult
)

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Storyline Evolution"],
    responses={404: {"description": "Not found"}}
)


async def validate_domain_dependency(domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN)) -> str:
    """Dependency to validate domain"""
    if not validate_domain(domain):
        raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
    return domain


@router.post("/{domain}/storylines/{storyline_id}/evolve", response_model=EvolutionResult)
async def evolve_domain_storyline(
    domain: str = Depends(validate_domain_dependency),
    storyline_id: int = Path(..., description="Storyline ID", ge=1),
    request: Optional[StorylineEvolutionRequest] = None,
    force_evolution: bool = Query(False, description="Force evolution even if recent")
):
    """Evolve storyline with new content"""
    try:
        storyline_service = StorylineService(domain=domain)
        
        new_article_ids = request.new_article_ids if request else None
        force = request.force_evolution if request else force_evolution
        
        result = await storyline_service.evolve_storyline_with_new_content(
            storyline_id, new_article_ids, force
        )
        
        if result.get("success"):
            data = result.get("data", {})
            return EvolutionResult(
                storyline_id=data.get("storyline_id", storyline_id),
                total_articles=data.get("total_articles", 0),
                new_articles=data.get("new_articles", 0),
                evolution_count=data.get("evolution_count", 0),
                summary_updated=data.get("summary_updated", False),
                context_updated=data.get("context_updated", False),
                summary_length=data.get("summary_length", 0),
                context_stats=data.get("context_stats", {})
            )
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Evolution failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error evolving storyline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{domain}/storylines/{storyline_id}/assess_quality", response_model=QualityAssessmentResult)
async def assess_domain_storyline_quality(
    domain: str = Depends(validate_domain_dependency),
    storyline_id: int = Path(..., description="Storyline ID", ge=1)
):
    """Assess storyline quality"""
    try:
        quality_service = QualityAssessmentService(domain=domain)
        result = await quality_service.assess_storyline_quality(storyline_id)
        
        if result.get("success"):
            data = result.get("data", {})
            return QualityAssessmentResult(
                storyline_id=storyline_id,
                overall_score=data.get("overall_score", 0.0),
                quality_score=data.get("quality_score", 0.0),
                factual_accuracy_score=data.get("factual_accuracy_score", 0.0),
                narrative_quality_score=data.get("narrative_quality_score", 0.0),
                source_diversity=data.get("source_diversity", 0),
                article_count=data.get("article_count", 0),
                recommendations=data.get("recommendations", [])
            )
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Assessment failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assessing quality: {e}")
        raise HTTPException(status_code=500, detail=str(e))

