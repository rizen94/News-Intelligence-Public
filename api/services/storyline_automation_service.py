#!/usr/bin/env python3
"""
Storyline Automation Service
Provides RAG-enhanced article discovery with configurable automation controls
"""

import logging
import psycopg2
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import json
import asyncio

from shared.services.llm_service import llm_service
from shared.database.connection import get_db_connection
from shared.services.domain_aware_service import DomainAwareService

logger = logging.getLogger(__name__)


class StorylineAutomationService(DomainAwareService):
    """Service for RAG-enhanced article discovery and automation"""
    
    def __init__(self, domain: str = 'politics'):
        """
        Initialize storyline automation service with domain context.
        
        Args:
            domain: Domain key (e.g., 'politics', 'finance', 'science-tech')
        """
        super().__init__(domain)
        self.default_settings = {
            "min_relevance_score": 0.6,  # Minimum relevance to suggest
            "min_quality_score": 0.5,      # Minimum article quality
            "min_semantic_score": 0.55,   # Minimum semantic similarity
            "max_articles_per_run": 20,    # Max articles to suggest per run
            "date_range_days": 30,         # Look back this many days
            "source_diversity": True,       # Prefer diverse sources
            "exclude_duplicates": True,     # Skip duplicate content
            "use_rag_expansion": True,     # Use RAG query expansion
            "rerank_results": True,        # Re-rank with multiple signals
        }
    
    async def discover_articles_for_storyline(
        self,
        storyline_id: int,
        max_results: Optional[int] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Discover relevant articles for a storyline using RAG-enhanced search
        
        Args:
            storyline_id: ID of the storyline
            max_results: Maximum number of articles to return
            force_refresh: Force new discovery even if recent run exists
            
        Returns:
            Dictionary with discovered articles and metadata
        """
        try:
            conn = get_db_connection()
            if not conn:
                raise Exception("Database connection failed")
            
            try:
                with conn.cursor() as cur:
                    # Get storyline and automation settings from domain schema
                    cur.execute(f"""
                        SELECT s.id, s.title, s.description, s.analysis_summary,
                               s.automation_enabled, s.automation_mode, s.automation_settings,
                               s.search_keywords, s.search_entities, s.search_exclude_keywords,
                               s.article_count, s.last_automation_run, s.automation_frequency_hours
                        FROM {self.schema}.storylines s
                        WHERE s.id = %s
                    """, (storyline_id,))
                    
                    storyline = cur.fetchone()
                    if not storyline:
                        raise Exception(f"Storyline {storyline_id} not found")
                    
                    (sl_id, title, description, analysis_summary, automation_enabled,
                     automation_mode, automation_settings_json, search_keywords, search_entities,
                     search_exclude_keywords, article_count, last_automation_run, 
                     automation_frequency_hours) = storyline
                    
                    # Parse automation settings
                    # Handle both dict (from psycopg2 JSONB) and string (legacy)
                    if isinstance(automation_settings_json, dict):
                        automation_settings = automation_settings_json
                    elif isinstance(automation_settings_json, str):
                        automation_settings = json.loads(automation_settings_json) if automation_settings_json else {}
                    else:
                        automation_settings = {}
                    settings = {**self.default_settings, **automation_settings}
                    
                    # Check if we should run (frequency check)
                    if not force_refresh and last_automation_run:
                        hours_since_run = (datetime.now() - last_automation_run).total_seconds() / 3600
                        if hours_since_run < (automation_frequency_hours or 24):
                            return {
                                "success": True,
                                "message": "Recent discovery run exists, use force_refresh=true to run again",
                                "last_run": last_automation_run.isoformat(),
                                "articles": []
                            }
                    
                    # Get existing article IDs to exclude from domain schema
                    cur.execute(f"""
                        SELECT article_id FROM {self.schema}.storyline_articles WHERE storyline_id = %s
                    """, (storyline_id,))
                    existing_article_ids = {row[0] for row in cur.fetchall()}
                    
                    # Build search query from storyline context
                    search_query = self._build_search_query(
                        title, description, analysis_summary,
                        search_keywords, search_entities
                    )
                    
                    # Use RAG-enhanced retrieval (if available)
                    # For now, use enhanced keyword/semantic search
                    discovered_articles = await self._rag_discover_articles(
                        search_query,
                        search_exclude_keywords or [],
                        settings,
                        list(existing_article_ids),
                        max_results or settings.get("max_articles_per_run", 20)
                    )
                    
                    # Store suggestions or auto-add based on mode
                    if automation_mode == 'auto_approve':
                        added_count = await self._auto_add_articles(
                            conn, storyline_id, discovered_articles, settings
                        )
                        return {
                            "success": True,
                            "mode": "auto_approve",
                            "articles_found": len(discovered_articles),
                            "articles_added": added_count,
                            "articles": discovered_articles[:added_count]
                        }
                    else:
                        # Store in suggestions queue
                        suggestions_count = await self._store_suggestions(
                            conn, storyline_id, discovered_articles, settings, search_query
                        )
                        
                        # Update last automation run in domain schema
                        cur.execute(f"""
                            UPDATE {self.schema}.storylines 
                            SET last_automation_run = %s
                            WHERE id = %s
                        """, (datetime.now(), storyline_id))
                        conn.commit()
                        
                        return {
                            "success": True,
                            "mode": automation_mode or "manual",
                            "articles_found": len(discovered_articles),
                            "articles_suggested": suggestions_count,
                            "articles": discovered_articles
                        }
                    
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"Error discovering articles for storyline {storyline_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "articles": []
            }
    
    def _build_search_query(
        self,
        title: str,
        description: Optional[str],
        analysis_summary: Optional[str],
        keywords: Optional[List[str]],
        entities: Optional[List[str]]
    ) -> str:
        """Build search query from storyline context"""
        query_parts = []
        
        # Use title as primary query
        if title:
            query_parts.append(title)
        
        # Add explicit keywords
        if keywords:
            query_parts.extend(keywords)
        
        # Add entities
        if entities:
            query_parts.extend(entities)
        
        # Use description/summary for context expansion
        if description:
            query_parts.append(description[:200])  # First 200 chars
        
        # Combine into search query
        query = " ".join(query_parts[:10])  # Limit to 10 terms
        
        return query
    
    async def _rag_discover_articles(
        self,
        query: str,
        exclude_keywords: List[str],
        settings: Dict[str, Any],
        existing_article_ids: List[int],
        max_results: int
    ) -> List[Dict[str, Any]]:
        """Use RAG-enhanced retrieval to find articles"""
        try:
            # Try to import enhanced RAG retrieval if available
            try:
                from services.enhanced_rag_retrieval import EnhancedRAGRetrieval
                rag_service = EnhancedRAGRetrieval()
                
                # Build filters
                filters = {
                    "date_range_days": settings.get("date_range_days", 30),
                    "min_quality": settings.get("min_quality_score", 0.5),
                    "exclude_article_ids": existing_article_ids,
                }
                
                # Retrieve articles
                articles = await rag_service.retrieve_relevant_articles(
                    query=query,
                    max_results=max_results * 2,  # Get more for filtering
                    use_semantic=True,
                    use_hybrid=True,
                    expand_query=settings.get("use_rag_expansion", True),
                    rerank=settings.get("rerank_results", True),
                    filters=filters
                )
                
                # Filter out excluded keywords
                if exclude_keywords:
                    filtered_articles = []
                    for article in articles:
                        article_text = f"{article.get('title', '')} {article.get('content', '')}".lower()
                        if not any(kw.lower() in article_text for kw in exclude_keywords):
                            filtered_articles.append(article)
                    articles = filtered_articles
                
                # Limit to max_results
                return articles[:max_results]
                
            except ImportError:
                # Fallback to database keyword search
                logger.warning("Enhanced RAG retrieval not available, using keyword search")
                return await self._keyword_search_fallback(
                    query, exclude_keywords, settings, existing_article_ids, max_results
                )
                
        except Exception as e:
            logger.error(f"Error in RAG article discovery: {e}")
            return await self._keyword_search_fallback(
                query, exclude_keywords, settings, existing_article_ids, max_results
            )
    
    async def _keyword_search_fallback(
        self,
        query: str,
        exclude_keywords: List[str],
        settings: Dict[str, Any],
        existing_article_ids: List[int],
        max_results: int
    ) -> List[Dict[str, Any]]:
        """Fallback keyword search when RAG is unavailable"""
        conn = get_db_connection()
        if not conn:
            return []
        
        try:
            with conn.cursor() as cur:
                # Build search terms
                query_terms = query.split()[:10]  # Limit terms
                
                # Build WHERE clause
                date_threshold = datetime.now() - timedelta(days=settings.get("date_range_days", 30))
                exclude_ids = existing_article_ids or [-1]  # Use -1 if empty list
                
                where_parts = [
                    "a.published_at >= %s",
                    f"a.id NOT IN ({','.join(['%s'] * len(exclude_ids))})",
                ]
                params = [date_threshold] + exclude_ids
                
                # Build keyword search conditions
                keyword_conditions = []
                for term in query_terms:
                    keyword_conditions.append("(a.title ILIKE %s OR a.content ILIKE %s OR a.summary ILIKE %s)")
                    term_pattern = f"%{term}%"
                    params.extend([term_pattern, term_pattern, term_pattern])
                
                if keyword_conditions:
                    where_parts.append(f"({' OR '.join(keyword_conditions)})")
                
                # Exclude keywords
                if exclude_keywords:
                    exclude_conditions = []
                    for kw in exclude_keywords:
                        exclude_conditions.append("(a.title NOT ILIKE %s AND a.content NOT ILIKE %s)")
                        kw_pattern = f"%{kw}%"
                        params.extend([kw_pattern, kw_pattern])
                    where_parts.append(f"({' AND '.join(exclude_conditions)})")
                
                query_sql = f"""
                    SELECT a.id, a.title, a.summary, a.content, a.url, 
                           a.source_domain, a.published_at, a.quality_score
                    FROM {self.schema}.articles a
                    WHERE {' AND '.join(where_parts)}
                    ORDER BY a.published_at DESC, a.quality_score DESC
                    LIMIT %s
                """
                params.append(max_results)
                
                cur.execute(query_sql, params)
                rows = cur.fetchall()
                
                articles = []
                for row in rows:
                    articles.append({
                        "id": row[0],
                        "title": row[1],
                        "summary": row[2],
                        "content": row[3][:500] if row[3] else None,
                        "url": row[4],
                        "source_domain": row[5],
                        "published_at": row[6].isoformat() if row[6] else None,
                        "quality_score": float(row[7]) if row[7] else 0.5,
                        "relevance_score": 0.6,  # Default relevance for keyword match
                    })
                
                return articles
                
        finally:
            conn.close()
    
    async def _store_suggestions(
        self,
        conn,
        storyline_id: int,
        articles: List[Dict[str, Any]],
        settings: Dict[str, Any],
        search_query: str
    ) -> int:
        """Store article suggestions in review queue"""
        try:
            with conn.cursor() as cur:
                stored_count = 0
                min_score = settings.get("min_relevance_score", 0.6)
                min_quality = settings.get("min_quality_score", 0.5)
                min_semantic = settings.get("min_semantic_score", 0.55)
                
                logger.info(f"Storing suggestions with thresholds: min_score={min_score}, min_quality={min_quality}, min_semantic={min_semantic}")
                
                for article in articles:
                    # Calculate combined score
                    relevance = article.get("relevance_score", 0.6)
                    quality = article.get("quality_score", 0.5)
                    semantic = article.get("semantic_score", 0.6)
                    
                    combined = (relevance * 0.4 + quality * 0.3 + semantic * 0.3)
                    
                    # Log scores for debugging
                    logger.debug(f"Article {article.get('id')}: relevance={relevance:.2f}, quality={quality:.2f}, semantic={semantic:.2f}, combined={combined:.2f}")
                    
                    # Check individual thresholds AND combined score
                    if (combined >= min_score and 
                        quality >= min_quality and 
                        semantic >= min_semantic):
                        reasoning = f"Matched search query: {search_query[:200]}"
                        
                        # Note: storyline_article_suggestions is in public schema (shared across domains)
                        cur.execute("""
                            INSERT INTO public.storyline_article_suggestions (
                                storyline_id, article_id, relevance_score, semantic_score,
                                keyword_score, quality_score, combined_score, reasoning,
                                status, suggested_at, expires_at
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                            ) ON CONFLICT (storyline_id, article_id) DO UPDATE SET
                                relevance_score = EXCLUDED.relevance_score,
                                combined_score = EXCLUDED.combined_score,
                                reasoning = EXCLUDED.reasoning,
                                suggested_at = EXCLUDED.suggested_at,
                                status = 'pending'
                            WHERE public.storyline_article_suggestions.status != 'added'
                        """, (
                            storyline_id,
                            article.get("id"),
                            relevance,
                            semantic,
                            relevance,  # keyword_score same as relevance for now
                            quality,
                            combined,
                            reasoning,
                            "pending",
                            datetime.now(),
                            datetime.now() + timedelta(days=7)  # Expire in 7 days
                        ))
                        
                        if cur.rowcount > 0:
                            stored_count += 1
                
                conn.commit()
                return stored_count
                
        except Exception as e:
            logger.error(f"Error storing suggestions: {e}")
            conn.rollback()
            return 0
    
    async def _auto_add_articles(
        self,
        conn,
        storyline_id: int,
        articles: List[Dict[str, Any]],
        settings: Dict[str, Any]
    ) -> int:
        """Auto-add articles that meet threshold criteria"""
        try:
            added_count = 0
            min_score = settings.get("min_relevance_score", 0.7)  # Higher threshold for auto-add
            
            with conn.cursor() as cur:
                for article in articles:
                    relevance = article.get("relevance_score", 0.6)
                    quality = article.get("quality_score", 0.5)
                    combined = (relevance * 0.6 + quality * 0.4)
                    
                    if combined >= min_score:
                        # Auto-add article to domain schema
                        try:
                            cur.execute(f"""
                                INSERT INTO {self.schema}.storyline_articles 
                                (storyline_id, article_id, added_at, relevance_score)
                                VALUES (%s, %s, %s, %s)
                                ON CONFLICT (storyline_id, article_id) DO NOTHING
                            """, (storyline_id, article.get("id"), datetime.now(), relevance))
                            
                            if cur.rowcount > 0:
                                added_count += 1
                        except Exception as e:
                            logger.warning(f"Error adding article {article.get('id')}: {e}")
                            continue
                
                # Update storyline article count
                cur.execute(f"""
                    UPDATE {self.schema}.storylines
                    SET article_count = (
                        SELECT COUNT(*) FROM {self.schema}.storyline_articles WHERE storyline_id = %s
                    ),
                    updated_at = %s
                    WHERE id = %s
                """, (storyline_id, datetime.now(), storyline_id))
                
                conn.commit()
            
            return added_count
            
        except Exception as e:
            logger.error(f"Error auto-adding articles: {e}")
            conn.rollback()
            return 0

