"""
Impact Assessment Service for News Intelligence System v3.0
Provides comprehensive impact assessment across multiple dimensions
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from config.database import get_db
from sqlalchemy import text

logger = logging.getLogger(__name__)


class ImpactDimension(Enum):
    """Available impact assessment dimensions"""

    POLITICAL = "political"
    ECONOMIC = "economic"
    SOCIAL = "social"
    ENVIRONMENTAL = "environmental"
    TECHNOLOGICAL = "technological"
    INTERNATIONAL = "international"


@dataclass
class ImpactAssessment:
    """Result of impact assessment for a specific dimension"""

    dimension: str
    impact_score: float
    impact_description: str
    subcategory_impacts: dict[str, Any]
    supporting_evidence: list[dict[str, Any]]
    confidence_level: float
    risk_level: str
    mitigation_strategies: list[str]
    assessment_metadata: dict[str, Any]


@dataclass
class ComprehensiveImpactResult:
    """Result of comprehensive impact assessment"""

    storyline_id: str
    dimension_assessments: dict[str, ImpactAssessment]
    overall_impact_score: float
    high_impact_scenarios: list[dict[str, Any]]
    risk_assessment: dict[str, Any]
    mitigation_recommendations: list[dict[str, Any]]
    assessment_quality_score: float


class ImpactAssessmentService:
    """
    Impact assessment service that analyzes potential impacts across multiple dimensions
    """

    def __init__(self, ml_service=None):
        """
        Initialize the Impact Assessment Service

        Args:
            ml_service: ML summarization service instance
        """
        self.ml_service = ml_service

        # Impact dimension configurations
        self.impact_dimensions = {
            ImpactDimension.POLITICAL: {
                "name": "Political Impact",
                "description": "Analysis of political implications and consequences",
                "subcategories": [
                    "policy_changes",
                    "election_impact",
                    "governance_effects",
                    "regulatory_impact",
                    "public_administration",
                ],
                "system_prompt": """You are a senior political analyst and policy expert with extensive experience in government affairs and political science. Analyze the political impact of this news story. Focus on:
- Policy implications and regulatory changes
- Election and electoral impact
- Governance and institutional effects
- Public administration and bureaucracy
- Political stability and institutional integrity
- Democratic processes and civil liberties
- Political party dynamics and coalition building
- Public trust in government and institutions
- Long-term political development and reform

Provide specific, actionable insights for political decision-makers and stakeholders.""",
                "user_prompt_template": """Analyze the political impact of this news story:

STORYLINE: {storyline_title}
ARTICLES: {articles_context}
RAG CONTEXT: {rag_context}

Provide a comprehensive political impact analysis covering:
1. **Policy Implications**: What policy changes might be needed?
2. **Election Impact**: How might this affect upcoming elections?
3. **Governance Effects**: What are the implications for government operations?
4. **Regulatory Impact**: What regulatory changes might be required?
5. **Public Administration**: How will this affect public sector management?
6. **Political Stability**: What are the risks to political stability?
7. **Democratic Processes**: How does this affect democratic institutions?
8. **Long-term Development**: What are the long-term political implications?

Focus on practical political consequences and policy recommendations.""",
            },
            ImpactDimension.ECONOMIC: {
                "name": "Economic Impact",
                "description": "Analysis of economic implications and consequences",
                "subcategories": [
                    "market_impact",
                    "gdp_effects",
                    "employment_changes",
                    "inflation_impact",
                    "trade_effects",
                    "investment_impact",
                ],
                "system_prompt": """You are a senior economic analyst and financial expert with extensive experience in macroeconomics, financial markets, and economic policy. Analyze the economic impact of this news story. Focus on:
- Market reactions and financial implications
- GDP and economic growth effects
- Employment and labor market impacts
- Inflation and price stability
- Trade and international economic relations
- Investment and capital allocation
- Consumer behavior and spending patterns
- Business and industry effects
- Economic inequality and distributional impacts
- Long-term economic development and growth

Provide specific, data-driven insights for economic decision-makers and investors.""",
                "user_prompt_template": """Analyze the economic impact of this news story:

STORYLINE: {storyline_title}
ARTICLES: {articles_context}
RAG CONTEXT: {rag_context}

Provide a comprehensive economic impact analysis covering:
1. **Market Impact**: How will this affect financial markets?
2. **GDP Effects**: What are the implications for economic growth?
3. **Employment Impact**: How will this affect jobs and employment?
4. **Inflation Impact**: What are the price stability implications?
5. **Trade Effects**: How will this affect international trade?
6. **Investment Impact**: What are the implications for investment?
7. **Consumer Behavior**: How will this affect consumer spending?
8. **Business Impact**: What are the implications for businesses and industries?

Focus on economic data, market analysis, and financial implications.""",
            },
            ImpactDimension.SOCIAL: {
                "name": "Social Impact",
                "description": "Analysis of social implications and consequences",
                "subcategories": [
                    "public_opinion",
                    "social_cohesion",
                    "demographic_impact",
                    "community_effects",
                    "social_services",
                    "public_health",
                ],
                "system_prompt": """You are a senior social policy analyst and sociologist with extensive experience in social research, community development, and public welfare. Analyze the social impact of this news story. Focus on:
- Public opinion and social attitudes
- Social cohesion and community relations
- Demographic and population impacts
- Community development and social capital
- Social services and public welfare
- Public health and safety implications
- Education and social mobility
- Cultural and social identity impacts
- Social inequality and justice
- Long-term social development and cohesion

Provide specific insights for social policy makers and community leaders.""",
                "user_prompt_template": """Analyze the social impact of this news story:

STORYLINE: {storyline_title}
ARTICLES: {articles_context}
RAG CONTEXT: {rag_context}

Provide a comprehensive social impact analysis covering:
1. **Public Opinion**: How will this affect public attitudes and beliefs?
2. **Social Cohesion**: What are the implications for community relations?
3. **Demographic Impact**: How will this affect different population groups?
4. **Community Effects**: What are the local community implications?
5. **Social Services**: How will this affect social service delivery?
6. **Public Health**: What are the health and safety implications?
7. **Education Impact**: How will this affect educational outcomes?
8. **Social Justice**: What are the implications for social equality?

Focus on community welfare, social equity, and public well-being.""",
            },
            ImpactDimension.ENVIRONMENTAL: {
                "name": "Environmental Impact",
                "description": "Analysis of environmental implications and consequences",
                "subcategories": [
                    "climate_impact",
                    "biodiversity_effects",
                    "resource_usage",
                    "pollution_impact",
                    "ecosystem_effects",
                    "sustainability_impact",
                ],
                "system_prompt": """You are a senior environmental scientist and policy expert with extensive experience in environmental research, climate science, and sustainability. Analyze the environmental impact of this news story. Focus on:
- Climate change and greenhouse gas implications
- Biodiversity and ecosystem effects
- Natural resource usage and depletion
- Pollution and environmental degradation
- Air, water, and soil quality impacts
- Renewable energy and sustainability
- Environmental justice and equity
- Long-term environmental sustainability
- Conservation and protection efforts
- Environmental policy and regulation

Provide specific insights for environmental policy makers and sustainability experts.""",
                "user_prompt_template": """Analyze the environmental impact of this news story:

STORYLINE: {storyline_title}
ARTICLES: {articles_context}
RAG CONTEXT: {rag_context}

Provide a comprehensive environmental impact analysis covering:
1. **Climate Impact**: How will this affect climate change and emissions?
2. **Biodiversity Effects**: What are the implications for ecosystems and wildlife?
3. **Resource Usage**: How will this affect natural resource consumption?
4. **Pollution Impact**: What are the environmental pollution implications?
5. **Ecosystem Effects**: How will this affect natural ecosystems?
6. **Sustainability Impact**: What are the long-term sustainability implications?
7. **Environmental Justice**: How will this affect environmental equity?
8. **Conservation Efforts**: What are the implications for environmental protection?

Focus on environmental sustainability, conservation, and climate action.""",
            },
            ImpactDimension.TECHNOLOGICAL: {
                "name": "Technological Impact",
                "description": "Analysis of technological implications and consequences",
                "subcategories": [
                    "innovation_effects",
                    "digital_impact",
                    "cybersecurity_implications",
                    "automation_effects",
                    "infrastructure_impact",
                    "research_development",
                ],
                "system_prompt": """You are a senior technology analyst and innovation expert with extensive experience in technology research, digital transformation, and innovation policy. Analyze the technological impact of this news story. Focus on:
- Innovation and technological advancement
- Digital transformation and adoption
- Cybersecurity and data protection
- Automation and artificial intelligence
- Infrastructure and connectivity
- Research and development implications
- Technology accessibility and equity
- Digital rights and privacy
- Long-term technological development
- Technology policy and regulation

Provide specific insights for technology leaders and innovation policy makers.""",
                "user_prompt_template": """Analyze the technological impact of this news story:

STORYLINE: {storyline_title}
ARTICLES: {articles_context}
RAG CONTEXT: {rag_context}

Provide a comprehensive technological impact analysis covering:
1. **Innovation Effects**: How will this affect technological innovation?
2. **Digital Impact**: What are the digital transformation implications?
3. **Cybersecurity**: How will this affect cybersecurity and data protection?
4. **Automation Effects**: What are the implications for automation and AI?
5. **Infrastructure Impact**: How will this affect technological infrastructure?
6. **Research & Development**: What are the R&D implications?
7. **Technology Access**: How will this affect digital equity and access?
8. **Digital Rights**: What are the implications for privacy and digital rights?

Focus on technological advancement, digital transformation, and innovation policy.""",
            },
            ImpactDimension.INTERNATIONAL: {
                "name": "International Impact",
                "description": "Analysis of international implications and consequences",
                "subcategories": [
                    "diplomatic_relations",
                    "trade_impact",
                    "security_implications",
                    "multilateral_cooperation",
                    "global_governance",
                    "international_law",
                ],
                "system_prompt": """You are a senior international relations analyst and diplomatic expert with extensive experience in global affairs, international law, and multilateral cooperation. Analyze the international impact of this news story. Focus on:
- Diplomatic relations and foreign policy
- International trade and economic cooperation
- Global security and conflict implications
- Multilateral cooperation and institutions
- Global governance and international law
- Cross-border effects and regional implications
- International development and aid
- Global public opinion and soft power
- Long-term international order
- International cooperation and partnerships

Provide specific insights for diplomats, international organizations, and global policy makers.""",
                "user_prompt_template": """Analyze the international impact of this news story:

STORYLINE: {storyline_title}
ARTICLES: {articles_context}
RAG CONTEXT: {rag_context}

Provide a comprehensive international impact analysis covering:
1. **Diplomatic Relations**: How will this affect international diplomacy?
2. **Trade Impact**: What are the implications for international trade?
3. **Security Implications**: How will this affect global security?
4. **Multilateral Cooperation**: What are the implications for international organizations?
5. **Global Governance**: How will this affect international law and governance?
6. **Regional Effects**: What are the regional and cross-border implications?
7. **International Development**: How will this affect global development efforts?
8. **Global Order**: What are the implications for international stability?

Focus on global cooperation, international law, and diplomatic relations.""",
            },
        }

    async def assess_impacts(
        self, storyline_id: str, articles: list[dict], rag_context: dict[str, Any] = None
    ) -> ComprehensiveImpactResult:
        """
        Assess potential impacts across all dimensions

        Args:
            storyline_id: ID of the storyline to assess
            articles: List of articles in the storyline
            rag_context: Optional RAG context for enhanced analysis

        Returns:
            ComprehensiveImpactResult with all dimension assessments
        """
        try:
            logger.info(f"Assessing impacts for storyline: {storyline_id}")

            # Generate individual dimension assessments
            dimension_assessments = {}
            for dimension in ImpactDimension:
                logger.info(f"Assessing {dimension.value} impact")

                assessment = await self._assess_dimension_impact(
                    storyline_id, articles, rag_context, dimension
                )
                dimension_assessments[dimension.value] = assessment

                # Store in database
                await self._store_impact_assessment(storyline_id, assessment)

            # Calculate overall impact score
            overall_impact_score = self._calculate_overall_impact_score(dimension_assessments)

            # Identify high-impact scenarios
            high_impact_scenarios = self._identify_high_impact_scenarios(dimension_assessments)

            # Generate risk assessment
            risk_assessment = self._generate_risk_assessment(dimension_assessments)

            # Generate mitigation recommendations
            mitigation_recommendations = self._generate_mitigation_recommendations(
                dimension_assessments
            )

            # Calculate assessment quality score
            assessment_quality_score = self._calculate_assessment_quality_score(
                dimension_assessments
            )

            # Create result
            result = ComprehensiveImpactResult(
                storyline_id=storyline_id,
                dimension_assessments=dimension_assessments,
                overall_impact_score=overall_impact_score,
                high_impact_scenarios=high_impact_scenarios,
                risk_assessment=risk_assessment,
                mitigation_recommendations=mitigation_recommendations,
                assessment_quality_score=assessment_quality_score,
            )

            # Store comprehensive assessment
            await self._store_comprehensive_impact_assessment(result)

            logger.info(f"Impact assessment completed for storyline: {storyline_id}")
            return result

        except Exception as e:
            logger.error(f"Error assessing impacts: {e}")
            raise

    async def _assess_dimension_impact(
        self,
        storyline_id: str,
        articles: list[dict],
        rag_context: dict[str, Any],
        dimension: ImpactDimension,
    ) -> ImpactAssessment:
        """Assess impact for a specific dimension"""
        try:
            config = self.impact_dimensions[dimension]

            # Prepare context
            storyline_title = "Storyline Analysis"  # Default title
            if articles:
                storyline_title = articles[0].get("title", "Storyline Analysis")

            articles_context = self._prepare_articles_context(articles)
            rag_context_str = (
                self._prepare_rag_context(rag_context)
                if rag_context
                else "No additional context available"
            )

            # Create prompts
            system_prompt = config["system_prompt"]
            user_prompt = config["user_prompt_template"].format(
                storyline_title=storyline_title,
                articles_context=articles_context,
                rag_context=rag_context_str,
            )

            # Generate analysis using ML service
            if self.ml_service:
                analysis_result = await self._call_ml_service(system_prompt, user_prompt)
                impact_description = analysis_result.get("summary", "")
                confidence_level = analysis_result.get("confidence_score", 0.5)
            else:
                # Fallback to basic analysis
                impact_description = await self._generate_fallback_impact_analysis(
                    storyline_title, articles, dimension
                )
                confidence_level = 0.3

            # Extract impact metrics
            impact_score = self._extract_impact_score(impact_description)
            subcategory_impacts = self._extract_subcategory_impacts(
                impact_description, config["subcategories"]
            )
            supporting_evidence = self._extract_supporting_evidence(articles, impact_description)
            risk_level = self._determine_risk_level(impact_score, confidence_level)
            mitigation_strategies = self._generate_mitigation_strategies(
                impact_description, dimension
            )

            # Create assessment metadata
            assessment_metadata = {
                "dimension_name": config["name"],
                "subcategories_analyzed": config["subcategories"],
                "analysis_length": len(impact_description),
                "confidence_level": confidence_level,
                "risk_level": risk_level,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

            return ImpactAssessment(
                dimension=dimension.value,
                impact_score=impact_score,
                impact_description=impact_description,
                subcategory_impacts=subcategory_impacts,
                supporting_evidence=supporting_evidence,
                confidence_level=confidence_level,
                risk_level=risk_level,
                mitigation_strategies=mitigation_strategies,
                assessment_metadata=assessment_metadata,
            )

        except Exception as e:
            logger.error(f"Error assessing {dimension.value} impact: {e}")
            # Return minimal assessment on error
            return ImpactAssessment(
                dimension=dimension.value,
                impact_score=0.0,
                impact_description=f"Impact assessment for {dimension.value} could not be generated due to error: {str(e)}",
                subcategory_impacts={},
                supporting_evidence=[],
                confidence_level=0.0,
                risk_level="unknown",
                mitigation_strategies=[],
                assessment_metadata={"error": str(e)},
            )

    async def _call_ml_service(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        """Call ML service for impact analysis generation"""
        try:
            if hasattr(self.ml_service, "generate_summary"):
                # Use existing ML service
                result = self.ml_service.generate_summary(user_prompt, system_prompt)
                return result
            else:
                # Fallback
                return {"summary": "ML service not available", "confidence_score": 0.0}
        except Exception as e:
            logger.error(f"Error calling ML service: {e}")
            return {"summary": "ML service error", "confidence_score": 0.0}

    async def _generate_fallback_impact_analysis(
        self, storyline_title: str, articles: list[dict], dimension: ImpactDimension
    ) -> str:
        """Generate fallback impact analysis when ML service is not available"""
        config = self.impact_dimensions[dimension]

        # Basic analysis based on article titles and content
        article_summaries = []
        for article in articles[:5]:  # Limit to first 5 articles
            title = article.get("title", "")
            content = article.get("content", "")[:200]  # First 200 chars
            article_summaries.append(f"- {title}: {content}...")

        articles_text = "\n".join(article_summaries)

        return f"""Impact Assessment: {config["name"]}

Storyline: {storyline_title}

Key Articles:
{articles_text}

Focus Areas: {", ".join(config["subcategories"])}

This is a basic impact assessment generated without full ML processing. For comprehensive analysis, the ML service should be available.

**Impact Score**: 0.5 (Medium)
**Risk Level**: Medium
**Key Considerations**:
- Monitor for additional developments
- Consider stakeholder implications
- Assess resource requirements
- Plan for potential mitigation strategies"""

    def _prepare_articles_context(self, articles: list[dict]) -> str:
        """Prepare articles context for impact analysis"""
        context_parts = []

        for i, article in enumerate(articles[:10], 1):  # Limit to 10 articles
            title = article.get("title", "No title")
            content = article.get("content", "")[:500]  # First 500 chars
            source = article.get("source", "Unknown source")
            published_at = article.get("published_at", "Unknown date")

            context_parts.append(f"""
Article {i}:
Title: {title}
Source: {source}
Published: {published_at}
Content: {content}...
""")

        return "\n".join(context_parts)

    def _prepare_rag_context(self, rag_context: dict[str, Any]) -> str:
        """Prepare RAG context for impact analysis"""
        if not rag_context:
            return "No additional context available"

        context_parts = []

        # Wikipedia context
        if "wikipedia" in rag_context:
            wiki = rag_context["wikipedia"]
            if "summaries" in wiki:
                context_parts.append(
                    f"Wikipedia Context: {json.dumps(wiki['summaries'], indent=2)}"
                )

        # GDELT context
        if "gdelt" in rag_context:
            gdelt = rag_context["gdelt"]
            if "events" in gdelt:
                context_parts.append(f"GDELT Events: {json.dumps(gdelt['events'], indent=2)}")

        # Extracted entities and topics
        if "extracted_entities" in rag_context:
            context_parts.append(f"Key Entities: {', '.join(rag_context['extracted_entities'])}")

        if "extracted_topics" in rag_context:
            context_parts.append(f"Key Topics: {', '.join(rag_context['extracted_topics'])}")

        return "\n".join(context_parts) if context_parts else "No additional context available"

    def _extract_impact_score(self, impact_description: str) -> float:
        """Extract impact score from analysis description"""
        # Simple extraction - look for impact score mentions
        import re

        # Look for explicit impact score mentions
        score_patterns = [
            r"impact score[:\s]*([0-9.]+)",
            r"impact level[:\s]*(low|medium|high|critical)",
            r"significance[:\s]*(low|medium|high|critical)",
            r"severity[:\s]*(low|medium|high|critical)",
        ]

        for pattern in score_patterns:
            match = re.search(pattern, impact_description.lower())
            if match:
                if "low" in match.group(1).lower():
                    return 0.25
                elif "medium" in match.group(1).lower():
                    return 0.5
                elif "high" in match.group(1).lower():
                    return 0.75
                elif "critical" in match.group(1).lower():
                    return 1.0
                else:
                    try:
                        return float(match.group(1))
                    except ValueError:
                        continue

        # Default to medium impact if no explicit score found
        return 0.5

    def _extract_subcategory_impacts(
        self, impact_description: str, subcategories: list[str]
    ) -> dict[str, Any]:
        """Extract subcategory-specific impacts"""
        subcategory_impacts = {}

        for subcategory in subcategories:
            # Simple keyword matching for subcategory impacts
            subcategory_keywords = {
                "policy_changes": ["policy", "regulation", "governance", "legislation"],
                "election_impact": ["election", "voting", "electoral", "campaign"],
                "governance_effects": [
                    "governance",
                    "administration",
                    "bureaucracy",
                    "institution",
                ],
                "market_impact": ["market", "financial", "economic", "trading"],
                "gdp_effects": ["gdp", "growth", "economic", "productivity"],
                "employment_changes": ["employment", "jobs", "workforce", "labor"],
                "public_opinion": ["opinion", "public", "attitude", "perception"],
                "social_cohesion": ["cohesion", "community", "social", "unity"],
                "demographic_impact": ["demographic", "population", "age", "gender"],
                "climate_impact": ["climate", "emissions", "carbon", "environmental"],
                "biodiversity_effects": ["biodiversity", "wildlife", "ecosystem", "species"],
                "resource_usage": ["resource", "energy", "water", "materials"],
                "innovation_effects": ["innovation", "technology", "research", "development"],
                "digital_impact": ["digital", "online", "cyber", "internet"],
                "cybersecurity_implications": ["cybersecurity", "security", "privacy", "data"],
                "diplomatic_relations": ["diplomatic", "foreign", "international", "relations"],
                "trade_impact": ["trade", "commerce", "export", "import"],
                "security_implications": ["security", "defense", "military", "threat"],
            }

            keywords = subcategory_keywords.get(subcategory, [])
            impact_level = 0.0

            for keyword in keywords:
                if keyword.lower() in impact_description.lower():
                    impact_level += 0.2

            subcategory_impacts[subcategory] = {
                "impact_level": min(impact_level, 1.0),
                "keywords_found": [
                    kw for kw in keywords if kw.lower() in impact_description.lower()
                ],
                "description": f"Impact on {subcategory.replace('_', ' ')}",
            }

        return subcategory_impacts

    def _extract_supporting_evidence(
        self, articles: list[dict], impact_description: str
    ) -> list[dict[str, Any]]:
        """Extract supporting evidence from articles"""
        evidence = []

        for article in articles[:5]:  # Limit to first 5 articles
            evidence.append(
                {
                    "article_id": article.get("id", 0),
                    "title": article.get("title", ""),
                    "source": article.get("source", ""),
                    "relevance_score": 0.5,  # Placeholder
                    "evidence_type": "article_content",
                    "supporting_quotes": [],  # Could be enhanced with quote extraction
                }
            )

        return evidence

    def _determine_risk_level(self, impact_score: float, confidence_level: float) -> str:
        """Determine risk level based on impact score and confidence"""
        # Weighted risk assessment
        weighted_score = (impact_score * 0.7) + (confidence_level * 0.3)

        if weighted_score >= 0.8:
            return "critical"
        elif weighted_score >= 0.6:
            return "high"
        elif weighted_score >= 0.4:
            return "medium"
        else:
            return "low"

    def _generate_mitigation_strategies(
        self, impact_description: str, dimension: ImpactDimension
    ) -> list[str]:
        """Generate mitigation strategies based on impact analysis"""
        strategies = []

        # Generic mitigation strategies based on dimension
        dimension_strategies = {
            ImpactDimension.POLITICAL: [
                "Engage with political stakeholders early",
                "Develop comprehensive policy framework",
                "Ensure transparent communication",
                "Build bipartisan support where possible",
            ],
            ImpactDimension.ECONOMIC: [
                "Conduct thorough economic impact assessment",
                "Develop economic stimulus measures",
                "Monitor market reactions closely",
                "Prepare contingency financial plans",
            ],
            ImpactDimension.SOCIAL: [
                "Engage with community stakeholders",
                "Develop social support programs",
                "Ensure equitable access to benefits",
                "Monitor social cohesion indicators",
            ],
            ImpactDimension.ENVIRONMENTAL: [
                "Conduct environmental impact assessment",
                "Implement sustainable practices",
                "Monitor environmental indicators",
                "Develop conservation strategies",
            ],
            ImpactDimension.TECHNOLOGICAL: [
                "Invest in technology infrastructure",
                "Ensure cybersecurity measures",
                "Promote digital literacy",
                "Develop innovation partnerships",
            ],
            ImpactDimension.INTERNATIONAL: [
                "Engage with international partners",
                "Strengthen diplomatic relations",
                "Monitor global implications",
                "Develop multilateral cooperation",
            ],
        }

        strategies.extend(dimension_strategies.get(dimension, []))

        # Add specific strategies based on impact description
        if "high" in impact_description.lower() or "critical" in impact_description.lower():
            strategies.extend(
                [
                    "Implement immediate response measures",
                    "Establish crisis management team",
                    "Develop rapid response protocols",
                    "Monitor situation continuously",
                ]
            )

        return strategies[:8]  # Limit to 8 strategies

    def _calculate_overall_impact_score(
        self, dimension_assessments: dict[str, ImpactAssessment]
    ) -> float:
        """Calculate overall impact score across all dimensions"""
        if not dimension_assessments:
            return 0.0

        # Weight different dimensions differently
        dimension_weights = {
            "political": 0.2,
            "economic": 0.25,
            "social": 0.15,
            "environmental": 0.15,
            "technological": 0.1,
            "international": 0.15,
        }

        weighted_score = 0.0
        total_weight = 0.0

        for dimension, assessment in dimension_assessments.items():
            weight = dimension_weights.get(dimension, 0.1)
            weighted_score += assessment.impact_score * weight
            total_weight += weight

        return weighted_score / total_weight if total_weight > 0 else 0.0

    def _identify_high_impact_scenarios(
        self, dimension_assessments: dict[str, ImpactAssessment]
    ) -> list[dict[str, Any]]:
        """Identify high-impact scenarios across dimensions"""
        high_impact_scenarios = []

        for dimension, assessment in dimension_assessments.items():
            if assessment.impact_score >= 0.7 or assessment.risk_level in ["high", "critical"]:
                high_impact_scenarios.append(
                    {
                        "dimension": dimension,
                        "impact_score": assessment.impact_score,
                        "risk_level": assessment.risk_level,
                        "description": f"High impact scenario in {dimension} dimension",
                        "mitigation_priority": "high"
                        if assessment.risk_level == "critical"
                        else "medium",
                    }
                )

        return high_impact_scenarios

    def _generate_risk_assessment(
        self, dimension_assessments: dict[str, ImpactAssessment]
    ) -> dict[str, Any]:
        """Generate comprehensive risk assessment"""
        risk_levels = [assessment.risk_level for assessment in dimension_assessments.values()]
        impact_scores = [assessment.impact_score for assessment in dimension_assessments.values()]

        # Calculate overall risk level
        critical_count = risk_levels.count("critical")
        high_count = risk_levels.count("high")
        medium_count = risk_levels.count("medium")
        low_count = risk_levels.count("low")

        if critical_count > 0:
            overall_risk = "critical"
        elif high_count >= 2:
            overall_risk = "high"
        elif high_count >= 1 or medium_count >= 3:
            overall_risk = "medium"
        else:
            overall_risk = "low"

        return {
            "overall_risk_level": overall_risk,
            "risk_distribution": {
                "critical": critical_count,
                "high": high_count,
                "medium": medium_count,
                "low": low_count,
            },
            "average_impact_score": sum(impact_scores) / len(impact_scores)
            if impact_scores
            else 0.0,
            "high_risk_dimensions": [
                dim
                for dim, assessment in dimension_assessments.items()
                if assessment.risk_level in ["high", "critical"]
            ],
        }

    def _generate_mitigation_recommendations(
        self, dimension_assessments: dict[str, ImpactAssessment]
    ) -> list[dict[str, Any]]:
        """Generate comprehensive mitigation recommendations"""
        recommendations = []

        # Collect all mitigation strategies
        all_strategies = []
        for assessment in dimension_assessments.values():
            all_strategies.extend(assessment.mitigation_strategies)

        # Prioritize strategies based on risk levels
        high_risk_dimensions = [
            dim
            for dim, assessment in dimension_assessments.items()
            if assessment.risk_level in ["high", "critical"]
        ]

        for strategy in set(all_strategies):  # Remove duplicates
            priority = (
                "high"
                if any(dim in high_risk_dimensions for dim in dimension_assessments.keys())
                else "medium"
            )
            recommendations.append(
                {
                    "strategy": strategy,
                    "priority": priority,
                    "applicable_dimensions": [
                        dim
                        for dim, assessment in dimension_assessments.items()
                        if strategy in assessment.mitigation_strategies
                    ],
                }
            )

        return recommendations

    def _calculate_assessment_quality_score(
        self, dimension_assessments: dict[str, ImpactAssessment]
    ) -> float:
        """Calculate overall assessment quality score"""
        if not dimension_assessments:
            return 0.0

        quality_factors = []

        for assessment in dimension_assessments.values():
            # Combine confidence level with content quality indicators
            content_quality = min(len(assessment.impact_description) / 1000, 1.0)  # Length factor
            evidence_quality = min(len(assessment.supporting_evidence) / 3, 1.0)  # Evidence factor
            strategy_quality = min(
                len(assessment.mitigation_strategies) / 5, 1.0
            )  # Strategy factor

            overall_quality = (
                assessment.confidence_level + content_quality + evidence_quality + strategy_quality
            ) / 4
            quality_factors.append(overall_quality)

        return sum(quality_factors) / len(quality_factors)

    async def _store_impact_assessment(self, storyline_id: str, assessment: ImpactAssessment):
        """Store impact assessment in database"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                insert_query = text("""
                    INSERT INTO impact_assessments (
                        storyline_id, impact_dimension, impact_score, impact_description,
                        subcategory_impacts, supporting_evidence, confidence_level,
                        risk_level, mitigation_strategies
                    ) VALUES (
                        :storyline_id, :impact_dimension, :impact_score, :impact_description,
                        :subcategory_impacts, :supporting_evidence, :confidence_level,
                        :risk_level, :mitigation_strategies
                    )
                """)

                db.execute(
                    insert_query,
                    {
                        "storyline_id": storyline_id,
                        "impact_dimension": assessment.dimension,
                        "impact_score": assessment.impact_score,
                        "impact_description": assessment.impact_description,
                        "subcategory_impacts": json.dumps(assessment.subcategory_impacts),
                        "supporting_evidence": json.dumps(assessment.supporting_evidence),
                        "confidence_level": assessment.confidence_level,
                        "risk_level": assessment.risk_level,
                        "mitigation_strategies": json.dumps(assessment.mitigation_strategies),
                    },
                )
                db.commit()

            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error storing impact assessment: {e}")

    async def _store_comprehensive_impact_assessment(self, result: ComprehensiveImpactResult):
        """Store comprehensive impact assessment result"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Store in a comprehensive impact assessments table (if it exists)
                # For now, we'll store the overall metrics in the analysis_quality_metrics table
                insert_query = text("""
                    INSERT INTO analysis_quality_metrics (
                        storyline_id, analysis_type, completeness_score, accuracy_score,
                        readability_score, timeliness_score, user_engagement_score,
                        overall_quality_score, quality_metadata
                    ) VALUES (
                        :storyline_id, :analysis_type, :completeness_score, :accuracy_score,
                        :readability_score, :timeliness_score, :user_engagement_score,
                        :overall_quality_score, :quality_metadata
                    )
                """)

                db.execute(
                    insert_query,
                    {
                        "storyline_id": result.storyline_id,
                        "analysis_type": "impact_assessment",
                        "completeness_score": result.assessment_quality_score,
                        "accuracy_score": result.assessment_quality_score,
                        "readability_score": result.assessment_quality_score,
                        "timeliness_score": 1.0,  # Assume current analysis is timely
                        "user_engagement_score": 0.5,  # Placeholder
                        "overall_quality_score": result.assessment_quality_score,
                        "quality_metadata": json.dumps(
                            {
                                "overall_impact_score": result.overall_impact_score,
                                "high_impact_scenarios_count": len(result.high_impact_scenarios),
                                "risk_assessment": result.risk_assessment,
                                "generated_at": datetime.now(timezone.utc).isoformat(),
                            }
                        ),
                    },
                )
                db.commit()

            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error storing comprehensive impact assessment: {e}")


# Global instance
_impact_assessment_service = None


def get_impact_assessment_service(ml_service=None) -> ImpactAssessmentService:
    """Get global impact assessment service instance"""
    global _impact_assessment_service
    if _impact_assessment_service is None:
        _impact_assessment_service = ImpactAssessmentService(ml_service)
    return _impact_assessment_service
