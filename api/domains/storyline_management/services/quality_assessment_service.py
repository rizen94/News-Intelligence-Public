#!/usr/bin/env python3
"""
Quality Assessment Service
Assesses storyline quality, coherence, and factual accuracy
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

from shared.services.domain_aware_service import DomainAwareService
from shared.services.llm_service import llm_service
from shared.database.connection import get_db_connection
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class QualityAssessmentService(DomainAwareService):
    """Service for assessing storyline quality and standards"""
    
    def __init__(self, domain: str = 'politics'):
        """
        Initialize quality assessment service with domain context.
        
        Args:
            domain: Domain key (e.g., 'politics', 'finance', 'science-tech')
        """
        super().__init__(domain)
    
    async def assess_storyline_quality(self, storyline_id: int) -> Dict[str, Any]:
        """
        Assess overall storyline quality.
        
        Args:
            storyline_id: ID of storyline to assess
            
        Returns:
            Dictionary with quality assessment results
        """
        try:
            conn = self.get_db_connection()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Get storyline
                    cur.execute(f"""
                        SELECT id, title, description, article_count,
                               quality_score,
                               analysis_summary
                        FROM {self.schema}.storylines
                        WHERE id = %s
                    """, (storyline_id,))
                    
                    storyline = cur.fetchone()
                    if not storyline:
                        return {"success": False, "error": "Storyline not found"}
                    
                    # Get articles
                    cur.execute(f"""
                        SELECT a.id, a.title, a.content, a.summary, a.published_at,
                               a.source_domain, a.quality_score, a.sentiment_score
                        FROM {self.schema}.articles a
                        JOIN {self.schema}.storyline_articles sa ON a.id = sa.article_id
                        WHERE sa.storyline_id = %s
                        ORDER BY a.published_at ASC
                    """, (storyline_id,))
                    
                    articles = cur.fetchall()
                    
                    if not articles:
                        return {
                            "success": False,
                            "error": "No articles in storyline"
                        }
                    
                    # Calculate quality metrics
                    assessment = await self._calculate_quality_metrics(
                        storyline, articles
                    )
                    
                    # Assess narrative coherence
                    coherence_assessment = await self._assess_narrative_coherence(
                        storyline, articles
                    )
                    
                    # Assess factual accuracy
                    accuracy_assessment = await self._assess_factual_accuracy(
                        articles
                    )
                    
                    # Assess professional standards
                    standards_assessment = await self._assess_professional_standards(
                        storyline, articles
                    )
                    
                    # Combine assessments
                    overall_score = (
                        assessment['quality_score'] * 0.3 +
                        coherence_assessment['coherence_score'] * 0.3 +
                        accuracy_assessment['accuracy_score'] * 0.2 +
                        standards_assessment['standards_score'] * 0.2
                    )
                    
                    # Update storyline with new scores
                    cur.execute(f"""
                        UPDATE {self.schema}.storylines
                        SET quality_score = %s,
                            factual_accuracy_score = %s,
                            narrative_quality_score = %s,
                            updated_at = %s
                        WHERE id = %s
                    """, (
                        overall_score,
                        accuracy_assessment['accuracy_score'],
                        standards_assessment['standards_score'],
                        datetime.now(),
                        storyline_id
                    ))
                    
                    conn.commit()
                    
                    return {
                        "success": True,
                        "data": {
                            "storyline_id": storyline_id,
                            "overall_quality_score": overall_score,
                            "quality_assessment": assessment,
                            "coherence_assessment": coherence_assessment,
                            "accuracy_assessment": accuracy_assessment,
                            "standards_assessment": standards_assessment,
                            "recommendations": self._generate_recommendations(
                                overall_score, coherence_assessment, 
                                accuracy_assessment, standards_assessment
                            )
                        }
                    }
                    
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"Error assessing storyline quality: {e}")
            return {"success": False, "error": str(e)}
    
    async def _calculate_quality_metrics(
        self,
        storyline: Dict,
        articles: List[Dict]
    ) -> Dict[str, Any]:
        """Calculate basic quality metrics"""
        article_count = len(articles)
        
        # Source diversity
        source_domains = set(a['source_domain'] for a in articles if a.get('source_domain'))
        source_diversity = len(source_domains)
        diversity_score = min(1.0, source_diversity / max(article_count, 1) * 2.0)
        
        # Average article quality
        quality_scores = [
            float(a.get('quality_score', 0.5)) 
            for a in articles 
            if a.get('quality_score')
        ]
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.5
        
        # Credibility scores (using quality_score as proxy since credibility_score doesn't exist)
        credibility_scores = [
            float(a.get('quality_score', 0.5))
            for a in articles
            if a.get('quality_score')
        ]
        avg_credibility = sum(credibility_scores) / len(credibility_scores) if credibility_scores else 0.5
        
        # Completeness (based on article count and coverage)
        completeness = min(1.0, article_count / 10.0)  # 10+ articles = complete
        
        # Overall quality score
        quality_score = (
            avg_quality * 0.4 +
            avg_credibility * 0.3 +
            diversity_score * 0.2 +
            completeness * 0.1
        )
        
        return {
            "quality_score": quality_score,
            "avg_article_quality": avg_quality,
            "avg_credibility": avg_credibility,
            "source_diversity": source_diversity,
            "diversity_score": diversity_score,
            "completeness": completeness,
            "article_count": article_count
        }
    
    async def _assess_narrative_coherence(
        self,
        storyline: Dict,
        articles: List[Dict]
    ) -> Dict[str, Any]:
        """Assess narrative coherence and flow"""
        article_count = len(articles)
        
        # Temporal coherence (articles in chronological order)
        dates = [a['published_at'] for a in articles if a.get('published_at')]
        temporal_coherence = 1.0 if len(dates) == article_count and dates == sorted(dates) else 0.7
        
        # Thematic coherence (based on title/description matching articles)
        title_keywords = set(
            storyline.get('title', '').lower().split() +
            (storyline.get('description', '') or '').lower().split()
        )
        
        # Check article title overlap
        article_matches = 0
        for article in articles:
            article_keywords = set(article.get('title', '').lower().split())
            if title_keywords & article_keywords:  # Intersection
                article_matches += 1
        
        thematic_coherence = article_matches / article_count if article_count > 0 else 0.0
        
        # Source consistency (diverse but related sources)
        source_domains = [a['source_domain'] for a in articles if a.get('source_domain')]
        unique_sources = len(set(source_domains))
        source_coherence = min(1.0, unique_sources / max(article_count, 1) * 1.5)
        
        # Overall coherence
        coherence_score = (
            temporal_coherence * 0.3 +
            thematic_coherence * 0.4 +
            source_coherence * 0.3
        )
        
        return {
            "coherence_score": coherence_score,
            "temporal_coherence": temporal_coherence,
            "thematic_coherence": thematic_coherence,
            "source_coherence": source_coherence,
            "article_matches": article_matches,
            "total_articles": article_count
        }
    
    async def _assess_factual_accuracy(self, articles: List[Dict]) -> Dict[str, Any]:
        """Assess factual accuracy across sources"""
        if not articles:
            return {"accuracy_score": 0.0, "cross_source_verification": 0.0}
        
        # Cross-source verification (more sources = higher confidence)
        source_domains = set(a['source_domain'] for a in articles if a.get('source_domain'))
        source_count = len(source_domains)
        
        # Credibility scores (using quality_score as proxy since credibility_score doesn't exist)
        credibility_scores = [
            float(a.get('quality_score', 0.5))
            for a in articles
            if a.get('quality_score')
        ]
        avg_credibility = sum(credibility_scores) / len(credibility_scores) if credibility_scores else 0.5
        
        # Cross-source verification score
        verification_score = min(1.0, source_count / 3.0)  # 3+ sources = verified
        
        # Overall accuracy
        accuracy_score = (
            avg_credibility * 0.6 +
            verification_score * 0.4
        )
        
        return {
            "accuracy_score": accuracy_score,
            "cross_source_verification": verification_score,
            "source_count": source_count,
            "avg_credibility": avg_credibility
        }
    
    async def _assess_professional_standards(
        self,
        storyline: Dict,
        articles: List[Dict]
    ) -> Dict[str, Any]:
        """Assess compliance with professional journalism standards"""
        article_count = len(articles)
        
        # Article count (professional stories have multiple sources)
        count_score = min(1.0, article_count / 5.0)  # 5+ articles = professional
        
        # Source diversity
        source_domains = set(a['source_domain'] for a in articles if a.get('source_domain'))
        diversity_score = min(1.0, len(source_domains) / 3.0)  # 3+ sources = diverse
        
        # Summary quality (has analysis summary)
        summary_score = 1.0 if storyline.get('analysis_summary') else 0.5
        
        # Quality scores
        quality_scores = [
            float(a.get('quality_score', 0.5))
            for a in articles
            if a.get('quality_score')
        ]
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.5
        
        # Overall standards score
        standards_score = (
            count_score * 0.3 +
            diversity_score * 0.3 +
            summary_score * 0.2 +
            avg_quality * 0.2
        )
        
        return {
            "standards_score": standards_score,
            "article_count_score": count_score,
            "source_diversity_score": diversity_score,
            "summary_score": summary_score,
            "avg_quality": avg_quality
        }
    
    def _generate_recommendations(
        self,
        overall_score: float,
        coherence: Dict,
        accuracy: Dict,
        standards: Dict
    ) -> List[str]:
        """Generate recommendations for improvement"""
        recommendations = []
        
        if overall_score < 0.7:
            recommendations.append("Overall quality is below professional standards. Consider adding more high-quality sources.")
        
        if coherence['coherence_score'] < 0.7:
            recommendations.append("Narrative coherence could be improved. Ensure articles are thematically related and chronologically ordered.")
        
        if accuracy['accuracy_score'] < 0.8:
            recommendations.append("Factual accuracy could be improved. Add more cross-source verification.")
        
        if standards['standards_score'] < 0.7:
            recommendations.append("Professional standards could be improved. Add more diverse sources and comprehensive analysis.")
        
        if coherence['source_coherence'] < 0.5:
            recommendations.append("Source diversity is low. Add articles from different sources to improve credibility.")
        
        if not recommendations:
            recommendations.append("Storyline meets professional quality standards.")
        
        return recommendations
    
    async def validate_factual_accuracy(self, storyline_id: int) -> Dict[str, Any]:
        """
        Validate factual accuracy of storyline.
        
        Args:
            storyline_id: ID of storyline to validate
            
        Returns:
            Dictionary with validation results
        """
        try:
            conn = self.get_db_connection()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Get articles
                    cur.execute(f"""
                        SELECT a.id, a.title, a.content, a.summary, a.source_domain,
                               a.quality_score
                        FROM {self.schema}.articles a
                        JOIN {self.schema}.storyline_articles sa ON a.id = sa.article_id
                        WHERE sa.storyline_id = %s
                    """, (storyline_id,))
                    
                    articles = cur.fetchall()
                    
                    if not articles:
                        return {"success": False, "error": "No articles in storyline"}
                    
                    # Assess accuracy
                    accuracy_assessment = await self._assess_factual_accuracy(articles)
                    
                    return {
                        "success": True,
                        "data": {
                            "storyline_id": storyline_id,
                            "factual_accuracy_score": accuracy_assessment['accuracy_score'],
                            "cross_source_verification": accuracy_assessment['cross_source_verification'],
                            "source_count": accuracy_assessment['source_count'],
                            "validation_status": "verified" if accuracy_assessment['accuracy_score'] >= 0.8 else "needs_review"
                        }
                    }
                    
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"Error validating factual accuracy: {e}")
            return {"success": False, "error": str(e)}
    
    async def suggest_improvements(self, storyline_id: int) -> Dict[str, Any]:
        """
        Suggest improvements to storyline.
        
        Args:
            storyline_id: ID of storyline to assess
            
        Returns:
            Dictionary with improvement suggestions
        """
        # Run full quality assessment
        assessment = await self.assess_storyline_quality(storyline_id)
        
        if not assessment.get("success"):
            return assessment
        
        data = assessment.get("data", {})
        
        return {
            "success": True,
            "data": {
                "storyline_id": storyline_id,
                "recommendations": data.get("recommendations", []),
                "quality_scores": {
                    "overall": data.get("overall_quality_score", 0.0),
                    "coherence": data.get("coherence_assessment", {}).get("coherence_score", 0.0),
                    "accuracy": data.get("accuracy_assessment", {}).get("accuracy_score", 0.0),
                    "standards": data.get("standards_assessment", {}).get("standards_score", 0.0)
                },
                "priority": "high" if data.get("overall_quality_score", 0.0) < 0.6 else "medium" if data.get("overall_quality_score", 0.0) < 0.8 else "low"
            }
        }

