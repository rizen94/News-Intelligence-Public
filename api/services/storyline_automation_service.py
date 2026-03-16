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
            "min_quality_tier": 2,          # 1=best, 4=worst; filter out worse
            "clickbait_threshold": 0.6,    # Reject if clickbait_probability > this
            "min_fact_density": 0.15,      # Reject if fact_density < this (when present)
            "require_named_sources": False,
        }
    
    def _apply_quality_gates(
        self,
        articles: List[Dict[str, Any]],
        settings: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Filter articles by quality gates and compute quality_score for scoring.
        Returns (filtered_articles, filter_stats).
        """
        min_tier = settings.get("min_quality_tier", 2)
        clickbait_threshold = settings.get("clickbait_threshold", 0.6)
        min_fact_density = settings.get("min_fact_density", 0.15)
        require_named_sources = settings.get("require_named_sources", False)
        stats = {"filtered_tier": 0, "filtered_clickbait": 0, "filtered_fact_density": 0, "filtered_sources": 0, "passed": 0}
        filtered = []
        for a in articles:
            # quality_tier: 1=best, 4=worst; reject if tier > min_quality_tier (worse)
            tier = a.get("quality_tier")
            if tier is not None and tier > min_tier:
                stats["filtered_tier"] += 1
                continue
            clickbait = a.get("clickbait_probability")
            if clickbait is not None and clickbait > clickbait_threshold:
                stats["filtered_clickbait"] += 1
                continue
            fact_density = a.get("fact_density")
            if fact_density is not None and fact_density < min_fact_density:
                stats["filtered_fact_density"] += 1
                continue
            if require_named_sources and not a.get("has_named_sources", True):
                stats["filtered_sources"] += 1
                continue
            # Compute 0-1 quality score for blending: tier 1=1.0, 2=0.75, 3=0.5, 4=0.25; blend with fact_density and (1-clickbait)
            q = a.get("quality_score")
            if q is None or q == 0.5:
                if tier is not None:
                    q = max(0.25, 1.0 - (tier - 1) * 0.25)
                else:
                    q = 0.5
                if clickbait is not None:
                    q = q * (1.0 - clickbait)
                if fact_density is not None:
                    q = (q + fact_density) / 2
            a["quality_score"] = round(min(1.0, max(0.0, q)), 4)
            filtered.append(a)
            stats["passed"] += 1
        return filtered, stats
    
    def _final_score(self, article: Dict[str, Any]) -> float:
        """final_score = relevance*0.7 + quality*0.3"""
        rel = article.get("relevance_score", 0.6)
        qual = article.get("quality_score", 0.5)
        return round(rel * 0.7 + qual * 0.3, 4)
    
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
                    
                    # Fetch key_entities and quality columns if they exist
                    key_entities = None
                    min_quality_tier = 2
                    try:
                        cur.execute(f"""
                            SELECT key_entities, min_quality_tier FROM {self.schema}.storylines WHERE id = %s
                        """, (storyline_id,))
                        row = cur.fetchone()
                        if row and row[0]:
                            key_entities = row[0]
                        if row and len(row) > 1 and row[1] is not None:
                            min_quality_tier = int(row[1])
                    except Exception:
                        try:
                            cur.execute(f"""
                                SELECT key_entities FROM {self.schema}.storylines WHERE id = %s
                            """, (storyline_id,))
                            row = cur.fetchone()
                            if row and row[0]:
                                key_entities = row[0]
                        except Exception:
                            pass
                    
                    # Parse automation settings
                    # Handle both dict (from psycopg2 JSONB) and string (legacy)
                    if isinstance(automation_settings_json, dict):
                        automation_settings = automation_settings_json
                    elif isinstance(automation_settings_json, str):
                        automation_settings = json.loads(automation_settings_json) if automation_settings_json else {}
                    else:
                        automation_settings = {}
                    settings = {**self.default_settings, **automation_settings}
                    if "min_quality_tier" not in automation_settings:
                        settings["min_quality_tier"] = min_quality_tier
                    
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
                    
                    # Collect storyline objects (entities, keywords) for high-probability matching
                    storyline_entities = self._collect_storyline_entities(
                        conn, cur, storyline_id, title,
                        key_entities, search_entities, search_keywords
                    )
                    
                    max_results = max_results or settings.get("max_articles_per_run", 20)
                    
                    # Entity-first: articles that mention storyline entities = high probability
                    discovered_articles = []
                    if storyline_entities:
                        entity_articles = await self._entity_based_article_search(
                            conn, storyline_entities, search_exclude_keywords or [],
                            settings, list(existing_article_ids), max_results
                        )
                        if entity_articles:
                            discovered_articles = entity_articles
                            logger.info(f"Entity-first search found {len(entity_articles)} articles matching storyline objects")
                    
                    # Fallback/supplement: RAG or keyword search if entity search yielded little
                    if len(discovered_articles) < max_results // 2:
                        search_query = self._build_search_query(
                            title, description, analysis_summary,
                            search_keywords, search_entities
                        )
                        rag_articles = await self._rag_discover_articles(
                            search_query,
                            search_exclude_keywords or [],
                            settings,
                            list(existing_article_ids),
                            max_results
                        )
                        # Merge: prefer entity matches, add RAG results not already found
                        existing_ids = {a["id"] for a in discovered_articles}
                        for a in rag_articles:
                            if a["id"] not in existing_ids:
                                discovered_articles.append(a)
                                existing_ids.add(a["id"])
                        # Re-sort by relevance, recency
                        discovered_articles.sort(
                            key=lambda x: (x.get("relevance_score", 0), x.get("published_at") or ""),
                            reverse=True
                        )
                        discovered_articles = discovered_articles[:max_results]
                    
                    # Quality gates: filter by min_quality_tier, clickbait, fact_density
                    discovered_articles, filter_stats = self._apply_quality_gates(discovered_articles, settings)
                    for a in discovered_articles:
                        a["combined_score"] = self._final_score(a)
                    
                    # Store suggestions or auto-add based on mode
                    if automation_mode == 'auto_approve':
                        added_count = await self._auto_add_articles(
                            conn, storyline_id, discovered_articles, settings
                        )
                    else:
                        suggestions_count = await self._store_suggestions(
                            conn, storyline_id, discovered_articles, settings, search_query
                        )
                    
                    # Update last automation run and quality_metrics (when column exists)
                    now = datetime.now()
                    quality_metrics = {
                        "last_run": now.isoformat(),
                        "filter_stats": filter_stats,
                        "articles_passed": len(discovered_articles),
                    }
                    if discovered_articles:
                        tiers = [a.get("quality_tier") for a in discovered_articles if a.get("quality_tier") is not None]
                        fds = [a.get("fact_density") for a in discovered_articles if a.get("fact_density") is not None]
                        if tiers:
                            quality_metrics["avg_quality_tier"] = round(sum(tiers) / len(tiers), 2)
                        if fds:
                            quality_metrics["avg_fact_density"] = round(sum(fds) / len(fds), 4)
                    try:
                        cur.execute(f"""
                            UPDATE {self.schema}.storylines 
                            SET last_automation_run = %s, quality_metrics = quality_metrics || %s::jsonb
                            WHERE id = %s
                        """, (now, json.dumps(quality_metrics), storyline_id))
                    except Exception:
                        cur.execute(f"""
                            UPDATE {self.schema}.storylines 
                            SET last_automation_run = %s
                            WHERE id = %s
                        """, (now, storyline_id))
                    conn.commit()
                        
                    if automation_mode == 'auto_approve':
                        return {
                            "success": True,
                            "mode": "auto_approve",
                            "articles_found": len(discovered_articles),
                            "articles_added": added_count,
                            "articles": discovered_articles[:added_count],
                            "quality_filter_stats": filter_stats,
                        }
                    return {
                        "success": True,
                        "mode": automation_mode or "manual",
                        "articles_found": len(discovered_articles),
                        "articles_suggested": suggestions_count,
                        "articles": discovered_articles,
                        "quality_filter_stats": filter_stats,
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
    
    def _collect_storyline_entities(
        self,
        conn,
        cur,
        storyline_id: int,
        title: str,
        key_entities: Any,
        search_entities: Optional[List[str]],
        search_keywords: Optional[List[str]]
    ) -> List[str]:
        """
        Collect all entity/keyword strings to search for.
        Sources: story_entity_index, key_entities JSONB, search_entities, search_keywords, title words.
        """
        entities = set()
        
        # 1. story_entity_index (entities extracted from chronology events)
        for sei_schema in [self.schema, "public"]:
            try:
                cur.execute(f"""
                    SELECT entity_name FROM {sei_schema}.story_entity_index
                    WHERE storyline_id = %s AND LENGTH(TRIM(entity_name)) >= 2
                    ORDER BY is_core_entity DESC, mention_count DESC
                    LIMIT 25
                """, (storyline_id,))
                for (name,) in cur.fetchall():
                    if name and len(name) >= 2:
                        entities.add(name.strip())
                break
            except Exception as e:
                logger.debug(f"story_entity_index not available in {sei_schema}: {e}")
        
        # 2. key_entities (JSONB: dict like {"Entity": count} or list)
        if key_entities:
            if isinstance(key_entities, dict):
                for k in list(key_entities.keys())[:20]:
                    if k and isinstance(k, str) and len(k) >= 2:
                        entities.add(k.strip())
            elif isinstance(key_entities, list):
                for item in key_entities[:20]:
                    name = item if isinstance(item, str) else (item.get("name") or item.get("text") if isinstance(item, dict) else None)
                    if name and len(str(name)) >= 2:
                        entities.add(str(name).strip())
        
        # 3. search_entities (explicit)
        if search_entities:
            for e in search_entities[:15]:
                if e and len(str(e)) >= 2:
                    entities.add(str(e).strip())
        
        # 4. search_keywords
        if search_keywords:
            for kw in search_keywords[:15]:
                if kw and len(str(kw)) >= 2:
                    entities.add(str(kw).strip())
        
        # 5. Significant words from title (3+ chars, capitalized or all-caps)
        if title:
            import re
            words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b|\b[A-Z]{2,}\b', title)
            for w in words[:5]:
                if len(w) >= 3:
                    entities.add(w.strip())
        
        # Filter very short and common terms
        skip = {"the", "and", "for", "with", "from", "this", "that", "have", "has", "been", "said"}
        return [e for e in sorted(entities) if e.lower() not in skip and len(e) >= 2][:30]
    
    async def _entity_based_article_search(
        self,
        conn,
        entities: List[str],
        exclude_keywords: List[str],
        settings: Dict[str, Any],
        existing_article_ids: List[int],
        max_results: int
    ) -> List[Dict[str, Any]]:
        """
        Fast search: articles whose title or content mentions any storyline entity.
        Rank by: entity matches in title (highest), then total matches, then recency.
        """
        if not entities:
            return []
        
        try:
            with conn.cursor() as cur:
                cur.execute(f"SET search_path TO {self.schema}, public")
                date_threshold = datetime.now() - timedelta(days=settings.get("date_range_days", 30))
                exclude_ids = list(existing_article_ids) if existing_article_ids else [-1]
                
                entity_conditions = []
                params = [date_threshold]
                
                for entity in entities[:20]:
                    pattern = f"%{entity}%"
                    entity_conditions.append(
                        "(a.title ILIKE %s OR COALESCE(a.content, '') ILIKE %s OR COALESCE(a.summary, '') ILIKE %s)"
                    )
                    params.extend([pattern, pattern, pattern])
                
                entity_clause = " OR ".join(entity_conditions)
                exclude_clause = ""
                if exclude_keywords:
                    for kw in exclude_keywords[:5]:
                        kw_pattern = f"%{kw}%"
                        exclude_clause += " AND (a.title NOT ILIKE %s AND COALESCE(a.content, '') NOT ILIKE %s)"
                        params.extend([kw_pattern, kw_pattern])
                
                exclude_sql = f"AND a.id NOT IN ({','.join(['%s'] * len(exclude_ids))})" if exclude_ids else ""
                params_with_exclude = params + exclude_ids
                
                # Include quality columns when present (migration 164)
                try:
                    cur.execute(f"""
                        SELECT a.id, a.title, a.summary, a.content, a.url, a.source_domain, a.published_at,
                               a.quality_score, a.quality_tier, a.clickbait_probability, a.fact_density
                        FROM {self.schema}.articles a
                        WHERE a.published_at >= %s
                          {exclude_sql}
                          AND ({entity_clause})
                          {exclude_clause}
                        ORDER BY a.published_at DESC, a.quality_score DESC
                        LIMIT %s
                    """, params_with_exclude + [max_results])
                except Exception:
                    cur.execute(f"""
                        SELECT a.id, a.title, a.summary, a.content, a.url, a.source_domain, a.published_at, a.quality_score
                        FROM {self.schema}.articles a
                        WHERE a.published_at >= %s
                          {exclude_sql}
                          AND ({entity_clause})
                          {exclude_clause}
                        ORDER BY a.published_at DESC, a.quality_score DESC
                        LIMIT %s
                    """, params_with_exclude + [max_results])
                rows = cur.fetchall()
                
                articles = []
                for row in rows:
                    art_id, art_title, summary, content, url, domain, pub_at = row[0], row[1], row[2], row[3], row[4], row[5], row[6]
                    quality = row[7] if len(row) > 7 else None
                    quality_tier = row[8] if len(row) > 8 else None
                    clickbait_probability = row[9] if len(row) > 9 else None
                    fact_density = row[10] if len(row) > 10 else None
                    title_lower = (art_title or "").lower()
                    content_lower = (content or "")[:2000].lower() if content else ""
                    matched_names = [e for e in entities[:15] if e.lower() in title_lower or e.lower() in content_lower]
                    match_count = len(matched_names)
                    relevance = min(0.95, 0.7 + match_count * 0.05)
                    articles.append({
                        "id": art_id,
                        "title": art_title,
                        "summary": summary,
                        "content": (content or "")[:500] if content else None,
                        "url": url,
                        "source_domain": domain,
                        "published_at": pub_at.isoformat() if pub_at else None,
                        "quality_score": float(quality) if quality else 0.5,
                        "quality_tier": int(quality_tier) if quality_tier is not None else None,
                        "clickbait_probability": float(clickbait_probability) if clickbait_probability is not None else None,
                        "fact_density": float(fact_density) if fact_density is not None else None,
                        "relevance_score": relevance,
                        "matched_entities": matched_names,
                        "matched_keywords": matched_names,
                    })
                
                return articles
                
        except Exception as e:
            logger.error(f"Entity-based search failed: {e}")
            return []
    
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
                from services.rag import RAGService
                rag_service = RAGService()
                # Use retrieval module for advanced retrieval
                # Note: EnhancedRAGRetrieval functionality is now in RAGService.retrieval
                
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
                
                try:
                    cur.execute(f"""
                        SELECT a.id, a.title, a.summary, a.content, a.url,
                               a.source_domain, a.published_at, a.quality_score,
                               a.quality_tier, a.clickbait_probability, a.fact_density
                        FROM {self.schema}.articles a
                        WHERE {' AND '.join(where_parts)}
                        ORDER BY a.published_at DESC, a.quality_score DESC
                        LIMIT %s
                    """, params + [max_results])
                except Exception:
                    cur.execute(f"""
                        SELECT a.id, a.title, a.summary, a.content, a.url,
                               a.source_domain, a.published_at, a.quality_score
                        FROM {self.schema}.articles a
                        WHERE {' AND '.join(where_parts)}
                        ORDER BY a.published_at DESC, a.quality_score DESC
                        LIMIT %s
                    """, params + [max_results])
                rows = cur.fetchall()
                
                articles = []
                for row in rows:
                    a = {
                        "id": row[0],
                        "title": row[1],
                        "summary": row[2],
                        "content": row[3][:500] if row[3] else None,
                        "url": row[4],
                        "source_domain": row[5],
                        "published_at": row[6].isoformat() if row[6] else None,
                        "quality_score": float(row[7]) if row[7] else 0.5,
                        "relevance_score": 0.6,
                    }
                    if len(row) > 8:
                        a["quality_tier"] = int(row[8]) if row[8] is not None else None
                    if len(row) > 9:
                        a["clickbait_probability"] = float(row[9]) if row[9] is not None else None
                    if len(row) > 10:
                        a["fact_density"] = float(row[10]) if row[10] is not None else None
                    articles.append(a)
                
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
                    relevance = article.get("relevance_score", 0.6)
                    quality = article.get("quality_score", 0.5)
                    semantic = article.get("semantic_score", 0.6)
                    # Use quality-gate combined_score (relevance*0.7 + quality*0.3) when set
                    combined = article.get("combined_score")
                    if combined is None:
                        combined = (relevance * 0.4 + quality * 0.3 + semantic * 0.3)
                    
                    # Log scores for debugging
                    logger.debug(f"Article {article.get('id')}: relevance={relevance:.2f}, quality={quality:.2f}, semantic={semantic:.2f}, combined={combined:.2f}")
                    
                    # Check individual thresholds AND combined score
                    if (combined >= min_score and 
                        quality >= min_quality and 
                        semantic >= min_semantic):
                        matched = article.get("matched_entities") or article.get("matched_keywords") or []
                        if isinstance(matched, int):
                            matched = []
                        reasoning = f"Matched search query: {search_query[:200]}"
                        if matched:
                            reasoning = f"Matched storyline entities: {', '.join(str(m) for m in matched[:8])}"
                        
                        # Note: storyline_article_suggestions is in public schema (shared across domains)
                        cur.execute("""
                            INSERT INTO public.storyline_article_suggestions (
                                storyline_id, article_id, relevance_score, semantic_score,
                                keyword_score, quality_score, combined_score, reasoning,
                                matched_keywords, matched_entities, status, suggested_at, expires_at
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                            ) ON CONFLICT (storyline_id, article_id) DO UPDATE SET
                                relevance_score = EXCLUDED.relevance_score,
                                combined_score = EXCLUDED.combined_score,
                                reasoning = EXCLUDED.reasoning,
                                matched_keywords = EXCLUDED.matched_keywords,
                                matched_entities = EXCLUDED.matched_entities,
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
                            matched,
                            matched,
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
    
    def _merge_article_entities_to_storyline(self, cur, storyline_id: int, article_id: int) -> None:
        """Merge article_entities into story_entity_index when article added to storyline."""
        type_map = {"person": "person", "organization": "organization", "subject": "other", "recurring_event": "event"}
        for sei_schema in [self.schema, "public"]:
            try:
                cur.execute(f"""
                    SELECT entity_name, entity_type FROM {self.schema}.article_entities
                    WHERE article_id = %s AND entity_name IS NOT NULL
                """, (article_id,))
                rows = cur.fetchall()
                for name, ae_type in rows:
                    if not name or len(name.strip()) < 2:
                        continue
                    sei_type = type_map.get(ae_type, "other")
                    try:
                        cur.execute(f"""
                            INSERT INTO {sei_schema}.story_entity_index
                            (storyline_id, entity_name, entity_type, mention_count, last_seen_at)
                            VALUES (%s, %s, %s, 1, NOW())
                            ON CONFLICT (storyline_id, entity_name, entity_type) DO UPDATE SET
                                mention_count = story_entity_index.mention_count + 1,
                                last_seen_at = NOW()
                        """, (storyline_id, name.strip()[:255], sei_type))
                    except Exception as e:
                        logger.debug(f"story_entity_index merge skip: {e}")
                break  # success
            except Exception as e:
                logger.debug(f"article_entities/story_entity_index merge: {e}")
                continue

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
                    combined = article.get("combined_score")
                    if combined is None:
                        relevance = article.get("relevance_score", 0.6)
                        quality = article.get("quality_score", 0.5)
                        combined = (relevance * 0.7 + quality * 0.3)
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
                                self._merge_article_entities_to_storyline(cur, storyline_id, article.get("id"))
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

