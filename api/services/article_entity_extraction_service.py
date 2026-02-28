"""
Article Entity Extraction Service - News Intelligence v4.0
Extracts structured entities from headline + full text at intake.
Stores: people, orgs, subjects, recurring events (article_entities)
        dates, times, countries (separate tables - excluded from topic clustering)
        thematic keywords (article_keywords)
"""

import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Union

from shared.database.connection import get_db_connection
from shared.services.llm_service import LLMService, ModelType

logger = logging.getLogger(__name__)

# ISO country names to codes (common subset for normalization)
COUNTRY_ALIASES = {
    "united states": "US", "usa": "US", "u.s.": "US", "america": "US",
    "united kingdom": "GB", "uk": "GB", "britain": "GB", "england": "GB",
    "china": "CN", "russia": "RU", "russian federation": "RU",
    "germany": "DE", "france": "FR", "japan": "JP", "canada": "CA",
    "india": "IN", "australia": "AU", "brazil": "BR", "mexico": "MX",
    "south korea": "KR", "north korea": "KP", "ukraine": "UA", "israel": "IL",
    "iran": "IR", "saudi arabia": "SA", "uae": "AE", "united arab emirates": "AE",
}


class ArticleEntityExtractionService:
    """
    Extracts and stores article entities using LLM.
    Uses headline + full text; writes to article_entities, article_extracted_dates/times/countries, article_keywords.
    """

    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.llm = LLMService(ollama_base_url=ollama_url)

    async def extract_and_store(
        self,
        article_id: int,
        title: str,
        content: Optional[str],
        schema: str = "politics",
    ) -> Dict[str, Any]:
        """
        Extract entities from headline + content and store in domain tables.
        Returns counts of stored entities.
        """
        content = content or ""
        combined = f"{title}\n\n{content}"[:6000]  # Limit for LLM

        if len(combined.strip()) < 50:
            logger.debug(f"Article {article_id}: text too short for entity extraction")
            return {"success": False, "reason": "text_too_short", "counts": {}}

        try:
            raw = await self._call_llm(combined, title)
            parsed = self._parse_response(raw, title)
            conn = get_db_connection()
            if not conn:
                return {"success": False, "error": "db_connection_failed", "counts": {}}

            try:
                counts = await self._store_all(conn, article_id, schema, parsed, title, content)
                conn.commit()
                return {"success": True, "counts": counts}
            except Exception as e:
                conn.rollback()
                logger.error(f"Entity storage failed for article {article_id}: {e}")
                return {"success": False, "error": str(e), "counts": {}}
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"Entity extraction failed for article {article_id}: {e}")
            return {"success": False, "error": str(e), "counts": {}}

    async def _call_llm(self, text: str, headline: str) -> str:
        prompt = f"""Extract structured entities from this news article. Use BOTH the headline and body.

Headline: "{headline}"

Full text:
{text[:5000]}

Return ONLY valid JSON (no markdown, no explanation):
{{
  "people": [{{"name": "Full Name", "confidence": 0.9, "in_headline": true}}],
  "organizations": [{{"name": "Org Name", "confidence": 0.85, "in_headline": false}}],
  "subjects": [{{"name": "Theme or concept", "confidence": 0.8, "in_headline": false}}],
  "recurring_events": [{{"name": "Earnings call / Summit / Hearing", "confidence": 0.85, "in_headline": true}}],
  "dates": [{{"raw": "March 15", "normalized_iso": "2024-03-15", "type": "absolute"}}],
  "times": [{{"raw": "3:00 PM EST", "normalized": "15:00", "timezone": "EST"}}],
  "countries": [{{"name": "Country Name", "iso_code": "US", "in_headline": false}}],
  "keywords": [{{"keyword": "thematic term", "type": "subject", "in_headline": false}}]
}}

Rules:
- people: Notable people only (politicians, executives, experts, public figures)
- recurring_events: Hearings, summits, earnings calls, trials, elections
- subjects: Themes, concepts (NOT dates/times/countries)
- keywords: Thematic only - NO dates, times, or country names
- dates/times/countries: Store in their arrays only
"""

        response = await self.llm._call_ollama(ModelType.LLAMA_8B, prompt)
        return response

    def _parse_response(self, raw: str, headline: str) -> Dict[str, List[Dict]]:
        """Parse LLM JSON response with fallbacks."""
        defaults = {
            "people": [], "organizations": [], "subjects": [], "recurring_events": [],
            "dates": [], "times": [], "countries": [], "keywords": []
        }
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(raw[start:end])
                for k in defaults:
                    if k in data and isinstance(data[k], list):
                        defaults[k] = data[k]
        except json.JSONDecodeError as e:
            logger.warning(f"Entity JSON parse failed: {e}")
        return defaults

    async def _store_all(
        self,
        conn,
        article_id: int,
        schema: str,
        parsed: Dict[str, List[Dict]],
        headline: str,
        content: str,
    ) -> Dict[str, int]:
        counts = {"entities": 0, "dates": 0, "times": 0, "countries": 0, "keywords": 0}

        with conn.cursor() as cur:
            cur.execute(f"SET search_path TO {schema}, public")

            def _item_name(item: Any) -> str:
                if isinstance(item, str):
                    return item.strip()
                if isinstance(item, dict):
                    return (item.get("name") or item.get("text") or "").strip()
                return ""

            def _item_conf(item: Any, default: float = 0.8) -> float:
                if isinstance(item, dict):
                    v = item.get("confidence")
                    if v is None:
                        v = default
                    try:
                        return min(1.0, max(0.0, float(v)))
                    except (TypeError, ValueError):
                        return default
                return default

            def _item_in_headline(item: Any) -> bool:
                return bool(isinstance(item, dict) and item.get("in_headline", False))

            # 1. article_entities (people, orgs, subjects, recurring_events)
            for entity_type, key in [
                ("person", "people"),
                ("organization", "organizations"),
                ("subject", "subjects"),
                ("recurring_event", "recurring_events"),
            ]:
                for item in parsed.get(key, [])[:30]:
                    name = _item_name(item)
                    if not name or len(name) < 2:
                        continue
                    mention = "headline" if _item_in_headline(item) else "body"
                    conf = _item_conf(item)
                    try:
                        cur.execute(f"""
                            INSERT INTO {schema}.article_entities
                            (article_id, entity_name, entity_type, mention_source, confidence, source_text_snippet)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT (article_id, entity_name, entity_type) DO UPDATE SET
                                confidence = EXCLUDED.confidence,
                                mention_source = EXCLUDED.mention_source
                        """, (article_id, name[:255], entity_type, mention, conf, name[:200]))
                        counts["entities"] += 1
                    except Exception as e:
                        logger.debug(f"article_entities insert skip: {e}")

            def _dict_val(item: Any, key: str, default: str = "") -> Optional[str]:
                if isinstance(item, dict):
                    v = item.get(key) or default
                    return str(v).strip() if v else None
                return str(item).strip() if item and key == "raw" else None

            # 2. article_extracted_dates
            for item in parsed.get("dates", [])[:15]:
                raw_expr = (_dict_val(item, "raw") or (str(item).strip() if isinstance(item, str) else "")) or ""
                if not raw_expr:
                    continue
                norm = _dict_val(item, "normalized_iso") or None
                expr_type = (_dict_val(item, "type") or "unknown")[:30]
                conf = _item_conf(item, 0.7)
                try:
                    cur.execute(f"""
                        INSERT INTO {schema}.article_extracted_dates
                        (article_id, raw_expression, normalized_date, expression_type, confidence)
                        VALUES (%s, %s, %s::date, %s, %s)
                    """, (article_id, raw_expr[:500], norm if norm else None, expr_type, conf))
                    counts["dates"] += 1
                except Exception:
                    try:
                        cur.execute(f"""
                            INSERT INTO {schema}.article_extracted_dates
                            (article_id, raw_expression, expression_type, confidence)
                            VALUES (%s, %s, %s, %s)
                        """, (article_id, raw_expr[:500], expr_type, conf))
                        counts["dates"] += 1
                    except Exception as e:
                        logger.debug(f"article_extracted_dates insert skip: {e}")

            # 3. article_extracted_times
            for item in parsed.get("times", [])[:10]:
                raw_expr = (_dict_val(item, "raw") or (str(item).strip() if isinstance(item, str) else "")) or ""
                if not raw_expr:
                    continue
                norm = _dict_val(item, "normalized") or None
                tz = (_dict_val(item, "timezone") or "")[:50] or None
                conf = _item_conf(item, 0.7)
                try:
                    cur.execute(f"""
                        INSERT INTO {schema}.article_extracted_times
                        (article_id, raw_expression, normalized_time, timezone, confidence)
                        VALUES (%s, %s, %s::time, %s, %s)
                    """, (article_id, raw_expr[:500], norm if norm else None, tz or None, conf))
                    counts["times"] += 1
                except Exception:
                    try:
                        cur.execute(f"""
                            INSERT INTO {schema}.article_extracted_times
                            (article_id, raw_expression, timezone, confidence)
                            VALUES (%s, %s, %s, %s)
                        """, (article_id, raw_expr[:500], tz or None, conf))
                        counts["times"] += 1
                    except Exception as e:
                        logger.debug(f"article_extracted_times insert skip: {e}")

            # 4. article_extracted_countries
            for item in parsed.get("countries", [])[:15]:
                name = _item_name(item) or (str(item).strip() if isinstance(item, str) else "")
                if not name:
                    continue
                iso = (_dict_val(item, "iso_code") if isinstance(item, dict) else None) or COUNTRY_ALIASES.get(name.lower())
                mention = "headline" if _item_in_headline(item) else "body"
                conf = _item_conf(item, 0.8)
                try:
                    cur.execute(f"""
                        INSERT INTO {schema}.article_extracted_countries
                        (article_id, country_name, iso_code, mention_context, confidence)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (article_id, country_name) DO UPDATE SET
                            iso_code = COALESCE(EXCLUDED.iso_code, article_extracted_countries.iso_code),
                            confidence = EXCLUDED.confidence
                    """, (article_id, name[:255], iso[:2] if iso else None, mention, conf))
                    counts["countries"] += 1
                except Exception as e:
                    logger.debug(f"article_extracted_countries insert skip: {e}")

            # 5. article_keywords (thematic only)
            for item in parsed.get("keywords", [])[:20]:
                kw = (_dict_val(item, "keyword") or _item_name(item) or (str(item).strip() if isinstance(item, str) else "")).strip()
                if not kw or len(kw) < 2:
                    continue
                kw_type = _dict_val(item, "type") or "general"
                if kw_type not in ("general", "subject", "product", "technology"):
                    kw_type = "general"
                source = "headline" if _item_in_headline(item) else "body"
                conf = _item_conf(item, 0.7)
                try:
                    cur.execute(f"""
                        INSERT INTO {schema}.article_keywords
                        (article_id, keyword, keyword_type, source, confidence)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (article_id, keyword) DO UPDATE SET
                            confidence = EXCLUDED.confidence
                    """, (article_id, kw[:255], kw_type, source, conf))
                    counts["keywords"] += 1
                except Exception as e:
                    logger.debug(f"article_keywords insert skip: {e}")

        return counts

    def entity_extraction_done(self, conn, schema: str, article_id: int) -> bool:
        """Check if article already has entities extracted. Returns True if table missing (skip extraction)."""
        try:
            with conn.cursor() as cur:
                cur.execute(f"SET search_path TO {schema}, public")
                cur.execute(f"""
                    SELECT 1 FROM {schema}.article_entities WHERE article_id = %s LIMIT 1
                """, (article_id,))
                return cur.fetchone() is not None
        except Exception as e:
            # Table may not exist (migration 138 not run) - skip extraction
            if "does not exist" in str(e).lower() or "undefined_table" in str(e).lower():
                return True  # Skip to avoid failed extract_and_store
            return False


# Singleton
_article_entity_extraction_service: Optional[ArticleEntityExtractionService] = None


def get_article_entity_extraction_service() -> ArticleEntityExtractionService:
    global _article_entity_extraction_service
    if _article_entity_extraction_service is None:
        _article_entity_extraction_service = ArticleEntityExtractionService()
    return _article_entity_extraction_service
