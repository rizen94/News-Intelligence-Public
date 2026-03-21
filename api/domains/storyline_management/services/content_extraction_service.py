#!/usr/bin/env python3
"""
Content Extraction Service
Intelligently extracts and structures information from articles for storyline integration
"""

import logging
import re
from datetime import datetime
from typing import Any

from shared.services.domain_aware_service import DomainAwareService
from shared.services.llm_service import llm_service

logger = logging.getLogger(__name__)


class ContentExtractionService(DomainAwareService):
    """Service for extracting structured information from articles"""

    def __init__(self, domain: str = "politics"):
        """
        Initialize content extraction service with domain context.

        Args:
            domain: Domain key (e.g., 'politics', 'finance', 'science-tech')
        """
        super().__init__(domain)

    async def extract_article_information(self, article: dict[str, Any]) -> dict[str, Any]:
        """
        Extract structured information from an article.

        Args:
            article: Article dictionary with title, content, summary, etc.

        Returns:
            Dictionary with extracted information:
            - key_facts: List of key facts/claims
            - entities: List of entities (people, organizations, locations)
            - dates: List of dates mentioned
            - quotes: List of quotes
            - new_information: New information not in existing context
            - themes: List of themes/topics
        """
        try:
            # Combine article text
            article_text = f"{article.get('title', '')}\n\n{article.get('summary', '')}\n\n{article.get('content', '')}"

            # Use LLM to extract structured information
            extraction_prompt = f"""
Extract structured information from the following news article. Provide a comprehensive analysis.

Article:
{article_text}

Extract and structure:
1. Key Facts: List all factual claims, events, and important information
2. Entities: Identify all people, organizations, locations, and other named entities
3. Dates: Extract all dates, times, and temporal references
4. Quotes: Extract all direct quotes with attribution
5. Themes: Identify main themes and topics
6. Significance: What makes this article important or newsworthy?

Format your response as structured data that can be easily integrated into a storyline.
"""

            # Get LLM extraction
            llm_result = await llm_service.generate_text(
                prompt=extraction_prompt, task_type="content_analysis", max_tokens=2000
            )

            if not llm_result.get("success"):
                # Fallback to basic extraction
                return self._basic_extraction(article_text)

            extracted_text = llm_result.get("text", "")

            # Parse LLM response into structured format
            extracted_info = self._parse_extraction(extracted_text, article_text)

            return {
                "success": True,
                "data": extracted_info,
                "article_id": article.get("id"),
                "extracted_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error extracting article information: {e}")
            # Fallback to basic extraction
            return {
                "success": True,
                "data": self._basic_extraction(
                    f"{article.get('title', '')}\n\n{article.get('summary', '')}\n\n{article.get('content', '')}"
                ),
                "article_id": article.get("id"),
                "extracted_at": datetime.now().isoformat(),
            }

    def _basic_extraction(self, text: str) -> dict[str, Any]:
        """Basic extraction using pattern matching (fallback)"""
        # Extract dates
        date_pattern = r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b"
        dates = re.findall(date_pattern, text)

        # Extract quotes (simple pattern)
        quote_pattern = r'["\']([^"\']{20,200})["\']'
        quotes = re.findall(quote_pattern, text)

        # Extract potential entities (capitalized words)
        entity_pattern = r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b"
        potential_entities = list(set(re.findall(entity_pattern, text)))[:20]

        # Extract key sentences (sentences with important keywords)
        sentences = re.split(r"[.!?]+", text)
        key_sentences = [
            s.strip()
            for s in sentences
            if len(s.strip()) > 50
            and any(
                keyword in s.lower()
                for keyword in ["announced", "reported", "confirmed", "revealed", "according"]
            )
        ][:10]

        return {
            "key_facts": key_sentences[:5],
            "entities": potential_entities[:15],
            "dates": list(set(dates))[:10],
            "quotes": quotes[:5],
            "themes": [],
            "significance": "",
        }

    def _parse_extraction(self, llm_text: str, original_text: str) -> dict[str, Any]:
        """Parse LLM extraction response into structured format"""
        # Try to extract structured sections from LLM response
        facts = []
        entities = []
        dates = []
        quotes = []
        themes = []
        significance = ""

        # Look for sections in LLM response
        if "Key Facts:" in llm_text or "1." in llm_text:
            facts_section = self._extract_section(llm_text, ["Key Facts:", "1.", "Facts:"])
            facts = [
                f.strip() for f in facts_section.split("\n") if f.strip() and len(f.strip()) > 20
            ][:10]

        if "Entities:" in llm_text or "2." in llm_text:
            entities_section = self._extract_section(
                llm_text, ["Entities:", "2.", "People/Organizations:"]
            )
            entities = [e.strip() for e in entities_section.split("\n") if e.strip()][:20]

        if "Dates:" in llm_text or "3." in llm_text:
            dates_section = self._extract_section(llm_text, ["Dates:", "3.", "Timeline:"])
            dates = [d.strip() for d in dates_section.split("\n") if d.strip()][:10]

        if "Quotes:" in llm_text or "4." in llm_text:
            quotes_section = self._extract_section(llm_text, ["Quotes:", "4."])
            quotes = [q.strip() for q in quotes_section.split("\n") if q.strip() and '"' in q][:10]

        if "Themes:" in llm_text or "5." in llm_text:
            themes_section = self._extract_section(llm_text, ["Themes:", "5.", "Topics:"])
            themes = [t.strip() for t in themes_section.split("\n") if t.strip()][:10]

        if "Significance:" in llm_text or "6." in llm_text:
            significance = self._extract_section(llm_text, ["Significance:", "6.", "Importance:"])

        # Fallback: if parsing failed, use basic extraction
        if not facts and not entities:
            return self._basic_extraction(original_text)

        return {
            "key_facts": facts,
            "entities": entities,
            "dates": dates,
            "quotes": quotes,
            "themes": themes,
            "significance": significance.strip() if significance else "",
        }

    def _extract_section(self, text: str, markers: list[str]) -> str:
        """Extract a section from text based on markers"""
        for marker in markers:
            if marker in text:
                start_idx = text.find(marker) + len(marker)
                # Find next section or end
                next_section = len(text)
                for next_marker in ["\n\n", "##", "**", "1.", "2.", "3.", "4.", "5.", "6."]:
                    next_idx = text.find(next_marker, start_idx + 10)
                    if next_idx != -1 and next_idx < next_section:
                        next_section = next_idx
                return text[start_idx:next_section].strip()
        return ""

    async def identify_new_information(
        self, extracted_info: dict[str, Any], existing_context: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Identify what information is new compared to existing storyline context.

        Args:
            extracted_info: Information extracted from new article
            existing_context: Existing storyline context (summary, facts, entities)

        Returns:
            Dictionary with:
            - new_facts: Facts not in existing context
            - new_entities: Entities not previously mentioned
            - new_dates: New dates/timeline information
            - updated_facts: Facts that update or contradict existing information
            - context_changes: Summary of what changed
        """
        try:
            existing_facts = set(existing_context.get("key_facts", []))
            existing_entities = set(existing_context.get("entities", []))
            existing_dates = set(existing_context.get("dates", []))

            new_facts = []
            new_entities = []
            new_dates = []
            updated_facts = []

            # Check for new facts
            for fact in extracted_info.get("key_facts", []):
                fact_lower = fact.lower()
                is_new = True
                for existing_fact in existing_facts:
                    # Check similarity (simple word overlap)
                    fact_words = set(fact_lower.split())
                    existing_words = set(existing_fact.lower().split())
                    overlap = len(fact_words & existing_words) / max(len(fact_words), 1)
                    if overlap > 0.6:  # 60% word overlap = similar fact
                        is_new = False
                        # Check if it's an update
                        if fact != existing_fact:
                            updated_facts.append({"old": existing_fact, "new": fact})
                        break
                if is_new:
                    new_facts.append(fact)

            # Check for new entities
            for entity in extracted_info.get("entities", []):
                entity_lower = entity.lower()
                is_new = True
                for existing_entity in existing_entities:
                    if (
                        entity_lower == existing_entity.lower()
                        or entity_lower in existing_entity.lower()
                    ):
                        is_new = False
                        break
                if is_new:
                    new_entities.append(entity)

            # Check for new dates
            for date in extracted_info.get("dates", []):
                if date not in existing_dates:
                    new_dates.append(date)

            # Generate context changes summary
            context_changes = []
            if new_facts:
                context_changes.append(f"Added {len(new_facts)} new facts")
            if new_entities:
                context_changes.append(f"Added {len(new_entities)} new entities")
            if new_dates:
                context_changes.append(f"Added {len(new_dates)} new dates")
            if updated_facts:
                context_changes.append(f"Updated {len(updated_facts)} existing facts")

            return {
                "success": True,
                "data": {
                    "new_facts": new_facts,
                    "new_entities": new_entities,
                    "new_dates": new_dates,
                    "updated_facts": updated_facts,
                    "context_changes": context_changes,
                    "has_new_information": len(new_facts) > 0
                    or len(new_entities) > 0
                    or len(new_dates) > 0,
                },
            }

        except Exception as e:
            logger.error(f"Error identifying new information: {e}")
            return {"success": False, "error": str(e)}

    async def merge_context(
        self,
        existing_summary: str,
        existing_context: dict[str, Any],
        new_information: dict[str, Any],
        article: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Merge new information into existing storyline context.

        Args:
            existing_summary: Current storyline summary
            existing_context: Current storyline context
            new_information: New information from article
            article: The new article being added

        Returns:
            Dictionary with:
            - updated_summary: Enhanced summary with new information
            - updated_context: Updated context dictionary
            - merge_notes: Notes about what was merged
        """
        try:
            # Use LLM to intelligently merge contexts
            merge_prompt = f"""
You are updating a news storyline with new information. Create a comprehensive, well-structured summary that integrates the new information seamlessly.

EXISTING STORYLINE SUMMARY:
{existing_summary}

EXISTING CONTEXT:
- Key Facts: {existing_context.get("key_facts", [])[:5]}
- Entities: {existing_context.get("entities", [])[:10]}
- Dates: {existing_context.get("dates", [])[:5]}

NEW ARTICLE INFORMATION:
Title: {article.get("title", "")}
Summary: {article.get("summary", "")}

NEW INFORMATION TO ADD:
- New Facts: {new_information.get("new_facts", [])}
- New Entities: {new_information.get("new_entities", [])}
- New Dates: {new_information.get("new_dates", [])}
- Updated Facts: {new_information.get("updated_facts", [])}

Create an updated, comprehensive summary that:
1. Maintains narrative coherence
2. Integrates new information naturally
3. Preserves important existing context
4. Highlights what's new or changed
5. Is well-structured and professional
6. Is detailed and comprehensive

Provide ONLY the updated summary, no additional commentary.
"""

            llm_result = await llm_service.generate_text(
                prompt=merge_prompt, task_type="content_analysis", max_tokens=2000
            )

            if llm_result.get("success"):
                updated_summary = llm_result.get("text", "").strip()
            else:
                # Fallback: simple concatenation
                updated_summary = f"{existing_summary}\n\nNEW: {article.get('summary', '')}"

            # Update context
            updated_context = existing_context.copy()
            updated_context["key_facts"].extend(new_information.get("new_facts", []))
            updated_context["entities"].extend(new_information.get("new_entities", []))
            updated_context["dates"].extend(new_information.get("new_dates", []))

            # Remove duplicates
            updated_context["key_facts"] = list(
                dict.fromkeys(updated_context["key_facts"])
            )  # Preserve order
            updated_context["entities"] = list(set(updated_context["entities"]))
            updated_context["dates"] = list(set(updated_context["dates"]))

            merge_notes = {
                "facts_added": len(new_information.get("new_facts", [])),
                "entities_added": len(new_information.get("new_entities", [])),
                "dates_added": len(new_information.get("new_dates", [])),
                "facts_updated": len(new_information.get("updated_facts", [])),
            }

            return {
                "success": True,
                "data": {
                    "updated_summary": updated_summary,
                    "updated_context": updated_context,
                    "merge_notes": merge_notes,
                },
            }

        except Exception as e:
            logger.error(f"Error merging context: {e}")
            return {"success": False, "error": str(e)}
