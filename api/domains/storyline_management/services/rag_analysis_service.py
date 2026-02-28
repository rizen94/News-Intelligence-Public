#!/usr/bin/env python3
"""
RAG Analysis Service
Provides RAG-enhanced storyline analysis with context retrieval
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


class RAGAnalysisService(DomainAwareService):
    """Service for RAG-enhanced storyline analysis"""
    
    def __init__(self, domain: str = 'politics'):
        """
        Initialize RAG analysis service with domain context.
        
        Args:
            domain: Domain key (e.g., 'politics', 'finance', 'science-tech')
        """
        super().__init__(domain)
    
    async def perform_comprehensive_analysis(self, storyline_id: int) -> Dict[str, Any]:
        """
        Perform comprehensive RAG analysis of storyline.
        
        Args:
            storyline_id: ID of storyline to analyze
            
        Returns:
            Dictionary with comprehensive analysis results
        """
        try:
            conn = self.get_db_connection()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Get storyline
                    cur.execute(f"""
                        SELECT id, title, description, analysis_summary,
                               article_count, created_at
                        FROM {self.schema}.storylines
                        WHERE id = %s
                    """, (storyline_id,))
                    
                    storyline = cur.fetchone()
                    if not storyline:
                        return {"success": False, "error": "Storyline not found"}
                    
                    # Get articles
                    cur.execute(f"""
                        SELECT a.id, a.title, a.content, a.summary, a.published_at,
                               a.source_domain, a.url, a.sentiment_score
                        FROM {self.schema}.articles a
                        JOIN {self.schema}.storyline_articles sa ON a.id = sa.article_id
                        WHERE sa.storyline_id = %s
                        ORDER BY a.published_at ASC
                    """, (storyline_id,))
                    
                    articles = cur.fetchall()
                    
                    if not articles:
                        return {"success": False, "error": "No articles in storyline"}
                    
                    # Build comprehensive context
                    context = await self._build_comprehensive_context(
                        storyline, articles
                    )
                    
                    # Retrieve historical context (if available)
                    historical_context = await self._retrieve_historical_context(
                        conn, storyline, articles
                    )
                    
                    # Generate analysis using LLM
                    analysis_prompt = self._build_analysis_prompt(
                        context, historical_context
                    )
                    
                    analysis_result = await llm_service.generate_storyline_analysis(
                        analysis_prompt
                    )
                    
                    if analysis_result.get("success"):
                        # Extract insights
                        insights = await self._extract_insights(
                            analysis_result.get("analysis", ""), storyline_id
                        )
                        
                        # Update storyline with analysis
                        cur.execute(f"""
                            UPDATE {self.schema}.storylines
                            SET analysis_summary = %s,
                                updated_at = %s
                            WHERE id = %s
                        """, (
                            analysis_result.get("analysis", ""),
                            datetime.now(),
                            storyline_id
                        ))
                        
                        conn.commit()
                        
                        return {
                            "success": True,
                            "data": {
                                "storyline_id": storyline_id,
                                "analysis": analysis_result.get("analysis", ""),
                                "insights": insights,
                                "articles_analyzed": len(articles),
                                "context_retrieved": historical_context is not None
                            }
                        }
                    else:
                        return {
                            "success": False,
                            "error": analysis_result.get("error", "Analysis failed")
                        }
                    
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"Error performing comprehensive analysis: {e}")
            return {"success": False, "error": str(e)}
    
    async def _build_comprehensive_context(
        self,
        storyline: Dict,
        articles: List[Dict]
    ) -> str:
        """Build comprehensive context from storyline and articles"""
        context_parts = [
            f"Storyline: {storyline.get('title', '')}",
            f"Description: {storyline.get('description', '') or 'No description'}",
            f"\nArticles ({len(articles)} total):"
        ]
        
        for i, article in enumerate(articles, 1):
            context_parts.append(f"\n{i}. {article.get('title', 'No title')}")
            context_parts.append(f"   Source: {article.get('source_domain', 'Unknown')}")
            context_parts.append(f"   Published: {article.get('published_at', 'Unknown')}")
            if article.get('summary'):
                context_parts.append(f"   Summary: {article.get('summary', '')[:200]}")
            elif article.get('content'):
                context_parts.append(f"   Content: {article.get('content', '')[:200]}...")
        
        return "\n".join(context_parts)
    
    async def _retrieve_historical_context(
        self,
        conn,
        storyline: Dict,
        articles: List[Dict]
    ) -> Optional[str]:
        """Retrieve historical context from related storylines"""
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get related storylines (by keywords or entities)
                storyline_title = storyline.get('title', '').lower()
                title_words = set(word for word in storyline_title.split() if len(word) > 3)
                
                if not title_words:
                    return None
                
                # Find storylines with similar keywords
                cur.execute(f"""
                    SELECT id, title, description, analysis_summary
                    FROM {self.schema}.storylines
                    WHERE id != %s 
                      AND status = 'active'
                      AND (
                        LOWER(title) LIKE ANY(ARRAY[%s])
                        OR LOWER(description) LIKE ANY(ARRAY[%s])
                      )
                    LIMIT 5
                """, (
                    storyline.get('id'),
                    [f'%{word}%' for word in list(title_words)[:3]],
                    [f'%{word}%' for word in list(title_words)[:3]]
                ))
                
                related = cur.fetchall()
                
                if related:
                    context_parts = ["\nRelated Storylines:"]
                    for rel in related:
                        context_parts.append(f"- {rel.get('title', '')}")
                        if rel.get('analysis_summary'):
                            context_parts.append(f"  {rel.get('analysis_summary', '')[:150]}...")
                    
                    return "\n".join(context_parts)
                
                return None
                
        except Exception as e:
            logger.warning(f"Error retrieving historical context: {e}")
            return None
    
    def _build_analysis_prompt(
        self,
        context: str,
        historical_context: Optional[str]
    ) -> str:
        """Build analysis prompt for LLM"""
        prompt = f"""
Analyze the following storyline and provide a comprehensive analysis:

{context}

{f'Historical Context:{historical_context}' if historical_context else ''}

Please provide:
1. A comprehensive summary of the storyline
2. Key events and developments
3. Important entities and their roles
4. Temporal patterns and trends
5. Implications and potential future developments
6. Source diversity and credibility assessment

Format your response as a well-structured analysis suitable for professional journalism.
"""
        return prompt
    
    async def _extract_insights(
        self,
        analysis: str,
        storyline_id: int
    ) -> List[Dict[str, Any]]:
        """Extract insights from analysis (simplified)"""
        # For now, return basic insights
        # In future, use LLM to extract structured insights
        insights = []
        
        # Simple pattern detection
        if "trend" in analysis.lower() or "increasing" in analysis.lower():
            insights.append({
                "type": "trend",
                "title": "Trending Story",
                "description": "Story shows increasing activity",
                "confidence_score": 0.7
            })
        
        if "important" in analysis.lower() or "significant" in analysis.lower():
            insights.append({
                "type": "pattern",
                "title": "Significant Development",
                "description": "Story contains significant developments",
                "confidence_score": 0.6
            })
        
        return insights
    
    async def generate_storyline_report(
        self,
        storyline_id: int,
        report_type: str = "comprehensive"
    ) -> Dict[str, Any]:
        """
        Generate comprehensive storyline report.
        
        Args:
            storyline_id: ID of storyline
            report_type: Type of report (comprehensive, executive, summary)
            
        Returns:
            Dictionary with report data
        """
        # Perform comprehensive analysis first
        analysis = await self.perform_comprehensive_analysis(storyline_id)
        
        if not analysis.get("success"):
            return analysis
        
        # Get additional data for report
        conn = self.get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"""
                    SELECT id, title, description, article_count,
                           quality_score, created_at, updated_at
                    FROM {self.schema}.storylines
                    WHERE id = %s
                """, (storyline_id,))
                
                storyline = cur.fetchone()
                
                cur.execute(f"""
                    SELECT COUNT(DISTINCT a.source_domain) as source_count
                    FROM {self.schema}.articles a
                    JOIN {self.schema}.storyline_articles sa ON a.id = sa.article_id
                    WHERE sa.storyline_id = %s
                """, (storyline_id,))
                
                source_result = cur.fetchone()
                source_count = source_result['source_count'] if source_result else 0
                
                return {
                    "success": True,
                    "data": {
                        "storyline_id": storyline_id,
                        "report_type": report_type,
                        "title": storyline.get('title', ''),
                        "description": storyline.get('description', ''),
                        "analysis": analysis.get("data", {}).get("analysis", ""),
                        "key_points": self._extract_key_points(analysis.get("data", {}).get("analysis", "")),
                        "article_count": storyline.get('article_count', 0),
                        "source_count": source_count,
                        "quality_score": storyline.get('quality_score', 0.0),
                        "coherence_score": 0.0,  # Calculated on demand, not stored
                        "generated_at": datetime.now().isoformat()
                    }
                }
        finally:
            conn.close()
    
    def _extract_key_points(self, analysis: str) -> List[str]:
        """Extract key points from analysis (simplified)"""
        # Simple extraction - split by sentences and take important ones
        sentences = analysis.split('.')
        key_points = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 50 and any(word in sentence.lower() for word in ['important', 'key', 'significant', 'major', 'critical']):
                key_points.append(sentence)
                if len(key_points) >= 5:
                    break
        
        return key_points[:5]
    
    async def find_storyline_correlations(self, storyline_id: int) -> Dict[str, Any]:
        """
        Find correlations with other storylines.
        
        Args:
            storyline_id: ID of storyline to find correlations for
            
        Returns:
            Dictionary with correlation results
        """
        # Use ProactiveDetectionService for correlations
        from .proactive_detection_service import ProactiveDetectionService
        
        detection_service = ProactiveDetectionService(self.domain)
        return await detection_service.identify_story_correlations(storyline_id)

