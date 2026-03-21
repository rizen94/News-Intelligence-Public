#!/usr/bin/env python3
"""
Proactive Detection Service
Detects emerging storylines and predicts story developments
"""

import logging
import os
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone
from collections import Counter, defaultdict
import json

from shared.services.domain_aware_service import DomainAwareService
from shared.services.llm_service import llm_service
from shared.database.connection import get_db_connection
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class ProactiveDetectionService(DomainAwareService):
    """Service for proactive story detection and prediction"""
    
    def __init__(self, domain: str = 'politics'):
        """
        Initialize proactive detection service with domain context.
        
        Args:
            domain: Domain key (e.g., 'politics', 'finance', 'science-tech')
        """
        super().__init__(domain)
        self.min_article_count = 3  # Minimum articles to consider emerging
        self.min_confidence = 0.6   # Minimum confidence to report
        # Promote to domain storylines when cluster is strong enough (balances domains vs test-only storylines)
        self.promote_min_articles = int(os.getenv("PROACTIVE_PROMOTE_MIN_ARTICLES", "4"))
        self.promote_min_confidence = float(os.getenv("PROACTIVE_PROMOTE_MIN_CONFIDENCE", "0.55"))

    async def detect_emerging_storylines(
        self,
        hours: int = 72,
        min_articles: int = 3
    ) -> Dict[str, Any]:
        """
        Detect emerging storylines from recent articles.
        
        Args:
            hours: Look back this many hours
            min_articles: Minimum articles to form a storyline
            
        Returns:
            Dictionary with detected emerging storylines
        """
        try:
            conn = self.get_db_connection()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
                    cur.execute(
                        f"""
                        SELECT a.id, a.title, a.content, a.summary, a.published_at,
                               a.source_domain, a.quality_score
                        FROM {self.schema}.articles a
                        LEFT JOIN {self.schema}.storyline_articles sa ON a.id = sa.article_id
                        WHERE a.published_at >= %s
                          AND sa.article_id IS NULL
                        ORDER BY a.published_at DESC
                        LIMIT 1000
                        """,
                        (cutoff_time,),
                    )
                    articles = cur.fetchall()

                if len(articles) < min_articles:
                    return {
                        "success": True,
                        "data": {
                            "emerging_storylines": [],
                            "articles_analyzed": len(articles),
                            "message": f"Not enough articles (need {min_articles}, found {len(articles)})",
                        },
                    }

                clusters = await self._cluster_articles_by_similarity(articles)
                valid_clusters = [
                    cluster for cluster in clusters if len(cluster["articles"]) >= min_articles
                ]
                emerging_storylines: List[Dict[str, Any]] = []
                for cluster in valid_clusters:
                    emerging = await self._create_emerging_storyline(cluster)
                    if emerging and emerging["confidence_score"] >= self.min_confidence:
                        emerging_storylines.append(emerging)

                stored_count, promoted_count = await self._store_emerging_storylines(conn, emerging_storylines)

                return {
                    "success": True,
                    "data": {
                        "emerging_storylines": emerging_storylines,
                        "articles_analyzed": len(articles),
                        "clusters_found": len(clusters),
                        "valid_clusters": len(valid_clusters),
                        "stored_count": stored_count,
                        "promoted_to_domain_storylines": promoted_count,
                    },
                }

            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"Error detecting emerging storylines: {e}")
            return {"success": False, "error": str(e)}
    
    async def _cluster_articles_by_similarity(
        self,
        articles: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Cluster articles by keyword and entity similarity"""
        clusters = []
        processed_article_ids = set()
        
        for article in articles:
            if article['id'] in processed_article_ids:
                continue
            
            # Extract keywords from title and summary
            article_keywords = self._extract_keywords(
                article.get('title', '') + ' ' + (article.get('summary', '') or '')
            )
            
            # Find similar articles
            similar_articles = [article]
            processed_article_ids.add(article['id'])
            
            for other_article in articles:
                if other_article['id'] in processed_article_ids:
                    continue
                
                other_keywords = self._extract_keywords(
                    other_article.get('title', '') + ' ' + (other_article.get('summary', '') or '')
                )
                
                # Calculate similarity (simple keyword overlap)
                similarity = self._calculate_keyword_similarity(article_keywords, other_keywords)
                
                if similarity > 0.3:  # 30% keyword overlap
                    similar_articles.append(other_article)
                    processed_article_ids.add(other_article['id'])
            
            if len(similar_articles) >= self.min_article_count:
                clusters.append({
                    "articles": similar_articles,
                    "keywords": article_keywords,
                    "article_count": len(similar_articles)
                })
        
        return clusters
    
    def _extract_keywords(self, text: str) -> set:
        """Extract keywords from text (simplified)"""
        if not text:
            return set()
        
        # Simple keyword extraction (remove stop words)
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this',
            'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they'
        }
        
        words = text.lower().split()
        keywords = {w for w in words if len(w) > 3 and w not in stop_words}
        
        return keywords
    
    def _calculate_keyword_similarity(self, keywords1: set, keywords2: set) -> float:
        """Calculate similarity between two keyword sets"""
        if not keywords1 or not keywords2:
            return 0.0
        
        intersection = keywords1 & keywords2
        union = keywords1 | keywords2
        
        if not union:
            return 0.0
        
        return len(intersection) / len(union)
    
    async def _create_emerging_storyline(self, cluster: Dict) -> Optional[Dict[str, Any]]:
        """Create emerging storyline from article cluster"""
        articles = cluster['articles']
        
        # Generate title from most common keywords
        all_keywords = []
        for article in articles:
            all_keywords.extend(self._extract_keywords(
                article.get('title', '') + ' ' + (article.get('summary', '') or '')
            ))
        
        keyword_counts = Counter(all_keywords)
        top_keywords = [kw for kw, _ in keyword_counts.most_common(5)]
        title = ' '.join(top_keywords[:3]).title() if top_keywords else "Emerging Story"
        
        # Calculate confidence
        article_count = len(articles)
        source_domains = set(a['source_domain'] for a in articles if a.get('source_domain'))
        source_diversity = len(source_domains)
        
        # Confidence based on article count, source diversity, and recency
        confidence = min(1.0, (
            (article_count / 10.0) * 0.4 +  # More articles = higher confidence
            (source_diversity / 5.0) * 0.3 +  # More sources = higher confidence
            0.3  # Base confidence
        ))
        
        # Trend score (based on recency)
        # Ensure timezone-aware datetime comparison
        published_dates = [a['published_at'] for a in articles if a.get('published_at')]
        if published_dates:
            most_recent = max(published_dates)
            # Ensure timezone-aware
            if most_recent.tzinfo is None:
                most_recent = most_recent.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            hours_ago = (now - most_recent).total_seconds() / 3600
        else:
            hours_ago = 0
        trend_score = max(0.0, 100.0 - (hours_ago * 2))  # Decay over time
        
        article_ids = [int(a["id"]) for a in articles if a.get("id") is not None]
        return {
            "title": title,
            "description": f"Emerging storyline detected from {article_count} articles",
            "confidence_score": confidence,
            "article_count": article_count,
            "trend_score": trend_score,
            "key_entities": list(keyword_counts.keys())[:10],
            "key_keywords": top_keywords,
            "source_diversity": source_diversity,
            "first_detected_at": datetime.now(timezone.utc).isoformat(),
            "article_ids": article_ids,
        }

    def _should_promote_to_storyline(self, emerging: Dict[str, Any]) -> bool:
        """Larger / higher-confidence clusters become domain storylines (narrative shell for other pipelines)."""
        n = len(emerging.get("article_ids") or [])
        conf = float(emerging.get("confidence_score") or 0)
        if n >= max(self.promote_min_articles, 5):
            return True
        if n >= self.promote_min_articles and conf >= self.promote_min_confidence:
            return True
        return False

    async def _promote_to_domain_storyline(
        self,
        cur,
        emerging: Dict[str, Any],
        emerging_row_id: int,
    ) -> bool:
        """
        Insert domain storyline + storyline_articles; enable automation; seed story_entity_index from article_entities.
        """
        if not self._should_promote_to_storyline(emerging):
            return False

        article_ids = [int(x) for x in (emerging.get("article_ids") or [])]
        if len(article_ids) < self.min_article_count:
            return False

        # Re-check unlinked (avoid duplicate storylines if another process linked articles)
        cur.execute(
            f"""
            SELECT a.id FROM {self.schema}.articles a
            WHERE a.id = ANY(%s)
              AND NOT EXISTS (
                  SELECT 1 FROM {self.schema}.storyline_articles sa WHERE sa.article_id = a.id
              )
            """,
            (article_ids,),
        )
        unlinked = [r[0] for r in cur.fetchall()]
        if len(unlinked) < self.promote_min_articles:
            return False

        title = (emerging.get("title") or "Emerging story")[:300]
        cur.execute(
            f"""
            SELECT 1 FROM {self.schema}.storylines
            WHERE lower(trim(title)) = lower(trim(%s))
              AND created_at > NOW() - INTERVAL '14 days'
            LIMIT 1
            """,
            (title,),
        )
        if cur.fetchone():
            logger.debug("Proactive promote skipped (recent storyline with same title): %s", title)
            return False

        desc = emerging.get("description") or ""
        key_kw = emerging.get("key_keywords") or []
        key_ent = emerging.get("key_entities") or []
        settings_json = json.dumps({"min_quality_tier": 2, "source": "proactive_detection_promote"})

        try:
            cur.execute(
                f"""
                INSERT INTO {self.schema}.storylines (
                    title, description, status, processing_status,
                    total_articles, article_count,
                    automation_enabled, automation_mode, automation_frequency_hours,
                    automation_settings, search_keywords, search_entities,
                    key_entities, created_at, updated_at
                )
                VALUES (
                    %s, %s, 'active', 'pending',
                    %s, %s,
                    TRUE, 'suggest_only', 6,
                    %s::jsonb, %s, %s,
                    %s::jsonb, NOW(), NOW()
                )
                RETURNING id
                """,
                (
                    title,
                    desc[:5000] if desc else None,
                    len(unlinked),
                    len(unlinked),
                    settings_json,
                    key_kw[:40] if key_kw else [],
                    key_ent[:40] if key_ent else [],
                    json.dumps({"keywords": key_kw[:20], "entities": key_ent[:20]}),
                ),
            )
        except Exception as e:
            logger.warning("Proactive promote: rich storylines INSERT failed (%s), trying minimal", e)
            cur.execute(
                f"""
                INSERT INTO {self.schema}.storylines (title, description, status, created_at, updated_at)
                VALUES (%s, %s, 'active', NOW(), NOW())
                RETURNING id
                """,
                (title, desc[:5000] if desc else None),
            )

        row = cur.fetchone()
        if not row:
            return False
        storyline_id = int(row[0])

        rel = min(0.95, 0.55 + 0.05 * len(unlinked))
        for aid in unlinked:
            try:
                cur.execute(
                    f"""
                    INSERT INTO {self.schema}.storyline_articles (storyline_id, article_id, relevance_score)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (storyline_id, aid, rel),
                )
            except Exception as sa_err:
                logger.debug("storyline_articles insert %s/%s: %s", storyline_id, aid, sa_err)

        # Seed story_entity_index for story_continuation / automation (best-effort)
        try:
            from services.storyline_automation_service import StorylineAutomationService

            svc = StorylineAutomationService(domain=self.domain)
            for aid in unlinked:
                try:
                    svc._merge_article_entities_to_storyline(cur, storyline_id, aid)
                except Exception as merge_err:
                    logger.debug("merge_article_entities storyline %s article %s: %s", storyline_id, aid, merge_err)
        except Exception as imp_err:
            logger.debug("StorylineAutomationService unavailable for entity merge: %s", imp_err)

        try:
            cur.execute(
                """
                UPDATE public.emerging_storylines
                SET status = 'confirmed',
                    merged_into_storyline_id = %s,
                    last_updated_at = NOW(),
                    metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                WHERE id = %s
                """,
                (
                    storyline_id,
                    json.dumps({"domain_schema": self.schema, "storyline_id": storyline_id}),
                    emerging_row_id,
                ),
            )
        except Exception as up_err:
            logger.warning("Could not update emerging_storylines row %s: %s", emerging_row_id, up_err)

        logger.info(
            "Proactive detection promoted emerging id=%s → %s.storylines id=%s (%s articles)",
            emerging_row_id,
            self.schema,
            storyline_id,
            len(unlinked),
        )
        return True

    async def _store_emerging_storylines(
        self,
        conn,
        emerging_storylines: List[Dict]
    ) -> Tuple[int, int]:
        """Store emerging rows; promote strong clusters to domain storylines."""
        stored_count = 0
        promoted_count = 0

        try:
            with conn.cursor() as cur:
                for emerging in emerging_storylines:
                    try:
                        cur.execute(
                            """
                            INSERT INTO public.emerging_storylines (
                                domain_schema, title, description, confidence_score,
                                article_count, trend_score, key_entities, key_keywords,
                                source_diversity, first_detected_at, last_updated_at, status
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            RETURNING id
                            """,
                            (
                                self.schema,
                                emerging["title"],
                                emerging["description"],
                                emerging["confidence_score"],
                                emerging["article_count"],
                                emerging["trend_score"],
                                emerging["key_entities"],
                                emerging["key_keywords"],
                                emerging["source_diversity"],
                                datetime.now(timezone.utc),
                                datetime.now(timezone.utc),
                                "emerging",
                            ),
                        )
                        rid = cur.fetchone()
                        if not rid:
                            continue
                        emerging_id = int(rid[0])
                        stored_count += 1

                        if await self._promote_to_domain_storyline(cur, emerging, emerging_id):
                            promoted_count += 1
                    except Exception as e:
                        logger.warning("Error storing emerging storyline: %s", e)
                        continue

                conn.commit()
        except Exception as e:
            logger.error("Error storing emerging storylines: %s", e)
            conn.rollback()

        return stored_count, promoted_count
    
    async def identify_story_correlations(
        self,
        storyline_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Identify correlations between storylines.
        
        Args:
            storyline_id: Optional specific storyline to find correlations for
            
        Returns:
            Dictionary with correlation results
        """
        try:
            conn = self.get_db_connection()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    if storyline_id:
                        # Find correlations for specific storyline
                        cur.execute(f"""
                            SELECT id, title, description, article_count
                            FROM {self.schema}.storylines
                            WHERE id = %s
                        """, (storyline_id,))
                        
                        target_storyline = cur.fetchone()
                        if not target_storyline:
                            return {"success": False, "error": "Storyline not found"}
                        
                        # Get all other storylines
                        cur.execute(f"""
                            SELECT id, title, description, article_count
                            FROM {self.schema}.storylines
                            WHERE id != %s AND status = 'active'
                        """, (storyline_id,))
                        
                        other_storylines = cur.fetchall()
                        
                        correlations = []
                        for other in other_storylines:
                            correlation = await self._calculate_correlation(
                                conn, storyline_id, other['id']
                            )
                            if correlation and correlation['correlation_strength'] > 0.3:
                                correlations.append(correlation)
                        
                        return {
                            "success": True,
                            "data": {
                                "storyline_id": storyline_id,
                                "correlations": correlations
                            }
                        }
                    else:
                        # Find all correlations
                        cur.execute(f"""
                            SELECT id, title FROM {self.schema}.storylines
                            WHERE status = 'active'
                            ORDER BY id
                        """)
                        
                        storylines = cur.fetchall()
                        
                        all_correlations = []
                        for i, sl1 in enumerate(storylines):
                            for sl2 in storylines[i+1:]:
                                correlation = await self._calculate_correlation(
                                    conn, sl1['id'], sl2['id']
                                )
                                if correlation and correlation['correlation_strength'] > 0.3:
                                    all_correlations.append(correlation)
                        
                        return {
                            "success": True,
                            "data": {
                                "correlations": all_correlations,
                                "total_storylines": len(storylines)
                            }
                        }
                    
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"Error identifying story correlations: {e}")
            return {"success": False, "error": str(e)}
    
    async def _calculate_correlation(
        self,
        conn,
        storyline_id_1: int,
        storyline_id_2: int
    ) -> Optional[Dict[str, Any]]:
        """Calculate correlation between two storylines"""
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get articles for both storylines
                cur.execute(f"""
                    SELECT a.id, a.title, a.source_domain, a.published_at
                    FROM {self.schema}.articles a
                    JOIN {self.schema}.storyline_articles sa ON a.id = sa.article_id
                    WHERE sa.storyline_id = %s
                """, (storyline_id_1,))
                articles1 = cur.fetchall()
                
                cur.execute(f"""
                    SELECT a.id, a.title, a.source_domain, a.published_at
                    FROM {self.schema}.articles a
                    JOIN {self.schema}.storyline_articles sa ON a.id = sa.article_id
                    WHERE sa.storyline_id = %s
                """, (storyline_id_2,))
                articles2 = cur.fetchall()
                
                if not articles1 or not articles2:
                    return None
                
                # Extract keywords from titles
                keywords1 = set()
                keywords2 = set()
                
                for article in articles1:
                    keywords1.update(self._extract_keywords(article.get('title', '')))
                
                for article in articles2:
                    keywords2.update(self._extract_keywords(article.get('title', '')))
                
                # Calculate keyword overlap
                keyword_similarity = self._calculate_keyword_similarity(keywords1, keywords2)
                
                # Check temporal overlap
                dates1 = [a['published_at'] for a in articles1 if a.get('published_at')]
                dates2 = [a['published_at'] for a in articles2 if a.get('published_at')]
                
                temporal_overlap = 0
                if dates1 and dates2:
                    min1, max1 = min(dates1), max(dates1)
                    min2, max2 = min(dates2), max(dates2)
                    
                    if max(min1, min2) <= min(max1, max2):
                        overlap_days = (min(max1, max2) - max(min1, min2)).days
                        total_span = (max(max1, max2) - min(min1, min2)).days
                        temporal_overlap = overlap_days if total_span > 0 else 0
                
                # Check shared sources
                sources1 = set(a['source_domain'] for a in articles1 if a.get('source_domain'))
                sources2 = set(a['source_domain'] for a in articles2 if a.get('source_domain'))
                shared_sources = sources1 & sources2
                
                # Calculate correlation strength
                correlation_strength = (
                    keyword_similarity * 0.5 +
                    (min(1.0, temporal_overlap / 30.0)) * 0.3 +  # 30 days = full score
                    (len(shared_sources) / max(len(sources1 | sources2), 1)) * 0.2
                )
                
                # Determine correlation type
                if temporal_overlap > 7:
                    corr_type = 'temporal'
                elif keyword_similarity > 0.5:
                    corr_type = 'thematic'
                elif shared_sources:
                    corr_type = 'source'
                else:
                    corr_type = 'entity'
                
                return {
                    "storyline_id_1": storyline_id_1,
                    "storyline_id_2": storyline_id_2,
                    "correlation_type": corr_type,
                    "correlation_strength": correlation_strength,
                    "shared_keywords": list(keywords1 & keywords2)[:10],
                    "temporal_overlap_days": temporal_overlap,
                    "shared_sources": list(shared_sources)
                }
                
        except Exception as e:
            logger.error(f"Error calculating correlation: {e}")
            return None
    
    async def predict_story_developments(self, storyline_id: int) -> Dict[str, Any]:
        """
        Predict potential future developments in storyline.
        
        Args:
            storyline_id: ID of storyline to predict for
            
        Returns:
            Dictionary with predictions
        """
        try:
            conn = self.get_db_connection()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Get storyline and articles
                    cur.execute(f"""
                        SELECT id, title, description, article_count,
                               last_evolution_at, created_at
                        FROM {self.schema}.storylines
                        WHERE id = %s
                    """, (storyline_id,))
                    
                    storyline = cur.fetchone()
                    if not storyline:
                        return {"success": False, "error": "Storyline not found"}
                    
                    cur.execute(f"""
                        SELECT a.id, a.title, a.published_at, a.source_domain
                        FROM {self.schema}.articles a
                        JOIN {self.schema}.storyline_articles sa ON a.id = sa.article_id
                        WHERE sa.storyline_id = %s
                        ORDER BY a.published_at DESC
                        LIMIT 20
                    """, (storyline_id,))
                    
                    articles = cur.fetchall()
                    
                    if not articles:
                        return {"success": False, "error": "No articles in storyline"}
                    
                    # Analyze trends
                    dates = [a['published_at'] for a in articles if a.get('published_at')]
                    if dates:
                        most_recent = max(dates)
                        # Ensure timezone-aware comparison
                        if most_recent.tzinfo is None:
                            most_recent = most_recent.replace(tzinfo=timezone.utc)
                        now = datetime.now(timezone.utc)
                        hours_since_last = (now - most_recent).total_seconds() / 3600
                        
                        # Predict based on activity pattern
                        if hours_since_last < 24:
                            prediction = "High activity - expect continued coverage"
                            confidence = 0.8
                        elif hours_since_last < 72:
                            prediction = "Moderate activity - may see follow-up stories"
                            confidence = 0.6
                        else:
                            prediction = "Low recent activity - story may be concluding"
                            confidence = 0.4
                    else:
                        prediction = "Insufficient data for prediction"
                        confidence = 0.3
                    
                    # Calculate trend direction
                    if len(articles) >= 2:
                        recent_count = len([a for a in articles[:5] if a.get('published_at')])
                        older_count = len([a for a in articles[5:10] if a.get('published_at')])
                        
                        if recent_count > older_count:
                            trend = "increasing"
                        elif recent_count < older_count:
                            trend = "decreasing"
                        else:
                            trend = "stable"
                    else:
                        trend = "insufficient_data"
                    
                    return {
                        "success": True,
                        "data": {
                            "storyline_id": storyline_id,
                            "prediction": prediction,
                            "confidence": confidence,
                            "trend": trend,
                            "hours_since_last_article": hours_since_last if dates else None,
                            "article_count": len(articles),
                            "recommendations": self._generate_prediction_recommendations(
                                hours_since_last if dates else None, trend
                            )
                        }
                    }
                    
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"Error predicting story developments: {e}")
            return {"success": False, "error": str(e)}
    
    def _generate_prediction_recommendations(
        self,
        hours_since_last: Optional[float],
        trend: str
    ) -> List[str]:
        """Generate recommendations based on predictions"""
        recommendations = []
        
        if hours_since_last and hours_since_last > 72:
            recommendations.append("Story appears to be concluding. Consider archiving if no new developments.")
        
        if trend == "increasing":
            recommendations.append("Story is gaining momentum. Monitor closely for new articles.")
        
        if trend == "decreasing":
            recommendations.append("Story activity is decreasing. May be reaching conclusion.")
        
        return recommendations

