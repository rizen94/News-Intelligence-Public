#!/usr/bin/env python3
"""
Storyline Service
Manages storyline creation, evolution, and quality updates
"""

import json
import logging
from datetime import datetime
from typing import Any

from psycopg2.extras import RealDictCursor
from shared.services.domain_aware_service import DomainAwareService
from shared.services.llm_service import llm_service

from ..services.content_extraction_service import ContentExtractionService

logger = logging.getLogger(__name__)


class StorylineService(DomainAwareService):
    """Service for managing storylines with evolution and quality tracking"""

    def __init__(self, domain: str = "politics"):
        """
        Initialize storyline service with domain context.

        Args:
            domain: Domain key (e.g., 'politics', 'finance', 'science-tech')
        """
        super().__init__(domain)

    async def create_storyline_from_articles(
        self, title: str, description: str | None = None, article_ids: list[int] | None = None
    ) -> dict[str, Any]:
        """
        Create a new storyline, optionally from article collection.

        Args:
            title: Storyline title
            description: Optional description
            article_ids: Optional list of article IDs to include

        Returns:
            Dictionary with created storyline data
        """
        try:
            conn = self.get_db_connection()
            try:
                with conn.cursor() as cur:
                    # Create storyline
                    cur.execute(
                        f"""
                        INSERT INTO {self.schema}.storylines (
                            title, description, status, created_at, updated_at,
                            article_count, quality_score
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """,
                        (
                            title,
                            description or "",
                            "active",
                            datetime.now(),
                            datetime.now(),
                            0,
                            0.5,  # Default quality
                        ),
                    )

                    storyline_id = cur.fetchone()[0]

                    # Add articles if provided
                    if article_ids:
                        article_count = await self._add_articles_to_storyline(
                            conn, storyline_id, article_ids
                        )

                        # Update article count
                        cur.execute(
                            f"""
                            UPDATE {self.schema}.storylines
                            SET article_count = %s, updated_at = %s
                            WHERE id = %s
                        """,
                            (article_count, datetime.now(), storyline_id),
                        )

                        # Living-by-default: enable automation (suggest_only), 6h frequency, min_quality_tier=2
                        keywords, entities = self._extract_keywords_entities_from_articles(
                            cur, article_ids
                        )
                        automation_settings = json.dumps({"min_quality_tier": 2})
                        try:
                            cur.execute(
                                f"""
                                UPDATE {self.schema}.storylines
                                SET automation_enabled = true, automation_mode = 'suggest_only',
                                    automation_frequency_hours = 6, automation_settings = %s::jsonb,
                                    search_keywords = %s, search_entities = %s, updated_at = %s
                                WHERE id = %s
                            """,
                                (
                                    automation_settings,
                                    keywords[:30] if keywords else [],
                                    entities[:30] if entities else [],
                                    datetime.now(),
                                    storyline_id,
                                ),
                            )
                        except Exception as e:
                            logger.debug(
                                "Storyline automation defaults not applied (columns may be missing): %s",
                                e,
                            )
                    else:
                        # No initial articles: still enable automation with defaults (user can add keywords later)
                        try:
                            cur.execute(
                                f"""
                                UPDATE {self.schema}.storylines
                                SET automation_enabled = true, automation_mode = 'suggest_only',
                                    automation_frequency_hours = 6, automation_settings = '{"min_quality_tier": 2}'::jsonb,
                                    updated_at = %s
                                WHERE id = %s
                            """,
                                (datetime.now(), storyline_id),
                            )
                        except Exception as e:
                            logger.debug("Storyline automation defaults not applied: %s", e)

                    conn.commit()

                    return {
                        "success": True,
                        "data": {
                            "id": storyline_id,
                            "title": title,
                            "description": description,
                            "article_count": article_ids and len(article_ids) or 0,
                        },
                    }
            finally:
                conn.close()

        except Exception as e:
            logger.error(f"Error creating storyline: {e}")
            return {"success": False, "error": str(e)}

    def _extract_keywords_entities_from_articles(self, cur, article_ids: list[int]) -> tuple:
        """Extract search_keywords and search_entities from initial articles for automation. Returns (keywords, entities)."""
        import re

        keywords = set()
        entities = set()
        if not article_ids:
            return ([], [])
        ids_placeholders = ",".join(["%s"] * len(article_ids))
        try:
            cur.execute(
                f"""
                SELECT title FROM {self.schema}.articles WHERE id IN ({ids_placeholders})
            """,
                article_ids,
            )
            for (t,) in cur.fetchall():
                if not t:
                    continue
                words = re.findall(r"\b[A-Za-z][a-z]+|\b[A-Z]{2,}\b", t)
                for w in words:
                    if len(w) >= 3 and w.lower() not in {
                        "the",
                        "and",
                        "for",
                        "with",
                        "from",
                        "this",
                        "that",
                        "have",
                        "has",
                        "been",
                        "said",
                    }:
                        keywords.add(w.strip())
        except Exception:
            pass
        try:
            cur.execute(
                f"""
                SELECT DISTINCT entity_name FROM {self.schema}.article_entities
                WHERE article_id IN ({ids_placeholders}) AND entity_name IS NOT NULL AND LENGTH(TRIM(entity_name)) >= 2
            """,
                article_ids,
            )
            for (name,) in cur.fetchall():
                if name:
                    entities.add(name.strip()[:255])
        except Exception:
            pass
        return (list(keywords)[:30], list(entities)[:30])

    async def evolve_storyline_with_new_content(
        self,
        storyline_id: int,
        new_article_ids: list[int] | None = None,
        force_evolution: bool = False,
    ) -> dict[str, Any]:
        """
        Intelligently evolve storyline with new content.
        Extracts new information from articles and automatically updates summary and context.

        Args:
            storyline_id: ID of storyline to evolve
            new_article_ids: Optional list of new article IDs to add
            force_evolution: Force evolution even if recent

        Returns:
            Dictionary with evolution results including updated summary and context
        """
        try:
            conn = self.get_db_connection()
            content_extractor = ContentExtractionService(domain=self.domain)

            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Get storyline with current context
                    cur.execute(
                        f"""
                        SELECT id, title, description, analysis_summary,
                               article_count, last_evolution_at, evolution_count,
                               background_information, historical_context
                        FROM {self.schema}.storylines
                        WHERE id = %s
                    """,
                        (storyline_id,),
                    )

                    storyline = cur.fetchone()
                    if not storyline:
                        return {"success": False, "error": "Storyline not found"}

                    # Check if evolution needed (avoid too frequent updates)
                    if not force_evolution and storyline.get("last_evolution_at"):
                        from datetime import timezone

                        last_evo = storyline["last_evolution_at"]
                        if last_evo.tzinfo is None:
                            last_evo = last_evo.replace(tzinfo=timezone.utc)
                        now = datetime.now(timezone.utc)
                        hours_since = (now - last_evo).total_seconds() / 3600
                        if hours_since < 0.5:  # Minimum 30 minutes between evolutions
                            return {
                                "success": True,
                                "message": "Recent evolution exists, use force_evolution=true to override",
                                "last_evolution": storyline["last_evolution_at"].isoformat(),
                            }

                    # Get existing context
                    existing_summary = (
                        storyline.get("analysis_summary") or storyline.get("description") or ""
                    )
                    existing_context = {"key_facts": [], "entities": [], "dates": [], "quotes": []}

                    # Parse existing context if available
                    if storyline.get("background_information"):
                        try:
                            existing_context = json.loads(storyline.get("background_information"))
                        except:
                            pass

                    # Add new articles if provided
                    new_articles_count = 0
                    new_articles_data = []
                    if new_article_ids:
                        new_articles_count = await self._add_articles_to_storyline(
                            conn, storyline_id, new_article_ids
                        )

                        # Get the newly added articles for analysis
                        cur.execute(
                            f"""
                            SELECT a.id, a.title, a.content, a.summary, a.published_at,
                                   a.source_domain, a.sentiment_score, a.quality_score
                            FROM {self.schema}.articles a
                            WHERE a.id = ANY(%s)
                            ORDER BY a.published_at DESC
                        """,
                            (new_article_ids,),
                        )
                        new_articles_data = cur.fetchall()

                    # Get all articles for analysis
                    cur.execute(
                        f"""
                        SELECT a.id, a.title, a.content, a.summary, a.published_at,
                               a.source_domain, a.sentiment_score, a.quality_score
                        FROM {self.schema}.articles a
                        JOIN {self.schema}.storyline_articles sa ON a.id = sa.article_id
                        WHERE sa.storyline_id = %s
                        ORDER BY a.published_at ASC
                    """,
                        (storyline_id,),
                    )

                    articles = cur.fetchall()

                    if not articles:
                        return {"success": False, "error": "No articles in storyline"}

                    # Process new articles: extract information and merge context
                    updated_summary = existing_summary
                    updated_context = existing_context.copy()
                    merge_results = []

                    # If no summary exists, generate initial summary from all articles
                    if not updated_summary and articles:
                        logger.info(
                            f"Generating initial summary for storyline {storyline_id} from {len(articles)} articles"
                        )
                        initial_summary_result = await self._generate_initial_summary(
                            articles, storyline
                        )
                        if initial_summary_result.get("success"):
                            updated_summary = initial_summary_result.get("data", {}).get(
                                "summary", ""
                            )
                            # Extract context from all articles for initial setup
                            for article in articles[:10]:  # Process first 10 for initial context
                                try:
                                    extraction_result = (
                                        await content_extractor.extract_article_information(article)
                                    )
                                    if extraction_result.get("success"):
                                        extracted_info = extraction_result.get("data", {})
                                        updated_context["key_facts"].extend(
                                            extracted_info.get("key_facts", [])[:3]
                                        )
                                        updated_context["entities"].extend(
                                            extracted_info.get("entities", [])[:5]
                                        )
                                        updated_context["dates"].extend(
                                            extracted_info.get("dates", [])[:3]
                                        )
                                except Exception as e:
                                    logger.warning(
                                        f"Error extracting initial context from article {article.get('id')}: {e}"
                                    )

                    # Process new articles: extract information and merge context
                    for new_article in new_articles_data:
                        try:
                            # Extract information from new article
                            extraction_result = await content_extractor.extract_article_information(
                                new_article
                            )
                            if extraction_result.get("success"):
                                extracted_info = extraction_result.get("data", {})

                                # Identify what's new
                                new_info_result = await content_extractor.identify_new_information(
                                    extracted_info, updated_context
                                )

                                if new_info_result.get("success") and new_info_result.get(
                                    "data", {}
                                ).get("has_new_information"):
                                    new_info = new_info_result.get("data", {})

                                    # Merge new information into context
                                    merge_result = await content_extractor.merge_context(
                                        updated_summary, updated_context, new_info, new_article
                                    )

                                    if merge_result.get("success"):
                                        merge_data = merge_result.get("data", {})
                                        updated_summary = merge_data.get(
                                            "updated_summary", updated_summary
                                        )
                                        updated_context = merge_data.get(
                                            "updated_context", updated_context
                                        )
                                        merge_results.append(
                                            {
                                                "article_id": new_article.get("id"),
                                                "article_title": new_article.get("title"),
                                                "merge_notes": merge_data.get("merge_notes", {}),
                                            }
                                        )
                        except Exception as e:
                            logger.warning(
                                f"Error processing article {new_article.get('id')} for evolution: {e}"
                            )
                            continue

                    # Update quality metrics
                    quality_update = await self._update_quality_metrics(
                        conn, storyline_id, articles, storyline
                    )

                    # Update storyline with new summary and context
                    evolution_count = (storyline.get("evolution_count") or 0) + 1

                    # Store updated context as JSON
                    context_json = json.dumps(updated_context)

                    cur.execute(
                        f"""
                        UPDATE {self.schema}.storylines
                        SET analysis_summary = %s,
                            background_information = %s,
                            context_last_updated = %s,
                            last_evolution_at = %s,
                            evolution_count = %s,
                            updated_at = %s
                        WHERE id = %s
                    """,
                        (
                            updated_summary,
                            context_json,
                            datetime.now(),
                            datetime.now(),
                            evolution_count,
                            datetime.now(),
                            storyline_id,
                        ),
                    )

                    conn.commit()

                    return {
                        "success": True,
                        "data": {
                            "storyline_id": storyline_id,
                            "total_articles": len(articles),
                            "new_articles": new_articles_count,
                            "evolution_count": evolution_count,
                            "quality_update": quality_update,
                            "summary_updated": updated_summary != existing_summary,
                            "context_updated": len(merge_results) > 0,
                            "merge_results": merge_results,
                            "summary_length": len(updated_summary),
                            "context_stats": {
                                "total_facts": len(updated_context.get("key_facts", [])),
                                "total_entities": len(updated_context.get("entities", [])),
                                "total_dates": len(updated_context.get("dates", [])),
                            },
                        },
                    }

            finally:
                conn.close()

        except Exception as e:
            logger.error(f"Error evolving storyline {storyline_id}: {e}")
            return {"success": False, "error": str(e)}

    async def _generate_initial_summary(
        self, articles: list[dict], storyline: dict
    ) -> dict[str, Any]:
        """
        Generate initial comprehensive summary from articles using LLM.

        Args:
            articles: List of article dictionaries
            storyline: Storyline dictionary

        Returns:
            Dictionary with generated summary
        """
        try:
            # Build context from articles (limit to avoid token limits)
            article_texts = []
            for article in articles[:20]:  # Limit to first 20 for summary
                article_text = f"Title: {article.get('title', '')}\n"
                if article.get("summary"):
                    article_text += f"Summary: {article.get('summary', '')}\n"
                if article.get("content"):
                    # Truncate content to avoid token limits
                    content = article.get("content", "")
                    article_text += (
                        f"Content: {content[:500]}...\n"
                        if len(content) > 500
                        else f"Content: {content}\n"
                    )
                article_texts.append(article_text)

            context = "\n\n---\n\n".join(article_texts)

            # Use LLM to generate comprehensive summary
            summary_prompt = f"""
Create a comprehensive, well-structured summary of this news storyline based on the following articles.

STORYLINE TITLE: {storyline.get("title", "Untitled Storyline")}
STORYLINE DESCRIPTION: {storyline.get("description", "")}

ARTICLES ({len(articles)} total):
{context}

Create a detailed, professional summary that:
1. Provides a clear overview of the storyline
2. Identifies key events and developments in chronological order
3. Highlights important facts, figures, and claims
4. Mentions key people, organizations, and locations
5. Explains the significance and context
6. Is well-structured and easy to read
7. Is comprehensive but concise (aim for 500-1000 words)

Format the summary as a professional news analysis suitable for publication.
"""

            llm_result = await llm_service.generate_text(
                prompt=summary_prompt, task_type="content_analysis", max_tokens=2000
            )

            if llm_result.get("success"):
                summary = llm_result.get("text", "").strip()
                return {
                    "success": True,
                    "data": {"summary": summary, "articles_processed": len(articles)},
                }
            else:
                # Fallback: simple concatenation
                summary = f"{storyline.get('title', 'Storyline')}\n\n"
                summary += "\n\n".join(
                    [f"- {a.get('title', '')}: {a.get('summary', '')[:200]}" for a in articles[:10]]
                )
                return {
                    "success": True,
                    "data": {"summary": summary, "articles_processed": len(articles)},
                }

        except Exception as e:
            logger.error(f"Error generating initial summary: {e}")
            return {"success": False, "error": str(e)}

    async def _add_articles_to_storyline(
        self, conn, storyline_id: int, article_ids: list[int]
    ) -> int:
        """Add articles to storyline, returning count of actually added"""
        added_count = 0
        with conn.cursor() as cur:
            for article_id in article_ids:
                try:
                    cur.execute(
                        f"""
                        INSERT INTO {self.schema}.storyline_articles
                        (storyline_id, article_id, added_at, relevance_score)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (storyline_id, article_id) DO NOTHING
                    """,
                        (storyline_id, article_id, datetime.now(), 0.7),
                    )

                    if cur.rowcount > 0:
                        added_count += 1
                except Exception as e:
                    logger.warning(f"Error adding article {article_id}: {e}")
                    continue

        return added_count

    async def _update_quality_metrics(
        self, conn, storyline_id: int, articles: list[dict], storyline: dict
    ) -> dict[str, Any]:
        """Update quality metrics for storyline"""
        try:
            # Calculate basic metrics
            article_count = len(articles)
            source_domains = set(a["source_domain"] for a in articles if a.get("source_domain"))
            source_diversity = len(source_domains)

            # Calculate average quality
            quality_scores = [
                float(a.get("quality_score", 0.5)) for a in articles if a.get("quality_score")
            ]
            avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.5

            # Calculate coherence (simplified - based on source diversity and article count)
            coherence = min(1.0, (source_diversity / max(article_count, 1)) * 2.0)
            coherence = max(0.3, coherence)  # Minimum coherence

            # Calculate completeness (based on article count and time span)
            if articles:
                dates = [a["published_at"] for a in articles if a.get("published_at")]
                if dates:
                    (max(dates) - min(dates)).days if len(dates) > 1 else 0
                    min(1.0, article_count / 10.0)  # 10 articles = complete
                else:
                    min(1.0, article_count / 10.0)
            else:
                pass

            # Update storyline
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE {self.schema}.storylines
                    SET article_count = %s,
                        quality_score = %s,
                        updated_at = %s
                    WHERE id = %s
                """,
                    (article_count, avg_quality, datetime.now(), storyline_id),
                )

            return {
                "quality_score": avg_quality,
                "source_diversity": source_diversity,
                "article_count": article_count,
            }

        except Exception as e:
            logger.error(f"Error updating quality metrics: {e}")
            return {}

    async def update_storyline_quality(self, storyline_id: int) -> dict[str, Any]:
        """
        Update storyline quality metrics.

        Args:
            storyline_id: ID of storyline to update

        Returns:
            Dictionary with updated quality metrics
        """
        try:
            conn = self.get_db_connection()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Get storyline and articles
                    cur.execute(
                        f"""
                        SELECT id, title, description, article_count
                        FROM {self.schema}.storylines
                        WHERE id = %s
                    """,
                        (storyline_id,),
                    )

                    storyline = cur.fetchone()
                    if not storyline:
                        return {"success": False, "error": "Storyline not found"}

                    cur.execute(
                        f"""
                        SELECT a.id, a.title, a.content, a.summary, a.published_at,
                               a.source_domain, a.sentiment_score, a.quality_score
                        FROM {self.schema}.articles a
                        JOIN {self.schema}.storyline_articles sa ON a.id = sa.article_id
                        WHERE sa.storyline_id = %s
                    """,
                        (storyline_id,),
                    )

                    articles = cur.fetchall()

                    # Update quality metrics
                    quality_update = await self._update_quality_metrics(
                        conn, storyline_id, articles, storyline
                    )

                    conn.commit()

                    return {"success": True, "data": quality_update}

            finally:
                conn.close()

        except Exception as e:
            logger.error(f"Error updating storyline quality: {e}")
            return {"success": False, "error": str(e)}

    async def archive_storyline(self, storyline_id: int) -> dict[str, Any]:
        """
        Archive a storyline (mark as completed/archived).

        Args:
            storyline_id: ID of storyline to archive

        Returns:
            Dictionary with archive result
        """
        try:
            conn = self.get_db_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        UPDATE {self.schema}.storylines
                        SET status = 'archived',
                            updated_at = %s
                        WHERE id = %s
                    """,
                        (datetime.now(), storyline_id),
                    )

                    if cur.rowcount == 0:
                        return {"success": False, "error": "Storyline not found"}

                    conn.commit()

                    return {"success": True, "message": "Storyline archived successfully"}

            finally:
                conn.close()

        except Exception as e:
            logger.error(f"Error archiving storyline: {e}")
            return {"success": False, "error": str(e)}

    async def get_storylines(
        self, limit: int = 20, offset: int = 0, status: str | None = None
    ) -> dict[str, Any]:
        """
        Get all storylines with pagination.

        Args:
            limit: Maximum number of storylines to return
            offset: Number of storylines to skip
            status: Optional status filter ('active', 'archived', 'draft')

        Returns:
            Dictionary with storylines and pagination info
        """
        try:
            conn = self.get_db_connection()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Build WHERE clause
                    where_clause = ""
                    params = []
                    if status:
                        where_clause = "WHERE s.status = %s"
                        params.append(status)

                    # Get total count
                    count_query = f"SELECT COUNT(*) FROM {self.schema}.storylines s {where_clause}"
                    cur.execute(count_query, params)
                    total_count = cur.fetchone()[0] if cur.rowcount > 0 else 0

                    # Get storylines with article counts
                    query = f"""
                        SELECT s.id, s.title, s.description, s.status, s.created_at, s.updated_at,
                               s.analysis_summary, s.quality_score,
                               COALESCE(COUNT(sa.article_id), 0) as article_count
                        FROM {self.schema}.storylines s
                        LEFT JOIN {self.schema}.storyline_articles sa ON s.id = sa.storyline_id
                        {where_clause}
                        GROUP BY s.id, s.title, s.description, s.status, s.created_at, s.updated_at,
                                 s.analysis_summary, s.quality_score
                        ORDER BY s.updated_at DESC
                        LIMIT %s OFFSET %s
                    """
                    params.extend([limit, offset])
                    cur.execute(query, params)

                    storylines = []
                    for row in cur.fetchall():
                        storylines.append(
                            {
                                "id": row["id"],
                                "title": row["title"],
                                "description": row.get("description", ""),
                                "status": row["status"],
                                "created_at": row["created_at"].isoformat()
                                if row["created_at"]
                                else None,
                                "updated_at": row["updated_at"].isoformat()
                                if row["updated_at"]
                                else None,
                                "analysis_summary": row.get("analysis_summary"),
                                "quality_score": float(row["quality_score"])
                                if row.get("quality_score")
                                else None,
                                "article_count": row["article_count"] or 0,
                            }
                        )

                    return {
                        "success": True,
                        "data": {
                            "storylines": storylines,
                            "total": total_count,
                            "limit": limit,
                            "offset": offset,
                        },
                    }

            finally:
                conn.close()

        except Exception as e:
            logger.error(f"Error getting storylines: {e}")
            return {"success": False, "error": str(e), "data": {"storylines": [], "total": 0}}

    async def get_storyline_by_id(self, storyline_id: int) -> dict[str, Any]:
        """
        Get a single storyline by ID.

        Args:
            storyline_id: ID of storyline to retrieve

        Returns:
            Dictionary with storyline data
        """
        try:
            conn = self.get_db_connection()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        f"""
                        SELECT s.id, s.title, s.description, s.status, s.created_at, s.updated_at,
                               s.analysis_summary, s.quality_score, s.background_information,
                               s.last_evolution_at, s.evolution_count,
                               COALESCE(COUNT(sa.article_id), 0) as article_count
                        FROM {self.schema}.storylines s
                        LEFT JOIN {self.schema}.storyline_articles sa ON s.id = sa.storyline_id
                        WHERE s.id = %s
                        GROUP BY s.id, s.title, s.description, s.status, s.created_at, s.updated_at,
                                 s.analysis_summary, s.quality_score, s.background_information,
                                 s.last_evolution_at, s.evolution_count
                    """,
                        (storyline_id,),
                    )

                    row = cur.fetchone()
                    if not row:
                        return {"success": False, "error": "Storyline not found"}

                    return {
                        "success": True,
                        "data": {
                            "id": row["id"],
                            "title": row["title"],
                            "description": row.get("description", ""),
                            "status": row["status"],
                            "created_at": row["created_at"].isoformat()
                            if row["created_at"]
                            else None,
                            "updated_at": row["updated_at"].isoformat()
                            if row["updated_at"]
                            else None,
                            "analysis_summary": row.get("analysis_summary"),
                            "quality_score": float(row["quality_score"])
                            if row.get("quality_score")
                            else None,
                            "background_information": row.get("background_information"),
                            "last_evolution_at": row["last_evolution_at"].isoformat()
                            if row.get("last_evolution_at")
                            else None,
                            "evolution_count": row.get("evolution_count", 0),
                            "article_count": row["article_count"] or 0,
                        },
                    }

            finally:
                conn.close()

        except Exception as e:
            logger.error(f"Error getting storyline {storyline_id}: {e}")
            return {"success": False, "error": str(e)}

    async def get_storyline_articles(self, storyline_id: int) -> dict[str, Any]:
        """
        Get all articles in a storyline.

        Args:
            storyline_id: ID of storyline

        Returns:
            Dictionary with storyline info and articles
        """
        try:
            conn = self.get_db_connection()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Get storyline info
                    cur.execute(
                        f"""
                        SELECT s.id, s.title, s.description, s.analysis_summary,
                               COALESCE(COUNT(sa.article_id), 0) as article_count
                        FROM {self.schema}.storylines s
                        LEFT JOIN {self.schema}.storyline_articles sa ON s.id = sa.storyline_id
                        WHERE s.id = %s
                        GROUP BY s.id, s.title, s.description, s.analysis_summary
                    """,
                        (storyline_id,),
                    )

                    storyline_row = cur.fetchone()
                    if not storyline_row:
                        return {"success": False, "error": "Storyline not found"}

                    # Get articles
                    cur.execute(
                        f"""
                        SELECT a.id, a.title, a.content, a.url, a.published_at, a.source_domain,
                               a.summary, a.sentiment_score, a.quality_score, a.entities,
                               sa.relevance_score, sa.added_at
                        FROM {self.schema}.storyline_articles sa
                        JOIN {self.schema}.articles a ON sa.article_id = a.id
                        WHERE sa.storyline_id = %s
                        ORDER BY sa.added_at DESC
                    """,
                        (storyline_id,),
                    )

                    articles = []
                    for row in cur.fetchall():
                        articles.append(
                            {
                                "id": row["id"],
                                "title": row["title"],
                                "content": row.get("content"),
                                "url": row.get("url"),
                                "published_at": row["published_at"].isoformat()
                                if row["published_at"]
                                else None,
                                "source_domain": row.get("source_domain"),
                                "summary": row.get("summary"),
                                "sentiment_score": float(row["sentiment_score"])
                                if row.get("sentiment_score")
                                else None,
                                "quality_score": float(row["quality_score"])
                                if row.get("quality_score")
                                else None,
                                "entities": row.get("entities", []),
                                "relevance_score": float(row["relevance_score"])
                                if row.get("relevance_score")
                                else None,
                                "added_at": row["added_at"].isoformat()
                                if row["added_at"]
                                else None,
                            }
                        )

                    return {
                        "success": True,
                        "data": {
                            "storyline": {
                                "id": storyline_row["id"],
                                "title": storyline_row["title"],
                                "description": storyline_row.get("description", ""),
                                "analysis_summary": storyline_row.get("analysis_summary"),
                                "article_count": storyline_row["article_count"] or 0,
                            },
                            "articles": articles,
                        },
                    }

            finally:
                conn.close()

        except Exception as e:
            logger.error(f"Error getting storyline articles: {e}")
            return {"success": False, "error": str(e)}

    async def add_article_to_storyline(
        self, storyline_id: int, article_id: int, relevance_score: float | None = None
    ) -> dict[str, Any]:
        """
        Add an article to a storyline.

        Args:
            storyline_id: ID of storyline
            article_id: ID of article to add
            relevance_score: Optional relevance score (0.0-1.0)

        Returns:
            Dictionary with result
        """
        try:
            conn = self.get_db_connection()
            try:
                with conn.cursor() as cur:
                    # Check if already exists
                    cur.execute(
                        f"""
                        SELECT id FROM {self.schema}.storyline_articles
                        WHERE storyline_id = %s AND article_id = %s
                    """,
                        (storyline_id, article_id),
                    )

                    if cur.fetchone():
                        return {"success": False, "error": "Article already in storyline"}

                    # Add article
                    cur.execute(
                        f"""
                        INSERT INTO {self.schema}.storyline_articles
                        (storyline_id, article_id, added_at, relevance_score)
                        VALUES (%s, %s, %s, %s)
                    """,
                        (storyline_id, article_id, datetime.now(), relevance_score or 0.7),
                    )

                    # Update article count
                    cur.execute(
                        f"""
                        UPDATE {self.schema}.storylines
                        SET article_count = (
                            SELECT COUNT(*) FROM {self.schema}.storyline_articles
                            WHERE storyline_id = %s
                        ),
                        updated_at = %s
                        WHERE id = %s
                    """,
                        (storyline_id, datetime.now(), storyline_id),
                    )

                    conn.commit()

                    return {
                        "success": True,
                        "message": "Article added to storyline successfully",
                        "data": {"storyline_id": storyline_id, "article_id": article_id},
                    }

            finally:
                conn.close()

        except Exception as e:
            logger.error(f"Error adding article to storyline: {e}")
            return {"success": False, "error": str(e)}

    async def remove_article_from_storyline(
        self, storyline_id: int, article_id: int
    ) -> dict[str, Any]:
        """
        Remove an article from a storyline.

        Args:
            storyline_id: ID of storyline
            article_id: ID of article to remove

        Returns:
            Dictionary with result
        """
        try:
            conn = self.get_db_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        DELETE FROM {self.schema}.storyline_articles
                        WHERE storyline_id = %s AND article_id = %s
                    """,
                        (storyline_id, article_id),
                    )

                    if cur.rowcount == 0:
                        return {"success": False, "error": "Article not found in storyline"}

                    # Update article count
                    cur.execute(
                        f"""
                        UPDATE {self.schema}.storylines
                        SET article_count = (
                            SELECT COUNT(*) FROM {self.schema}.storyline_articles
                            WHERE storyline_id = %s
                        ),
                        updated_at = %s
                        WHERE id = %s
                    """,
                        (storyline_id, datetime.now(), storyline_id),
                    )

                    conn.commit()

                    return {
                        "success": True,
                        "message": "Article removed from storyline successfully",
                    }

            finally:
                conn.close()

        except Exception as e:
            logger.error(f"Error removing article from storyline: {e}")
            return {"success": False, "error": str(e)}

    async def delete_storyline(self, storyline_id: int) -> dict[str, Any]:
        """
        Delete a storyline and all associated data.

        Args:
            storyline_id: ID of storyline to delete

        Returns:
            Dictionary with result
        """
        try:
            conn = self.get_db_connection()
            try:
                with conn.cursor() as cur:
                    # Get storyline title for response
                    cur.execute(
                        f"""
                        SELECT title FROM {self.schema}.storylines WHERE id = %s
                    """,
                        (storyline_id,),
                    )
                    row = cur.fetchone()
                    if not row:
                        return {"success": False, "error": "Storyline not found"}

                    title = row[0]

                    # Delete storyline (cascade will handle related records)
                    cur.execute(
                        f"""
                        DELETE FROM {self.schema}.storylines WHERE id = %s
                    """,
                        (storyline_id,),
                    )

                    conn.commit()

                    return {"success": True, "message": f"Storyline '{title}' deleted successfully"}

            finally:
                conn.close()

        except Exception as e:
            logger.error(f"Error deleting storyline: {e}")
            return {"success": False, "error": str(e)}

    async def generate_storyline_summary(self, storyline_id: int) -> dict[str, Any]:
        """
        Generate AI-powered summary for storyline using full article content.

        Args:
            storyline_id: ID of storyline

        Returns:
            Dictionary with generated summary
        """
        try:
            # Get storyline articles
            storyline_data = await self.get_storyline_articles(storyline_id)

            if not storyline_data.get("success"):
                return storyline_data

            articles = storyline_data.get("data", {}).get("articles", [])
            storyline = storyline_data.get("data", {}).get("storyline", {})

            if not articles:
                return {"success": False, "error": "No articles in storyline"}

            # Build context from articles
            articles_context = []
            for article in articles:
                content = article.get("content", "")
                summary = article.get("summary", "")
                title = article.get("title", "")

                article_text = (
                    content if content and len(content) > 50 else (summary if summary else title)
                )

                articles_context.append(
                    {
                        "title": title,
                        "content": article_text,
                        "source": article.get("source_domain", "Unknown"),
                        "published_at": article.get("published_at", ""),
                    }
                )

            # Create prompt for LLM
            context_text = f"Storyline: {storyline.get('title', 'Untitled')}\n\n"
            context_text += f"Total Articles: {len(articles)}\n\n"
            context_text += "Article Contents:\n\n"

            for i, article in enumerate(articles_context, 1):
                context_text += f"Article {i} - {article['title']} ({article['source']}):\n"
                context_text += f"{article['content'][:1000]}\n\n"  # Limit content length

            prompt = f"""
Analyze the following news articles and create a comprehensive storyline summary.

{context_text}

Please provide a professional journalistic summary that:
1. Identifies the main themes and developments
2. Highlights key facts and developments
3. Shows the progression of events over time
4. Identifies important stakeholders and their roles
5. Provides context and implications

CRITICAL FORMATTING REQUIREMENTS:
- Use double line breaks between paragraphs
- Use ## for section headers
- Use bullet points (-) for lists
- Use **bold** for important names and organizations

Your response MUST follow this structure:

## Executive Summary

[Write 2-3 paragraphs here]

## Key Developments

- Event 1 with date and details
- Event 2 with date and details
- Event 3 with date and details

## Key Players and Stakeholders

- **Person Name** - Role and significance
- **Organization Name** - What they do

## Analysis and Context

[Write analysis paragraphs here]

## Current Status and Outlook

[Write current status and future outlook here]

REMEMBER: Use double line breaks between all sections and paragraphs!
"""

            # Use LLM to generate summary
            llm_result = await llm_service.generate_text(
                prompt=prompt, task_type="content_analysis", max_tokens=2000, model="llama3.1:8b"
            )

            if llm_result.get("success"):
                summary = llm_result.get("text", "").strip()
                formatted_summary = self._format_ai_summary(summary)
                master_summary = (
                    f"Storyline: {storyline.get('title', 'Untitled')}\n\n{formatted_summary}"
                )
            else:
                # Fallback summary
                master_summary = self._create_fallback_summary(
                    storyline.get("title", "Untitled"), articles_context
                )

            # Update storyline with summary
            conn = self.get_db_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        UPDATE {self.schema}.storylines
                        SET analysis_summary = %s,
                            updated_at = %s
                        WHERE id = %s
                    """,
                        (master_summary, datetime.now(), storyline_id),
                    )
                    conn.commit()
            finally:
                conn.close()

            return {
                "success": True,
                "data": {
                    "storyline_id": storyline_id,
                    "summary": master_summary,
                    "article_count": len(articles),
                },
            }

        except Exception as e:
            logger.error(f"Error generating storyline summary: {e}")
            return {"success": False, "error": str(e)}

    def _create_fallback_summary(
        self, storyline_title: str, articles_context: list[dict[str, Any]]
    ) -> str:
        """Create a structured fallback summary when AI is not available"""
        master_summary = f"Storyline: {storyline_title}\n\n"
        master_summary += f"Total Articles: {len(articles_context)}\n\n"
        master_summary += "## Key Developments\n\n"

        for i, article in enumerate(articles_context[:5], 1):
            content = (
                article["content"]
                if article["content"] and len(article["content"]) > 50
                else article["title"]
            )
            master_summary += f"{i}. {content[:200]}\n"

        if len(articles_context) > 5:
            master_summary += f"\n... and {len(articles_context) - 5} more articles\n"

        # Add source diversity
        sources = list(set(article["source"] for article in articles_context))
        master_summary += f"\n## Sources\n\n{', '.join(sources[:5])}"
        if len(sources) > 5:
            master_summary += f" and {len(sources) - 5} more"

        return master_summary

    def _format_ai_summary(self, text: str) -> str:
        """Format AI-generated summary with proper structure"""
        if not text:
            return text

        # Remove "Storyline:" prefix if exists
        if text.startswith("Storyline:"):
            text = text.split("\n", 2)[-1] if "\n" in text else text

        # Ensure proper section headers
        text = text.replace("###", "##")

        # Ensure double line breaks between sections
        paragraphs = text.split("\n\n")
        formatted = []

        for para in paragraphs:
            para = para.strip()
            if para:
                formatted.append(para)
                formatted.append("")  # Add blank line

        return "\n".join(formatted).strip()
