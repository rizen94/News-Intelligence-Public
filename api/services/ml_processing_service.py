"""
Improved ML Processing Service for News Intelligence System
Focuses on narrative building rather than content dumping
"""

import logging
import re
import threading
import time
from datetime import datetime
from typing import Any

from config.database import get_db
from sqlalchemy import text

logger = logging.getLogger(__name__)


class MLProcessingService:
    """Service for managing ML processing with narrative-focused summarization"""

    def __init__(self):
        self.is_running = False
        self.processing_thread = None
        self.stats = {
            "total_processed": 0,
            "successful": 0,
            "failed": 0,
            "currently_processing": 0,
            "queue_size": 0,
            "last_processed": None,
            "avg_processing_time": 0.0,
        }
        self.processing_times = []

    def start_processing(self):
        """Start the ML processing service"""
        if self.is_running:
            logger.warning("ML processing service is already running")
            return

        self.is_running = True
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()
        logger.info("🚀 Improved ML Processing Service started")

    def stop_processing(self):
        """Stop the ML processing service"""
        self.is_running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=5)
        logger.info("🛑 ML Processing Service stopped")

    def get_stats(self) -> dict[str, Any]:
        """Get processing statistics"""
        return self.stats.copy()

    def get_processing_status(self) -> dict[str, Any]:
        """Get current processing status"""
        return {
            "is_running": self.is_running,
            "stats": self.stats.copy(),
            "status": "running" if self.is_running else "stopped",
            "last_update": datetime.now().isoformat(),
        }

    def _processing_loop(self):
        """Main processing loop"""
        while self.is_running:
            try:
                self._process_storylines()
                time.sleep(30)  # Check every 30 seconds
            except Exception as e:
                logger.error(f"Error in processing loop: {e}")
                time.sleep(60)

    def _process_storylines(self):
        """Process storylines that need ML analysis (per active domain schema)."""
        try:
            from shared.domain_registry import domain_key_to_schema, get_active_domain_keys
        except Exception as e:
            logger.error(f"domain registry unavailable for ML processing: {e}")
            return

        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                for domain_key in get_active_domain_keys():
                    schema = domain_key_to_schema(domain_key)
                    if not schema or not schema.replace("_", "").isalnum():
                        continue
                    # Skip empty magnets: pending with no membership only burned CPU
                    # and spammed "No articles found" forever.
                    query = text(f"""
                        SELECT id, title, description, article_count
                        FROM {schema}.storylines
                        WHERE (
                            ml_processing_status = 'pending'
                            OR (
                                ml_processing_status = 'completed'
                                AND EXISTS (
                                    SELECT 1 FROM {schema}.storyline_articles sa
                                    WHERE sa.storyline_id = {schema}.storylines.id
                                      AND sa.added_at > COALESCE(
                                          {schema}.storylines.ml_last_processed,
                                          '1970-01-01'::timestamptz
                                      )
                                )
                            )
                        )
                        AND EXISTS (
                            SELECT 1 FROM {schema}.storyline_articles sa2
                            WHERE sa2.storyline_id = {schema}.storylines.id
                        )
                        AND COALESCE(article_count, 0) > 0
                        ORDER BY priority DESC, created_at ASC
                        LIMIT 3
                    """)
                    storylines = db.execute(query).fetchall()
                    for storyline in storylines:
                        self._process_storyline_with_ml(storyline, schema=schema)

                    db.execute(
                        text(f"""
                            UPDATE {schema}.storylines
                            SET ml_processing_status = 'skipped_empty',
                                ml_last_processed = CURRENT_TIMESTAMP
                            WHERE ml_processing_status = 'pending'
                              AND (
                                COALESCE(article_count, 0) <= 0
                                OR NOT EXISTS (
                                    SELECT 1 FROM {schema}.storyline_articles sa
                                    WHERE sa.storyline_id = {schema}.storylines.id
                                )
                              )
                        """)
                    )
                db.commit()
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error processing storylines: {e}")

    def _process_storyline_with_ml(self, storyline, *, schema: str = "public"):
        """Process a single storyline with improved ML summarization"""
        try:
            start_time = time.time()
            storyline_id = storyline.id

            logger.info(f"Processing storyline: {storyline.title}")

            # Get articles for this storyline
            articles = self._get_storyline_articles(storyline_id, schema=schema)

            if not articles:
                logger.info(
                    "Skipping empty storyline %s (marking skipped_empty)", storyline_id
                )
                self._mark_storyline_ml_skipped(storyline_id, schema=schema)
                return

            # Import ML service
            from services.ml_summarization_service import MLSummarizationService

            ml_service = MLSummarizationService()

            # Generate narrative-focused summary
            master_summary = self._generate_narrative_summary(ml_service, articles, storyline)

            # Update storyline with ML results
            self._update_storyline_ml_results(storyline_id, master_summary, schema=schema)

            processing_time = time.time() - start_time
            logger.info(f"Narrative ML processing completed in {processing_time:.2f}s")

            return processing_time

        except Exception as e:
            logger.error(f"ML processing failed: {e}")
            return 0

    def _get_storyline_articles(
        self, storyline_id: int, *, schema: str = "public"
    ) -> list[dict[str, Any]]:
        """Get articles for a storyline"""
        if not schema.replace("_", "").isalnum():
            return []
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                query = text(f"""
                    SELECT a.id, a.title, a.content, a.summary, a.source_domain, a.published_at, a.author
                    FROM {schema}.articles a
                    JOIN {schema}.storyline_articles sa ON a.id = sa.article_id
                    WHERE sa.storyline_id = :storyline_id
                    ORDER BY a.published_at ASC
                """)

                result = db.execute(query, {"storyline_id": storyline_id}).fetchall()
                return [dict(row._mapping) for row in result]
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error getting storyline articles: {e}")
            return []

    def _generate_narrative_summary(
        self, ml_service, articles: list[dict[str, Any]], storyline
    ) -> str:
        """Generate narrative-focused summary using improved approach"""
        try:
            # Create narrative-focused input
            narrative_input = self._create_narrative_input(articles, storyline)

            if not narrative_input:
                return "No content available for narrative analysis."

            # Create focused prompt for narrative building
            narrative_prompt = self._create_narrative_prompt(narrative_input, articles, storyline)

            # Generate summary using ML service
            summary_result = ml_service.generate_summary(narrative_prompt)

            if summary_result and summary_result.get("success"):
                raw_summary = summary_result.get("summary", "Summary generation failed.")
                return self._enhance_narrative_summary(raw_summary, articles, storyline)
            else:
                logger.warning("ML service returned no summary, using narrative fallback")
                return self._generate_narrative_fallback(articles, storyline)

        except Exception as e:
            logger.error(f"Error generating narrative summary: {e}")
            return self._generate_narrative_fallback(articles, storyline)

    def _create_narrative_input(self, articles: list[dict[str, Any]], storyline) -> str:
        """Create input focused on narrative building rather than content dumping"""
        if not articles:
            return ""

        # Sort articles by publication date for chronological context
        sorted_articles = sorted(articles, key=lambda x: x.get("published_at", ""))

        narrative_input = []
        narrative_input.append("=== NARRATIVE STORY ANALYSIS ===")
        narrative_input.append("")
        narrative_input.append(f"Storyline: {storyline.title}")
        narrative_input.append(f"Description: {storyline.description}")
        narrative_input.append("")
        narrative_input.append(
            "Create a cohesive, high-level story summary by analyzing how these story elements connect and evolve."
        )
        narrative_input.append(
            "Focus on building a unified narrative that shows the bigger picture."
        )
        narrative_input.append("")
        narrative_input.append("=== STORY ELEMENTS ===")
        narrative_input.append("")

        for i, article in enumerate(sorted_articles, 1):
            published_date = article.get("published_at", "Unknown date")
            title = article.get("title", "Untitled")
            content = article.get("content") or article.get("summary", "")

            # Extract key narrative elements from substantial content (not title-only)
            narrative_elements = self._extract_narrative_elements(content, title)

            src = article.get("source_domain") or article.get("source") or "Unknown source"
            narrative_input.append(f"--- STORY ELEMENT {i} ---")
            narrative_input.append(f"Source: {src}")
            narrative_input.append(f"Date: {published_date}")
            narrative_input.append(f"Headline: {title}")
            narrative_input.append("Key Narrative Points:")
            for element in narrative_elements:
                narrative_input.append(f"  • {element}")
            narrative_input.append("")

        return "\n".join(narrative_input)

    def _extract_narrative_elements(self, content: str, title: str) -> list[str]:
        """Extract key narrative elements from article content"""
        from shared.llm_text_sanitize import html_to_visible_text

        if not content:
            return [f"Headline: {title}"]

        prose = html_to_visible_text(str(content), max_length=1400)
        if not prose:
            return [f"Headline: {title}"]

        # Prefer first ~1200 chars of visible prose for substance
        content_preview = prose[:1200]
        sentences = re.split(r"(?<=[.!?])\s+", content_preview)
        narrative_elements = []

        for sentence in sentences[:6]:
            if sentence.strip() and len(sentence.strip()) > 25:
                clean_sentence = sentence.strip().replace("\n", " ").replace("\r", " ")
                if clean_sentence and not clean_sentence.endswith((".", "!", "?")):
                    clean_sentence += "."
                narrative_elements.append(clean_sentence)

        if len(narrative_elements) < 2:
            narrative_elements.insert(0, f"Headline: {title}")

        return narrative_elements[:6]

    def _create_narrative_prompt(
        self, narrative_input: str, articles: list[dict[str, Any]], storyline
    ) -> str:
        """Create a focused prompt for narrative building"""
        sources = list(
            {
                (article.get("source_domain") or article.get("source") or "Unknown")
                for article in articles
            }
        )
        date_range = self._get_date_range(articles)

        prompt = f"""
{narrative_input}

=== NARRATIVE BUILDING INSTRUCTIONS ===

Based on the story elements above, create a cohesive narrative summary that:

**FOCUS ON:**
- How these story elements connect to form a bigger picture
- The main story arc and its progression over time
- Key themes and patterns that emerge across sources
- The significance and implications of the overall story

**STRUCTURE YOUR RESPONSE AS plain markdown (no inventory counts):**
1. **Lede** — what happened, grounded in the article text
2. **Background** — durable context from the evidence
3. **What happened** — sequence of moves / developments
4. **Competing views** — labeled perspectives when sources disagree
5. **Why it matters** — stakes and what to watch

Do NOT list source counts, outlet tallies, "story elements analyzed", or date-span inventory.
Do NOT invent themes like "multiple perspectives on the same core story".
Every sentence must be supported by the story elements above.

**WRITING STYLE:**
- Write as a journalist creating a comprehensive story report
- Use clear, engaging language that tells a story
- Connect the dots between different story elements
- Focus on the narrative flow rather than listing individual article details
- Aim for 400-600 words that provide a complete picture

**STORYLINE CONTEXT:**
- Title: {storyline.title}
- Description: {storyline.description}
- Sources: {len(sources)} different sources ({", ".join(sources)})
- Time Period: {date_range}
- Total Elements: {len(articles)} story components

Create a narrative that shows how these individual story elements combine to tell a complete, compelling story.
"""
        return prompt

    def _enhance_narrative_summary(
        self, raw_summary: str, articles: list[dict[str, Any]], storyline
    ) -> str:
        """Keep article-grounded prose only — never wrap with inventory metadata."""
        from shared.llm_text_sanitize import (
            is_inventory_metadata_summary,
            strip_inventory_metadata_summary,
            strip_trailing_llm_json,
        )

        cleaned = strip_trailing_llm_json(strip_inventory_metadata_summary(raw_summary or ""))
        if not cleaned or len(cleaned.strip()) < 100 or is_inventory_metadata_summary(cleaned):
            return self._generate_narrative_fallback(articles, storyline)
        # Drop accidental title-only echo
        title = (getattr(storyline, "title", None) or "").strip()
        if title and cleaned.strip().casefold() == title.casefold():
            return self._generate_narrative_fallback(articles, storyline)
        return cleaned.strip()

    def _generate_narrative_fallback(self, articles: list[dict[str, Any]], storyline) -> str:
        """Article-grounded fallback — never emit Story Overview inventory fluff."""
        from shared.llm_text_sanitize import html_to_visible_text

        if not articles:
            return ""

        title = (getattr(storyline, "title", None) or "").strip()
        chunks: list[str] = []
        ranked = sorted(
            articles,
            key=lambda a: len(str(a.get("content") or a.get("summary") or "")),
            reverse=True,
        )
        for article in ranked[:4]:
            raw = article.get("content") or article.get("summary") or ""
            prose = html_to_visible_text(str(raw), max_length=900)
            if not prose or len(prose) < 80:
                continue
            prose = re.sub(r"^##\s+[^\n]+\n+", "", prose).strip()
            paras = [p.strip() for p in re.split(r"\n\s*\n+", prose) if p.strip()]
            excerpt = " ".join(paras[:2]) if paras else prose
            excerpt = re.sub(r"\s+", " ", excerpt).strip()
            if len(excerpt) < 80:
                continue
            headline = (article.get("title") or "").strip()
            src = (
                article.get("source_domain")
                or article.get("source")
                or ""
            ).strip()
            lead = excerpt if len(excerpt) <= 560 else excerpt[:540].rsplit(" ", 1)[0] + "…"
            if headline and headline.casefold() != title.casefold():
                label = f"**{headline}**" + (f" ({src})" if src else "")
                chunks.append(f"{label} — {lead}")
            else:
                chunks.append(lead)
            if sum(len(c) for c in chunks) >= 1600:
                break

        if not chunks:
            # Minimal honest stub — still not inventory metadata
            return (
                f"Coverage on «{title}» is thin in stored article bodies; "
                "await enrichment or narrative finish."
                if title
                else ""
            )
        return "\n\n".join(chunks)

    def _get_date_range(self, articles: list[dict[str, Any]]) -> str:
        """Get date range for articles"""
        if not articles:
            return "Unknown"

        dates = [article.get("published_at") for article in articles if article.get("published_at")]
        if not dates:
            return "Unknown"

        try:
            min_date = min(dates)
            max_date = max(dates)
            if min_date == max_date:
                return min_date.strftime("%B %d, %Y")
            else:
                return f"{min_date.strftime('%B %d, %Y')} - {max_date.strftime('%B %d, %Y')}"
        except:
            return "Unknown"

    def _mark_storyline_ml_skipped(self, storyline_id: int, *, schema: str = "public") -> None:
        """Leave empty magnets out of the pending ML queue."""
        if not schema.replace("_", "").isalnum():
            return
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                db.execute(
                    text(f"""
                        UPDATE {schema}.storylines
                        SET ml_processing_status = 'skipped_empty',
                            ml_last_processed = CURRENT_TIMESTAMP
                        WHERE id = :storyline_id
                    """),
                    {"storyline_id": storyline_id},
                )
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error marking storyline {storyline_id} skipped_empty: {e}")

    def _update_storyline_ml_results(
        self, storyline_id: int, master_summary: str, *, schema: str = "public"
    ):
        """Update storyline with ML results"""
        if not schema.replace("_", "").isalnum():
            return
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                query = text(f"""
                    UPDATE {schema}.storylines
                    SET master_summary = :summary,
                        ml_processing_status = 'completed',
                        ml_last_processed = CURRENT_TIMESTAMP
                    WHERE id = :storyline_id
                """)

                db.execute(query, {"summary": master_summary, "storyline_id": storyline_id})
                db.commit()

                logger.info(f"Updated storyline {storyline_id} with narrative summary")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error updating storyline ML results: {e}")


# Create global instance
ml_processing_service = MLProcessingService()
