"""
Multi-Perspective Analysis Service for News Intelligence System v3.0
Provides comprehensive multi-perspective analysis for storylines
"""

import asyncio
import logging
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum

from config.database import get_db
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class PerspectiveType(Enum):
    """Available analysis perspectives"""
    GOVERNMENT_OFFICIAL = "government_official"
    OPPOSITION_CRITICAL = "opposition_critical"
    EXPERT_ACADEMIC = "expert_academic"
    INTERNATIONAL = "international"
    ECONOMIC = "economic"
    SOCIAL_CIVIL = "social_civil"

@dataclass
class PerspectiveAnalysis:
    """Result of perspective analysis"""
    perspective_type: str
    analysis_content: str
    confidence_score: float
    key_points: List[str]
    supporting_evidence: List[Dict[str, Any]]
    source_articles: List[int]
    analysis_metadata: Dict[str, Any]

@dataclass
class MultiPerspectiveResult:
    """Result of multi-perspective analysis"""
    storyline_id: str
    individual_perspectives: Dict[str, PerspectiveAnalysis]
    synthesized_analysis: str
    perspective_agreement: Dict[str, float]
    key_disagreements: List[Dict[str, Any]]
    consensus_score: float
    analysis_quality_score: float

class MultiPerspectiveAnalyzer:
    """
    Multi-perspective analysis service that analyzes storylines from different viewpoints
    """
    
    def __init__(self, ml_service=None, rag_service=None):
        """
        Initialize the Multi-Perspective Analyzer
        
        Args:
            ml_service: ML summarization service instance
            rag_service: RAG service instance
        """
        self.ml_service = ml_service
        self.rag_service = rag_service
        
        # Perspective templates with specialized prompts
        self.perspective_templates = {
            PerspectiveType.GOVERNMENT_OFFICIAL: {
                'name': 'Government/Official Perspective',
                'description': 'Analysis from government and official sources perspective',
                'focus_areas': ['policy_implications', 'official_statements', 'regulatory_impact', 'governance_effects'],
                'system_prompt': """You are a senior government policy analyst with expertise in public administration and governance. Analyze this news story from the perspective of government officials and policymakers. Focus on:
- Policy implications and regulatory impact
- Official government positions and statements
- Governance and administrative considerations
- Public sector response and management
- Legal and regulatory framework implications
- Inter-agency coordination and response
- Public interest and citizen welfare considerations
- Budgetary and resource allocation impacts
- Political stability and institutional integrity
- Long-term policy planning and implementation

Maintain a professional, objective tone while representing the government perspective. Consider both immediate responses and long-term strategic implications.""",
                'user_prompt_template': """Analyze the following news story from a government/official perspective:

STORYLINE: {storyline_title}
ARTICLES: {articles_context}
RAG CONTEXT: {rag_context}

Provide a comprehensive analysis covering:
1. **Policy Implications**: How does this affect current policies and regulations?
2. **Official Response**: What should be the government's official response?
3. **Regulatory Impact**: What regulatory changes might be needed?
4. **Resource Requirements**: What resources will be needed to address this?
5. **Stakeholder Management**: How should different stakeholders be managed?
6. **Risk Assessment**: What are the risks to government operations?
7. **Communication Strategy**: How should this be communicated to the public?
8. **Long-term Planning**: What are the long-term implications for governance?

Focus on practical, actionable insights for government decision-makers."""
            },
            
            PerspectiveType.OPPOSITION_CRITICAL: {
                'name': 'Opposition/Critical Perspective',
                'description': 'Analysis from opposition and critical sources perspective',
                'focus_areas': ['criticisms', 'alternative_solutions', 'accountability', 'transparency'],
                'system_prompt': """You are an independent investigative journalist and critical analyst with expertise in holding power accountable. Analyze this news story from the perspective of opposition groups, civil society, and critical observers. Focus on:
- Critical analysis of official narratives
- Alternative explanations and viewpoints
- Accountability and transparency issues
- Civil society and public interest concerns
- Potential abuses of power or authority
- Alternative policy solutions and approaches
- Democratic oversight and checks and balances
- Public participation and engagement
- Human rights and civil liberties implications
- Long-term democratic health and institutional integrity

Maintain a critical but fair tone, focusing on accountability and democratic values. Challenge assumptions and provide alternative viewpoints.""",
                'user_prompt_template': """Analyze the following news story from an opposition/critical perspective:

STORYLINE: {storyline_title}
ARTICLES: {articles_context}
RAG CONTEXT: {rag_context}

Provide a comprehensive critical analysis covering:
1. **Critical Assessment**: What are the problems with the official narrative?
2. **Alternative Explanations**: What alternative explanations exist?
3. **Accountability Issues**: Who should be held accountable and how?
4. **Transparency Concerns**: What information is missing or hidden?
5. **Alternative Solutions**: What better approaches could be taken?
6. **Democratic Implications**: How does this affect democratic processes?
7. **Public Interest**: What are the real public interest concerns?
8. **Long-term Risks**: What are the long-term risks to democracy and rights?

Focus on holding power accountable and protecting democratic values."""
            },
            
            PerspectiveType.EXPERT_ACADEMIC: {
                'name': 'Expert/Academic Perspective',
                'description': 'Analysis from expert and academic sources perspective',
                'focus_areas': ['research_evidence', 'theoretical_frameworks', 'methodology', 'peer_review'],
                'system_prompt': """You are a senior academic researcher and subject matter expert with extensive experience in peer-reviewed research and evidence-based analysis. Analyze this news story from the perspective of academic experts and researchers. Focus on:
- Evidence-based analysis and research findings
- Theoretical frameworks and academic perspectives
- Methodological rigor and data quality
- Peer-reviewed research and scholarly consensus
- Interdisciplinary analysis and multiple expert viewpoints
- Historical context and comparative analysis
- Statistical significance and research limitations
- Academic debate and scholarly disagreement
- Long-term research implications and knowledge gaps
- Policy-relevant research and evidence synthesis

Maintain academic rigor and objectivity while providing expert insights. Cite relevant research and acknowledge limitations and uncertainties.""",
                'user_prompt_template': """Analyze the following news story from an expert/academic perspective:

STORYLINE: {storyline_title}
ARTICLES: {articles_context}
RAG CONTEXT: {rag_context}

Provide a comprehensive expert analysis covering:
1. **Research Evidence**: What does the research literature say about this?
2. **Theoretical Framework**: What theoretical frameworks apply here?
3. **Methodological Assessment**: How reliable is the available data?
4. **Expert Consensus**: What do experts generally agree on?
5. **Academic Debate**: Where do experts disagree and why?
6. **Historical Precedents**: What historical examples are relevant?
7. **Comparative Analysis**: How does this compare to similar cases?
8. **Research Gaps**: What additional research is needed?

Focus on evidence-based analysis and scholarly rigor."""
            },
            
            PerspectiveType.INTERNATIONAL: {
                'name': 'International Perspective',
                'description': 'Analysis from international and global sources perspective',
                'focus_areas': ['global_implications', 'international_reactions', 'diplomatic_impact', 'multilateral_cooperation'],
                'system_prompt': """You are a senior international relations analyst and diplomatic expert with extensive experience in global affairs and multilateral cooperation. Analyze this news story from the perspective of international observers and global stakeholders. Focus on:
- Global implications and international impact
- Diplomatic relations and multilateral cooperation
- International law and treaty obligations
- Global governance and international institutions
- Cross-border effects and regional implications
- International media and global public opinion
- Economic globalization and international trade
- Security implications and international stability
- Human rights and international humanitarian law
- Long-term global trends and international order

Maintain an international perspective while considering diverse global viewpoints and cultural contexts.""",
                'user_prompt_template': """Analyze the following news story from an international perspective:

STORYLINE: {storyline_title}
ARTICLES: {articles_context}
RAG CONTEXT: {rag_context}

Provide a comprehensive international analysis covering:
1. **Global Implications**: How does this affect international relations?
2. **Diplomatic Impact**: What are the diplomatic consequences?
3. **International Law**: What international legal frameworks apply?
4. **Multilateral Response**: How should international organizations respond?
5. **Regional Effects**: What are the regional implications?
6. **Global Public Opinion**: How is this viewed internationally?
7. **Economic Globalization**: What are the global economic impacts?
8. **Security Implications**: How does this affect international security?

Focus on global perspectives and international cooperation."""
            },
            
            PerspectiveType.ECONOMIC: {
                'name': 'Economic Perspective',
                'description': 'Analysis from economic and financial sources perspective',
                'focus_areas': ['market_impact', 'financial_implications', 'economic_indicators', 'business_effects'],
                'system_prompt': """You are a senior economic analyst and financial expert with extensive experience in macroeconomics, financial markets, and business analysis. Analyze this news story from the perspective of economic and financial stakeholders. Focus on:
- Economic impact and market implications
- Financial market reactions and investor sentiment
- Business and industry effects
- Economic indicators and data analysis
- Cost-benefit analysis and economic efficiency
- Investment and capital allocation decisions
- Employment and labor market effects
- Consumer behavior and market demand
- Supply chain and trade implications
- Long-term economic growth and development

Maintain economic objectivity while providing practical financial and business insights.""",
                'user_prompt_template': """Analyze the following news story from an economic perspective:

STORYLINE: {storyline_title}
ARTICLES: {articles_context}
RAG CONTEXT: {rag_context}

Provide a comprehensive economic analysis covering:
1. **Market Impact**: How will this affect financial markets?
2. **Economic Indicators**: What economic data is relevant?
3. **Business Effects**: How will this impact businesses and industries?
4. **Investment Implications**: What are the investment implications?
5. **Consumer Impact**: How will this affect consumers and demand?
6. **Employment Effects**: What are the labor market implications?
7. **Trade and Supply Chain**: How will this affect trade and supply chains?
8. **Long-term Growth**: What are the long-term economic implications?

Focus on economic data, market analysis, and business implications."""
            },
            
            PerspectiveType.SOCIAL_CIVIL: {
                'name': 'Social/Civil Society Perspective',
                'description': 'Analysis from social and civil society sources perspective',
                'focus_areas': ['social_impact', 'civil_rights', 'community_effects', 'public_welfare'],
                'system_prompt': """You are a senior social policy analyst and civil society expert with extensive experience in social justice, community development, and public welfare. Analyze this news story from the perspective of civil society organizations and social stakeholders. Focus on:
- Social impact and community effects
- Civil rights and human rights implications
- Public welfare and social justice concerns
- Community development and social cohesion
- Vulnerable populations and social equity
- Public participation and civic engagement
- Social services and public health
- Education and social mobility
- Cultural and social identity impacts
- Long-term social development and community resilience

Maintain a social justice perspective while advocating for community welfare and civil rights.""",
                'user_prompt_template': """Analyze the following news story from a social/civil society perspective:

STORYLINE: {storyline_title}
ARTICLES: {articles_context}
RAG CONTEXT: {rag_context}

Provide a comprehensive social analysis covering:
1. **Social Impact**: How will this affect communities and society?
2. **Civil Rights**: What are the civil rights implications?
3. **Vulnerable Populations**: How will this affect vulnerable groups?
4. **Public Welfare**: What are the public welfare implications?
5. **Community Effects**: How will this affect local communities?
6. **Social Services**: What are the implications for social services?
7. **Public Health**: How will this affect public health and safety?
8. **Social Justice**: What are the social justice implications?

Focus on community welfare, civil rights, and social equity."""
            }
        }
    
    async def generate_multi_perspective_analysis(self, storyline_id: str, rag_context: Dict[str, Any]) -> MultiPerspectiveResult:
        """
        Generate comprehensive multi-perspective analysis for a storyline
        
        Args:
            storyline_id: ID of the storyline to analyze
            rag_context: RAG context from external sources
            
        Returns:
            MultiPerspectiveResult with all perspective analyses
        """
        try:
            logger.info(f"Generating multi-perspective analysis for storyline: {storyline_id}")
            
            # Get storyline data
            storyline_data = await self._get_storyline_data(storyline_id)
            if not storyline_data:
                raise ValueError(f"Storyline {storyline_id} not found")
            
            storyline_title = storyline_data.get('title', 'Untitled Storyline')
            articles = storyline_data.get('articles', [])
            
            # Generate individual perspective analyses
            individual_perspectives = {}
            for perspective_type in PerspectiveType:
                logger.info(f"Analyzing from {perspective_type.value} perspective")
                
                perspective_analysis = await self._analyze_from_perspective(
                    storyline_id, storyline_title, articles, rag_context, perspective_type
                )
                individual_perspectives[perspective_type.value] = perspective_analysis
                
                # Store in database
                await self._store_perspective_analysis(storyline_id, perspective_analysis)
            
            # Synthesize perspectives into unified analysis
            synthesized_analysis = await self._synthesize_perspectives(individual_perspectives)
            
            # Calculate agreement levels and identify disagreements
            perspective_agreement = self._calculate_agreement_levels(individual_perspectives)
            key_disagreements = self._identify_key_disagreements(individual_perspectives)
            
            # Calculate overall scores
            consensus_score = self._calculate_consensus_score(perspective_agreement)
            analysis_quality_score = self._calculate_analysis_quality_score(individual_perspectives)
            
            # Create result
            result = MultiPerspectiveResult(
                storyline_id=storyline_id,
                individual_perspectives=individual_perspectives,
                synthesized_analysis=synthesized_analysis,
                perspective_agreement=perspective_agreement,
                key_disagreements=key_disagreements,
                consensus_score=consensus_score,
                analysis_quality_score=analysis_quality_score
            )
            
            # Store synthesized analysis
            await self._store_multi_perspective_analysis(result)
            
            logger.info(f"Multi-perspective analysis completed for storyline: {storyline_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error generating multi-perspective analysis: {e}")
            raise
    
    async def _analyze_from_perspective(self, storyline_id: str, storyline_title: str, 
                                      articles: List[Dict], rag_context: Dict[str, Any], 
                                      perspective_type: PerspectiveType) -> PerspectiveAnalysis:
        """Analyze storyline from a specific perspective"""
        try:
            template = self.perspective_templates[perspective_type]
            
            # Prepare articles context
            articles_context = self._prepare_articles_context(articles)
            
            # Prepare RAG context
            rag_context_str = self._prepare_rag_context(rag_context)
            
            # Create prompts
            system_prompt = template['system_prompt']
            user_prompt = template['user_prompt_template'].format(
                storyline_title=storyline_title,
                articles_context=articles_context,
                rag_context=rag_context_str
            )
            
            # Generate analysis using ML service
            if self.ml_service:
                analysis_result = await self._call_ml_service(system_prompt, user_prompt)
                analysis_content = analysis_result.get('summary', '')
                confidence_score = analysis_result.get('confidence_score', 0.5)
            else:
                # Fallback to basic analysis
                analysis_content = await self._generate_fallback_analysis(
                    storyline_title, articles, perspective_type
                )
                confidence_score = 0.3
            
            # Extract key points and supporting evidence
            key_points = self._extract_key_points(analysis_content)
            supporting_evidence = self._extract_supporting_evidence(articles, analysis_content)
            source_articles = [article.get('id', 0) for article in articles]
            
            # Create analysis metadata
            analysis_metadata = {
                'perspective_name': template['name'],
                'focus_areas': template['focus_areas'],
                'analysis_length': len(analysis_content),
                'key_points_count': len(key_points),
                'supporting_evidence_count': len(supporting_evidence),
                'generated_at': datetime.now(timezone.utc).isoformat()
            }
            
            return PerspectiveAnalysis(
                perspective_type=perspective_type.value,
                analysis_content=analysis_content,
                confidence_score=confidence_score,
                key_points=key_points,
                supporting_evidence=supporting_evidence,
                source_articles=source_articles,
                analysis_metadata=analysis_metadata
            )
            
        except Exception as e:
            logger.error(f"Error analyzing from {perspective_type.value} perspective: {e}")
            # Return minimal analysis on error
            return PerspectiveAnalysis(
                perspective_type=perspective_type.value,
                analysis_content=f"Analysis from {perspective_type.value} perspective could not be generated due to error: {str(e)}",
                confidence_score=0.0,
                key_points=[],
                supporting_evidence=[],
                source_articles=[],
                analysis_metadata={'error': str(e)}
            )
    
    async def _call_ml_service(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Call ML service for analysis generation"""
        try:
            if hasattr(self.ml_service, 'generate_summary'):
                # Use existing ML service
                result = self.ml_service.generate_summary(user_prompt, system_prompt)
                return result
            else:
                # Fallback
                return {'summary': 'ML service not available', 'confidence_score': 0.0}
        except Exception as e:
            logger.error(f"Error calling ML service: {e}")
            return {'summary': 'ML service error', 'confidence_score': 0.0}
    
    async def _generate_fallback_analysis(self, storyline_title: str, articles: List[Dict], 
                                        perspective_type: PerspectiveType) -> str:
        """Generate fallback analysis when ML service is not available"""
        template = self.perspective_templates[perspective_type]
        
        # Basic analysis based on article titles and content
        article_summaries = []
        for article in articles[:5]:  # Limit to first 5 articles
            title = article.get('title', '')
            content = article.get('content', '')[:200]  # First 200 chars
            article_summaries.append(f"- {title}: {content}...")
        
        articles_text = "\n".join(article_summaries)
        
        return f"""Analysis from {template['name']}:

Storyline: {storyline_title}

Key Articles:
{articles_text}

Focus Areas: {', '.join(template['focus_areas'])}

This is a basic analysis generated without full ML processing. For comprehensive analysis, the ML service should be available."""
    
    def _prepare_articles_context(self, articles: List[Dict]) -> str:
        """Prepare articles context for analysis"""
        context_parts = []
        
        for i, article in enumerate(articles[:10], 1):  # Limit to 10 articles
            title = article.get('title', 'No title')
            content = article.get('content', '')[:500]  # First 500 chars
            source = article.get('source', 'Unknown source')
            published_at = article.get('published_at', 'Unknown date')
            
            context_parts.append(f"""
Article {i}:
Title: {title}
Source: {source}
Published: {published_at}
Content: {content}...
""")
        
        return "\n".join(context_parts)
    
    def _prepare_rag_context(self, rag_context: Dict[str, Any]) -> str:
        """Prepare RAG context for analysis"""
        if not rag_context:
            return "No additional context available"
        
        context_parts = []
        
        # Wikipedia context
        if 'wikipedia' in rag_context:
            wiki = rag_context['wikipedia']
            if 'summaries' in wiki:
                context_parts.append(f"Wikipedia Context: {json.dumps(wiki['summaries'], indent=2)}")
        
        # GDELT context
        if 'gdelt' in rag_context:
            gdelt = rag_context['gdelt']
            if 'events' in gdelt:
                context_parts.append(f"GDELT Events: {json.dumps(gdelt['events'], indent=2)}")
        
        # Extracted entities and topics
        if 'extracted_entities' in rag_context:
            context_parts.append(f"Key Entities: {', '.join(rag_context['extracted_entities'])}")
        
        if 'extracted_topics' in rag_context:
            context_parts.append(f"Key Topics: {', '.join(rag_context['extracted_topics'])}")
        
        return "\n".join(context_parts) if context_parts else "No additional context available"
    
    def _extract_key_points(self, analysis_content: str) -> List[str]:
        """Extract key points from analysis content"""
        # Simple extraction - look for bullet points and numbered lists
        lines = analysis_content.split('\n')
        key_points = []
        
        for line in lines:
            line = line.strip()
            if line.startswith(('-', '*', '•')) or line.startswith(tuple('123456789')):
                # Remove bullet/number and clean up
                clean_line = line.lstrip('-*•0123456789. ').strip()
                if clean_line and len(clean_line) > 10:
                    key_points.append(clean_line)
        
        return key_points[:10]  # Limit to 10 key points
    
    def _extract_supporting_evidence(self, articles: List[Dict], analysis_content: str) -> List[Dict[str, Any]]:
        """Extract supporting evidence from articles"""
        evidence = []
        
        for article in articles[:5]:  # Limit to first 5 articles
            evidence.append({
                'article_id': article.get('id', 0),
                'title': article.get('title', ''),
                'source': article.get('source', ''),
                'relevance_score': 0.5,  # Placeholder
                'evidence_type': 'article_content'
            })
        
        return evidence
    
    async def _synthesize_perspectives(self, individual_perspectives: Dict[str, PerspectiveAnalysis]) -> str:
        """Synthesize individual perspectives into unified analysis"""
        try:
            # Prepare synthesis prompt
            perspectives_summary = []
            for perspective_type, analysis in individual_perspectives.items():
                perspectives_summary.append(f"""
{perspective_type.replace('_', ' ').title()}:
{analysis.analysis_content[:500]}...
""")
            
            synthesis_prompt = f"""
Synthesize the following multi-perspective analysis into a unified, comprehensive analysis:

{''.join(perspectives_summary)}

Provide a synthesized analysis that:
1. Identifies common themes and agreements across perspectives
2. Highlights key disagreements and alternative viewpoints
3. Provides a balanced, comprehensive overview
4. Maintains objectivity while acknowledging different viewpoints
5. Offers practical insights for decision-makers

Structure the response with clear sections and actionable insights.
"""
            
            if self.ml_service:
                synthesis_result = await self._call_ml_service(
                    "You are a senior intelligence analyst specializing in multi-perspective synthesis.",
                    synthesis_prompt
                )
                return synthesis_result.get('summary', 'Synthesis could not be generated')
            else:
                return self._generate_fallback_synthesis(individual_perspectives)
                
        except Exception as e:
            logger.error(f"Error synthesizing perspectives: {e}")
            return f"Synthesis error: {str(e)}"
    
    def _generate_fallback_synthesis(self, individual_perspectives: Dict[str, PerspectiveAnalysis]) -> str:
        """Generate fallback synthesis when ML service is not available"""
        synthesis_parts = ["Multi-Perspective Analysis Synthesis:\n"]
        
        for perspective_type, analysis in individual_perspectives.items():
            synthesis_parts.append(f"""
{perspective_type.replace('_', ' ').title()}:
{analysis.analysis_content[:200]}...
""")
        
        synthesis_parts.append("""
This is a basic synthesis generated without full ML processing. 
For comprehensive synthesis, the ML service should be available.
""")
        
        return "\n".join(synthesis_parts)
    
    def _calculate_agreement_levels(self, individual_perspectives: Dict[str, PerspectiveAnalysis]) -> Dict[str, float]:
        """Calculate agreement levels between perspectives"""
        # Simple implementation - can be enhanced with more sophisticated analysis
        agreement_levels = {}
        
        perspective_types = list(individual_perspectives.keys())
        for i, perspective_type in enumerate(perspective_types):
            agreement_scores = []
            for j, other_type in enumerate(perspective_types):
                if i != j:
                    # Simple similarity based on key points overlap
                    similarity = self._calculate_perspective_similarity(
                        individual_perspectives[perspective_type],
                        individual_perspectives[other_type]
                    )
                    agreement_scores.append(similarity)
            
            agreement_levels[perspective_type] = sum(agreement_scores) / len(agreement_scores) if agreement_scores else 0.0
        
        return agreement_levels
    
    def _calculate_perspective_similarity(self, perspective1: PerspectiveAnalysis, perspective2: PerspectiveAnalysis) -> float:
        """Calculate similarity between two perspectives"""
        # Simple implementation based on key points overlap
        key_points1 = set(perspective1.key_points)
        key_points2 = set(perspective2.key_points)
        
        if not key_points1 or not key_points2:
            return 0.0
        
        intersection = key_points1.intersection(key_points2)
        union = key_points1.union(key_points2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _identify_key_disagreements(self, individual_perspectives: Dict[str, PerspectiveAnalysis]) -> List[Dict[str, Any]]:
        """Identify key disagreements between perspectives"""
        disagreements = []
        
        # Simple implementation - can be enhanced with more sophisticated analysis
        perspective_types = list(individual_perspectives.keys())
        
        for i in range(len(perspective_types)):
            for j in range(i + 1, len(perspective_types)):
                type1 = perspective_types[i]
                type2 = perspective_types[j]
                
                perspective1 = individual_perspectives[type1]
                perspective2 = individual_perspectives[type2]
                
                # Calculate disagreement level
                disagreement_level = 1.0 - self._calculate_perspective_similarity(perspective1, perspective2)
                
                if disagreement_level > 0.3:  # Threshold for significant disagreement
                    disagreements.append({
                        'perspective1': type1,
                        'perspective2': type2,
                        'disagreement_level': disagreement_level,
                        'description': f"Significant disagreement between {type1} and {type2} perspectives"
                    })
        
        return disagreements
    
    def _calculate_consensus_score(self, perspective_agreement: Dict[str, float]) -> float:
        """Calculate overall consensus score"""
        if not perspective_agreement:
            return 0.0
        
        return sum(perspective_agreement.values()) / len(perspective_agreement)
    
    def _calculate_analysis_quality_score(self, individual_perspectives: Dict[str, PerspectiveAnalysis]) -> float:
        """Calculate overall analysis quality score"""
        if not individual_perspectives:
            return 0.0
        
        quality_scores = []
        for analysis in individual_perspectives.values():
            # Combine confidence score with content quality indicators
            content_quality = min(len(analysis.analysis_content) / 1000, 1.0)  # Length factor
            key_points_quality = min(len(analysis.key_points) / 5, 1.0)  # Key points factor
            evidence_quality = min(len(analysis.supporting_evidence) / 3, 1.0)  # Evidence factor
            
            overall_quality = (analysis.confidence_score + content_quality + key_points_quality + evidence_quality) / 4
            quality_scores.append(overall_quality)
        
        return sum(quality_scores) / len(quality_scores)
    
    async def _get_storyline_data(self, storyline_id: str) -> Optional[Dict[str, Any]]:
        """Get storyline data from database"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Get storyline basic info
                storyline_query = text("""
                    SELECT id, title, description, status, created_at, updated_at
                    FROM storylines 
                    WHERE id = :storyline_id
                """)
                storyline_result = db.execute(storyline_query, {"storyline_id": storyline_id}).fetchone()
                
                if not storyline_result:
                    return None
                
                # Get articles for this storyline
                articles_query = text("""
                    SELECT id, title, content, summary, source, published_at, quality_score
                    FROM articles 
                    WHERE storyline_id = :storyline_id 
                    AND status = 'processed'
                    ORDER BY published_at DESC
                    LIMIT 50
                """)
                articles_result = db.execute(articles_query, {"storyline_id": storyline_id}).fetchall()
                
                articles = []
                for row in articles_result:
                    articles.append({
                        'id': row[0],
                        'title': row[1],
                        'content': row[2] or '',
                        'summary': row[3] or '',
                        'source': row[4] or '',
                        'published_at': row[5].isoformat() if row[5] else '',
                        'quality_score': float(row[6]) if row[6] else 0.0
                    })
                
                return {
                    'id': storyline_result[0],
                    'title': storyline_result[1],
                    'description': storyline_result[2],
                    'status': storyline_result[3],
                    'created_at': storyline_result[4].isoformat() if storyline_result[4] else '',
                    'updated_at': storyline_result[5].isoformat() if storyline_result[5] else '',
                    'articles': articles
                }
                
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error getting storyline data: {e}")
            return None
    
    async def _store_perspective_analysis(self, storyline_id: str, analysis: PerspectiveAnalysis):
        """Store perspective analysis in database"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                insert_query = text("""
                    INSERT INTO analysis_perspectives (
                        storyline_id, perspective_type, analysis_content, confidence_score,
                        key_points, supporting_evidence, source_articles, analysis_metadata
                    ) VALUES (
                        :storyline_id, :perspective_type, :analysis_content, :confidence_score,
                        :key_points, :supporting_evidence, :source_articles, :analysis_metadata
                    )
                """)
                
                db.execute(insert_query, {
                    'storyline_id': storyline_id,
                    'perspective_type': analysis.perspective_type,
                    'analysis_content': analysis.analysis_content,
                    'confidence_score': analysis.confidence_score,
                    'key_points': json.dumps(analysis.key_points),
                    'supporting_evidence': json.dumps(analysis.supporting_evidence),
                    'source_articles': json.dumps(analysis.source_articles),
                    'analysis_metadata': json.dumps(analysis.analysis_metadata)
                })
                db.commit()
                
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error storing perspective analysis: {e}")
    
    async def _store_multi_perspective_analysis(self, result: MultiPerspectiveResult):
        """Store multi-perspective analysis result in database"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                insert_query = text("""
                    INSERT INTO multi_perspective_analysis (
                        storyline_id, analysis_version, synthesized_analysis,
                        perspective_agreement, key_disagreements, consensus_score,
                        analysis_quality_score, processing_metadata
                    ) VALUES (
                        :storyline_id, :analysis_version, :synthesized_analysis,
                        :perspective_agreement, :key_disagreements, :consensus_score,
                        :analysis_quality_score, :processing_metadata
                    )
                """)
                
                db.execute(insert_query, {
                    'storyline_id': result.storyline_id,
                    'analysis_version': 1,
                    'synthesized_analysis': result.synthesized_analysis,
                    'perspective_agreement': json.dumps(result.perspective_agreement),
                    'key_disagreements': json.dumps(result.key_disagreements),
                    'consensus_score': result.consensus_score,
                    'analysis_quality_score': result.analysis_quality_score,
                    'processing_metadata': json.dumps({
                        'generated_at': datetime.now(timezone.utc).isoformat(),
                        'perspective_count': len(result.individual_perspectives)
                    })
                })
                db.commit()
                
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error storing multi-perspective analysis: {e}")

# Global instance
_multi_perspective_analyzer = None

def get_multi_perspective_analyzer(ml_service=None, rag_service=None) -> MultiPerspectiveAnalyzer:
    """Get global multi-perspective analyzer instance"""
    global _multi_perspective_analyzer
    if _multi_perspective_analyzer is None:
        _multi_perspective_analyzer = MultiPerspectiveAnalyzer(ml_service, rag_service)
    return _multi_perspective_analyzer

