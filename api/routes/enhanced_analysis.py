"""
Enhanced Analysis API Routes for News Intelligence System v3.0
Provides endpoints for multi-perspective analysis and enhanced storyline analysis
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Path
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
import logging

from services.enhanced_storyline_service import get_enhanced_storyline_service
from services.multi_perspective_analyzer import get_multi_perspective_analyzer
from modules.ml.summarization_service import MLSummarizationService
from services.rag_service import RAGService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/enhanced-analysis", tags=["Enhanced Analysis"])

# Pydantic models for request/response
class EnhancedAnalysisRequest(BaseModel):
    storyline_id: str = Field(..., description="ID of the storyline to analyze")
    include_multi_perspective: bool = Field(True, description="Whether to include multi-perspective analysis")
    include_rag_enhancement: bool = Field(True, description="Whether to include RAG enhancement")
    include_impact_assessment: bool = Field(True, description="Whether to include impact assessment")
    include_historical_context: bool = Field(True, description="Whether to include historical context analysis")
    include_predictive_analysis: bool = Field(True, description="Whether to include predictive analysis")
    include_expert_analysis: bool = Field(True, description="Whether to include expert analysis integration")
    force_regenerate: bool = Field(False, description="Force regeneration even if analysis exists")

class MultiPerspectiveAnalysisRequest(BaseModel):
    storyline_id: str = Field(..., description="ID of the storyline to analyze")
    perspectives: Optional[List[str]] = Field(None, description="Specific perspectives to analyze (if None, analyzes all)")

class AnalysisQualityMetrics(BaseModel):
    overall_quality_score: float = Field(..., description="Overall analysis quality score (0-1)")
    completeness_score: float = Field(..., description="Completeness score (0-1)")
    accuracy_score: float = Field(..., description="Accuracy score (0-1)")
    readability_score: float = Field(..., description="Readability score (0-1)")
    timeliness_score: float = Field(..., description="Timeliness score (0-1)")

class PerspectiveAnalysis(BaseModel):
    perspective_type: str = Field(..., description="Type of perspective")
    analysis_content: str = Field(..., description="Analysis content")
    confidence_score: float = Field(..., description="Confidence score (0-1)")
    key_points: List[str] = Field(..., description="Key points extracted from analysis")
    supporting_evidence: List[Dict[str, Any]] = Field(..., description="Supporting evidence")
    analysis_metadata: Dict[str, Any] = Field(..., description="Analysis metadata")

class MultiPerspectiveResult(BaseModel):
    storyline_id: str = Field(..., description="Storyline ID")
    individual_perspectives: Dict[str, PerspectiveAnalysis] = Field(..., description="Individual perspective analyses")
    synthesized_analysis: str = Field(..., description="Synthesized analysis")
    perspective_agreement: Dict[str, float] = Field(..., description="Agreement levels between perspectives")
    key_disagreements: List[Dict[str, Any]] = Field(..., description="Key disagreements identified")
    consensus_score: float = Field(..., description="Overall consensus score (0-1)")
    analysis_quality_score: float = Field(..., description="Analysis quality score (0-1)")

class EnhancedAnalysisResponse(BaseModel):
    storyline_id: str = Field(..., description="Storyline ID")
    storyline_title: str = Field(..., description="Storyline title")
    analysis_timestamp: str = Field(..., description="Analysis timestamp")
    article_count: int = Field(..., description="Number of articles analyzed")
    overall_quality_score: float = Field(..., description="Overall analysis quality score")
    analysis_components: Dict[str, Any] = Field(..., description="Analysis components")
    recommendations: Dict[str, Any] = Field(..., description="Analysis recommendations")

# Dependency injection
def get_ml_service() -> MLSummarizationService:
    """Get ML service instance"""
    return MLSummarizationService()

def get_rag_service() -> RAGService:
    """Get RAG service instance"""
    return RAGService()

def get_enhanced_service(ml_service: MLSummarizationService = Depends(get_ml_service),
                        rag_service: RAGService = Depends(get_rag_service)):
    """Get enhanced storyline service instance"""
    return get_enhanced_storyline_service(ml_service, rag_service)

def get_multi_perspective_service(ml_service: MLSummarizationService = Depends(get_ml_service),
                                 rag_service: RAGService = Depends(get_rag_service)):
    """Get multi-perspective analyzer instance"""
    return get_multi_perspective_analyzer(ml_service, rag_service)

@router.post("/storyline", response_model=EnhancedAnalysisResponse)
async def generate_enhanced_storyline_analysis(
    request: EnhancedAnalysisRequest,
    enhanced_service = Depends(get_enhanced_service)
):
    """
    Generate comprehensive enhanced storyline analysis with multi-perspective analysis
    
    This endpoint generates a comprehensive analysis that includes:
    - Basic storyline summary
    - RAG-enhanced context (Wikipedia, GDELT)
    - Multi-perspective analysis (6 different viewpoints)
    - Synthesized analysis
    - Quality metrics and recommendations
    """
    try:
        logger.info(f"Generating enhanced analysis for storyline: {request.storyline_id}")
        
        # Check if analysis already exists and force_regenerate is False
        if not request.force_regenerate:
            existing_analysis = await enhanced_service.get_enhanced_storyline_analysis(request.storyline_id)
            if existing_analysis.get("analysis_available", False):
                logger.info(f"Returning existing analysis for storyline: {request.storyline_id}")
                return existing_analysis
        
        # Generate new analysis
        analysis_result = await enhanced_service.generate_enhanced_storyline_analysis(
            storyline_id=request.storyline_id,
            include_multi_perspective=request.include_multi_perspective,
            include_rag_enhancement=request.include_rag_enhancement,
            include_impact_assessment=request.include_impact_assessment,
            include_historical_context=request.include_historical_context,
            include_predictive_analysis=request.include_predictive_analysis,
            include_expert_analysis=request.include_expert_analysis
        )
        
        if "error" in analysis_result:
            raise HTTPException(status_code=400, detail=analysis_result["error"])
        
        return EnhancedAnalysisResponse(**analysis_result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating enhanced storyline analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/multi-perspective", response_model=MultiPerspectiveResult)
async def generate_multi_perspective_analysis(
    request: MultiPerspectiveAnalysisRequest,
    multi_perspective_service = Depends(get_multi_perspective_service),
    rag_service = Depends(get_rag_service)
):
    """
    Generate multi-perspective analysis for a storyline
    
    This endpoint analyzes a storyline from 6 different perspectives:
    - Government/Official
    - Opposition/Critical
    - Expert/Academic
    - International
    - Economic
    - Social/Civil Society
    """
    try:
        logger.info(f"Generating multi-perspective analysis for storyline: {request.storyline_id}")
        
        # Get RAG context
        rag_context = await rag_service.enhance_storyline_context(
            request.storyline_id, 
            "Storyline Analysis", 
            []
        )
        
        # Generate multi-perspective analysis
        result = await multi_perspective_service.generate_multi_perspective_analysis(
            request.storyline_id, rag_context
        )
        
        # Convert to response model
        individual_perspectives = {}
        for perspective_type, analysis in result.individual_perspectives.items():
            individual_perspectives[perspective_type] = PerspectiveAnalysis(
                perspective_type=analysis.perspective_type,
                analysis_content=analysis.analysis_content,
                confidence_score=analysis.confidence_score,
                key_points=analysis.key_points,
                supporting_evidence=analysis.supporting_evidence,
                analysis_metadata=analysis.analysis_metadata
            )
        
        return MultiPerspectiveResult(
            storyline_id=result.storyline_id,
            individual_perspectives=individual_perspectives,
            synthesized_analysis=result.synthesized_analysis,
            perspective_agreement=result.perspective_agreement,
            key_disagreements=result.key_disagreements,
            consensus_score=result.consensus_score,
            analysis_quality_score=result.analysis_quality_score
        )
        
    except Exception as e:
        logger.error(f"Error generating multi-perspective analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/storyline/{storyline_id}", response_model=EnhancedAnalysisResponse)
async def get_enhanced_storyline_analysis(
    storyline_id: str,
    enhanced_service = Depends(get_enhanced_service)
):
    """
    Get existing enhanced storyline analysis
    
    Retrieves previously generated enhanced analysis for a storyline
    """
    try:
        logger.info(f"Getting enhanced analysis for storyline: {storyline_id}")
        
        analysis_result = await enhanced_service.get_enhanced_storyline_analysis(storyline_id)
        
        if "error" in analysis_result:
            raise HTTPException(status_code=404, detail=analysis_result["error"])
        
        if not analysis_result.get("analysis_available", False):
            raise HTTPException(status_code=404, detail="No enhanced analysis found for this storyline")
        
        return analysis_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting enhanced storyline analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/storyline/{storyline_id}/perspectives")
async def get_storyline_perspectives(
    storyline_id: str,
    perspective_type: Optional[str] = Query(None, description="Filter by specific perspective type"),
    enhanced_service = Depends(get_enhanced_service)
):
    """
    Get individual perspective analyses for a storyline
    
    Optionally filter by specific perspective type
    """
    try:
        logger.info(f"Getting perspectives for storyline: {storyline_id}")
        
        analysis_result = await enhanced_service.get_enhanced_storyline_analysis(storyline_id)
        
        if "error" in analysis_result:
            raise HTTPException(status_code=404, detail=analysis_result["error"])
        
        individual_perspectives = analysis_result.get("individual_perspectives", {})
        
        if perspective_type:
            if perspective_type not in individual_perspectives:
                raise HTTPException(status_code=404, detail=f"Perspective type '{perspective_type}' not found")
            return {perspective_type: individual_perspectives[perspective_type]}
        
        return individual_perspectives
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting storyline perspectives: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/storyline/{storyline_id}/quality")
async def get_analysis_quality_metrics(
    storyline_id: str,
    enhanced_service = Depends(get_enhanced_service)
):
    """
    Get analysis quality metrics for a storyline
    """
    try:
        logger.info(f"Getting quality metrics for storyline: {storyline_id}")
        
        analysis_result = await enhanced_service.get_enhanced_storyline_analysis(storyline_id)
        
        if "error" in analysis_result:
            raise HTTPException(status_code=404, detail=analysis_result["error"])
        
        multi_perspective = analysis_result.get("multi_perspective_analysis", {})
        
        quality_metrics = {
            "overall_quality_score": analysis_result.get("overall_quality_score", 0.0),
            "consensus_score": multi_perspective.get("consensus_score", 0.0),
            "analysis_quality_score": multi_perspective.get("analysis_quality_score", 0.0),
            "perspective_count": len(analysis_result.get("individual_perspectives", {})),
            "key_disagreements_count": len(multi_perspective.get("key_disagreements", [])),
            "article_count": analysis_result.get("storyline_data", {}).get("article_count", 0)
        }
        
        return quality_metrics
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting analysis quality metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/perspectives/available")
async def get_available_perspectives():
    """
    Get list of available analysis perspectives
    """
    return {
        "perspectives": [
            {
                "type": "government_official",
                "name": "Government/Official Perspective",
                "description": "Analysis from government and official sources perspective"
            },
            {
                "type": "opposition_critical",
                "name": "Opposition/Critical Perspective",
                "description": "Analysis from opposition and critical sources perspective"
            },
            {
                "type": "expert_academic",
                "name": "Expert/Academic Perspective",
                "description": "Analysis from expert and academic sources perspective"
            },
            {
                "type": "international",
                "name": "International Perspective",
                "description": "Analysis from international and global sources perspective"
            },
            {
                "type": "economic",
                "name": "Economic Perspective",
                "description": "Analysis from economic and financial sources perspective"
            },
            {
                "type": "social_civil",
                "name": "Social/Civil Society Perspective",
                "description": "Analysis from social and civil society sources perspective"
            }
        ]
    }

@router.post("/impact-assessment/{storyline_id}")
async def generate_impact_assessment(
    storyline_id: str,
    enhanced_service = Depends(get_enhanced_service)
):
    """
    Generate comprehensive impact assessment for a storyline
    
    This endpoint analyzes potential impacts across 6 dimensions:
    - Political Impact
    - Economic Impact  
    - Social Impact
    - Environmental Impact
    - Technological Impact
    - International Impact
    """
    try:
        logger.info(f"Generating impact assessment for storyline: {storyline_id}")
        
        # Get storyline data
        storyline_data = await enhanced_service.get_storyline_articles(storyline_id)
        if not storyline_data or 'storyline' not in storyline_data:
            raise HTTPException(status_code=404, detail="Storyline not found")
        
        articles = storyline_data.get('articles', [])
        if not articles:
            raise HTTPException(status_code=400, detail="No articles found in storyline")
        
        # Generate impact assessment
        impact_result = await enhanced_service.impact_assessment_service.assess_impacts(
            storyline_id, articles
        )
        
        return {
            "storyline_id": storyline_id,
            "overall_impact_score": impact_result.overall_impact_score,
            "assessment_quality_score": impact_result.assessment_quality_score,
            "risk_assessment": impact_result.risk_assessment,
            "high_impact_scenarios": impact_result.high_impact_scenarios,
            "dimension_assessments": {
                dimension: {
                    "impact_score": assessment.impact_score,
                    "risk_level": assessment.risk_level,
                    "confidence_level": assessment.confidence_level,
                    "impact_description": assessment.impact_description,
                    "mitigation_strategies": assessment.mitigation_strategies
                }
                for dimension, assessment in impact_result.dimension_assessments.items()
            },
            "mitigation_recommendations": impact_result.mitigation_recommendations
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating impact assessment: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/impact-dimensions")
async def get_impact_dimensions():
    """
    Get list of available impact assessment dimensions
    """
    return {
        "dimensions": [
            {
                "type": "political",
                "name": "Political Impact",
                "description": "Analysis of political implications and consequences",
                "subcategories": ["policy_changes", "election_impact", "governance_effects", "regulatory_impact", "public_administration"]
            },
            {
                "type": "economic",
                "name": "Economic Impact", 
                "description": "Analysis of economic implications and consequences",
                "subcategories": ["market_impact", "gdp_effects", "employment_changes", "inflation_impact", "trade_effects", "investment_impact"]
            },
            {
                "type": "social",
                "name": "Social Impact",
                "description": "Analysis of social implications and consequences", 
                "subcategories": ["public_opinion", "social_cohesion", "demographic_impact", "community_effects", "social_services", "public_health"]
            },
            {
                "type": "environmental",
                "name": "Environmental Impact",
                "description": "Analysis of environmental implications and consequences",
                "subcategories": ["climate_impact", "biodiversity_effects", "resource_usage", "pollution_impact", "ecosystem_effects", "sustainability_impact"]
            },
            {
                "type": "technological",
                "name": "Technological Impact",
                "description": "Analysis of technological implications and consequences",
                "subcategories": ["innovation_effects", "digital_impact", "cybersecurity_implications", "automation_effects", "infrastructure_impact", "research_development"]
            },
            {
                "type": "international",
                "name": "International Impact",
                "description": "Analysis of international implications and consequences",
                "subcategories": ["diplomatic_relations", "trade_impact", "security_implications", "multilateral_cooperation", "global_governance", "international_law"]
            }
        ]
    }

@router.post("/historical-context/{storyline_id}")
async def generate_historical_context(
    storyline_id: str,
    enhanced_service = Depends(get_enhanced_service)
):
    """
    Generate historical context analysis for a storyline
    
    This endpoint provides:
    - Historical timeline generation
    - Pattern recognition and precedent analysis
    - Similar event identification
    - Historical trend analysis
    """
    try:
        logger.info(f"Generating historical context for storyline: {storyline_id}")
        
        # Get storyline data
        storyline_data = await enhanced_service.get_storyline_articles(storyline_id)
        if not storyline_data or 'storyline' not in storyline_data:
            raise HTTPException(status_code=404, detail="Storyline not found")
        
        articles = storyline_data.get('articles', [])
        if not articles:
            raise HTTPException(status_code=400, detail="No articles found in storyline")
        
        # Generate historical context
        historical_result = await enhanced_service.historical_context_service.generate_historical_context(
            storyline_id, storyline_data['storyline'].get('title', 'Untitled Storyline'), articles
        )
        
        return {
            "storyline_id": storyline_id,
            "timeline_events_count": len(historical_result.historical_timeline),
            "patterns_identified": len(historical_result.identified_patterns),
            "similar_events_count": len(historical_result.similar_events),
            "context_quality_score": historical_result.context_quality_score,
            "historical_timeline": [{
                "event_id": event.event_id,
                "title": event.title,
                "date": event.date,
                "category": event.category,
                "significance_score": event.significance_score,
                "similarity_score": event.similarity_score
            } for event in historical_result.historical_timeline[:20]],  # Limit to 20 events
            "identified_patterns": [{
                "pattern_id": pattern.pattern_id,
                "pattern_type": pattern.pattern_type,
                "description": pattern.description,
                "similarity_score": pattern.similarity_score,
                "confidence_level": pattern.confidence_level
            } for pattern in historical_result.identified_patterns],
            "precedent_analysis": historical_result.precedent_analysis,
            "trend_analysis": historical_result.trend_analysis
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating historical context: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/predictive-analysis/{storyline_id}")
async def generate_predictive_analysis(
    storyline_id: str,
    enhanced_service = Depends(get_enhanced_service)
):
    """
    Generate predictive analysis for a storyline
    
    This endpoint provides:
    - Short-term predictions (1-6 months)
    - Medium-term predictions (6-24 months)
    - Long-term predictions (2+ years)
    - Scenario planning and uncertainty analysis
    """
    try:
        logger.info(f"Generating predictive analysis for storyline: {storyline_id}")
        
        # Get storyline data
        storyline_data = await enhanced_service.get_storyline_articles(storyline_id)
        if not storyline_data or 'storyline' not in storyline_data:
            raise HTTPException(status_code=404, detail="Storyline not found")
        
        # Prepare current analysis context
        current_analysis = {
            "basic_summary": storyline_data.get('summary', {}),
            "articles": storyline_data.get('articles', []),
            "storyline": storyline_data.get('storyline', {})
        }
        
        # Generate predictive analysis
        predictive_result = await enhanced_service.predictive_analysis_service.generate_predictive_analysis(
            storyline_id, current_analysis
        )
        
        return {
            "storyline_id": storyline_id,
            "overall_confidence": predictive_result.overall_confidence,
            "prediction_quality_score": predictive_result.prediction_quality_score,
            "key_uncertainties_count": len(predictive_result.key_uncertainties),
            "predictions": {
                horizon: {
                    "horizon": prediction.horizon,
                    "confidence_level": prediction.confidence_level,
                    "prediction_content": prediction.prediction_content,
                    "scenarios_count": len(prediction.key_scenarios),
                    "uncertainty_factors_count": len(prediction.uncertainty_factors),
                    "monitoring_indicators": prediction.monitoring_indicators
                }
                for horizon, prediction in predictive_result.predictions.items()
            },
            "key_uncertainties": [{
                "factor_id": uncertainty.factor_id,
                "factor_name": uncertainty.factor_name,
                "description": uncertainty.description,
                "impact_level": uncertainty.impact_level,
                "probability_of_change": uncertainty.probability_of_change
            } for uncertainty in predictive_result.key_uncertainties],
            "scenario_planning": predictive_result.scenario_planning,
            "monitoring_recommendations": predictive_result.monitoring_recommendations
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating predictive analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/prediction-horizons")
async def get_prediction_horizons():
    """
    Get list of available prediction horizons
    """
    return {
        "horizons": [
            {
                "type": "short_term",
                "name": "Short-term Predictions",
                "description": "Predictions for 1-6 months ahead",
                "time_range_months": 6,
                "focus_areas": ["immediate_developments", "near_term_impacts", "quick_responses"]
            },
            {
                "type": "medium_term",
                "name": "Medium-term Predictions",
                "description": "Predictions for 6-24 months ahead",
                "time_range_months": 18,
                "focus_areas": ["strategic_developments", "policy_changes", "market_evolution"]
            },
            {
                "type": "long_term",
                "name": "Long-term Predictions",
                "description": "Predictions for 2+ years ahead",
                "time_range_months": 36,
                "focus_areas": ["structural_changes", "paradigm_shifts", "generational_impacts"]
            }
        ]
    }

@router.post("/expert-analysis/{storyline_id}")
async def generate_expert_analysis(
    storyline_id: str,
    enhanced_service = Depends(get_enhanced_service)
):
    """
    Generate expert analysis for a storyline
    
    This endpoint provides:
    - Academic research integration
    - Think tank reports analysis
    - Expert opinion synthesis
    - Policy papers analysis
    - Industry analysis integration
    - International organization perspectives
    """
    try:
        logger.info(f"Generating expert analysis for storyline: {storyline_id}")
        
        # Get storyline data
        storyline_data = await enhanced_service.get_storyline_articles(storyline_id)
        if not storyline_data or 'storyline' not in storyline_data:
            raise HTTPException(status_code=404, detail="Storyline not found")
        
        articles = storyline_data.get('articles', [])
        if not articles:
            raise HTTPException(status_code=400, detail="No articles found in storyline")
        
        # Generate expert analysis
        expert_result = await enhanced_service.expert_analysis_service.generate_expert_analysis(
            storyline_id, storyline_data['storyline'].get('title', 'Untitled Storyline'), articles
        )
        
        return {
            "storyline_id": storyline_id,
            "synthesis_quality_score": expert_result.synthesis_quality_score,
            "expert_consensus_score": expert_result.expert_synthesis.expert_consensus_score,
            "source_coverage": expert_result.source_coverage,
            "credibility_distribution": expert_result.credibility_distribution,
            "expertise_areas_covered": expert_result.expertise_areas_covered,
            "expert_analyses": [{
                "analysis_id": analysis.analysis_id,
                "source_type": analysis.source.source_type,
                "source_name": analysis.source.source_name,
                "credibility_level": analysis.source.credibility_level,
                "confidence_score": analysis.confidence_score,
                "relevance_score": analysis.relevance_score,
                "key_insights": analysis.key_insights,
                "methodology": analysis.methodology
            } for analysis in expert_result.expert_synthesis.expert_analyses],
            "consensus_analysis": expert_result.expert_synthesis.consensus_analysis,
            "key_disagreements": expert_result.expert_synthesis.key_disagreements,
            "expert_recommendations": expert_result.expert_recommendations
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating expert analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/expert-sources")
async def get_expert_sources():
    """
    Get list of available expert analysis sources
    """
    return {
        "sources": [
            {
                "type": "academic_research",
                "name": "Academic Research",
                "description": "Peer-reviewed academic papers and research",
                "credibility_level": "high",
                "expertise_areas": ["political_science", "economics", "sociology", "international_relations", "public_policy"]
            },
            {
                "type": "think_tank_reports",
                "name": "Think Tank Reports",
                "description": "Policy research from think tanks and research institutions",
                "credibility_level": "high",
                "expertise_areas": ["policy_analysis", "strategic_studies", "economic_policy", "foreign_policy", "social_policy"]
            },
            {
                "type": "expert_opinions",
                "name": "Expert Opinions",
                "description": "Expert commentary and professional opinions",
                "credibility_level": "medium",
                "expertise_areas": ["professional_expertise", "industry_knowledge", "practical_experience", "field_expertise"]
            },
            {
                "type": "policy_papers",
                "name": "Policy Papers",
                "description": "Government and institutional policy documents",
                "credibility_level": "high",
                "expertise_areas": ["government_policy", "regulatory_analysis", "public_administration", "governance", "institutional_policy"]
            },
            {
                "type": "industry_analysis",
                "name": "Industry Analysis",
                "description": "Industry-specific analysis and market research",
                "credibility_level": "medium",
                "expertise_areas": ["market_analysis", "industry_trends", "business_intelligence", "sector_analysis", "economic_analysis"]
            },
            {
                "type": "international_organizations",
                "name": "International Organizations",
                "description": "Analysis from international organizations and multilateral institutions",
                "credibility_level": "high",
                "expertise_areas": ["international_relations", "multilateral_cooperation", "global_governance", "international_law", "development"]
            }
        ]
    }

@router.get("/expertise-areas")
async def get_expertise_areas():
    """
    Get list of available expertise areas
    """
    return {
        "expertise_areas": [
            {
                "id": "political_science",
                "name": "Political Science",
                "description": "Political theory, governance, and political systems",
                "keywords": ["politics", "government", "governance", "political", "democracy", "authoritarianism"]
            },
            {
                "id": "economics",
                "name": "Economics",
                "description": "Economic theory, policy, and market analysis",
                "keywords": ["economic", "economy", "market", "financial", "monetary", "fiscal"]
            },
            {
                "id": "sociology",
                "name": "Sociology",
                "description": "Social theory, social movements, and social change",
                "keywords": ["social", "society", "community", "culture", "demographic", "social_change"]
            },
            {
                "id": "international_relations",
                "name": "International Relations",
                "description": "Global politics, diplomacy, and international cooperation",
                "keywords": ["international", "global", "diplomatic", "foreign_policy", "multilateral", "geopolitics"]
            },
            {
                "id": "public_policy",
                "name": "Public Policy",
                "description": "Policy analysis, implementation, and evaluation",
                "keywords": ["policy", "public_policy", "regulation", "governance", "administration", "implementation"]
            },
            {
                "id": "technology",
                "name": "Technology",
                "description": "Technology policy, innovation, and digital transformation",
                "keywords": ["technology", "digital", "innovation", "tech", "cyber", "artificial_intelligence"]
            },
            {
                "id": "environment",
                "name": "Environment",
                "description": "Environmental policy, sustainability, and climate change",
                "keywords": ["environment", "climate", "sustainability", "green", "ecological", "environmental"]
            },
            {
                "id": "security",
                "name": "Security",
                "description": "Security studies, defense, and risk analysis",
                "keywords": ["security", "defense", "military", "intelligence", "risk", "threat"]
            }
        ]
    }

@router.get("/health")
async def health_check():
    """
    Health check endpoint for enhanced analysis service
    """
    return {
        "status": "healthy",
        "service": "enhanced-analysis",
        "version": "3.0.0",
        "features": [
            "multi_perspective_analysis",
            "rag_enhancement",
            "impact_assessment",
            "historical_context",
            "predictive_analysis",
            "expert_analysis",
            "comprehensive_summary",
            "quality_metrics"
        ]
    }
