"""
Predictive Analysis Service for News Intelligence System v3.0
Provides comprehensive predictive analysis and future outlook
"""

import asyncio
import logging
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from enum import Enum

from database.connection import get_db
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class PredictionHorizon(Enum):
    """Available prediction time horizons"""
    SHORT_TERM = "short_term"  # 1-6 months
    MEDIUM_TERM = "medium_term"  # 6-24 months
    LONG_TERM = "long_term"  # 2+ years

@dataclass
class PredictionScenario:
    """Prediction scenario data structure"""
    scenario_id: str
    scenario_name: str
    description: str
    probability: float
    confidence_level: float
    key_factors: List[str]
    potential_outcomes: List[str]
    risk_factors: List[str]
    opportunities: List[str]
    metadata: Dict[str, Any]

@dataclass
class UncertaintyFactor:
    """Uncertainty factor data structure"""
    factor_id: str
    factor_name: str
    description: str
    impact_level: str  # low, medium, high, critical
    probability_of_change: float
    potential_impact: str
    monitoring_indicators: List[str]
    metadata: Dict[str, Any]

@dataclass
class PredictiveAnalysis:
    """Predictive analysis data structure"""
    horizon: str
    prediction_content: str
    confidence_level: float
    key_scenarios: List[PredictionScenario]
    uncertainty_factors: List[UncertaintyFactor]
    monitoring_indicators: List[str]
    prediction_metadata: Dict[str, Any]

@dataclass
class ComprehensivePredictionResult:
    """Result of comprehensive predictive analysis"""
    storyline_id: str
    predictions: Dict[str, PredictiveAnalysis]
    overall_confidence: float
    key_uncertainties: List[UncertaintyFactor]
    scenario_planning: Dict[str, Any]
    monitoring_recommendations: List[Dict[str, Any]]
    prediction_quality_score: float

class PredictiveAnalysisService:
    """
    Predictive analysis service that provides future outlook and scenario planning
    """
    
    def __init__(self, ml_service=None, historical_service=None):
        """
        Initialize the Predictive Analysis Service
        
        Args:
            ml_service: ML summarization service instance
            historical_service: Historical context service instance
        """
        self.ml_service = ml_service
        self.historical_service = historical_service
        
        # Prediction horizon configurations
        self.prediction_horizons = {
            PredictionHorizon.SHORT_TERM: {
                'name': 'Short-term Predictions',
                'description': 'Predictions for 1-6 months ahead',
                'time_range_months': 6,
                'focus_areas': ['immediate_developments', 'near_term_impacts', 'quick_responses'],
                'confidence_threshold': 0.6,
                'system_prompt': """You are a senior strategic analyst specializing in short-term forecasting and immediate impact assessment. Focus on:
- Immediate developments and near-term consequences
- Quick response strategies and tactical approaches
- Short-term risk mitigation and opportunity capture
- Operational implications and resource requirements
- Stakeholder reactions and market responses

Provide specific, actionable insights for immediate decision-making."""
            },
            PredictionHorizon.MEDIUM_TERM: {
                'name': 'Medium-term Predictions',
                'description': 'Predictions for 6-24 months ahead',
                'time_range_months': 18,
                'focus_areas': ['strategic_developments', 'policy_changes', 'market_evolution'],
                'confidence_threshold': 0.5,
                'system_prompt': """You are a senior strategic analyst specializing in medium-term forecasting and strategic planning. Focus on:
- Strategic developments and policy evolution
- Market and economic trends
- Organizational and institutional changes
- Technology adoption and innovation
- Social and cultural shifts

Provide strategic insights for medium-term planning and decision-making."""
            },
            PredictionHorizon.LONG_TERM: {
                'name': 'Long-term Predictions',
                'description': 'Predictions for 2+ years ahead',
                'time_range_months': 36,
                'focus_areas': ['structural_changes', 'paradigm_shifts', 'generational_impacts'],
                'confidence_threshold': 0.4,
                'system_prompt': """You are a senior strategic analyst specializing in long-term forecasting and scenario planning. Focus on:
- Structural changes and paradigm shifts
- Generational and cultural transformations
- Technological and economic revolutions
- Geopolitical and global order changes
- Environmental and sustainability impacts

Provide visionary insights for long-term strategic planning and future preparedness."""
            }
        }
        
        # Scenario types
        self.scenario_types = {
            'optimistic': {
                'name': 'Optimistic Scenario',
                'description': 'Best-case development scenario',
                'probability_range': (0.2, 0.4),
                'key_characteristics': ['positive_outcomes', 'successful_mitigation', 'opportunity_capture']
            },
            'realistic': {
                'name': 'Realistic Scenario',
                'description': 'Most likely development scenario',
                'probability_range': (0.4, 0.6),
                'key_characteristics': ['balanced_outcomes', 'mixed_results', 'moderate_changes']
            },
            'pessimistic': {
                'name': 'Pessimistic Scenario',
                'description': 'Worst-case development scenario',
                'probability_range': (0.2, 0.4),
                'key_characteristics': ['negative_outcomes', 'escalation', 'crisis_conditions']
            },
            'disruptive': {
                'name': 'Disruptive Scenario',
                'description': 'Unexpected disruption scenario',
                'probability_range': (0.1, 0.3),
                'key_characteristics': ['unexpected_events', 'rapid_change', 'paradigm_shift']
            }
        }
    
    async def generate_predictive_analysis(self, storyline_id: str, current_analysis: Dict[str, Any]) -> ComprehensivePredictionResult:
        """
        Generate comprehensive predictive analysis for a storyline
        
        Args:
            storyline_id: ID of the storyline
            current_analysis: Current analysis data (multi-perspective, impact assessment, etc.)
            
        Returns:
            ComprehensivePredictionResult with all prediction horizons
        """
        try:
            logger.info(f"Generating predictive analysis for storyline: {storyline_id}")
            
            # Generate predictions for each horizon
            predictions = {}
            for horizon in PredictionHorizon:
                logger.info(f"Generating {horizon.value} predictions")
                
                prediction = await self._generate_horizon_predictions(
                    storyline_id, current_analysis, horizon
                )
                predictions[horizon.value] = prediction
                
                # Store in database
                await self._store_predictive_analysis(storyline_id, prediction)
            
            # Identify key uncertainties
            key_uncertainties = self._identify_key_uncertainties(predictions)
            
            # Generate scenario planning
            scenario_planning = await self._generate_scenario_planning(predictions, key_uncertainties)
            
            # Generate monitoring recommendations
            monitoring_recommendations = self._generate_monitoring_recommendations(predictions, key_uncertainties)
            
            # Calculate overall confidence
            overall_confidence = self._calculate_overall_confidence(predictions)
            
            # Calculate prediction quality score
            prediction_quality_score = self._calculate_prediction_quality_score(predictions, key_uncertainties)
            
            # Create result
            result = ComprehensivePredictionResult(
                storyline_id=storyline_id,
                predictions=predictions,
                overall_confidence=overall_confidence,
                key_uncertainties=key_uncertainties,
                scenario_planning=scenario_planning,
                monitoring_recommendations=monitoring_recommendations,
                prediction_quality_score=prediction_quality_score
            )
            
            logger.info(f"Predictive analysis generated for storyline: {storyline_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error generating predictive analysis: {e}")
            raise
    
    async def _generate_horizon_predictions(self, storyline_id: str, current_analysis: Dict[str, Any], 
                                          horizon: PredictionHorizon) -> PredictiveAnalysis:
        """Generate predictions for a specific time horizon"""
        try:
            config = self.prediction_horizons[horizon]
            
            # Prepare analysis context
            analysis_context = self._prepare_analysis_context(current_analysis)
            
            # Create prediction prompt
            system_prompt = config['system_prompt']
            user_prompt = self._create_prediction_prompt(storyline_id, analysis_context, horizon)
            
            # Generate prediction using ML service
            if self.ml_service:
                prediction_result = await self._call_ml_service(system_prompt, user_prompt)
                prediction_content = prediction_result.get('summary', '')
                confidence_level = prediction_result.get('confidence_score', 0.5)
            else:
                # Fallback prediction
                prediction_content = await self._generate_fallback_prediction(horizon, analysis_context)
                confidence_level = 0.3
            
            # Generate key scenarios
            key_scenarios = await self._generate_key_scenarios(horizon, analysis_context)
            
            # Identify uncertainty factors
            uncertainty_factors = self._identify_uncertainty_factors(horizon, analysis_context)
            
            # Generate monitoring indicators
            monitoring_indicators = self._generate_monitoring_indicators(horizon, analysis_context)
            
            # Create prediction metadata
            prediction_metadata = {
                'horizon_name': config['name'],
                'time_range_months': config['time_range_months'],
                'focus_areas': config['focus_areas'],
                'confidence_threshold': config['confidence_threshold'],
                'generated_at': datetime.now(timezone.utc).isoformat()
            }
            
            return PredictiveAnalysis(
                horizon=horizon.value,
                prediction_content=prediction_content,
                confidence_level=confidence_level,
                key_scenarios=key_scenarios,
                uncertainty_factors=uncertainty_factors,
                monitoring_indicators=monitoring_indicators,
                prediction_metadata=prediction_metadata
            )
            
        except Exception as e:
            logger.error(f"Error generating {horizon.value} predictions: {e}")
            # Return minimal prediction on error
            return PredictiveAnalysis(
                horizon=horizon.value,
                prediction_content=f"Prediction for {horizon.value} could not be generated due to error: {str(e)}",
                confidence_level=0.0,
                key_scenarios=[],
                uncertainty_factors=[],
                monitoring_indicators=[],
                prediction_metadata={'error': str(e)}
            )
    
    def _prepare_analysis_context(self, current_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare current analysis context for prediction"""
        context = {
            'multi_perspective': current_analysis.get('multi_perspective', {}),
            'impact_assessment': current_analysis.get('impact_assessment', {}),
            'historical_context': current_analysis.get('historical_context', {}),
            'basic_summary': current_analysis.get('basic_summary', {}),
            'rag_context': current_analysis.get('rag_context', {})
        }
        
        # Extract key insights
        context['key_insights'] = []
        
        # From multi-perspective analysis
        if context['multi_perspective']:
            consensus_score = context['multi_perspective'].get('consensus_score', 0.0)
            context['key_insights'].append(f"Multi-perspective consensus: {consensus_score:.2f}")
        
        # From impact assessment
        if context['impact_assessment']:
            overall_impact = context['impact_assessment'].get('overall_impact_score', 0.0)
            context['key_insights'].append(f"Overall impact score: {overall_impact:.2f}")
        
        # From historical context
        if context['historical_context']:
            patterns_count = context['historical_context'].get('patterns_identified', 0)
            context['key_insights'].append(f"Historical patterns identified: {patterns_count}")
        
        return context
    
    def _create_prediction_prompt(self, storyline_id: str, analysis_context: Dict[str, Any], 
                                horizon: PredictionHorizon) -> str:
        """Create prediction prompt for ML service"""
        config = self.prediction_horizons[horizon]
        
        prompt = f"""
        Generate {config['name']} for the following storyline:
        
        Storyline ID: {storyline_id}
        Time Horizon: {config['time_range_months']} months
        
        Current Analysis Context:
        {json.dumps(analysis_context, indent=2)}
        
        Focus Areas: {', '.join(config['focus_areas'])}
        
        Provide comprehensive predictions covering:
        1. **Key Developments**: What are the most likely developments in this timeframe?
        2. **Impact Assessment**: How will current trends and patterns evolve?
        3. **Risk Factors**: What are the main risks and uncertainties?
        4. **Opportunities**: What opportunities might emerge?
        5. **Stakeholder Implications**: How will different stakeholders be affected?
        6. **Resource Requirements**: What resources will be needed?
        7. **Monitoring Indicators**: What should be monitored closely?
        8. **Scenario Variations**: What are the different possible outcomes?
        
        Structure your response with clear sections and actionable insights.
        """
        
        return prompt
    
    async def _generate_fallback_prediction(self, horizon: PredictionHorizon, 
                                          analysis_context: Dict[str, Any]) -> str:
        """Generate fallback prediction when ML service is not available"""
        config = self.prediction_horizons[horizon]
        
        prediction = f"""# {config['name']}
        
## Key Developments
Based on current analysis, the following developments are likely in the next {config['time_range_months']} months:

- Continued evolution of current trends
- Potential policy and regulatory changes
- Market and stakeholder responses
- Technological and social adaptations

## Impact Assessment
Current impact patterns suggest:
- Moderate to high impact potential
- Multiple stakeholder groups affected
- Cross-sector implications likely

## Risk Factors
Key risks to monitor:
- Uncertainty in current trajectory
- External factors and disruptions
- Stakeholder resistance or support
- Resource and capacity constraints

## Opportunities
Potential opportunities:
- Strategic positioning advantages
- Innovation and adaptation possibilities
- Partnership and collaboration opportunities
- Market and competitive advantages

## Monitoring Recommendations
- Track key performance indicators
- Monitor stakeholder sentiment
- Watch for policy and regulatory changes
- Assess resource and capacity needs

*Note: This is a basic prediction generated without full ML processing. For comprehensive analysis, the ML service should be available.*
"""
        
        return prediction
    
    async def _generate_key_scenarios(self, horizon: PredictionHorizon, 
                                    analysis_context: Dict[str, Any]) -> List[PredictionScenario]:
        """Generate key scenarios for the prediction horizon"""
        scenarios = []
        
        for scenario_type, scenario_config in self.scenario_types.items():
            # Calculate probability based on current analysis
            probability = self._calculate_scenario_probability(scenario_type, analysis_context)
            
            if probability > 0.1:  # Only include scenarios with >10% probability
                scenario = PredictionScenario(
                    scenario_id=f"{horizon.value}_{scenario_type}",
                    scenario_name=scenario_config['name'],
                    description=f"{scenario_config['description']} for {horizon.value} horizon",
                    probability=probability,
                    confidence_level=min(probability * 1.5, 1.0),
                    key_factors=self._identify_scenario_factors(scenario_type, analysis_context),
                    potential_outcomes=self._generate_scenario_outcomes(scenario_type, horizon),
                    risk_factors=self._identify_scenario_risks(scenario_type, analysis_context),
                    opportunities=self._identify_scenario_opportunities(scenario_type, analysis_context),
                    metadata={
                        'scenario_type': scenario_type,
                        'horizon': horizon.value,
                        'generated_at': datetime.now(timezone.utc).isoformat()
                    }
                )
                scenarios.append(scenario)
        
        return scenarios
    
    def _calculate_scenario_probability(self, scenario_type: str, analysis_context: Dict[str, Any]) -> float:
        """Calculate probability for a scenario type"""
        base_probabilities = {
            'optimistic': 0.25,
            'realistic': 0.45,
            'pessimistic': 0.20,
            'disruptive': 0.10
        }
        
        base_prob = base_probabilities.get(scenario_type, 0.1)
        
        # Adjust based on current analysis
        if 'impact_assessment' in analysis_context:
            impact_score = analysis_context['impact_assessment'].get('overall_impact_score', 0.5)
            if scenario_type == 'pessimistic' and impact_score > 0.7:
                base_prob += 0.1
            elif scenario_type == 'optimistic' and impact_score < 0.3:
                base_prob += 0.1
        
        return min(base_prob, 0.8)  # Cap at 80%
    
    def _identify_scenario_factors(self, scenario_type: str, analysis_context: Dict[str, Any]) -> List[str]:
        """Identify key factors for a scenario"""
        factors = []
        
        # Common factors
        factors.extend([
            "Current trend continuation",
            "Stakeholder responses",
            "External environment changes",
            "Resource availability"
        ])
        
        # Scenario-specific factors
        if scenario_type == 'optimistic':
            factors.extend([
                "Successful risk mitigation",
                "Stakeholder alignment",
                "Favorable external conditions"
            ])
        elif scenario_type == 'pessimistic':
            factors.extend([
                "Risk escalation",
                "Stakeholder resistance",
                "Adverse external conditions"
            ])
        elif scenario_type == 'disruptive':
            factors.extend([
                "Unexpected events",
                "Technology breakthroughs",
                "Regulatory changes"
            ])
        
        return factors[:8]  # Limit to 8 factors
    
    def _generate_scenario_outcomes(self, scenario_type: str, horizon: PredictionHorizon) -> List[str]:
        """Generate potential outcomes for a scenario"""
        outcomes = []
        
        if scenario_type == 'optimistic':
            outcomes = [
                "Successful implementation of strategies",
                "Positive stakeholder engagement",
                "Achievement of key objectives",
                "Market and competitive advantages"
            ]
        elif scenario_type == 'realistic':
            outcomes = [
                "Mixed results with some successes",
                "Moderate stakeholder support",
                "Partial achievement of objectives",
                "Balanced market response"
            ]
        elif scenario_type == 'pessimistic':
            outcomes = [
                "Challenges in implementation",
                "Stakeholder resistance or opposition",
                "Limited achievement of objectives",
                "Market and competitive disadvantages"
            ]
        elif scenario_type == 'disruptive':
            outcomes = [
                "Rapid and unexpected changes",
                "Paradigm shifts in approach",
                "New opportunities and challenges",
                "Fundamental restructuring required"
            ]
        
        return outcomes
    
    def _identify_scenario_risks(self, scenario_type: str, analysis_context: Dict[str, Any]) -> List[str]:
        """Identify risks for a scenario"""
        risks = []
        
        # Common risks
        risks.extend([
            "Resource constraints",
            "Timeline delays",
            "Stakeholder resistance"
        ])
        
        # Scenario-specific risks
        if scenario_type == 'pessimistic':
            risks.extend([
                "Crisis escalation",
                "Complete failure",
                "Reputation damage"
            ])
        elif scenario_type == 'disruptive':
            risks.extend([
                "Loss of control",
                "Rapid obsolescence",
                "Strategic confusion"
            ])
        
        return risks[:6]  # Limit to 6 risks
    
    def _identify_scenario_opportunities(self, scenario_type: str, analysis_context: Dict[str, Any]) -> List[str]:
        """Identify opportunities for a scenario"""
        opportunities = []
        
        # Common opportunities
        opportunities.extend([
            "Strategic positioning",
            "Partnership development",
            "Innovation potential"
        ])
        
        # Scenario-specific opportunities
        if scenario_type == 'optimistic':
            opportunities.extend([
                "Market leadership",
                "Competitive advantages",
                "Stakeholder loyalty"
            ])
        elif scenario_type == 'disruptive':
            opportunities.extend([
                "First-mover advantages",
                "New market creation",
                "Technology leadership"
            ])
        
        return opportunities[:6]  # Limit to 6 opportunities
    
    def _identify_uncertainty_factors(self, horizon: PredictionHorizon, 
                                    analysis_context: Dict[str, Any]) -> List[UncertaintyFactor]:
        """Identify uncertainty factors for the prediction horizon"""
        factors = []
        
        # Common uncertainty factors
        common_factors = [
            {
                'name': 'External Environment',
                'description': 'Changes in external political, economic, or social environment',
                'impact_level': 'high',
                'probability_of_change': 0.6
            },
            {
                'name': 'Stakeholder Behavior',
                'description': 'Unpredictable changes in stakeholder responses and actions',
                'impact_level': 'medium',
                'probability_of_change': 0.7
            },
            {
                'name': 'Resource Availability',
                'description': 'Changes in resource availability and allocation',
                'impact_level': 'medium',
                'probability_of_change': 0.5
            },
            {
                'name': 'Technology Changes',
                'description': 'Rapid technological developments and disruptions',
                'impact_level': 'high',
                'probability_of_change': 0.4
            }
        ]
        
        for i, factor_data in enumerate(common_factors):
            factor = UncertaintyFactor(
                factor_id=f"uncertainty_{horizon.value}_{i}",
                factor_name=factor_data['name'],
                description=factor_data['description'],
                impact_level=factor_data['impact_level'],
                probability_of_change=factor_data['probability_of_change'],
                potential_impact=f"Potential {factor_data['impact_level']} impact on {horizon.value} outcomes",
                monitoring_indicators=[
                    f"Monitor {factor_data['name'].lower()} indicators",
                    f"Track {factor_data['name'].lower()} trends",
                    f"Assess {factor_data['name'].lower()} changes"
                ],
                metadata={
                    'horizon': horizon.value,
                    'generated_at': datetime.now(timezone.utc).isoformat()
                }
            )
            factors.append(factor)
        
        return factors
    
    def _generate_monitoring_indicators(self, horizon: PredictionHorizon, 
                                      analysis_context: Dict[str, Any]) -> List[str]:
        """Generate monitoring indicators for the prediction horizon"""
        indicators = []
        
        # Common monitoring indicators
        indicators.extend([
            "Key performance metrics",
            "Stakeholder sentiment",
            "Market conditions",
            "Regulatory changes"
        ])
        
        # Horizon-specific indicators
        if horizon == PredictionHorizon.SHORT_TERM:
            indicators.extend([
                "Immediate response metrics",
                "Quick wins indicators",
                "Crisis management metrics"
            ])
        elif horizon == PredictionHorizon.MEDIUM_TERM:
            indicators.extend([
                "Strategic progress indicators",
                "Policy implementation metrics",
                "Market evolution indicators"
            ])
        elif horizon == PredictionHorizon.LONG_TERM:
            indicators.extend([
                "Structural change indicators",
                "Paradigm shift metrics",
                "Generational impact indicators"
            ])
        
        return indicators[:10]  # Limit to 10 indicators
    
    def _identify_key_uncertainties(self, predictions: Dict[str, PredictiveAnalysis]) -> List[UncertaintyFactor]:
        """Identify key uncertainties across all prediction horizons"""
        all_uncertainties = []
        
        for prediction in predictions.values():
            all_uncertainties.extend(prediction.uncertainty_factors)
        
        # Sort by impact level and probability
        all_uncertainties.sort(key=lambda x: (
            {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}.get(x.impact_level, 0),
            -x.probability_of_change
        ), reverse=True)
        
        return all_uncertainties[:15]  # Top 15 uncertainties
    
    async def _generate_scenario_planning(self, predictions: Dict[str, PredictiveAnalysis], 
                                        key_uncertainties: List[UncertaintyFactor]) -> Dict[str, Any]:
        """Generate comprehensive scenario planning"""
        scenario_planning = {
            'scenario_matrix': {},
            'contingency_plans': [],
            'decision_points': [],
            'resource_requirements': {},
            'timeline_milestones': []
        }
        
        # Create scenario matrix
        for horizon, prediction in predictions.items():
            scenario_planning['scenario_matrix'][horizon] = {
                'scenarios': [{
                    'name': scenario.scenario_name,
                    'probability': scenario.probability,
                    'confidence': scenario.confidence_level
                } for scenario in prediction.key_scenarios]
            }
        
        # Generate contingency plans
        for uncertainty in key_uncertainties[:5]:  # Top 5 uncertainties
            scenario_planning['contingency_plans'].append({
                'uncertainty': uncertainty.factor_name,
                'plan': f"Contingency plan for {uncertainty.factor_name}",
                'triggers': uncertainty.monitoring_indicators,
                'actions': [
                    f"Monitor {uncertainty.factor_name} closely",
                    f"Prepare response for {uncertainty.impact_level} impact",
                    f"Develop mitigation strategies"
                ]
            })
        
        # Generate decision points
        scenario_planning['decision_points'] = [
            "Review progress at 3-month intervals",
            "Assess scenario probabilities quarterly",
            "Update predictions based on new information",
            "Adjust strategies based on outcomes"
        ]
        
        return scenario_planning
    
    def _generate_monitoring_recommendations(self, predictions: Dict[str, PredictiveAnalysis], 
                                           key_uncertainties: List[UncertaintyFactor]) -> List[Dict[str, Any]]:
        """Generate monitoring recommendations"""
        recommendations = []
        
        # Generate recommendations for each horizon
        for horizon, prediction in predictions.items():
            recommendations.append({
                'horizon': horizon,
                'priority_indicators': prediction.monitoring_indicators[:5],
                'monitoring_frequency': 'weekly' if horizon == 'short_term' else 'monthly',
                'review_schedule': 'bi-weekly' if horizon == 'short_term' else 'quarterly'
            })
        
        # Generate recommendations for key uncertainties
        for uncertainty in key_uncertainties[:5]:  # Top 5 uncertainties
            recommendations.append({
                'uncertainty': uncertainty.factor_name,
                'monitoring_indicators': uncertainty.monitoring_indicators,
                'monitoring_frequency': 'daily' if uncertainty.impact_level == 'critical' else 'weekly',
                'alert_thresholds': f"Alert when {uncertainty.factor_name} changes significantly"
            })
        
        return recommendations
    
    def _calculate_overall_confidence(self, predictions: Dict[str, PredictiveAnalysis]) -> float:
        """Calculate overall confidence across all predictions"""
        if not predictions:
            return 0.0
        
        confidence_scores = [prediction.confidence_level for prediction in predictions.values()]
        return sum(confidence_scores) / len(confidence_scores)
    
    def _calculate_prediction_quality_score(self, predictions: Dict[str, PredictiveAnalysis], 
                                          key_uncertainties: List[UncertaintyFactor]) -> float:
        """Calculate overall prediction quality score"""
        try:
            quality_factors = []
            
            # Prediction coverage factor
            coverage_factor = len(predictions) / 3  # 3 horizons
            quality_factors.append(min(coverage_factor, 1.0))
            
            # Confidence factor
            if predictions:
                avg_confidence = sum(p.confidence_level for p in predictions.values()) / len(predictions)
                quality_factors.append(avg_confidence)
            
            # Scenario diversity factor
            total_scenarios = sum(len(p.key_scenarios) for p in predictions.values())
            scenario_factor = min(total_scenarios / 12, 1.0)  # 12 scenarios across all horizons
            quality_factors.append(scenario_factor)
            
            # Uncertainty coverage factor
            uncertainty_factor = min(len(key_uncertainties) / 10, 1.0)  # 10 uncertainties
            quality_factors.append(uncertainty_factor)
            
            return sum(quality_factors) / len(quality_factors) if quality_factors else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating prediction quality score: {e}")
            return 0.0
    
    async def _call_ml_service(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Call ML service for prediction generation"""
        try:
            if hasattr(self.ml_service, 'generate_summary'):
                result = self.ml_service.generate_summary(user_prompt, system_prompt)
                return result
            else:
                return {'summary': 'ML service not available', 'confidence_score': 0.0}
        except Exception as e:
            logger.error(f"Error calling ML service: {e}")
            return {'summary': 'ML service error', 'confidence_score': 0.0}
    
    async def _store_predictive_analysis(self, storyline_id: str, prediction: PredictiveAnalysis):
        """Store predictive analysis in database"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                insert_query = text("""
                    INSERT INTO predictive_analysis (
                        storyline_id, prediction_horizon, prediction_content,
                        confidence_level, key_scenarios, uncertainty_factors,
                        monitoring_indicators, prediction_metadata
                    ) VALUES (
                        :storyline_id, :prediction_horizon, :prediction_content,
                        :confidence_level, :key_scenarios, :uncertainty_factors,
                        :monitoring_indicators, :prediction_metadata
                    )
                """)
                
                db.execute(insert_query, {
                    'storyline_id': storyline_id,
                    'prediction_horizon': prediction.horizon,
                    'prediction_content': prediction.prediction_content,
                    'confidence_level': prediction.confidence_level,
                    'key_scenarios': json.dumps([{
                        'scenario_id': s.scenario_id,
                        'scenario_name': s.scenario_name,
                        'probability': s.probability,
                        'confidence_level': s.confidence_level
                    } for s in prediction.key_scenarios]),
                    'uncertainty_factors': json.dumps([{
                        'factor_id': u.factor_id,
                        'factor_name': u.factor_name,
                        'impact_level': u.impact_level,
                        'probability_of_change': u.probability_of_change
                    } for u in prediction.uncertainty_factors]),
                    'monitoring_indicators': json.dumps(prediction.monitoring_indicators),
                    'prediction_metadata': json.dumps(prediction.prediction_metadata)
                })
                db.commit()
                
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error storing predictive analysis: {e}")

# Global instance
_predictive_analysis_service = None

def get_predictive_analysis_service(ml_service=None, historical_service=None) -> PredictiveAnalysisService:
    """Get global predictive analysis service instance"""
    global _predictive_analysis_service
    if _predictive_analysis_service is None:
        _predictive_analysis_service = PredictiveAnalysisService(ml_service, historical_service)
    return _predictive_analysis_service

