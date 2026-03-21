"""
RAG Service Base - Core RAG Operations
Basic RAG functionality with Wikipedia and GDELT integration
Consolidated from rag_service.py
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import requests
from psycopg2.extras import RealDictCursor
from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)


class BaseRAGService:
    """
    Base RAG Service - Core RAG operations

    Provides:
    - Wikipedia API integration
    - GDELT API integration
    - Basic context enhancement
    - Entity and topic extraction
    - RAG context storage
    """

    def __init__(self, db_config: dict[str, str] = None):
        """
        Initialize base RAG service

        Args:
            db_config: Database configuration (optional, uses env vars if not provided)
        """
        if db_config is None:
            from shared.database.connection import get_db_config

            db_config = get_db_config()
        self.db_config = db_config
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "News Intelligence System v3.0 RAG Service"})

        # Wikipedia API configuration
        self.wikipedia_api_url = "https://en.wikipedia.org/api/rest_v1"

        # GDELT API configuration (using free tier)
        self.gdelt_api_url = "https://api.gdeltproject.org/api/v2"

        # Smart cache service
        self.cache_service = None

    def _get_cache_service(self):
        """Get smart cache service instance"""
        if self.cache_service is None:
            try:
                from services.smart_cache_service import get_smart_cache_service

                self.cache_service = get_smart_cache_service()
            except ImportError:
                logger.warning("Smart cache service not available")
                self.cache_service = None
        return self.cache_service

    async def enhance_storyline_context(
        self,
        storyline_id: str,
        storyline_title: str,
        articles: list[dict[str, Any]],
        domain: str | None = None,
    ) -> dict[str, Any]:
        """Enhance storyline with RAG context from Wikipedia and GDELT. v8: domain keys storage (domain_key, storyline_id). Uses DB entities when domain and article ids available."""
        try:
            logger.info(f"Enhancing storyline context for: {storyline_title} (domain={domain})")
            entity_names: list[str] = []
            entity_backgrounds: list[dict[str, Any]] = []
            if domain and articles:
                article_ids = [a.get("id") for a in articles if a.get("id") is not None]
                if article_ids:
                    enriched = self._get_entities_from_db(article_ids, domain)
                    entity_names = [e["name"] for e in enriched]
                    entity_backgrounds = [
                        {
                            "name": e["name"],
                            "type": e.get("type", ""),
                            "description": e.get("description", ""),
                            "wikipedia_url": e.get("wikipedia_url"),
                        }
                        for e in enriched
                    ]
            if not entity_names:
                entity_names = self._extract_entities_from_articles(articles)
            topics = self._extract_topics_from_articles(articles)
            wikipedia_context = await self._get_wikipedia_context(topics, entity_names)
            gdelt_context = await self._get_gdelt_context(topics, entity_names)
            rag_context = {
                "wikipedia": wikipedia_context,
                "gdelt": gdelt_context,
                "extracted_entities": entity_names,
                "extracted_topics": topics,
                "entity_backgrounds": entity_backgrounds,
                "enhanced_at": datetime.now(timezone.utc).isoformat(),
                "storyline_id": storyline_id,
                "domain_key": domain,
            }
            await self._save_rag_context(storyline_id, rag_context, domain=domain)
            # Phase 4A: persist GDELT events to chronological_events for timeline/dedup pipeline
            gdelt_events = (rag_context.get("gdelt") or {}).get("events") or []
            if gdelt_events and domain and articles:
                self._store_gdelt_events_to_chronological(
                    storyline_id=str(storyline_id),
                    domain=domain,
                    articles=articles,
                    gdelt_events=gdelt_events,
                )
            return rag_context
        except Exception as e:
            logger.error(f"Error enhancing storyline context: {e}")
            return {
                "error": str(e),
                "wikipedia": {},
                "gdelt": {},
                "extracted_entities": [],
                "extracted_topics": [],
                "entity_backgrounds": [],
                "enhanced_at": datetime.now(timezone.utc).isoformat(),
                "storyline_id": storyline_id,
            }

    def _get_entities_from_db(self, article_ids: list[int], domain: str) -> list[dict[str, Any]]:
        """Load entities from article_entities + entity_canonical for given article ids. Returns list of dicts with canonical_entity_id, name, type, description, aliases, wikipedia_url so context enrichment and entity viewer can use the main entity and all aliases."""
        schema = domain.replace("-", "_") if domain else "politics"
        conn = get_db_connection()
        if not conn:
            return []
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT ec.id, ec.canonical_name, ec.entity_type, ec.description, ec.aliases, ec.wikipedia_page_id
                    FROM {schema}.article_entities ae
                    JOIN {schema}.entity_canonical ec ON ec.id = ae.canonical_entity_id
                    WHERE ae.article_id = ANY(%s) AND ec.canonical_name IS NOT NULL
                    GROUP BY ec.id, ec.canonical_name, ec.entity_type, ec.description, ec.aliases, ec.wikipedia_page_id
                    ORDER BY COUNT(ae.id) DESC
                    LIMIT 20
                    """,
                    (article_ids,),
                )
                seen = set()
                out = []
                for row in cur.fetchall():
                    name = (row[1] or "").strip()
                    if not name or name in seen:
                        continue
                    seen.add(name)
                    wiki_url = ""
                    if row[5]:
                        wiki_url = f"https://en.wikipedia.org/wiki/?curid={row[5]}"
                    out.append(
                        {
                            "canonical_entity_id": row[0],
                            "name": name,
                            "type": row[2] or "other",
                            "description": (row[3] or "").strip() or None,
                            "aliases": list(row[4] or []),
                            "wikipedia_page_id": row[5],
                            "wikipedia_url": wiki_url or None,
                        }
                    )
                return out
        except Exception as e:
            logger.debug("_get_entities_from_db: %s", e)
            return []
        finally:
            conn.close()

    def _extract_entities_from_articles(self, articles: list[dict[str, Any]]) -> list[str]:
        """Extract key entities from articles"""
        entities = set()

        for article in articles:
            # Extract from title
            title_entities = self._extract_entities_from_text(article.get("title", ""))
            entities.update(title_entities)

            # Extract from content
            content_entities = self._extract_entities_from_text(article.get("content", ""))
            entities.update(content_entities)

            # Extract from source
            if article.get("source"):
                entities.add(article["source"])

        # Filter and clean entities
        filtered_entities = []
        for entity in entities:
            if len(entity) > 2 and len(entity) < 50:  # Reasonable length
                # Remove common words
                if entity.lower() not in [
                    "the",
                    "and",
                    "or",
                    "but",
                    "in",
                    "on",
                    "at",
                    "to",
                    "for",
                    "of",
                    "with",
                    "by",
                ]:
                    filtered_entities.append(entity)

        return filtered_entities[:20]  # Limit to top 20 entities

    def _extract_topics_from_articles(self, articles: list[dict[str, Any]]) -> list[str]:
        """Extract key topics from articles"""
        topics = set()

        for article in articles:
            # Extract from title
            title_topics = self._extract_topics_from_text(article.get("title", ""))
            topics.update(title_topics)

            # Extract from content
            content_topics = self._extract_topics_from_text(article.get("content", ""))
            topics.update(content_topics)

        return list(topics)[:15]  # Limit to top 15 topics

    def _extract_entities_from_text(self, text: str) -> list[str]:
        """Extract entities from text using simple pattern matching"""
        if not text:
            return []

        # Simple entity extraction - look for capitalized words and phrases
        entities = []

        # Find capitalized words (potential proper nouns)
        capitalized_words = re.findall(r"\b[A-Z][a-z]+\b", text)
        entities.extend(capitalized_words)

        # Find quoted phrases
        quoted_phrases = re.findall(r'"([^"]+)"', text)
        entities.extend(quoted_phrases)

        # Find company/product names (common patterns)
        company_patterns = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text)
        entities.extend(company_patterns)

        return entities

    def _extract_topics_from_text(self, text: str) -> list[str]:
        """Extract topics from text"""
        if not text:
            return []

        topics = []

        # Common tech/business topics
        topic_keywords = [
            "AI",
            "artificial intelligence",
            "machine learning",
            "blockchain",
            "cryptocurrency",
            "startup",
            "funding",
            "investment",
            "venture capital",
            "IPO",
            "acquisition",
            "technology",
            "innovation",
            "digital",
            "platform",
            "app",
            "software",
            "data",
            "analytics",
            "cloud",
            "cybersecurity",
            "privacy",
            "regulation",
            "market",
            "economy",
            "business",
            "finance",
            "banking",
            "fintech",
        ]

        text_lower = text.lower()
        for keyword in topic_keywords:
            if keyword.lower() in text_lower:
                topics.append(keyword)

        return topics

    async def _get_wikipedia_context(
        self, topics: list[str], entities: list[str]
    ) -> dict[str, Any]:
        """Get Wikipedia context for topics and entities with smart caching"""
        wikipedia_context = {
            "articles": [],
            "summaries": [],
            "error": None,
            "cache_hits": 0,
            "cache_misses": 0,
        }

        try:
            cache_service = self._get_cache_service()

            # Search for each topic/entity
            search_terms = (topics + entities)[:10]  # Limit to 10 searches

            for term in search_terms:
                try:
                    # Check cache first
                    if cache_service:
                        cached_data = await cache_service.get("wikipedia", term)

                        if cached_data:
                            wikipedia_context["articles"].extend(cached_data.get("articles", []))
                            wikipedia_context["summaries"].extend(cached_data.get("summaries", []))
                            wikipedia_context["cache_hits"] += 1
                            logger.debug(f"Wikipedia cache hit for: {term}")
                            continue

                    # Cache miss - fetch from API
                    wikipedia_context["cache_misses"] += 1

                    # Search for the term
                    search_url = f"{self.wikipedia_api_url}/page/summary/{quote(term)}"
                    response = self.session.get(search_url, timeout=10)

                    if response.status_code == 200:
                        data = response.json()

                        if "extract" in data:
                            article_data = {
                                "title": data.get("title", term),
                                "extract": data.get("extract", ""),
                                "url": data.get("content_urls", {})
                                .get("desktop", {})
                                .get("page", ""),
                                "search_term": term,
                            }
                            wikipedia_context["articles"].append(article_data)

                            summary_data = {
                                "term": term,
                                "summary": data.get("extract", "")[:500] + "..."
                                if len(data.get("extract", "")) > 500
                                else data.get("extract", ""),
                            }
                            wikipedia_context["summaries"].append(summary_data)

                            # Cache the result
                            if cache_service:
                                cache_data = {
                                    "articles": [article_data],
                                    "summaries": [summary_data],
                                }
                                await cache_service.set("wikipedia", term, cache_data)
                                logger.debug(f"Cached Wikipedia data for: {term}")

                    # Rate limiting
                    await asyncio.sleep(0.5)

                except Exception as e:
                    logger.warning(f"Error fetching Wikipedia context for {term}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error in Wikipedia context retrieval: {e}")
            wikipedia_context["error"] = str(e)

        return wikipedia_context

    async def _get_gdelt_context(self, topics: list[str], entities: list[str]) -> dict[str, Any]:
        """Get GDELT context for topics and entities with smart caching"""
        gdelt_context = {
            "events": [],
            "mentions": [],
            "error": None,
            "cache_hits": 0,
            "cache_misses": 0,
        }

        try:
            cache_service = self._get_cache_service()

            # Search for recent events related to topics
            search_terms = (topics + entities)[:5]  # Limit to 5 searches

            for term in search_terms:
                try:
                    # Check cache first
                    if cache_service:
                        cached_data = await cache_service.get("gdelt", term)

                        if cached_data:
                            gdelt_context["events"].extend(cached_data.get("events", []))
                            gdelt_context["mentions"].extend(cached_data.get("mentions", []))
                            gdelt_context["cache_hits"] += 1
                            logger.debug(f"GDELT cache hit for: {term}")
                            continue

                    # Cache miss - fetch from API
                    gdelt_context["cache_misses"] += 1

                    # Search GDELT for recent events
                    search_url = f"{self.gdelt_api_url}/doc/doc"
                    params = {
                        "query": term,
                        "format": "json",
                        "maxrecords": 10,
                        "startdatetime": (datetime.now() - timedelta(days=30)).strftime(
                            "%Y%m%d%H%M%S"
                        ),
                        "enddatetime": datetime.now().strftime("%Y%m%d%H%M%S"),
                    }

                    response = self.session.get(search_url, params=params, timeout=15)

                    if response.status_code == 200:
                        data = response.json()
                        events = []

                        if "docs" in data:
                            for doc in data["docs"][:5]:  # Limit to 5 events per term
                                event_data = {
                                    "title": doc.get("title", ""),
                                    "url": doc.get("url", ""),
                                    "date": doc.get("date", ""),
                                    "source": doc.get("source", ""),
                                    "search_term": term,
                                }
                                events.append(event_data)
                                gdelt_context["events"].append(event_data)

                        # Cache the result
                        if cache_service:
                            cache_data = {"events": events, "mentions": []}
                            await cache_service.set("gdelt", term, cache_data)
                            logger.debug(f"Cached GDELT data for: {term}")

                    # Rate limiting
                    await asyncio.sleep(1)

                except Exception as e:
                    logger.warning(f"Error fetching GDELT context for {term}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error in GDELT context retrieval: {e}")
            gdelt_context["error"] = str(e)

        return gdelt_context

    def _store_gdelt_events_to_chronological(
        self,
        storyline_id: str,
        domain: str,
        articles: list[dict[str, Any]],
        gdelt_events: list[dict[str, Any]],
    ) -> None:
        """
        Store GDELT events as chronological_events (extraction_method='gdelt') so they
        enter the timeline and dedup pipeline. Uses first article id as source_article_id
        for FK; may no-op if table/schema does not allow it.
        """
        if not gdelt_events or not articles:
            return
        first_article_id = None
        for a in articles:
            aid = a.get("id") if isinstance(a, dict) else None
            if aid is not None:
                first_article_id = int(aid)
                break
        if first_article_id is None:
            return
        schema = (domain or "politics").replace("-", "_")
        conn = get_db_connection()
        if not conn:
            return
        try:
            with conn.cursor() as cur:
                cur.execute(f"SET search_path TO {schema}, public")
                for i, ev in enumerate(gdelt_events[:20]):
                    if not isinstance(ev, dict):
                        continue
                    title = (ev.get("title") or ev.get("event", "") or "GDELT event")[:500]
                    date_str = ev.get("date") or ev.get("event_date", "")
                    try:
                        actual_date = (
                            datetime.strptime(date_str[:10], "%Y-%m-%d").date()
                            if date_str and len(date_str) >= 10
                            else None
                        )
                    except Exception:
                        actual_date = None
                    event_id = f"gdelt_{storyline_id}_{i}_{hash(title + str(actual_date)) % 10**8}"
                    try:
                        cur.execute(
                            """
                            INSERT INTO chronological_events (
                                event_id, storyline_id, title, description, event_type,
                                actual_event_date, source_article_id, extraction_method,
                                extraction_confidence, importance_score
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (event_id) DO NOTHING
                            """,
                            (
                                event_id,
                                str(storyline_id),
                                title[:300],
                                (ev.get("summary") or ev.get("url") or "")[:2000],
                                ev.get("event_type", "other"),
                                actual_date,
                                first_article_id,
                                "gdelt",
                                0.6,
                                0.5,
                            ),
                        )
                    except Exception as ins_err:
                        if (
                            "does not exist" in str(ins_err).lower()
                            or "foreign key" in str(ins_err).lower()
                        ):
                            logger.debug("GDELT store chronological_events skip: %s", ins_err)
                            break
                        logger.debug("GDELT event insert skip: %s", ins_err)
            conn.commit()
        except Exception as e:
            logger.debug("_store_gdelt_events_to_chronological: %s", e)
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    async def _save_rag_context(
        self,
        storyline_id: str,
        rag_context: dict[str, Any],
        domain: str | None = None,
    ):
        """Save RAG context. v8: when domain is set, use intelligence.storyline_rag_context (domain_key, storyline_id)."""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            now = datetime.now(timezone.utc)
            data = json.dumps(rag_context)

            if domain:
                domain_key = domain.replace("-", "_") if domain else "politics"
                cursor.execute(
                    """
                    INSERT INTO intelligence.storyline_rag_context (
                        domain_key, storyline_id, rag_data, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (domain_key, storyline_id)
                    DO UPDATE SET rag_data = EXCLUDED.rag_data, updated_at = EXCLUDED.updated_at
                """,
                    (domain_key, int(storyline_id), data, now, now),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO storyline_rag_context (
                        storyline_id, rag_data, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s)
                    ON CONFLICT (storyline_id)
                    DO UPDATE SET rag_data = EXCLUDED.rag_data, updated_at = EXCLUDED.updated_at
                """,
                    (storyline_id, data, now, now),
                )

            conn.commit()
            cursor.close()
            conn.close()
            logger.info(f"Saved RAG context for storyline {storyline_id} (domain={domain})")
        except Exception as e:
            logger.error(f"Error saving RAG context: {e}")

    async def get_rag_context(
        self,
        storyline_id: str,
        domain: str | None = None,
    ) -> dict[str, Any] | None:
        """Get RAG context for a storyline. v8: when domain is set, read from intelligence.storyline_rag_context."""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            if domain:
                cursor.execute(
                    """
                    SELECT rag_data FROM intelligence.storyline_rag_context
                    WHERE domain_key = %s AND storyline_id = %s
                """,
                    (domain.replace("-", "_"), int(storyline_id)),
                )
            else:
                cursor.execute(
                    """
                    SELECT rag_data FROM storyline_rag_context WHERE storyline_id = %s
                """,
                    (storyline_id,),
                )
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            if result and result.get("rag_data"):
                r = result["rag_data"]
                if isinstance(r, str):
                    return json.loads(r)
                if isinstance(r, dict):
                    return r
            return None

        except Exception as e:
            logger.error(f"Error getting RAG context: {e}")
            return None
