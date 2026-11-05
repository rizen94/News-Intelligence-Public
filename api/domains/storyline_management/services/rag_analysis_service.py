#!/usr/bin/env python3
"""
RAG Analysis Service
Provides RAG-enhanced storyline analysis with context retrieval
"""

import asyncio
import json
import logging
import os
from datetime import datetime as dt, datetime
from typing import Any, Optional

from psycopg2.extras import RealDictCursor
from config.settings import MODELS
from shared.domain_registry import resolve_domain_schema
from shared.services.domain_aware_service import DomainAwareService, validate_domain
from shared.services.llm_service import llm_service

logger = logging.getLogger(__name__)


class RAGAnalysisService(DomainAwareService):
    """Service for RAG-enhanced storyline analysis"""

    def __init__(self, domain: str = "politics"):
        """
        Initialize RAG analysis service with domain context.

        Args:
            domain: Domain key (e.g., 'politics', 'finance', 'science-tech')
        """
        super().__init__(domain)

    async def perform_comprehensive_analysis(self, storyline_id: int) -> dict[str, Any]:
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
                    cur.execute(
                        f"""
                        SELECT id, title, description, analysis_summary,
                               article_count, created_at
                        FROM {self.schema}.storylines
                        WHERE id = %s
                    """,
                        (storyline_id,),
                    )

                    storyline = cur.fetchone()
                    if not storyline:
                        return {"success": False, "error": "Storyline not found"}

                    # Get articles
                    cur.execute(
                        f"""
                        SELECT a.id, a.title, a.content, a.summary, a.published_at,
                               a.source_domain, a.url, a.sentiment_score
                        FROM {self.schema}.articles a
                        JOIN {self.schema}.storyline_articles sa ON a.id = sa.article_id
                        WHERE sa.storyline_id = %s
                          AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                        ORDER BY a.published_at ASC
                    """,
                        (storyline_id,),
                    )

                    articles = cur.fetchall()

                    if not articles:
                        return {"success": False, "error": "No articles in storyline"}

                    # Build comprehensive context
                    context = await self._build_comprehensive_context(storyline, articles)

                    # Retrieve historical context (if available)
                    historical_context = await self._retrieve_historical_context(
                        conn, storyline, articles
                    )

                    # Generate analysis using LLM
                    analysis_prompt = self._build_analysis_prompt(context, historical_context)

                    analysis_result = await llm_service.generate_storyline_analysis(analysis_prompt)

                    if analysis_result.get("success"):
                        # Extract insights
                        insights = await self._extract_insights(
                            analysis_result.get("analysis", ""), storyline_id
                        )

                        # Update storyline with analysis
                        cur.execute(
                            f"""
                            UPDATE {self.schema}.storylines
                            SET analysis_summary = %s,
                                updated_at = %s
                            WHERE id = %s
                        """,
                            (analysis_result.get("analysis", ""), datetime.now(), storyline_id),
                        )

                        conn.commit()

                        return {
                            "success": True,
                            "data": {
                                "storyline_id": storyline_id,
                                "analysis": analysis_result.get("analysis", ""),
                                "insights": insights,
                                "articles_analyzed": len(articles),
                                "context_retrieved": historical_context is not None,
                            },
                        }
                    else:
                        return {
                            "success": False,
                            "error": analysis_result.get("error", "Analysis failed"),
                        }

            finally:
                conn.close()

        except Exception as e:
            logger.error(f"Error performing comprehensive analysis: {e}")
            return {"success": False, "error": str(e)}

    async def _build_comprehensive_context(self, storyline: dict, articles: list[dict]) -> str:
        """Build comprehensive context from storyline and articles"""
        context_parts = [
            f"Storyline: {storyline.get('title', '')}",
            f"Description: {storyline.get('description', '') or 'No description'}",
            f"\nArticles ({len(articles)} total):",
        ]

        for i, article in enumerate(articles, 1):
            context_parts.append(f"\n{i}. {article.get('title', 'No title')}")
            context_parts.append(f"   Source: {article.get('source_domain', 'Unknown')}")
            context_parts.append(f"   Published: {article.get('published_at', 'Unknown')}")
            if article.get("summary"):
                context_parts.append(f"   Summary: {article.get('summary', '')[:200]}")
            elif article.get("content"):
                context_parts.append(f"   Content: {article.get('content', '')[:200]}...")

        return "\n".join(context_parts)

    async def _retrieve_historical_context(
        self, conn, storyline: dict, articles: list[dict]
    ) -> str | None:
        """Durable storyline memory (facts + spine); falls back to related-storyline keyword match."""
        storyline_id = storyline.get("id")
        if storyline_id:
            try:
                from services.storyline_historical_context_service import (
                    build_storyline_historical_context,
                    render_historical_context_for_llm,
                )

                ctx = build_storyline_historical_context(
                    self.domain, int(storyline_id), conn=conn
                )
                if ctx.get("success"):
                    rendered = render_historical_context_for_llm(ctx)
                    if rendered.strip():
                        return rendered
            except Exception as e:
                logger.debug("RAG historical_context service: %s", e)

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get related storylines (by keywords or entities)
                storyline_title = storyline.get("title", "").lower()
                title_words = set(word for word in storyline_title.split() if len(word) > 3)

                if not title_words:
                    return None

                # Find storylines with similar keywords
                cur.execute(
                    f"""
                    SELECT id, title, description, analysis_summary
                    FROM {self.schema}.storylines
                    WHERE id != %s
                      AND status = 'active'
                      AND (
                        LOWER(title) LIKE ANY(ARRAY[%s])
                        OR LOWER(description) LIKE ANY(ARRAY[%s])
                      )
                    LIMIT 5
                """,
                    (
                        storyline.get("id"),
                        [f"%{word}%" for word in list(title_words)[:3]],
                        [f"%{word}%" for word in list(title_words)[:3]],
                    ),
                )

                related = cur.fetchall()

                if related:
                    context_parts = ["\nRelated Storylines:"]
                    for rel in related:
                        context_parts.append(f"- {rel.get('title', '')}")
                        if rel.get("analysis_summary"):
                            context_parts.append(f"  {rel.get('analysis_summary', '')[:150]}...")

                    return "\n".join(context_parts)

                return None

        except Exception as e:
            logger.warning(f"Error retrieving historical context: {e}")
            return None

    def _build_analysis_prompt(self, context: str, historical_context: str | None) -> str:
        """Build analysis prompt for LLM"""
        prompt = f"""
Analyze the following storyline and provide a comprehensive analysis:

{context}

{f"Historical Context:{historical_context}" if historical_context else ""}

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

    async def _extract_insights(self, analysis: str, storyline_id: int) -> list[dict[str, Any]]:
        """Extract insights from analysis (simplified)"""
        # For now, return basic insights
        # In future, use LLM to extract structured insights
        insights = []

        # Simple pattern detection
        if "trend" in analysis.lower() or "increasing" in analysis.lower():
            insights.append(
                {
                    "type": "trend",
                    "title": "Trending Story",
                    "description": "Story shows increasing activity",
                    "confidence_score": 0.7,
                }
            )

        if "important" in analysis.lower() or "significant" in analysis.lower():
            insights.append(
                {
                    "type": "pattern",
                    "title": "Significant Development",
                    "description": "Story contains significant developments",
                    "confidence_score": 0.6,
                }
            )

        return insights

    async def generate_storyline_report(
        self, storyline_id: int, report_type: str = "comprehensive"
    ) -> dict[str, Any]:
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
                cur.execute(
                    f"""
                    SELECT id, title, description, article_count,
                           quality_score, created_at, updated_at
                    FROM {self.schema}.storylines
                    WHERE id = %s
                """,
                    (storyline_id,),
                )

                storyline = cur.fetchone()

                cur.execute(
                    f"""
                    SELECT COUNT(DISTINCT a.source_domain) as source_count
                    FROM {self.schema}.articles a
                    JOIN {self.schema}.storyline_articles sa ON a.id = sa.article_id
                    WHERE sa.storyline_id = %s
                      AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                """,
                    (storyline_id,),
                )

                source_result = cur.fetchone()
                source_count = source_result["source_count"] if source_result else 0

                return {
                    "success": True,
                    "data": {
                        "storyline_id": storyline_id,
                        "report_type": report_type,
                        "title": storyline.get("title", ""),
                        "description": storyline.get("description", ""),
                        "analysis": analysis.get("data", {}).get("analysis", ""),
                        "key_points": self._extract_key_points(
                            analysis.get("data", {}).get("analysis", "")
                        ),
                        "article_count": storyline.get("article_count", 0),
                        "source_count": source_count,
                        "quality_score": storyline.get("quality_score", 0.0),
                        "coherence_score": 0.0,  # Calculated on demand, not stored
                        "generated_at": datetime.now().isoformat(),
                    },
                }
        finally:
            conn.close()

    def _extract_key_points(self, analysis: str) -> list[str]:
        """Extract key points from analysis (simplified)"""
        # Simple extraction - split by sentences and take important ones
        sentences = analysis.split(".")
        key_points = []

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 50 and any(
                word in sentence.lower()
                for word in ["important", "key", "significant", "major", "critical"]
            ):
                key_points.append(sentence)
                if len(key_points) >= 5:
                    break

        return key_points[:5]

    async def find_storyline_correlations(self, storyline_id: int) -> dict[str, Any]:
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


# ---------------------------------------------------------------------------
# Module-level helpers — formerly in ``storyline_management.py``.
# ---------------------------------------------------------------------------

async def perform_rag_analysis_background(domain: str, storyline_id: int):
    """Enqueue storyline analysis for workers (replaces ad-hoc background LLM)."""
    try:
        from services.content_refinement_queue_service import (
            JOB_COMPREHENSIVE_RAG,
            enqueue_content_refinement,
        )

        enq = enqueue_content_refinement(
            domain, storyline_id, JOB_COMPREHENSIVE_RAG, priority="medium"
        )
        if enq.get("success"):
            logger.info(
                "Queued comprehensive_rag for storyline %s domain=%s queue_id=%s",
                storyline_id,
                domain,
                enq.get("queue_id"),
            )
        else:
            logger.warning("enqueue comprehensive_rag failed: %s", enq.get("error"))
    except Exception as e:
        logger.error(f"Error enqueueing RAG analysis: {e}")


async def trigger_storyline_evolution(
    domain: str, storyline_id: int, new_article_ids: list[int] | None = None
):
    """
    Background task to trigger intelligent storyline evolution.
    Extracts new information from articles and automatically updates summary and context.
    """
    try:
        from .storyline_service import StorylineService

        storyline_service = StorylineService(domain=domain)
        result = await storyline_service.evolve_storyline_with_new_content(
            storyline_id, new_article_ids, force_evolution=False
        )

        if result.get("success"):
            data = result.get("data", {})
            logger.info(
                "Storyline %s evolved - summary updated: %s, new articles: %d, context: %s",
                storyline_id,
                data.get("summary_updated", False),
                data.get("new_articles", 0),
                data.get("context_updated", False),
            )
        else:
            logger.warning("Storyline evolution failed: %s", result.get("error"))
    except Exception as e:
        logger.error("Error in storyline evolution background task: %s", e)


def load_rag_analysis_inputs_for_queue(
    domain: str,
    storyline_id: int,
) -> tuple[tuple, list[tuple]] | None:
    """
    Load (storyline_row, articles_rows) for process_storyline_rag_analysis.
    Returns None if storyline missing or no matching articles.
    """
    schema = resolve_domain_schema(domain)
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT s.title, s.description, s.analysis_summary
                FROM {schema}.storylines s
                WHERE s.id = %s
                """,
                (storyline_id,),
            )
            storyline = cur.fetchone()
            if not storyline:
                return None
            cur.execute(
                f"""
                SELECT a.id, a.title, a.content, a.summary, a.published_at, a.source_domain, a.url
                FROM {schema}.articles a
                JOIN {schema}.storyline_articles sa ON a.id = sa.article_id
                WHERE sa.storyline_id = %s
                  AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                ORDER BY a.published_at ASC
                """,
                (storyline_id,),
            )
            articles = cur.fetchall()
            if not articles:
                return None
            return (storyline, articles)
    finally:
        conn.close()


async def process_storyline_rag_analysis(
    domain: str, storyline_id: int, storyline: tuple, articles: list[tuple]
):
    """Background task for RAG-enhanced storyline analysis"""
    try:
        from shared.database import get_db_connection

        schema = resolve_domain_schema(domain)
        title, description, current_summary = storyline

        context_parts = [f"Storyline: {title}"]
        if description:
            context_parts.append(f"Description: {description}")

        context_parts.append("\nArticles in storyline:")
        for article in articles:
            article_id, article_title, content, summary, published_at, source, url = article
            context_parts.append(f"\n- {article_title} ({source}, {published_at})")
            if summary:
                context_parts.append(f"  Summary: {summary}")
            else:
                context_parts.append(f"  Content: {content[:500]}...")

        storyline_context = "\n".join(context_parts)

        # Living vault background for long-running arcs
        try:
            from domains.reader.services.vault_context_pack import (
                build_vault_pack_for_entity_ids,
                render_vault_context_pack_for_llm,
            )
            from shared.database import get_db_connection_context

            entity_ids: list[int] = []
            with get_db_connection_context() as _conn:
                with _conn.cursor() as _cur:
                    _cur.execute(
                        f"""
                        SELECT DISTINCT ae.canonical_entity_id
                        FROM {schema}.article_entities ae
                        JOIN {schema}.storyline_articles sa ON sa.article_id = ae.article_id
                        WHERE sa.storyline_id = %s
                          AND ae.canonical_entity_id IS NOT NULL
                        LIMIT 16
                        """,
                        (storyline_id,),
                    )
                    entity_ids = [int(r[0]) for r in _cur.fetchall() if r[0]]
            if entity_ids:
                vpack = build_vault_pack_for_entity_ids(
                    domain, entity_ids, hops=2, max_notes=10
                )
                vault_context = render_vault_context_pack_for_llm(vpack)
        except Exception as _vp_err:
            logger.debug("Vault pack unavailable for RAG context: %s", _vp_err)
            vault_context = None

        # Assemble full system prompt
        max_depth = int(os.environ.get("STORYLINE_RAG_MAX_DEPTH", "1"))
        sys_parts = [MODELS["rag_analysis_system_prompt"]]
        if vault_context:
            sys_parts.append(
                f"\n\n**Living Vault background** (from prior entity packs):\n{vault_context}"
            )
        system_msg = "\n".join(sys_parts)

        prompt = (
            f"{storyline_context}\n\n"
            f"**Instructions:**\n"
            f"- Analyze the above storyline with **{max_depth}** level(s) of reasoning.\n"
            f"- Identify key developments, turning points, and implications.\n"
            f"- Write a comprehensive editorial analysis (lede + development breakdown).\n"
            f"**Format:**\n"
            f"- Start with a lede paragraph (3-4 sentences) capturing the essence.\n"
            f"- Include numbered developments with bullet points for details.\n"
            f"- Conclude with implications and future outlook.\n"
        )

        analysis_result = await llm_service.generate_response(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
            model=MODELS["rag_analysis"],
            temperature=0.1,
            max_tokens=2500,
        )

        if not analysis_result.get("success") or not analysis_result.get("response"):
            logger.warning(
                "RAG analysis failed for storyline %s: %s",
                storyline_id,
                analysis_result.get("error", "empty response"),
            )
            return {"success": False, "error": analysis_result.get("error", "Empty response")}

        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(f"SET search_path TO {schema}, public")

                    analysis_text = analysis_result["analysis"]

                    editorial_doc = {
                        "lede": analysis_text[:300] if analysis_text else "",
                        "developments": [],
                        "analysis": analysis_text or "",
                        "outlook": "",
                        "key_entities": [],
                        "sources": list(set(a[5] for a in articles if len(a) > 5 and a[5])),
                        "generated_at": datetime.now().isoformat(),
                        "based_on_articles": [a[0] for a in articles if a[0]],
                    }

                    cur.execute(
                        f"""
                        UPDATE {schema}.storylines
                        SET analysis_summary = %s,
                            quality_score = %s,
                            ml_processing_status = 'completed',
                            editorial_document = %s,
                            document_version = COALESCE(document_version, 0) + 1,
                            document_status = 'rag_analyzed',
                            last_refinement = %s
                        WHERE id = %s
                    """,
                        (
                            analysis_text,
                            0.90,
                            json.dumps(editorial_doc),
                            datetime.now(),
                            storyline_id,
                        ),
                    )
                    conn.commit()
                    logger.info("Updated RAG analysis for storyline %s", storyline_id)

                if os.environ.get("LEGACY_TIMELINE_EVENTS_WRITES", "0").strip().lower() in (
                    "1", "true", "yes",
                ):
                    _extract_timeline_events_from_articles(
                        conn, schema, storyline_id, articles, title
                    )

            except Exception as e:
                logger.error("Error updating storyline or extracting timeline: %s", e, exc_info=True)
            finally:
                conn.close()

    except Exception as e:
        logger.error("Error in storyline RAG analysis: %s", e)


def _extract_timeline_events_from_articles(
    conn, schema: str, storyline_id: int, articles: list[tuple], storyline_title: str
):
    """Extract timeline events from articles and store them in timeline_events table"""
    try:
        logger.info("Starting timeline extraction for storyline %s with %d articles", storyline_id, len(articles))

        cur = conn.cursor()
        events_created = 0
        articles_skipped = 0

        for article in articles:
            article_id, article_title, content, summary, published_at, source, url = article

            if not published_at:
                logger.debug("Skipping article %s: no published_at date", article_id)
                articles_skipped += 1
                continue

            event_date = None
            if isinstance(published_at, dt):
                event_date = published_at.date()
            elif hasattr(published_at, "date"):
                event_date = published_at.date()
            elif isinstance(published_at, str):
                try:
                    pub_str = published_at.replace("Z", "+00:00")
                    event_date = dt.fromisoformat(pub_str).date()
                except Exception as parse_error:
                    logger.warning("Could not parse date %s: %s", published_at, parse_error)
                    continue

            if not event_date:
                continue

            event_title = article_title[:200] if article_title else "Untitled Event"
            event_description = summary[:500] if summary else (content[:500] if content else "")
            event_id = f"storyline_{storyline_id}_article_{article_id}_{event_date.isoformat()}"

            cur.execute(
                f"""
                INSERT INTO {schema}.timeline_events (
                    event_id, storyline_id, title, description, event_date, event_time,
                    source, url, importance_score, event_type, location, entities, tags,
                    ml_generated, confidence_score, source_article_ids, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) ON CONFLICT (event_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    updated_at = EXCLUDED.updated_at
            """,
                (
                    event_id, str(storyline_id), event_title, event_description,
                    event_date, None, source, url, 0.7, "general",
                    None, json.dumps([]), [], True, 0.8, [article_id],
                    dt.now(), dt.now(),
                ),
            )
            events_created += 1

        conn.commit()
        logger.info("Extracted %d timeline events for storyline %s (skipped %d articles)", events_created, storyline_id, articles_skipped)

    except Exception as e:
        logger.error("Error extracting timeline events from articles: %s", e, exc_info=True)
