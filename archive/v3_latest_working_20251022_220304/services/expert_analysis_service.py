"""
Expert Analysis Service for News Intelligence System v3.0
Provides comprehensive expert analysis integration and academic research synthesis
"""

import asyncio
import logging
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from enum import Enum

from config.database import get_db
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class ExpertSourceType(Enum):
    """Available expert analysis sources"""
    ACADEMIC_RESEARCH = "academic_research"
    THINK_TANK_REPORTS = "think_tank_reports"
    EXPERT_OPINIONS = "expert_opinions"
    POLICY_PAPERS = "policy_papers"
    INDUSTRY_ANALYSIS = "industry_analysis"
    INTERNATIONAL_ORGS = "international_organizations"

class ExpertCredibility(Enum):
    """Expert credibility levels"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"

@dataclass
class ExpertSource:
    """Expert source data structure"""
    source_id: str
    source_name: str
    source_type: str
    credibility_level: str
    expertise_areas: List[str]
    institutional_affiliation: str
    publication_date: str
    source_url: str
    metadata: Dict[str, Any]

@dataclass
class ExpertAnalysis:
    """Expert analysis data structure"""
    analysis_id: str
    source: ExpertSource
    analysis_content: str
    key_insights: List[str]
    methodology: str
    confidence_score: float
    relevance_score: float
    credibility_score: float
    supporting_evidence: List[Dict[str, Any]]
    limitations: List[str]
    metadata: Dict[str, Any]

@dataclass
class ExpertSynthesis:
    """Expert synthesis data structure"""
    synthesis_id: str
    storyline_id: str
    expert_analyses: List[ExpertAnalysis]
    consensus_analysis: str
    key_disagreements: List[Dict[str, Any]]
    expert_consensus_score: float
    synthesis_quality_score: float
    methodology_notes: str
    synthesis_metadata: Dict[str, Any]

@dataclass
class ComprehensiveExpertResult:
    """Result of comprehensive expert analysis"""
    storyline_id: str
    expert_synthesis: ExpertSynthesis
    source_coverage: Dict[str, int]
    credibility_distribution: Dict[str, int]
    expertise_areas_covered: List[str]
    synthesis_quality_score: float
    expert_recommendations: List[Dict[str, Any]]

class ExpertAnalysisService:
    """
    Expert analysis service that integrates academic research, think tank reports, and expert opinions
    """
    
    def __init__(self, ml_service=None, rag_service=None):
        """
        Initialize the Expert Analysis Service
        
        Args:
            ml_service: ML summarization service instance
            rag_service: RAG service instance
        """
        self.ml_service = ml_service
        self.rag_service = rag_service
        
        # Expert source configurations
        self.expert_sources = {
            ExpertSourceType.ACADEMIC_RESEARCH: {
                'name': 'Academic Research',
                'description': 'Peer-reviewed academic papers and research',
                'credibility_weight': 0.9,
                'expertise_areas': ['political_science', 'economics', 'sociology', 'international_relations', 'public_policy'],
                'search_keywords': ['research', 'study', 'analysis', 'academic', 'peer-reviewed'],
                'system_prompt': """You are a senior academic researcher and policy analyst with extensive experience in peer-reviewed research and scholarly analysis. Focus on:
- Rigorous academic methodology and evidence-based analysis
- Theoretical frameworks and empirical research
- Peer-reviewed sources and academic credibility
- Research limitations and methodological considerations
- Scholarly consensus and academic debates
- Long-term research implications and policy relevance

Provide scholarly insights grounded in academic research and theoretical frameworks."""
            },
            
            ExpertSourceType.THINK_TANK_REPORTS: {
                'name': 'Think Tank Reports',
                'description': 'Policy research from think tanks and research institutions',
                'credibility_weight': 0.8,
                'expertise_areas': ['policy_analysis', 'strategic_studies', 'economic_policy', 'foreign_policy', 'social_policy'],
                'search_keywords': ['think_tank', 'policy_brief', 'research_report', 'institutional_analysis'],
                'system_prompt': """You are a senior policy analyst and think tank researcher with extensive experience in policy research and institutional analysis. Focus on:
- Policy implications and strategic recommendations
- Institutional perspectives and organizational analysis
- Policy briefs and research reports
- Strategic thinking and long-term planning
- Cross-institutional collaboration and policy networks
- Practical policy implementation and governance

Provide policy-focused insights from institutional research and strategic analysis."""
            },
            
            ExpertSourceType.EXPERT_OPINIONS: {
                'name': 'Expert Opinions',
                'description': 'Expert commentary and professional opinions',
                'credibility_weight': 0.7,
                'expertise_areas': ['professional_expertise', 'industry_knowledge', 'practical_experience', 'field_expertise'],
                'search_keywords': ['expert', 'opinion', 'commentary', 'analysis', 'professional'],
                'system_prompt': """You are a senior expert and professional with extensive field experience and domain expertise. Focus on:
- Professional insights and practical experience
- Industry knowledge and field expertise
- Expert commentary and professional opinions
- Real-world implications and practical considerations
- Professional networks and expert communities
- Field-specific knowledge and specialized expertise

Provide expert insights based on professional experience and domain expertise."""
            },
            
            ExpertSourceType.POLICY_PAPERS: {
                'name': 'Policy Papers',
                'description': 'Government and institutional policy documents',
                'credibility_weight': 0.8,
                'expertise_areas': ['government_policy', 'regulatory_analysis', 'public_administration', 'governance', 'institutional_policy'],
                'search_keywords': ['policy', 'government', 'regulatory', 'administrative', 'governance'],
                'system_prompt': """You are a senior policy analyst and government relations expert with extensive experience in policy development and regulatory analysis. Focus on:
- Government policy positions and regulatory frameworks
- Administrative procedures and governance structures
- Policy implementation and regulatory compliance
- Government relations and institutional processes
- Public administration and bureaucratic analysis
- Regulatory impact and policy effectiveness

Provide policy insights from government and institutional perspectives."""
            },
            
            ExpertSourceType.INDUSTRY_ANALYSIS: {
                'name': 'Industry Analysis',
                'description': 'Industry-specific analysis and market research',
                'credibility_weight': 0.7,
                'expertise_areas': ['market_analysis', 'industry_trends', 'business_intelligence', 'sector_analysis', 'economic_analysis'],
                'search_keywords': ['industry', 'market', 'business', 'sector', 'economic'],
                'system_prompt': """You are a senior industry analyst and business intelligence expert with extensive experience in market analysis and sector research. Focus on:
- Industry trends and market dynamics
- Business intelligence and sector analysis
- Economic implications and market impacts
- Industry best practices and competitive analysis
- Market research and business strategy
- Sector-specific expertise and industry knowledge

Provide industry-focused insights from market analysis and business intelligence."""
            },
            
            ExpertSourceType.INTERNATIONAL_ORGS: {
                'name': 'International Organizations',
                'description': 'Analysis from international organizations and multilateral institutions',
                'credibility_weight': 0.8,
                'expertise_areas': ['international_relations', 'multilateral_cooperation', 'global_governance', 'international_law', 'development'],
                'search_keywords': ['international', 'multilateral', 'global', 'organization', 'institution'],
                'system_prompt': """You are a senior international relations expert and multilateral analyst with extensive experience in global governance and international cooperation. Focus on:
- International perspectives and global implications
- Multilateral cooperation and international law
- Global governance and international institutions
- Cross-border analysis and international relations
- International development and global policy
- Diplomatic relations and international cooperation

Provide international insights from multilateral and global governance perspectives."""
            }
        }
        
        # Expertise area mappings
        self.expertise_areas = {
            'political_science': {
                'name': 'Political Science',
                'description': 'Political theory, governance, and political systems',
                'keywords': ['politics', 'government', 'governance', 'political', 'democracy', 'authoritarianism']
            },
            'economics': {
                'name': 'Economics',
                'description': 'Economic theory, policy, and market analysis',
                'keywords': ['economic', 'economy', 'market', 'financial', 'monetary', 'fiscal']
            },
            'sociology': {
                'name': 'Sociology',
                'description': 'Social theory, social movements, and social change',
                'keywords': ['social', 'society', 'community', 'culture', 'demographic', 'social_change']
            },
            'international_relations': {
                'name': 'International Relations',
                'description': 'Global politics, diplomacy, and international cooperation',
                'keywords': ['international', 'global', 'diplomatic', 'foreign_policy', 'multilateral', 'geopolitics']
            },
            'public_policy': {
                'name': 'Public Policy',
                'description': 'Policy analysis, implementation, and evaluation',
                'keywords': ['policy', 'public_policy', 'regulation', 'governance', 'administration', 'implementation']
            },
            'technology': {
                'name': 'Technology',
                'description': 'Technology policy, innovation, and digital transformation',
                'keywords': ['technology', 'digital', 'innovation', 'tech', 'cyber', 'artificial_intelligence']
            },
            'environment': {
                'name': 'Environment',
                'description': 'Environmental policy, sustainability, and climate change',
                'keywords': ['environment', 'climate', 'sustainability', 'green', 'ecological', 'environmental']
            },
            'security': {
                'name': 'Security',
                'description': 'Security studies, defense, and risk analysis',
                'keywords': ['security', 'defense', 'military', 'intelligence', 'risk', 'threat']
            }
        }
    
    async def generate_expert_analysis(self, storyline_id: str, storyline_title: str, 
                                    articles: List[Dict], rag_context: Dict[str, Any] = None) -> ComprehensiveExpertResult:
        """
        Generate comprehensive expert analysis for a storyline
        
        Args:
            storyline_id: ID of the storyline
            storyline_title: Title of the storyline
            articles: List of articles in the storyline
            rag_context: Optional RAG context for enhanced analysis
            
        Returns:
            ComprehensiveExpertResult with expert analysis synthesis
        """
        try:
            logger.info(f"Generating expert analysis for storyline: {storyline_id}")
            
            # Identify relevant expertise areas
            expertise_areas = self._identify_expertise_areas(storyline_title, articles, rag_context)
            
            # Search for expert sources
            expert_sources = await self._search_expert_sources(storyline_title, expertise_areas, rag_context)
            
            # Generate expert analyses
            expert_analyses = []
            for source in expert_sources:
                analysis = await self._generate_expert_analysis_for_source(
                    storyline_id, storyline_title, source, articles, rag_context
                )
                if analysis:
                    expert_analyses.append(analysis)
            
            # Synthesize expert analyses
            expert_synthesis = await self._synthesize_expert_analyses(
                storyline_id, expert_analyses, storyline_title
            )
            
            # Calculate source coverage and credibility distribution
            source_coverage = self._calculate_source_coverage(expert_analyses)
            credibility_distribution = self._calculate_credibility_distribution(expert_analyses)
            
            # Generate expert recommendations
            expert_recommendations = self._generate_expert_recommendations(expert_synthesis, expert_analyses)
            
            # Calculate synthesis quality score
            synthesis_quality_score = self._calculate_synthesis_quality_score(expert_synthesis, expert_analyses)
            
            # Create result
            result = ComprehensiveExpertResult(
                storyline_id=storyline_id,
                expert_synthesis=expert_synthesis,
                source_coverage=source_coverage,
                credibility_distribution=credibility_distribution,
                expertise_areas_covered=expertise_areas,
                synthesis_quality_score=synthesis_quality_score,
                expert_recommendations=expert_recommendations
            )
            
            # Store expert analysis
            await self._store_expert_analysis(result)
            
            logger.info(f"Expert analysis generated for storyline: {storyline_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error generating expert analysis: {e}")
            raise
    
    def _identify_expertise_areas(self, storyline_title: str, articles: List[Dict], 
                                rag_context: Dict[str, Any]) -> List[str]:
        """Identify relevant expertise areas for the storyline"""
        expertise_areas = []
        
        # Extract from storyline title and articles
        text_content = storyline_title + " "
        for article in articles[:5]:  # Limit to first 5 articles
            text_content += article.get('title', '') + " " + article.get('content', '')[:500] + " "
        
        # Add RAG context
        if rag_context:
            if 'extracted_topics' in rag_context:
                text_content += " ".join(rag_context['extracted_topics']) + " "
            if 'extracted_entities' in rag_context:
                text_content += " ".join(rag_context['extracted_entities']) + " "
        
        # Match against expertise area keywords
        for area_id, area_config in self.expertise_areas.items():
            keywords = area_config['keywords']
            keyword_matches = sum(1 for keyword in keywords if keyword.lower() in text_content.lower())
            
            if keyword_matches >= 2:  # At least 2 keyword matches
                expertise_areas.append(area_id)
        
        # Ensure we have at least some expertise areas
        if not expertise_areas:
            expertise_areas = ['public_policy', 'political_science']  # Default areas
        
        return expertise_areas[:6]  # Limit to 6 areas
    
    async def _search_expert_sources(self, storyline_title: str, expertise_areas: List[str], 
                                   rag_context: Dict[str, Any]) -> List[ExpertSource]:
        """Search for relevant expert sources"""
        expert_sources = []
        
        # This is a simplified implementation - in production, you would integrate with actual APIs
        for source_type, source_config in self.expert_sources.items():
            # Check if source type is relevant to expertise areas
            if any(area in source_config['expertise_areas'] for area in expertise_areas):
                # Generate mock expert source
                source = ExpertSource(
                    source_id=f"{source_type.value}_{len(expert_sources)}",
                    source_name=f"{source_config['name']} Analysis",
                    source_type=source_type.value,
                    credibility_level=self._determine_credibility_level(source_type),
                    expertise_areas=source_config['expertise_areas'][:3],  # Top 3 areas
                    institutional_affiliation=f"{source_config['name']} Institution",
                    publication_date=self._generate_publication_date(),
                    source_url=f"https://example.com/{source_type.value}/analysis",
                    metadata={
                        'search_keywords': source_config['search_keywords'],
                        'credibility_weight': source_config['credibility_weight'],
                        'generated_at': datetime.now(timezone.utc).isoformat()
                    }
                )
                expert_sources.append(source)
        
        return expert_sources[:8]  # Limit to 8 sources
    
    async def _generate_expert_analysis_for_source(self, storyline_id: str, storyline_title: str, 
                                                 source: ExpertSource, articles: List[Dict], 
                                                 rag_context: Dict[str, Any]) -> Optional[ExpertAnalysis]:
        """Generate expert analysis for a specific source"""
        try:
            source_config = self.expert_sources[ExpertSource(source.source_type)]
            
            # Prepare analysis context
            analysis_context = self._prepare_analysis_context(storyline_title, articles, rag_context)
            
            # Create analysis prompt
            system_prompt = source_config['system_prompt']
            user_prompt = self._create_expert_analysis_prompt(
                storyline_title, analysis_context, source, source_config
            )
            
            # Generate analysis using ML service
            if self.ml_service:
                analysis_result = await self._call_ml_service(system_prompt, user_prompt)
                analysis_content = analysis_result.get('summary', '')
                confidence_score = analysis_result.get('confidence_score', 0.5)
            else:
                # Fallback analysis
                analysis_content = await self._generate_fallback_expert_analysis(source, storyline_title)
                confidence_score = 0.3
            
            # Extract key insights
            key_insights = self._extract_key_insights(analysis_content)
            
            # Generate methodology notes
            methodology = self._generate_methodology_notes(source, source_config)
            
            # Calculate relevance and credibility scores
            relevance_score = self._calculate_relevance_score(analysis_content, storyline_title)
            credibility_score = source_config['credibility_weight']
            
            # Extract supporting evidence
            supporting_evidence = self._extract_supporting_evidence(articles, analysis_content)
            
            # Identify limitations
            limitations = self._identify_limitations(source, analysis_content)
            
            # Create analysis metadata
            analysis_metadata = {
                'source_type': source.source_type,
                'expertise_areas': source.expertise_areas,
                'credibility_level': source.credibility_level,
                'institutional_affiliation': source.institutional_affiliation,
                'generated_at': datetime.now(timezone.utc).isoformat()
            }
            
            return ExpertAnalysis(
                analysis_id=f"expert_analysis_{source.source_id}",
                source=source,
                analysis_content=analysis_content,
                key_insights=key_insights,
                methodology=methodology,
                confidence_score=confidence_score,
                relevance_score=relevance_score,
                credibility_score=credibility_score,
                supporting_evidence=supporting_evidence,
                limitations=limitations,
                metadata=analysis_metadata
            )
            
        except Exception as e:
            logger.error(f"Error generating expert analysis for source {source.source_id}: {e}")
            return None
    
    async def _synthesize_expert_analyses(self, storyline_id: str, expert_analyses: List[ExpertAnalysis], 
                                        storyline_title: str) -> ExpertSynthesis:
        """Synthesize multiple expert analyses into a comprehensive synthesis"""
        try:
            if not expert_analyses:
                return ExpertSynthesis(
                    synthesis_id=f"expert_synthesis_{storyline_id}",
                    storyline_id=storyline_id,
                    expert_analyses=[],
                    consensus_analysis="No expert analyses available for synthesis",
                    key_disagreements=[],
                    expert_consensus_score=0.0,
                    synthesis_quality_score=0.0,
                    methodology_notes="No expert analyses to synthesize",
                    synthesis_metadata={'error': 'No expert analyses available'}
                )
            
            # Generate consensus analysis
            consensus_analysis = await self._generate_consensus_analysis(expert_analyses, storyline_title)
            
            # Identify key disagreements
            key_disagreements = self._identify_key_disagreements(expert_analyses)
            
            # Calculate expert consensus score
            expert_consensus_score = self._calculate_expert_consensus_score(expert_analyses)
            
            # Generate synthesis quality score
            synthesis_quality_score = self._calculate_synthesis_quality_score_from_analyses(expert_analyses)
            
            # Generate methodology notes
            methodology_notes = self._generate_synthesis_methodology_notes(expert_analyses)
            
            # Create synthesis metadata
            synthesis_metadata = {
                'analyses_count': len(expert_analyses),
                'source_types': list(set(analysis.source.source_type for analysis in expert_analyses)),
                'expertise_areas': list(set(area for analysis in expert_analyses for area in analysis.source.expertise_areas)),
                'credibility_levels': list(set(analysis.source.credibility_level for analysis in expert_analyses)),
                'generated_at': datetime.now(timezone.utc).isoformat()
            }
            
            return ExpertSynthesis(
                synthesis_id=f"expert_synthesis_{storyline_id}",
                storyline_id=storyline_id,
                expert_analyses=expert_analyses,
                consensus_analysis=consensus_analysis,
                key_disagreements=key_disagreements,
                expert_consensus_score=expert_consensus_score,
                synthesis_quality_score=synthesis_quality_score,
                methodology_notes=methodology_notes,
                synthesis_metadata=synthesis_metadata
            )
            
        except Exception as e:
            logger.error(f"Error synthesizing expert analyses: {e}")
            return ExpertSynthesis(
                synthesis_id=f"expert_synthesis_{storyline_id}",
                storyline_id=storyline_id,
                expert_analyses=expert_analyses,
                consensus_analysis=f"Synthesis error: {str(e)}",
                key_disagreements=[],
                expert_consensus_score=0.0,
                synthesis_quality_score=0.0,
                methodology_notes=f"Synthesis failed: {str(e)}",
                synthesis_metadata={'error': str(e)}
            )
    
    def _determine_credibility_level(self, source_type: ExpertSourceType) -> str:
        """Determine credibility level for a source type"""
        credibility_mapping = {
            ExpertSourceType.ACADEMIC_RESEARCH: ExpertCredibility.HIGH,
            ExpertSourceType.THINK_TANK_REPORTS: ExpertCredibility.HIGH,
            ExpertSourceType.POLICY_PAPERS: ExpertCredibility.HIGH,
            ExpertSourceType.INTERNATIONAL_ORGS: ExpertCredibility.HIGH,
            ExpertSourceType.INDUSTRY_ANALYSIS: ExpertCredibility.MEDIUM,
            ExpertSourceType.EXPERT_OPINIONS: ExpertCredibility.MEDIUM
        }
        return credibility_mapping.get(source_type, ExpertCredibility.UNKNOWN).value
    
    def _generate_publication_date(self) -> str:
        """Generate a random publication date"""
        import random
        from datetime import datetime, timedelta
        
        # Generate date between 6 months ago and 2 years ago
        end_date = datetime.now() - timedelta(days=180)
        start_date = end_date - timedelta(days=365)
        
        random_days = random.randint(0, (end_date - start_date).days)
        random_date = start_date + timedelta(days=random_days)
        
        return random_date.strftime('%Y-%m-%d')
    
    def _prepare_analysis_context(self, storyline_title: str, articles: List[Dict], 
                                rag_context: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare analysis context for expert analysis"""
        context = {
            'storyline_title': storyline_title,
            'articles_count': len(articles),
            'article_summaries': [],
            'rag_context': rag_context or {}
        }
        
        # Add article summaries
        for article in articles[:5]:  # Limit to first 5 articles
            context['article_summaries'].append({
                'title': article.get('title', ''),
                'source': article.get('source', ''),
                'content_preview': article.get('content', '')[:200]
            })
        
        return context
    
    def _create_expert_analysis_prompt(self, storyline_title: str, analysis_context: Dict[str, Any], 
                                     source: ExpertSource, source_config: Dict[str, Any]) -> str:
        """Create analysis prompt for expert analysis"""
        prompt = f"""
        Generate expert analysis for the following storyline:
        
        Storyline: {storyline_title}
        
        Analysis Context:
        - Articles Count: {analysis_context['articles_count']}
        - Article Summaries: {json.dumps(analysis_context['article_summaries'], indent=2)}
        - RAG Context: {json.dumps(analysis_context['rag_context'], indent=2)}
        
        Source Information:
        - Source Type: {source_config['name']}
        - Expertise Areas: {', '.join(source.expertise_areas)}
        - Credibility Level: {source.credibility_level}
        - Institutional Affiliation: {source.institutional_affiliation}
        
        Provide comprehensive expert analysis covering:
        1. **Expert Assessment**: Professional analysis and expert opinion
        2. **Key Insights**: Critical insights and expert recommendations
        3. **Methodology**: Analytical approach and evidence base
        4. **Implications**: Professional implications and expert perspective
        5. **Limitations**: Analysis limitations and caveats
        6. **Recommendations**: Expert recommendations and next steps
        
        Structure your response with clear sections and professional insights.
        """
        
        return prompt
    
    async def _generate_fallback_expert_analysis(self, source: ExpertSource, storyline_title: str) -> str:
        """Generate fallback expert analysis when ML service is not available"""
        analysis = f"""# Expert Analysis: {source.source_name}
        
## Expert Assessment
Based on {source.source_type} expertise in {', '.join(source.expertise_areas)}, this analysis provides professional insights on the storyline: {storyline_title}

## Key Insights
- Professional assessment from {source.institutional_affiliation}
- Expert perspective on {storyline_title}
- Industry/professional implications
- Strategic considerations and recommendations

## Methodology
- {source.source_type} analytical approach
- Professional expertise and domain knowledge
- Evidence-based analysis and professional judgment
- Institutional perspective and professional standards

## Implications
- Professional implications for stakeholders
- Industry/professional impact assessment
- Strategic recommendations and next steps
- Professional best practices and standards

## Limitations
- Analysis based on available information
- Professional judgment and expert opinion
- Limited to {source.source_type} perspective
- Requires additional verification and validation

## Recommendations
- Professional recommendations for stakeholders
- Strategic next steps and actions
- Professional best practices and standards
- Continued monitoring and assessment

*Note: This is a basic expert analysis generated without full ML processing. For comprehensive analysis, the ML service should be available.*
"""
        
        return analysis
    
    def _extract_key_insights(self, analysis_content: str) -> List[str]:
        """Extract key insights from analysis content"""
        insights = []
        
        # Simple extraction - look for bullet points and key phrases
        lines = analysis_content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('- ') or line.startswith('* '):
                insights.append(line[2:].strip())
            elif 'insight' in line.lower() or 'key' in line.lower():
                insights.append(line)
        
        return insights[:10]  # Limit to 10 insights
    
    def _generate_methodology_notes(self, source: ExpertSource, source_config: Dict[str, Any]) -> str:
        """Generate methodology notes for the analysis"""
        methodology_notes = f"""
        Analysis Methodology:
        - Source Type: {source_config['name']}
        - Expertise Areas: {', '.join(source.expertise_areas)}
        - Credibility Level: {source.credibility_level}
        - Institutional Affiliation: {source.institutional_affiliation}
        - Analytical Approach: {source_config['name']} methodology
        - Evidence Base: Professional expertise and domain knowledge
        - Quality Standards: {source_config['name']} professional standards
        """
        
        return methodology_notes.strip()
    
    def _calculate_relevance_score(self, analysis_content: str, storyline_title: str) -> float:
        """Calculate relevance score for the analysis"""
        # Simple relevance calculation based on content overlap
        storyline_words = set(storyline_title.lower().split())
        analysis_words = set(analysis_content.lower().split())
        
        if storyline_words and analysis_words:
            overlap = len(storyline_words.intersection(analysis_words))
            total_words = len(storyline_words.union(analysis_words))
            return overlap / total_words if total_words > 0 else 0.0
        
        return 0.5  # Default relevance score
    
    def _extract_supporting_evidence(self, articles: List[Dict], analysis_content: str) -> List[Dict[str, Any]]:
        """Extract supporting evidence from articles"""
        evidence = []
        
        for article in articles[:3]:  # Limit to first 3 articles
            evidence.append({
                'article_id': article.get('id', 0),
                'title': article.get('title', ''),
                'source': article.get('source', ''),
                'relevance_score': 0.5,  # Placeholder
                'evidence_type': 'article_content',
                'supporting_quotes': []  # Could be enhanced with quote extraction
            })
        
        return evidence
    
    def _identify_limitations(self, source: ExpertSource, analysis_content: str) -> List[str]:
        """Identify limitations of the analysis"""
        limitations = []
        
        # Generic limitations based on source type
        if source.source_type == 'academic_research':
            limitations.extend([
                "Limited to academic perspective and theoretical frameworks",
                "May not reflect practical implementation considerations",
                "Research limitations and methodological constraints"
            ])
        elif source.source_type == 'think_tank_reports':
            limitations.extend([
                "Institutional perspective and organizational bias",
                "Policy focus may not reflect all stakeholder views",
                "Limited to think tank research scope and methodology"
            ])
        elif source.source_type == 'expert_opinions':
            limitations.extend([
                "Individual expert perspective and personal bias",
                "Limited to professional experience and expertise",
                "May not reflect broader consensus or alternative views"
            ])
        else:
            limitations.extend([
                "Limited to specific source type perspective",
                "May not reflect all stakeholder views",
                "Analysis scope and methodology limitations"
            ])
        
        return limitations[:5]  # Limit to 5 limitations
    
    async def _generate_consensus_analysis(self, expert_analyses: List[ExpertAnalysis], 
                                         storyline_title: str) -> str:
        """Generate consensus analysis from multiple expert analyses"""
        try:
            if not expert_analyses:
                return "No expert analyses available for consensus analysis"
            
            if self.ml_service:
                # Use ML service for consensus analysis
                prompt = f"""
                Generate a consensus analysis from multiple expert analyses:
                
                Storyline: {storyline_title}
                
                Expert Analyses:
                {json.dumps([{
                    'source_type': analysis.source.source_type,
                    'analysis_content': analysis.analysis_content[:500],
                    'key_insights': analysis.key_insights,
                    'credibility_score': analysis.credibility_score
                } for analysis in expert_analyses], indent=2)}
                
                Provide a comprehensive consensus analysis covering:
                1. **Consensus Points**: Areas of agreement among experts
                2. **Key Disagreements**: Areas of disagreement and debate
                3. **Synthesized Insights**: Combined expert insights and recommendations
                4. **Expert Recommendations**: Consensus recommendations and next steps
                5. **Methodology Notes**: How the consensus was derived
                """
                
                result = await self._call_ml_service(
                    "You are a senior research analyst specializing in expert consensus analysis.",
                    prompt
                )
                return result.get('summary', 'Consensus analysis not available')
            else:
                # Fallback consensus analysis
                return f"Consensus analysis from {len(expert_analyses)} expert sources. Key areas of agreement include professional insights and expert recommendations. Areas of disagreement may include methodological approaches and specific recommendations."
                
        except Exception as e:
            logger.error(f"Error generating consensus analysis: {e}")
            return f"Consensus analysis error: {str(e)}"
    
    def _identify_key_disagreements(self, expert_analyses: List[ExpertAnalysis]) -> List[Dict[str, Any]]:
        """Identify key disagreements among expert analyses"""
        disagreements = []
        
        if len(expert_analyses) < 2:
            return disagreements
        
        # Simple disagreement identification based on content analysis
        for i, analysis1 in enumerate(expert_analyses):
            for analysis2 in expert_analyses[i+1:]:
                # Look for contrasting keywords or phrases
                if analysis1.source.source_type != analysis2.source.source_type:
                    disagreement = {
                        'disagreement_type': 'methodological_approach',
                        'sources': [analysis1.source.source_name, analysis2.source.source_name],
                        'description': f"Different analytical approaches between {analysis1.source.source_type} and {analysis2.source.source_type}",
                        'severity': 'medium'
                    }
                    disagreements.append(disagreement)
        
        return disagreements[:5]  # Limit to 5 disagreements
    
    def _calculate_expert_consensus_score(self, expert_analyses: List[ExpertAnalysis]) -> float:
        """Calculate expert consensus score"""
        if len(expert_analyses) < 2:
            return 1.0  # Perfect consensus with only one analysis
        
        # Calculate based on source type diversity and credibility
        source_types = set(analysis.source.source_type for analysis in expert_analyses)
        credibility_scores = [analysis.credibility_score for analysis in expert_analyses]
        
        # Higher diversity and credibility = higher consensus score
        diversity_factor = len(source_types) / len(expert_analyses)
        credibility_factor = sum(credibility_scores) / len(credibility_scores)
        
        return (diversity_factor * 0.3) + (credibility_factor * 0.7)
    
    def _calculate_synthesis_quality_score_from_analyses(self, expert_analyses: List[ExpertAnalysis]) -> float:
        """Calculate synthesis quality score from expert analyses"""
        if not expert_analyses:
            return 0.0
        
        quality_factors = []
        
        # Analysis count factor
        count_factor = min(len(expert_analyses) / 5, 1.0)  # More analyses = better
        quality_factors.append(count_factor)
        
        # Average confidence factor
        avg_confidence = sum(analysis.confidence_score for analysis in expert_analyses) / len(expert_analyses)
        quality_factors.append(avg_confidence)
        
        # Average credibility factor
        avg_credibility = sum(analysis.credibility_score for analysis in expert_analyses) / len(expert_analyses)
        quality_factors.append(avg_credibility)
        
        # Source diversity factor
        source_types = set(analysis.source.source_type for analysis in expert_analyses)
        diversity_factor = len(source_types) / len(ExpertSourceType)
        quality_factors.append(diversity_factor)
        
        return sum(quality_factors) / len(quality_factors)
    
    def _generate_synthesis_methodology_notes(self, expert_analyses: List[ExpertAnalysis]) -> str:
        """Generate methodology notes for synthesis"""
        if not expert_analyses:
            return "No expert analyses available for synthesis methodology"
        
        source_types = [analysis.source.source_type for analysis in expert_analyses]
        expertise_areas = set(area for analysis in expert_analyses for area in analysis.source.expertise_areas)
        
        methodology = f"""
        Synthesis Methodology:
        - Expert Analyses Count: {len(expert_analyses)}
        - Source Types: {', '.join(set(source_types))}
        - Expertise Areas: {', '.join(list(expertise_areas)[:5])}
        - Credibility Levels: {', '.join(set(analysis.source.credibility_level for analysis in expert_analyses))}
        - Synthesis Approach: Multi-source expert analysis integration
        - Quality Standards: Professional expert analysis standards
        """
        
        return methodology.strip()
    
    def _calculate_source_coverage(self, expert_analyses: List[ExpertAnalysis]) -> Dict[str, int]:
        """Calculate source coverage statistics"""
        coverage = {}
        
        for analysis in expert_analyses:
            source_type = analysis.source.source_type
            coverage[source_type] = coverage.get(source_type, 0) + 1
        
        return coverage
    
    def _calculate_credibility_distribution(self, expert_analyses: List[ExpertAnalysis]) -> Dict[str, int]:
        """Calculate credibility distribution statistics"""
        distribution = {}
        
        for analysis in expert_analyses:
            credibility_level = analysis.source.credibility_level
            distribution[credibility_level] = distribution.get(credibility_level, 0) + 1
        
        return distribution
    
    def _generate_expert_recommendations(self, expert_synthesis: ExpertSynthesis, 
                                       expert_analyses: List[ExpertAnalysis]) -> List[Dict[str, Any]]:
        """Generate expert recommendations"""
        recommendations = []
        
        # Generate recommendations based on synthesis
        if expert_synthesis.consensus_analysis:
            recommendations.append({
                'type': 'consensus_recommendation',
                'priority': 'high',
                'description': 'Follow expert consensus recommendations',
                'source': 'expert_synthesis'
            })
        
        # Generate recommendations based on individual analyses
        for analysis in expert_analyses[:3]:  # Top 3 analyses
            recommendations.append({
                'type': 'expert_recommendation',
                'priority': 'medium',
                'description': f"Consider {analysis.source.source_name} recommendations",
                'source': analysis.source.source_name
            })
        
        # Generate general recommendations
        recommendations.extend([
            {
                'type': 'methodology_recommendation',
                'priority': 'medium',
                'description': 'Continue monitoring expert sources for updates',
                'source': 'synthesis_methodology'
            },
            {
                'type': 'quality_recommendation',
                'priority': 'low',
                'description': 'Validate expert analysis with additional sources',
                'source': 'quality_assurance'
            }
        ])
        
        return recommendations[:8]  # Limit to 8 recommendations
    
    def _calculate_synthesis_quality_score(self, expert_synthesis: ExpertSynthesis, 
                                         expert_analyses: List[ExpertAnalysis]) -> float:
        """Calculate overall synthesis quality score"""
        try:
            quality_factors = []
            
            # Synthesis quality factor
            quality_factors.append(expert_synthesis.synthesis_quality_score)
            
            # Expert consensus factor
            quality_factors.append(expert_synthesis.expert_consensus_score)
            
            # Analysis count factor
            if expert_analyses:
                count_factor = min(len(expert_analyses) / 5, 1.0)
                quality_factors.append(count_factor)
            
            # Source diversity factor
            if expert_analyses:
                source_types = set(analysis.source.source_type for analysis in expert_analyses)
                diversity_factor = len(source_types) / len(ExpertSource)
                quality_factors.append(diversity_factor)
            
            return sum(quality_factors) / len(quality_factors) if quality_factors else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating synthesis quality score: {e}")
            return 0.0
    
    async def _call_ml_service(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Call ML service for expert analysis generation"""
        try:
            if hasattr(self.ml_service, 'generate_summary'):
                result = self.ml_service.generate_summary(user_prompt, system_prompt)
                return result
            else:
                return {'summary': 'ML service not available', 'confidence_score': 0.0}
        except Exception as e:
            logger.error(f"Error calling ML service: {e}")
            return {'summary': 'ML service error', 'confidence_score': 0.0}
    
    async def _store_expert_analysis(self, result: ComprehensiveExpertResult):
        """Store expert analysis result in database"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Store expert synthesis
                insert_query = text("""
                    INSERT INTO expert_synthesis (
                        storyline_id, synthesis_id, consensus_analysis,
                        key_disagreements, expert_consensus_score,
                        synthesis_quality_score, methodology_notes,
                        synthesis_metadata
                    ) VALUES (
                        :storyline_id, :synthesis_id, :consensus_analysis,
                        :key_disagreements, :expert_consensus_score,
                        :synthesis_quality_score, :methodology_notes,
                        :synthesis_metadata
                    )
                """)
                
                db.execute(insert_query, {
                    'storyline_id': result.storyline_id,
                    'synthesis_id': result.expert_synthesis.synthesis_id,
                    'consensus_analysis': result.expert_synthesis.consensus_analysis,
                    'key_disagreements': json.dumps(result.expert_synthesis.key_disagreements),
                    'expert_consensus_score': result.expert_synthesis.expert_consensus_score,
                    'synthesis_quality_score': result.expert_synthesis.synthesis_quality_score,
                    'methodology_notes': result.expert_synthesis.methodology_notes,
                    'synthesis_metadata': json.dumps(result.expert_synthesis.synthesis_metadata)
                })
                
                # Store individual expert analyses
                for analysis in result.expert_synthesis.expert_analyses:
                    analysis_query = text("""
                        INSERT INTO expert_analyses (
                            storyline_id, analysis_id, source_id, source_type,
                            analysis_content, key_insights, methodology,
                            confidence_score, relevance_score, credibility_score,
                            supporting_evidence, limitations, analysis_metadata
                        ) VALUES (
                            :storyline_id, :analysis_id, :source_id, :source_type,
                            :analysis_content, :key_insights, :methodology,
                            :confidence_score, :relevance_score, :credibility_score,
                            :supporting_evidence, :limitations, :analysis_metadata
                        )
                    """)
                    
                    db.execute(analysis_query, {
                        'storyline_id': result.storyline_id,
                        'analysis_id': analysis.analysis_id,
                        'source_id': analysis.source.source_id,
                        'source_type': analysis.source.source_type,
                        'analysis_content': analysis.analysis_content,
                        'key_insights': json.dumps(analysis.key_insights),
                        'methodology': analysis.methodology,
                        'confidence_score': analysis.confidence_score,
                        'relevance_score': analysis.relevance_score,
                        'credibility_score': analysis.credibility_score,
                        'supporting_evidence': json.dumps(analysis.supporting_evidence),
                        'limitations': json.dumps(analysis.limitations),
                        'analysis_metadata': json.dumps(analysis.metadata)
                    })
                
                db.commit()
                
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error storing expert analysis: {e}")

# Global instance
_expert_analysis_service = None

def get_expert_analysis_service(ml_service=None, rag_service=None) -> ExpertAnalysisService:
    """Get global expert analysis service instance"""
    global _expert_analysis_service
    if _expert_analysis_service is None:
        _expert_analysis_service = ExpertAnalysisService(ml_service, rag_service)
    return _expert_analysis_service
