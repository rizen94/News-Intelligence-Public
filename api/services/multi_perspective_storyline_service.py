"""
Multi-Perspective Storyline Service for News Intelligence System v3.0
Integrates multi-perspective analysis with existing storyline functionality
"""

import asyncio
import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from config.database import get_db
from sqlalchemy import text
from services.storyline_service import StorylineService
from services.multi_perspective_analyzer import MultiPerspectiveAnalyzer, get_multi_perspective_analyzer
from services.impact_assessment_service import ImpactAssessmentService, get_impact_assessment_service
from services.historical_context_service import HistoricalContextService, get_historical_context_service
from services.predictive_analysis_service import PredictiveAnalysisService, get_predictive_analysis_service
from services.expert_analysis_service import ExpertAnalysisService, get_expert_analysis_service
from services.rag import RAGService
from modules.ml.summarization_service import MLSummarizationService

logger = logging.getLogger(__name__)

class MultiPerspectiveStorylineService(StorylineService):
    """
    Multi-perspective storyline service with advanced analysis capabilities
    """
    
    def __init__(self, db_connection=None, ml_service=None, rag_service=None):
        """
        Initialize multi-perspective storyline service
        
        Args:
            db_connection: Database connection
            ml_service: ML summarization service
            rag_service: RAG service for context enhancement
        """
        super().__init__(db_connection)
        self.ml_service = ml_service or MLSummarizationService()
        self.rag_service = rag_service
        self.multi_perspective_analyzer = get_multi_perspective_analyzer(self.ml_service, self.rag_service)
        self.impact_assessment_service = get_impact_assessment_service(self.ml_service)
        self.historical_context_service = get_historical_context_service(self.ml_service, self.rag_service)
        self.predictive_analysis_service = get_predictive_analysis_service(self.ml_service, self.historical_context_service)
        self.expert_analysis_service = get_expert_analysis_service(self.ml_service, self.rag_service)
    
    async def generate_enhanced_storyline_analysis(self, storyline_id: str, 
                                                 include_multi_perspective: bool = True,
                                                 include_rag_enhancement: bool = True,
                                                 include_impact_assessment: bool = True,
                                                 include_historical_context: bool = True,
                                                 include_predictive_analysis: bool = True,
                                                 include_expert_analysis: bool = True) -> Dict[str, Any]:
        """
        Generate comprehensive enhanced storyline analysis
        
        Args:
            storyline_id: ID of the storyline to analyze
            include_multi_perspective: Whether to include multi-perspective analysis
            include_rag_enhancement: Whether to include RAG enhancement
            include_impact_assessment: Whether to include impact assessment
            include_historical_context: Whether to include historical context analysis
            include_predictive_analysis: Whether to include predictive analysis
            include_expert_analysis: Whether to include expert analysis integration
            
        Returns:
            Dictionary containing comprehensive analysis
        """
        try:
            logger.info(f"Generating enhanced analysis for storyline: {storyline_id}")
            
            # Get basic storyline data
            storyline_data = await self.get_storyline_articles(storyline_id)
            if not storyline_data or 'storyline' not in storyline_data:
                return {"error": "Storyline not found"}
            
            storyline = storyline_data['storyline']
            articles = storyline_data.get('articles', [])
            
            if not articles:
                return {"error": "No articles in storyline"}
            
            # Initialize result structure
            analysis_result = {
                "storyline_id": storyline_id,
                "storyline_title": storyline.get('title', 'Untitled Storyline'),
                "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
                "article_count": len(articles),
                "analysis_components": {}
            }
            
            # Generate basic summary (existing functionality)
            basic_summary = await self.generate_storyline_summary(storyline_id)
            analysis_result["analysis_components"]["basic_summary"] = {
                "content": basic_summary.get("master_summary", ""),
                "status": basic_summary.get("status", "unknown"),
                "article_count": basic_summary.get("article_count", 0)
            }
            
            # Generate RAG-enhanced context
            rag_context = {}
            if include_rag_enhancement and self.rag_service:
                logger.info("Generating RAG-enhanced context")
                try:
                    rag_context = await self.rag_service.enhance_storyline_context(
                        storyline_id, 
                        storyline.get('title', 'Untitled Storyline'), 
                        articles
                    )
                except Exception as e:
                    logger.warning(f"RAG enhancement failed, using empty context: {e}")
                    rag_context = {}
                analysis_result["analysis_components"]["rag_context"] = {
                    "wikipedia_sources": len(rag_context.get('wikipedia', {}).get('summaries', [])),
                    "gdelt_events": len(rag_context.get('gdelt', {}).get('events', [])),
                    "extracted_entities": len(rag_context.get('extracted_entities', [])),
                    "extracted_topics": len(rag_context.get('extracted_topics', [])),
                    "enhanced_at": rag_context.get('enhanced_at', '')
                }
            
            # Generate multi-perspective analysis
            multi_perspective_result = None
            if include_multi_perspective and self.multi_perspective_analyzer:
                logger.info("Generating multi-perspective analysis")
                try:
                    multi_perspective_result = await self.multi_perspective_analyzer.generate_multi_perspective_analysis(
                        storyline_id, rag_context
                    )
                except Exception as e:
                    logger.warning(f"Multi-perspective analysis failed: {e}")
                    multi_perspective_result = None
                if multi_perspective_result:
                    analysis_result["analysis_components"]["multi_perspective"] = {
                        "perspective_count": len(multi_perspective_result.individual_perspectives),
                        "consensus_score": multi_perspective_result.consensus_score,
                        "analysis_quality_score": multi_perspective_result.analysis_quality_score,
                        "key_disagreements_count": len(multi_perspective_result.key_disagreements),
                        "synthesized_analysis": multi_perspective_result.synthesized_analysis,
                        "individual_perspectives": {
                            perspective_type: {
                                "confidence_score": analysis.confidence_score,
                                "key_points_count": len(analysis.key_points),
                                "supporting_evidence_count": len(analysis.supporting_evidence),
                                "analysis_length": len(analysis.analysis_content)
                            }
                            for perspective_type, analysis in multi_perspective_result.individual_perspectives.items()
                        }
                    }
                else:
                    analysis_result["analysis_components"]["multi_perspective"] = {
                        "perspective_count": 0,
                        "consensus_score": 0.0,
                        "analysis_quality_score": 0.0,
                        "key_disagreements_count": 0,
                        "synthesized_analysis": "Multi-perspective analysis not available",
                        "individual_perspectives": {}
                    }
            
            # Generate impact assessment
            impact_assessment_result = None
            if include_impact_assessment and self.impact_assessment_service:
                logger.info("Generating impact assessment")
                try:
                    impact_assessment_result = await self.impact_assessment_service.assess_impacts(
                        storyline_id, articles, rag_context
                    )
                except Exception as e:
                    logger.warning(f"Impact assessment failed: {e}")
                    impact_assessment_result = None
                
                if impact_assessment_result:
                    analysis_result["analysis_components"]["impact_assessment"] = {
                        "overall_impact_score": impact_assessment_result.overall_impact_score,
                        "assessment_quality_score": impact_assessment_result.assessment_quality_score,
                        "high_impact_scenarios_count": len(impact_assessment_result.high_impact_scenarios),
                        "risk_assessment": impact_assessment_result.risk_assessment,
                        "dimension_assessments": {
                            dimension: {
                                "impact_score": assessment.impact_score,
                                "risk_level": assessment.risk_level,
                                "confidence_level": assessment.confidence_level,
                                "mitigation_strategies_count": len(assessment.mitigation_strategies)
                            }
                            for dimension, assessment in impact_assessment_result.dimension_assessments.items()
                        }
                    }
                else:
                    analysis_result["analysis_components"]["impact_assessment"] = {
                        "overall_impact_score": 0.0,
                        "assessment_quality_score": 0.0,
                        "high_impact_scenarios_count": 0,
                        "risk_assessment": {"overall_risk_level": "unknown"},
                        "dimension_assessments": {}
                    }
            
            # Generate historical context
            historical_context_result = None
            if include_historical_context and self.historical_context_service:
                logger.info("Generating historical context")
                try:
                    historical_context_result = await self.historical_context_service.generate_historical_context(
                        storyline_id, storyline.get('title', 'Untitled Storyline'), articles, rag_context
                    )
                except Exception as e:
                    logger.warning(f"Historical context generation failed: {e}")
                    historical_context_result = None
                
                if historical_context_result:
                    analysis_result["analysis_components"]["historical_context"] = {
                        "timeline_events_count": len(historical_context_result.historical_timeline),
                        "patterns_identified": len(historical_context_result.identified_patterns),
                        "similar_events_count": len(historical_context_result.similar_events),
                        "context_quality_score": historical_context_result.context_quality_score,
                        "precedent_analysis": historical_context_result.precedent_analysis,
                        "trend_analysis": historical_context_result.trend_analysis
                    }
                else:
                    analysis_result["analysis_components"]["historical_context"] = {
                        "timeline_events_count": 0,
                        "patterns_identified": 0,
                        "similar_events_count": 0,
                        "context_quality_score": 0.0,
                        "precedent_analysis": {},
                        "trend_analysis": {}
                    }
            
            # Generate predictive analysis
            predictive_analysis_result = None
            if include_predictive_analysis and self.predictive_analysis_service:
                logger.info("Generating predictive analysis")
                try:
                    # Prepare current analysis for prediction
                    current_analysis = {
                        "multi_perspective": multi_perspective_result.__dict__ if multi_perspective_result else {},
                        "impact_assessment": impact_assessment_result.__dict__ if impact_assessment_result else {},
                        "historical_context": historical_context_result.__dict__ if historical_context_result else {},
                        "basic_summary": basic_summary,
                        "rag_context": rag_context
                    }
                    
                    predictive_analysis_result = await self.predictive_analysis_service.generate_predictive_analysis(
                        storyline_id, current_analysis
                    )
                except Exception as e:
                    logger.warning(f"Predictive analysis generation failed: {e}")
                    predictive_analysis_result = None
                
                if predictive_analysis_result:
                    analysis_result["analysis_components"]["predictive_analysis"] = {
                        "overall_confidence": predictive_analysis_result.overall_confidence,
                        "prediction_quality_score": predictive_analysis_result.prediction_quality_score,
                        "key_uncertainties_count": len(predictive_analysis_result.key_uncertainties),
                        "scenario_planning": predictive_analysis_result.scenario_planning,
                        "monitoring_recommendations_count": len(predictive_analysis_result.monitoring_recommendations),
                        "predictions": {
                            horizon: {
                                "confidence_level": prediction.confidence_level,
                                "scenarios_count": len(prediction.key_scenarios),
                                "uncertainty_factors_count": len(prediction.uncertainty_factors)
                            }
                            for horizon, prediction in predictive_analysis_result.predictions.items()
                        }
                    }
                else:
                    analysis_result["analysis_components"]["predictive_analysis"] = {
                        "overall_confidence": 0.0,
                        "prediction_quality_score": 0.0,
                        "key_uncertainties_count": 0,
                        "scenario_planning": {},
                        "monitoring_recommendations_count": 0,
                        "predictions": {}
                    }
            
            # Generate expert analysis
            expert_analysis_result = None
            if include_expert_analysis and self.expert_analysis_service:
                logger.info("Generating expert analysis")
                try:
                    expert_analysis_result = await self.expert_analysis_service.generate_expert_analysis(
                        storyline_id, storyline.get('title', 'Untitled Storyline'), articles, rag_context
                    )
                except Exception as e:
                    logger.warning(f"Expert analysis generation failed: {e}")
                    expert_analysis_result = None
                
                if expert_analysis_result:
                    analysis_result["analysis_components"]["expert_analysis"] = {
                        "synthesis_quality_score": expert_analysis_result.synthesis_quality_score,
                        "expert_consensus_score": expert_analysis_result.expert_synthesis.expert_consensus_score,
                        "source_coverage": expert_analysis_result.source_coverage,
                        "credibility_distribution": expert_analysis_result.credibility_distribution,
                        "expertise_areas_covered": expert_analysis_result.expertise_areas_covered,
                        "expert_analyses_count": len(expert_analysis_result.expert_synthesis.expert_analyses),
                        "key_disagreements_count": len(expert_analysis_result.expert_synthesis.key_disagreements),
                        "expert_recommendations_count": len(expert_analysis_result.expert_recommendations)
                    }
                else:
                    analysis_result["analysis_components"]["expert_analysis"] = {
                        "synthesis_quality_score": 0.0,
                        "expert_consensus_score": 0.0,
                        "source_coverage": {},
                        "credibility_distribution": {},
                        "expertise_areas_covered": [],
                        "expert_analyses_count": 0,
                        "key_disagreements_count": 0,
                        "expert_recommendations_count": 0
                    }
            
            # Generate comprehensive summary
            comprehensive_summary = await self._generate_comprehensive_summary(
                storyline, articles, basic_summary, multi_perspective_result, rag_context, 
                impact_assessment_result, historical_context_result, predictive_analysis_result, expert_analysis_result
            )
            analysis_result["analysis_components"]["comprehensive_summary"] = comprehensive_summary
            
            # Calculate overall analysis quality
            overall_quality = self._calculate_overall_analysis_quality(analysis_result)
            analysis_result["overall_quality_score"] = overall_quality
            
            # Generate recommendations
            recommendations = await self._generate_analysis_recommendations(analysis_result)
            analysis_result["recommendations"] = recommendations
            
            logger.info(f"Enhanced analysis completed for storyline: {storyline_id}")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error generating enhanced storyline analysis: {e}")
            return {"error": str(e)}
    
    async def _generate_comprehensive_summary(self, storyline: Dict, articles: List[Dict], 
                                            basic_summary: Dict, multi_perspective_result: Optional[Any], 
                                            rag_context: Dict, impact_assessment_result: Optional[Any] = None,
                                            historical_context_result: Optional[Any] = None,
                                            predictive_analysis_result: Optional[Any] = None,
                                            expert_analysis_result: Optional[Any] = None) -> Dict[str, Any]:
        """Generate comprehensive summary combining all analysis components"""
        try:
            summary_parts = []
            
            # Executive Summary
            summary_parts.append("# COMPREHENSIVE INTELLIGENCE ANALYSIS")
            summary_parts.append(f"## {storyline.get('title', 'Untitled Storyline')}")
            summary_parts.append("")
            summary_parts.append("### 🎯 EXECUTIVE SUMMARY")
            summary_parts.append(basic_summary.get("master_summary", "No summary available"))
            summary_parts.append("")
            
            # Multi-Perspective Analysis Section
            if multi_perspective_result:
                summary_parts.append("### 📊 MULTI-PERSPECTIVE ANALYSIS")
                summary_parts.append("")
                
                # Individual Perspectives
                for perspective_type, analysis in multi_perspective_result.individual_perspectives.items():
                    perspective_name = perspective_type.replace('_', ' ').title()
                    summary_parts.append(f"#### {perspective_name} Perspective")
                    summary_parts.append(f"*Confidence Score: {analysis.confidence_score:.2f}*")
                    summary_parts.append("")
                    summary_parts.append(analysis.analysis_content[:500] + "..." if len(analysis.analysis_content) > 500 else analysis.analysis_content)
                    summary_parts.append("")
                
                # Synthesized Analysis
                summary_parts.append("#### Synthesized Multi-Perspective Analysis")
                summary_parts.append(multi_perspective_result.synthesized_analysis)
                summary_parts.append("")
                
                # Key Disagreements
                if multi_perspective_result.key_disagreements:
                    summary_parts.append("#### Key Disagreements")
                    for disagreement in multi_perspective_result.key_disagreements:
                        summary_parts.append(f"- **{disagreement['perspective1']} vs {disagreement['perspective2']}**: {disagreement['description']}")
                    summary_parts.append("")
            
            # RAG Context Section
            if rag_context:
                summary_parts.append("### 🧠 ENHANCED CONTEXT")
                summary_parts.append("")
                
                # Wikipedia Context
                if rag_context.get('wikipedia', {}).get('summaries'):
                    summary_parts.append("#### Wikipedia Context")
                    for summary in rag_context['wikipedia']['summaries'][:3]:  # Limit to 3
                        summary_parts.append(f"- {summary}")
                    summary_parts.append("")
                
                # GDELT Context
                if rag_context.get('gdelt', {}).get('events'):
                    summary_parts.append("#### Recent Events Context (GDELT)")
                    for event in rag_context['gdelt']['events'][:3]:  # Limit to 3
                        summary_parts.append(f"- {event}")
                    summary_parts.append("")
                
                # Extracted Entities and Topics
                if rag_context.get('extracted_entities'):
                    summary_parts.append("#### Key Entities")
                    summary_parts.append(f"*{', '.join(rag_context['extracted_entities'][:10])}*")
                    summary_parts.append("")
                
                if rag_context.get('extracted_topics'):
                    summary_parts.append("#### Key Topics")
                    summary_parts.append(f"*{', '.join(rag_context['extracted_topics'][:10])}*")
                    summary_parts.append("")
            
            # Impact Assessment Section
            if impact_assessment_result:
                summary_parts.append("### 📊 IMPACT ASSESSMENT")
                summary_parts.append("")
                summary_parts.append(f"**Overall Impact Score**: {impact_assessment_result.overall_impact_score:.2f}")
                summary_parts.append(f"**Risk Level**: {impact_assessment_result.risk_assessment.get('overall_risk_level', 'unknown').title()}")
                summary_parts.append("")
                
                # Individual dimension impacts
                for dimension, assessment in impact_assessment_result.dimension_assessments.items():
                    dimension_name = dimension.replace('_', ' ').title()
                    summary_parts.append(f"#### {dimension_name} Impact")
                    summary_parts.append(f"*Impact Score: {assessment.impact_score:.2f} | Risk Level: {assessment.risk_level.title()}*")
                    summary_parts.append("")
                    summary_parts.append(assessment.impact_description[:300] + "..." if len(assessment.impact_description) > 300 else assessment.impact_description)
                    summary_parts.append("")
                
                # High-impact scenarios
                if impact_assessment_result.high_impact_scenarios:
                    summary_parts.append("#### High-Impact Scenarios")
                    for scenario in impact_assessment_result.high_impact_scenarios[:3]:  # Limit to 3
                        summary_parts.append(f"- **{scenario['dimension'].replace('_', ' ').title()}**: {scenario['description']}")
                    summary_parts.append("")
                
                # Mitigation recommendations
                if impact_assessment_result.mitigation_recommendations:
                    summary_parts.append("#### Mitigation Recommendations")
                    for rec in impact_assessment_result.mitigation_recommendations[:5]:  # Limit to 5
                        summary_parts.append(f"- {rec['strategy']}")
                    summary_parts.append("")
            
            # Historical Context Section
            if historical_context_result:
                summary_parts.append("### 📚 HISTORICAL CONTEXT")
                summary_parts.append("")
                summary_parts.append(f"**Timeline Events**: {len(historical_context_result.historical_timeline)} historical events identified")
                summary_parts.append(f"**Patterns Identified**: {len(historical_context_result.identified_patterns)} historical patterns")
                summary_parts.append(f"**Similar Events**: {len(historical_context_result.similar_events)} similar historical events")
                summary_parts.append("")
                
                # Historical patterns
                if historical_context_result.identified_patterns:
                    summary_parts.append("#### Historical Patterns")
                    for pattern in historical_context_result.identified_patterns[:3]:  # Limit to 3
                        pattern_name = pattern.pattern_type.replace('_', ' ').title()
                        summary_parts.append(f"- **{pattern_name}**: {pattern.description}")
                    summary_parts.append("")
                
                # Precedent analysis
                if historical_context_result.precedent_analysis:
                    precedent = historical_context_result.precedent_analysis
                    if precedent.get('precedent_lessons'):
                        summary_parts.append("#### Historical Lessons")
                        for lesson in precedent['precedent_lessons'][:3]:  # Limit to 3
                            summary_parts.append(f"- {lesson}")
                        summary_parts.append("")
                
                # Trend analysis
                if historical_context_result.trend_analysis:
                    trends = historical_context_result.trend_analysis
                    if trends.get('emerging_patterns'):
                        summary_parts.append("#### Emerging Trends")
                        for pattern in trends['emerging_patterns'][:3]:  # Limit to 3
                            summary_parts.append(f"- {pattern}")
                        summary_parts.append("")
            
            # Predictive Analysis Section
            if predictive_analysis_result:
                summary_parts.append("### 🔮 FUTURE OUTLOOK")
                summary_parts.append("")
                summary_parts.append(f"**Overall Confidence**: {predictive_analysis_result.overall_confidence:.2f}")
                summary_parts.append(f"**Key Uncertainties**: {len(predictive_analysis_result.key_uncertainties)} factors identified")
                summary_parts.append("")
                
                # Prediction horizons
                for horizon, prediction in predictive_analysis_result.predictions.items():
                    horizon_name = horizon.replace('_', ' ').title()
                    summary_parts.append(f"#### {horizon_name} Predictions")
                    summary_parts.append(f"*Confidence: {prediction.confidence_level:.2f} | Scenarios: {len(prediction.key_scenarios)}*")
                    summary_parts.append("")
                    summary_parts.append(prediction.prediction_content[:300] + "..." if len(prediction.prediction_content) > 300 else prediction.prediction_content)
                    summary_parts.append("")
                
                # Key uncertainties
                if predictive_analysis_result.key_uncertainties:
                    summary_parts.append("#### Key Uncertainties")
                    for uncertainty in predictive_analysis_result.key_uncertainties[:5]:  # Limit to 5
                        summary_parts.append(f"- **{uncertainty.factor_name}**: {uncertainty.description}")
                    summary_parts.append("")
                
                # Scenario planning
                if predictive_analysis_result.scenario_planning:
                    scenarios = predictive_analysis_result.scenario_planning
                    if scenarios.get('contingency_plans'):
                        summary_parts.append("#### Contingency Planning")
                        for plan in scenarios['contingency_plans'][:3]:  # Limit to 3
                            summary_parts.append(f"- **{plan['uncertainty']}**: {plan['plan']}")
                        summary_parts.append("")
            
            # Expert Analysis Section
            if expert_analysis_result:
                summary_parts.append("### 🎓 EXPERT ANALYSIS")
                summary_parts.append("")
                summary_parts.append(f"**Expert Consensus Score**: {expert_analysis_result.expert_synthesis.expert_consensus_score:.2f}")
                summary_parts.append(f"**Synthesis Quality Score**: {expert_analysis_result.synthesis_quality_score:.2f}")
                summary_parts.append(f"**Expert Analyses**: {len(expert_analysis_result.expert_synthesis.expert_analyses)} expert sources")
                summary_parts.append("")
                
                # Expert consensus analysis
                if expert_analysis_result.expert_synthesis.consensus_analysis:
                    summary_parts.append("#### Expert Consensus")
                    summary_parts.append(expert_analysis_result.expert_synthesis.consensus_analysis[:400] + "..." if len(expert_analysis_result.expert_synthesis.consensus_analysis) > 400 else expert_analysis_result.expert_synthesis.consensus_analysis)
                    summary_parts.append("")
                
                # Key disagreements
                if expert_analysis_result.expert_synthesis.key_disagreements:
                    summary_parts.append("#### Key Expert Disagreements")
                    for disagreement in expert_analysis_result.expert_synthesis.key_disagreements[:3]:  # Limit to 3
                        summary_parts.append(f"- **{disagreement.get('disagreement_type', 'Unknown')}**: {disagreement.get('description', '')}")
                    summary_parts.append("")
                
                # Expert recommendations
                if expert_analysis_result.expert_recommendations:
                    summary_parts.append("#### Expert Recommendations")
                    for rec in expert_analysis_result.expert_recommendations[:5]:  # Limit to 5
                        summary_parts.append(f"- **{rec.get('type', 'Recommendation').replace('_', ' ').title()}**: {rec.get('description', '')}")
                    summary_parts.append("")
                
                # Source coverage
                if expert_analysis_result.source_coverage:
                    summary_parts.append("#### Expert Source Coverage")
                    for source_type, count in expert_analysis_result.source_coverage.items():
                        source_name = source_type.replace('_', ' ').title()
                        summary_parts.append(f"- **{source_name}**: {count} analyses")
                    summary_parts.append("")
            
            # Analysis Quality Section
            summary_parts.append("### 📈 ANALYSIS QUALITY METRICS")
            summary_parts.append("")
            summary_parts.append(f"- **Article Count**: {len(articles)}")
            summary_parts.append(f"- **Source Diversity**: {len(set(article.get('source', '') for article in articles))}")
            
            if multi_perspective_result:
                summary_parts.append(f"- **Consensus Score**: {multi_perspective_result.consensus_score:.2f}")
                summary_parts.append(f"- **Analysis Quality Score**: {multi_perspective_result.analysis_quality_score:.2f}")
                summary_parts.append(f"- **Perspective Coverage**: {len(multi_perspective_result.individual_perspectives)} perspectives")
            
            if impact_assessment_result:
                summary_parts.append(f"- **Overall Impact Score**: {impact_assessment_result.overall_impact_score:.2f}")
                summary_parts.append(f"- **Risk Assessment**: {impact_assessment_result.risk_assessment.get('overall_risk_level', 'unknown').title()}")
                summary_parts.append(f"- **High-Impact Scenarios**: {len(impact_assessment_result.high_impact_scenarios)}")
            
            if historical_context_result:
                summary_parts.append(f"- **Historical Events**: {len(historical_context_result.historical_timeline)}")
                summary_parts.append(f"- **Historical Patterns**: {len(historical_context_result.identified_patterns)}")
                summary_parts.append(f"- **Context Quality**: {historical_context_result.context_quality_score:.2f}")
            
            if predictive_analysis_result:
                summary_parts.append(f"- **Prediction Confidence**: {predictive_analysis_result.overall_confidence:.2f}")
                summary_parts.append(f"- **Key Uncertainties**: {len(predictive_analysis_result.key_uncertainties)}")
                summary_parts.append(f"- **Prediction Quality**: {predictive_analysis_result.prediction_quality_score:.2f}")
            
            if expert_analysis_result:
                summary_parts.append(f"- **Expert Consensus**: {expert_analysis_result.expert_synthesis.expert_consensus_score:.2f}")
                summary_parts.append(f"- **Expert Sources**: {len(expert_analysis_result.expert_synthesis.expert_analyses)}")
                summary_parts.append(f"- **Expertise Areas**: {len(expert_analysis_result.expertise_areas_covered)}")
                summary_parts.append(f"- **Synthesis Quality**: {expert_analysis_result.synthesis_quality_score:.2f}")
            
            summary_parts.append("")
            
            # Recommendations Section
            summary_parts.append("### 📋 RECOMMENDATIONS")
            summary_parts.append("")
            summary_parts.append("#### For Decision-Makers")
            summary_parts.append("- Review all perspective analyses to understand different viewpoints")
            summary_parts.append("- Pay attention to areas of disagreement between perspectives")
            summary_parts.append("- Consider the confidence scores when weighing different analyses")
            summary_parts.append("")
            
            summary_parts.append("#### For Further Analysis")
            summary_parts.append("- Monitor for new articles that may change the analysis")
            summary_parts.append("- Consider additional expert sources for areas with low confidence")
            summary_parts.append("- Track the evolution of disagreements over time")
            summary_parts.append("")
            
            comprehensive_content = "\n".join(summary_parts)
            
            return {
                "content": comprehensive_content,
                "word_count": len(comprehensive_content.split()),
                "section_count": len([s for s in summary_parts if s.startswith("###")]),
                "generated_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating comprehensive summary: {e}")
            return {
                "content": f"Error generating comprehensive summary: {str(e)}",
                "word_count": 0,
                "section_count": 0,
                "generated_at": datetime.now(timezone.utc).isoformat()
            }
    
    def _calculate_overall_analysis_quality(self, analysis_result: Dict[str, Any]) -> float:
        """Calculate overall analysis quality score"""
        try:
            quality_factors = []
            
            # Basic summary quality
            basic_summary = analysis_result.get("analysis_components", {}).get("basic_summary", {})
            if basic_summary.get("content"):
                content_length = len(basic_summary["content"])
                quality_factors.append(min(content_length / 1000, 1.0))  # Length factor
            
            # Multi-perspective quality
            multi_perspective = analysis_result.get("analysis_components", {}).get("multi_perspective", {})
            if multi_perspective:
                quality_factors.append(multi_perspective.get("analysis_quality_score", 0.0))
                quality_factors.append(multi_perspective.get("consensus_score", 0.0))
                
                # Perspective coverage factor
                perspective_count = multi_perspective.get("perspective_count", 0)
                quality_factors.append(min(perspective_count / 6, 1.0))  # 6 is max perspectives
            
            # RAG context quality
            rag_context = analysis_result.get("analysis_components", {}).get("rag_context", {})
            if rag_context:
                wikipedia_sources = rag_context.get("wikipedia_sources", 0)
                gdelt_events = rag_context.get("gdelt_events", 0)
                entities = rag_context.get("extracted_entities", 0)
                
                quality_factors.append(min(wikipedia_sources / 5, 1.0))  # Wikipedia factor
                quality_factors.append(min(gdelt_events / 3, 1.0))  # GDELT factor
                quality_factors.append(min(entities / 10, 1.0))  # Entities factor
            
            # Article count quality
            article_count = analysis_result.get("article_count", 0)
            quality_factors.append(min(article_count / 20, 1.0))  # Article count factor
            
            return sum(quality_factors) / len(quality_factors) if quality_factors else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating overall analysis quality: {e}")
            return 0.0
    
    async def _generate_analysis_recommendations(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate recommendations based on analysis results"""
        try:
            recommendations = {
                "immediate_actions": [],
                "monitoring_suggestions": [],
                "quality_improvements": []
            }
            
            # Immediate actions based on analysis quality
            overall_quality = analysis_result.get("overall_quality_score", 0.0)
            if overall_quality < 0.5:
                recommendations["immediate_actions"].append("Consider gathering more articles for this storyline")
                recommendations["immediate_actions"].append("Review source diversity and credibility")
            
            # Multi-perspective specific recommendations
            multi_perspective = analysis_result.get("analysis_components", {}).get("multi_perspective", {})
            if multi_perspective:
                consensus_score = multi_perspective.get("consensus_score", 0.0)
                if consensus_score < 0.3:
                    recommendations["immediate_actions"].append("High disagreement between perspectives - investigate further")
                
                disagreement_count = multi_perspective.get("key_disagreements_count", 0)
                if disagreement_count > 3:
                    recommendations["monitoring_suggestions"].append("Monitor for resolution of key disagreements")
            
            # RAG context recommendations
            rag_context = analysis_result.get("analysis_components", {}).get("rag_context", {})
            if rag_context:
                wikipedia_sources = rag_context.get("wikipedia_sources", 0)
                if wikipedia_sources < 2:
                    recommendations["quality_improvements"].append("Consider enhancing Wikipedia context")
                
                gdelt_events = rag_context.get("gdelt_events", 0)
                if gdelt_events < 1:
                    recommendations["quality_improvements"].append("Consider enhancing GDELT context")
            
            # Article count recommendations
            article_count = analysis_result.get("article_count", 0)
            if article_count < 5:
                recommendations["quality_improvements"].append("Consider adding more articles for comprehensive analysis")
            elif article_count > 50:
                recommendations["monitoring_suggestions"].append("Monitor for information overload - consider filtering")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating analysis recommendations: {e}")
            return {
                "immediate_actions": ["Error generating recommendations"],
                "monitoring_suggestions": [],
                "quality_improvements": []
            }
    
    async def process_storyline_ml(self, storyline_id: str) -> Dict[str, Any]:
        """Process storyline with ML to generate summary and analysis"""
        try:
            # Get storyline and articles
            storyline_data = await self.get_storyline_articles(storyline_id)
            
            if "error" in storyline_data:
                return {"error": storyline_data["error"]}
            
            storyline = storyline_data.get("storyline", {})
            articles = storyline_data.get("articles", [])
            
            if not articles:
                return {
                    "error": "No articles found for storyline",
                    "data": {
                        "master_summary": "No articles available for analysis",
                        "timeline_summary": "No timeline data available",
                        "key_entities": {},
                        "sentiment_trend": {"overall": 0.0, "trend": "neutral"},
                        "source_diversity": {"score": 0.0, "sources": [], "total_sources": 0, "total_articles": 0}
                    }
                }
            
            # Check if ML service is available
            if not self.ml_service or not self.ml_service.ml_available:
                logger.error("❌ ML service not available - cannot process storyline")
                return {
                    "error": "ML service not available - Ollama connection failed",
                    "data": {
                        "master_summary": "ML service unavailable - cannot generate summary",
                        "timeline_summary": "ML service unavailable - cannot generate timeline",
                        "key_entities": {},
                        "sentiment_trend": {"overall": 0.0, "trend": "error"},
                        "source_diversity": {"score": 0.0, "sources": [], "total_sources": 0, "total_articles": len(articles)},
                        "ml_status": "failed",
                        "ml_error": "Ollama connection failed"
                    }
                }
            
            # Process with ML service
            logger.info(f"🔍 Calling ML service with {len(articles)} articles")
            logger.info(f"🔍 ML service available: {self.ml_service.ml_available}")
            logger.info(f"🔍 First article content length: {len(articles[0].get('content', '')) if articles else 0}")
            
            ml_result = self.ml_service.summarize_articles(articles)
            logger.info(f"🔍 ML result status: {ml_result.get('status')}")
            logger.info(f"🔍 ML result summary length: {len(ml_result.get('summary', ''))}")
            
            if ml_result.get("status") == "failed":
                logger.error(f"❌ ML processing failed: {ml_result.get('error')}")
                return {
                    "error": f"ML processing failed: {ml_result.get('error')}",
                    "data": {
                        "master_summary": "ML processing failed",
                        "timeline_summary": "ML processing failed",
                        "key_entities": {},
                        "sentiment_trend": {"overall": 0.0, "trend": "error"},
                        "source_diversity": {"score": 0.0, "sources": [], "total_sources": 0, "total_articles": len(articles)},
                        "ml_status": "failed",
                        "ml_error": ml_result.get("error")
                    }
                }
            
            # Extract sources
            sources = list(set([article.get("source", "Unknown") for article in articles]))
            
            # Generate timeline summary
            timeline_summary = f"{datetime.now().isoformat()}: {storyline.get('title', 'Untitled')} ({sources[0] if sources else 'Unknown'})"
            
            # Extract key entities (simple word frequency)
            all_text = " ".join([article.get("title", "") + " " + article.get("content", "") for article in articles])
            words = all_text.lower().split()
            word_freq = {}
            for word in words:
                if len(word) > 4 and word.isalpha():
                    word_freq[word] = word_freq.get(word, 0) + 1
            
            key_entities = dict(sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10])
            
            result = {
                "master_summary": ml_result.get("summary", "No summary available"),
                "timeline_summary": timeline_summary,
                "key_entities": key_entities,
                "sentiment_trend": {
                    "overall": 0.0,  # Would need sentiment analysis
                    "trend": ml_result.get("sentiment", "neutral")
                },
                "source_diversity": {
                    "score": 1.0 if len(sources) > 1 else 0.5,
                    "sources": sources,
                    "total_sources": len(sources),
                    "total_articles": len(articles)
                },
                "ml_status": "success",
                "ml_model": ml_result.get("model_used", "unknown")
            }
            
            # Update storyline with results
            try:
                db_gen = get_db()
                db = next(db_gen)
                try:
                    db.execute(text("""
                        UPDATE storylines 
                        SET master_summary = :summary,
                            ml_processed = true,
                            ml_processing_status = 'completed',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = :storyline_id
                    """), {
                        "summary": result["master_summary"],
                        "storyline_id": storyline_id
                    })
                    db.commit()
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"Error updating storyline with ML results: {e}")
            
            return {"data": result}
            
        except Exception as e:
            logger.error(f"Error processing storyline ML: {e}")
            return {
                "error": str(e),
                "data": {
                    "master_summary": "Error processing storyline",
                    "timeline_summary": "Error processing storyline",
                    "key_entities": {},
                    "sentiment_trend": {"overall": 0.0, "trend": "error"},
                    "source_diversity": {"score": 0.0, "sources": [], "total_sources": 0, "total_articles": 0},
                    "ml_status": "error",
                    "ml_error": str(e)
                }
            }

    async def get_enhanced_storyline_analysis(self, storyline_id: str) -> Dict[str, Any]:
        """Get existing enhanced storyline analysis from database"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Get multi-perspective analysis
                mpa_query = text("""
                    SELECT synthesized_analysis, perspective_agreement, key_disagreements,
                           consensus_score, analysis_quality_score, created_at
                    FROM multi_perspective_analysis 
                    WHERE storyline_id = :storyline_id 
                    ORDER BY created_at DESC 
                    LIMIT 1
                """)
                mpa_result = db.execute(mpa_query, {"storyline_id": storyline_id}).fetchone()
                
                # Get individual perspectives
                perspectives_query = text("""
                    SELECT perspective_type, analysis_content, confidence_score,
                           key_points, supporting_evidence, created_at
                    FROM analysis_perspectives 
                    WHERE storyline_id = :storyline_id
                    ORDER BY created_at DESC
                """)
                perspectives_result = db.execute(perspectives_query, {"storyline_id": storyline_id}).fetchall()
                
                # Get basic storyline info
                storyline_data = await self.get_storyline_articles(storyline_id)
                
                result = {
                    "storyline_id": storyline_id,
                    "storyline_data": storyline_data,
                    "multi_perspective_analysis": None,
                    "individual_perspectives": {},
                    "analysis_available": False
                }
                
                if mpa_result:
                    result["multi_perspective_analysis"] = {
                        "synthesized_analysis": mpa_result[0],
                        "perspective_agreement": json.loads(mpa_result[1]) if mpa_result[1] else {},
                        "key_disagreements": json.loads(mpa_result[2]) if mpa_result[2] else [],
                        "consensus_score": float(mpa_result[3]) if mpa_result[3] else 0.0,
                        "analysis_quality_score": float(mpa_result[4]) if mpa_result[4] else 0.0,
                        "created_at": mpa_result[5].isoformat() if mpa_result[5] else None
                    }
                    result["analysis_available"] = True
                
                for row in perspectives_result:
                    result["individual_perspectives"][row[0]] = {
                        "analysis_content": row[1],
                        "confidence_score": float(row[2]) if row[2] else 0.0,
                        "key_points": json.loads(row[3]) if row[3] else [],
                        "supporting_evidence": json.loads(row[4]) if row[4] else [],
                        "created_at": row[5].isoformat() if row[5] else None
                    }
                
                return result
                
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error getting enhanced storyline analysis: {e}")
            return {"error": str(e)}

# Global instance
_multi_perspective_storyline_service = None

def get_multi_perspective_storyline_service(ml_service=None, rag_service=None) -> MultiPerspectiveStorylineService:
    """Get global multi-perspective storyline service instance"""
    global _multi_perspective_storyline_service
    if _multi_perspective_storyline_service is None:
        _multi_perspective_storyline_service = MultiPerspectiveStorylineService(ml_service=ml_service, rag_service=rag_service)
    return _multi_perspective_storyline_service

# Backward compatibility alias
def get_enhanced_storyline_service(ml_service=None, rag_service=None) -> MultiPerspectiveStorylineService:
    """Backward compatibility alias - use get_multi_perspective_storyline_service instead"""
    return get_multi_perspective_storyline_service(ml_service, rag_service)
