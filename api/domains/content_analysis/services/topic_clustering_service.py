"""
Topic Clustering and Auto-Tagging Service with Iterative Learning
Uses LLM to intelligently cluster articles by topic and learn from feedback
"""

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx
from config.settings import OLLAMA_HOST
from psycopg2.extras import Json, RealDictCursor
from config.runtime import env_bool, env_float, env_int, env_pop, env_set, env_setdefault, env_str

logger = logging.getLogger(__name__)


def _float_confidence(value: Any, default: float = 0.5) -> float:
    """Normalize DB Decimal / numeric confidence for arithmetic."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def default_batch_ollama_url() -> str:
    """
    When dual-host routing is on, structured-extraction batch calls use the CPU Ollama endpoint
    (same family as ``STRUCTURED_EXTRACTION``). Otherwise ``OLLAMA_HOST`` (single server).
    """
    if env_str("OLLAMA_DUAL_HOST_ROUTING_ENABLED", "false").lower() in (
        "1",
        "true",
        "yes",
    ):
        return env_str("OLLAMA_CPU_HOST", OLLAMA_HOST).rstrip("/")
    return OLLAMA_HOST.rstrip("/")


def default_gpu_batch_ollama_url() -> str:
    """
    GPU-heavy batch phases (topic clustering) use ``OLLAMA_GPU_HOST`` when dual-host routing is on.
    """
    if env_str("OLLAMA_DUAL_HOST_ROUTING_ENABLED", "false").lower() in (
        "1",
        "true",
        "yes",
    ):
        return env_str("OLLAMA_GPU_HOST", OLLAMA_HOST).rstrip("/")
    return OLLAMA_HOST.rstrip("/")


class TopicClusteringService:
    """
    Intelligent topic clustering service using LLM with iterative learning
    Now supports domain-aware operations via DomainAwareService
    """

    def __init__(
        self,
        db_config: dict[str, str],
        ollama_url: str | None = None,
        domain: str = "politics",
    ):
        """
        Initialize the topic clustering service

        Args:
            db_config: Database configuration dictionary
            ollama_url: URL of the Ollama service (default: GPU host when dual routing on, else OLLAMA_HOST)
            domain: Domain key (e.g., 'politics', 'finance', 'science-tech')
        """
        self.db_config = db_config
        self.ollama_url = (ollama_url or default_gpu_batch_ollama_url()).rstrip("/")
        self.model_name = "llama3.1:8b"
        self.timeout = 120  # 2 minutes timeout
        self.domain = domain
        self.schema = self._get_schema_name(domain)
        try:
            self.topic_auto_match_min_score = float(
                env_str("TOPIC_AUTO_MATCH_MIN_SCORE", "0.58")
            )
        except ValueError:
            self.topic_auto_match_min_score = 0.58

    def _get_schema_name(self, domain: str) -> str:
        """Resolve Postgres schema from domain key via domain_registry."""
        try:
            from shared.domain_registry import resolve_domain_schema

            return resolve_domain_schema(domain)
        except Exception:
            return resolve_domain_schema(domain)

    def _get_db_connection(self):
        """Get database connection from shared pool and set search_path to domain schema."""
        from shared.database.connection import get_db_connection

        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(f"SET search_path TO {self.schema}, public")
        return conn

    def record_topic_clustering_pass(self, article_id: int, outcome: str) -> None:
        """
        Mark an article as having completed a topic_clustering attempt (Monitor backlog + automation).

        Stored at ``articles.metadata.pipeline.topic_clustering`` (JSONB merge).
        """
        iso = datetime.now(timezone.utc).isoformat()
        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            cur.execute(
                f"""
                UPDATE {self.schema}.articles
                SET metadata =
                    COALESCE(metadata, '{{}}'::jsonb)
                    || jsonb_build_object(
                        'pipeline',
                        COALESCE(metadata->'pipeline', '{{}}'::jsonb)
                        || jsonb_build_object(
                            'topic_clustering',
                            COALESCE(metadata->'pipeline'->'topic_clustering', '{{}}'::jsonb)
                            || jsonb_build_object(
                                'last_pass_at', to_jsonb(%s::text),
                                'last_outcome', to_jsonb(%s::text)
                            )
                        )
                    )
                WHERE id = %s
                """,
                (iso, outcome, article_id),
            )
            conn.commit()
        except Exception as e:
            logger.warning("record_topic_clustering_pass failed for article %s: %s", article_id, e)
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    async def _call_ollama(self, prompt: str, system_prompt: str = None) -> str:
        """
        Make a call to Ollama API

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt for context

        Returns:
            Generated text response
        """
        try:
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,  # Lower temperature for more consistent results
                    "top_p": 0.9,
                    "num_predict": 500,  # 2-5 topics + keywords; 500 sufficient, faster than 1500
                },
            }

            if system_prompt:
                payload["system"] = system_prompt

            logger.info(f"🤖 Calling Ollama for topic clustering with model: {self.model_name}")

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.ollama_url}/api/generate", json=payload)

                if response.status_code == 200:
                    result = response.json()
                    response_text = result.get("response", "").strip()
                    logger.info("✅ Ollama response received for topic clustering")
                    return response_text
                else:
                    logger.error(f"❌ Ollama API error: {response.status_code} - {response.text}")
                    return ""

        except Exception as e:
            logger.error(f"❌ Ollama API error: {e}")
            return ""

    async def extract_topics_from_article(self, article: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Extract topics from a single article using LLM

        Args:
            article: Article dictionary with title, content, etc.

        Returns:
            List of topic dictionaries with name, confidence, and keywords
        """
        try:
            title = article.get("title", "")
            content = article.get("content", "") or article.get("excerpt", "")
            existing_topics = article.get("topics", []) or []

            # Limit content length for LLM
            content_preview = content[:5000] if len(content) > 5000 else content  # long-form body preview

            # Domain-specific context so the LLM knows what matters for this domain
            domain_hint = ""
            category_choices = "politics, business, technology, health, environment, international, sports, entertainment, other"
            try:
                from services.domain_synthesis_config import get_domain_synthesis_config

                cfg = get_domain_synthesis_config(self.domain)
                if cfg.focus_areas:
                    domain_hint = f" For this domain, prioritise topics related to: {', '.join(cfg.focus_areas[:8])}."
                if cfg.macro_subject_axes:
                    domain_hint += (
                        " When relevant, tie themes to these cross-field axes (keywords only; do not force): "
                        f"{', '.join(cfg.macro_subject_axes[:10])}."
                    )
                if cfg.llm_context:
                    domain_hint += f" {cfg.llm_context[:500]}"
                dk = (self.domain or "").lower().replace("_", "-")
                if dk in (
                    "artificial-intelligence",
                    "medicine",
                    "environment-climate",
                ):
                    category_choices = (
                        "technology, health, medicine, artificial_intelligence, biotechnology, genomics, "
                        "aerospace, energy, materials_science, quantum_computing, robotics, climate_science, "
                        "neuroscience, cybersecurity, environment, business, other"
                    )
            except Exception:
                pass

            system_prompt = (
                """You are an expert news analyst specializing in topic extraction and categorization.
Your task is to identify the main topics and themes in news articles.
Return your response as a JSON array of topics, each with: name, confidence (0-1), keywords (array), and category.
CRITICAL: Only extract topics that are EXPLICITLY discussed in this specific article. Do not include topics from other news. Each topic must be clearly mentioned in the article text. Never infer or hallucinate topics."""
                + domain_hint
            )

            prompt = (
                f"""Analyze the following news article and extract the main topics.

Article Title: {title}

Article Content:
{content_preview}

Existing Topics (if any): {json.dumps(existing_topics)}

Instructions:
1. Identify 2-5 main topics that are EXPLICITLY discussed in this article (each must be clearly mentioned in the text)
2. Do NOT include topics from other news stories, sidebars, or tangentially related events not in this article
3. For each topic, provide:
   - name: A clear, concise topic name (2-4 words)
   - confidence: Your confidence in this topic (0.0 to 1.0)
   - keywords: 3-5 related keywords
   - category: One of: """
                + category_choices
                + """

4. Focus on specific, meaningful topics (not generic terms like "news" or "article")
5. Consider the article's main subject, key entities, and themes
6. Do NOT include dates (e.g. "March 15", "2024"), times (e.g. "3pm"), or country names as topic names or keywords

Return ONLY a JSON array in this exact format:
[
  {
    "name": "Topic Name",
    "confidence": 0.85,
    "keywords": ["keyword1", "keyword2", "keyword3"],
    "category": "politics"
  }
]

JSON Response:"""
            )

            response = await self._call_ollama(prompt, system_prompt)

            if not response:
                return []

            # Extract JSON from response
            json_match = re.search(r"\[.*\]", response, re.DOTALL)
            if json_match:
                try:
                    topics = json.loads(json_match.group())
                    # Validate and clean topics
                    validated_topics = []
                    for topic in topics:
                        if isinstance(topic, dict) and "name" in topic:
                            validated_topics.append(
                                {
                                    "name": topic.get("name", "").strip(),
                                    "confidence": float(topic.get("confidence", 0.5)),
                                    "keywords": topic.get("keywords", []),
                                    "category": topic.get("category", "other"),
                                }
                            )
                    return validated_topics
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON from LLM response: {e}")
                    logger.debug(f"Response was: {response[:500]}")

            return []

        except Exception as e:
            logger.error(f"Error extracting topics from article: {e}")
            return []

    @staticmethod
    def _allow_fuzzy_topic_match(topic_name: str) -> bool:
        """Skip lexical similarity for very short single-token names (e.g. WHO, Fed) to limit false merges."""
        toks = re.findall(r"[a-z0-9']+", topic_name.lower())
        return not (len(toks) == 1 and len(toks[0]) <= 4)

    @staticmethod
    def select_pending_article_ids(
        cur,
        schema: str,
        *,
        batch_size: int = 20,
        use_pass_marker: bool = True,
        iterative: bool = False,
        confidence_threshold: float = 0.88,
        low_confidence_threshold: float = 0.7,
        signal_full_only: bool = True,
    ) -> list[int]:
        """Bounded backlog selection — LIMIT in SQL, no full-table fetch."""
        from shared.pipeline_article_selection import sql_order_created_at

        signal_sql = ""
        if signal_full_only:
            try:
                from shared.article_signal_gate import (
                    article_signal_enabled,
                    sql_article_signal_full_lane_filter,
                )

                if article_signal_enabled():
                    filt = sql_article_signal_full_lane_filter("a", schema)
                    if filt:
                        signal_sql = f" AND ({filt}) "
            except Exception:
                pass

        age_order = sql_order_created_at()
        if use_pass_marker and not iterative:
            cur.execute(
                f"""
                SELECT a.id
                FROM {schema}.articles a
                WHERE a.content IS NOT NULL
                  AND LENGTH(a.content) > 100
                  AND (
                    a.metadata->'pipeline'->'topic_clustering'->>'last_pass_at' IS NULL
                    OR TRIM(COALESCE(a.metadata->'pipeline'->'topic_clustering'->>'last_pass_at', '')) = ''
                  )
                  {signal_sql}
                ORDER BY a.created_at {age_order}
                LIMIT %s
                """,
                (batch_size,),
            )
            return [int(r[0]) for r in cur.fetchall()]

        cur.execute(
            f"""
            WITH article_confidence AS (
                SELECT
                    a.id,
                    COALESCE(AVG(atc.confidence_score), 0.0) AS avg_confidence,
                    (a.metadata->'pipeline'->'topic_clustering'->>'last_pass_at') AS pass_at
                FROM {schema}.articles a
                LEFT JOIN {schema}.article_topic_clusters atc ON a.id = atc.article_id
                WHERE a.content IS NOT NULL AND LENGTH(a.content) > 100
                  {signal_sql}
                GROUP BY a.id, pass_at
            )
            SELECT id
            FROM article_confidence
            WHERE avg_confidence < %s
              AND (
                pass_at IS NULL
                OR TRIM(COALESCE(pass_at, '')) = ''
                OR avg_confidence < %s
              )
            ORDER BY avg_confidence ASC, id ASC
            LIMIT %s
            """,
            (confidence_threshold, low_confidence_threshold, batch_size),
        )
        return [int(r[0]) for r in cur.fetchall()]

    async def assign_topics_to_article(
        self, article_id: int, topics: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Assign topics to an article via topic_clusters (legacy topics table is read-only)."""
        from shared.topic_cluster_store import assign_topics_to_clusters

        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            result = assign_topics_to_clusters(
                cur,
                self.schema,
                article_id,
                topics,
                min_match_score=self.topic_auto_match_min_score,
            )
            cur.execute(
                f"""
                UPDATE {self.schema}.articles
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (article_id,),
            )
            conn.commit()
            return result

        except Exception as e:
            logger.error(f"Error assigning topics to article {article_id}: {e}")
            if conn:
                conn.rollback()
            return {"success": False, "error": str(e)}
        finally:
            if conn:
                cur.close()
                conn.close()

    async def process_article(self, article_id: int) -> dict[str, Any]:
        """
        Process a single article: fast-lane match or LLM extract + cluster assignment.
        """
        conn = None
        try:
            from domains.content_analysis.services.topic_fast_match_service import apply_fast_match

            conn = self._get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute(
                f"""
                SELECT id, title, content, excerpt, topics,
                       published_at, source_domain
                FROM {self.schema}.articles
                WHERE id = %s
                """,
                (article_id,),
            )
            article = cur.fetchone()
            if not article:
                return {"success": False, "error": "Article not found"}

            article_dict = dict(article)

            # Fast lane — keyword / entity / trgm match against topic_clusters
            cur_plain = conn.cursor()
            try:
                fast_result = apply_fast_match(cur_plain, self.schema, article_id)
                if fast_result and fast_result.get("total_assigned", 0) > 0:
                    conn.commit()
                    self.record_topic_clustering_pass(article_id, "fast_lane_matched")
                    logger.info(
                        "Fast-lane topic match for article %s: %s clusters",
                        article_id,
                        fast_result.get("total_assigned", 0),
                    )
                    return {**fast_result, "success": True, "fast_lane": True}
                conn.rollback()
            except Exception as e:
                logger.debug("Fast-lane skipped for article %s: %s", article_id, e)
                conn.rollback()
            finally:
                cur_plain.close()

            logger.info(
                "Extracting topics (LLM) for article %s: %s",
                article_id,
                (article_dict.get("title") or "")[:50],
            )
            extracted_topics = await self.extract_topics_from_article(article_dict)

            if not extracted_topics:
                logger.warning("No topics extracted for article %s", article_id)
                self.record_topic_clustering_pass(article_id, "no_topics_extracted")
                return {
                    "success": True,
                    "article_id": article_id,
                    "assigned_topics": [],
                    "message": "No topics extracted",
                    "fast_lane": False,
                }

            cur.close()
            conn.close()
            conn = None

            assignment_result = await self.assign_topics_to_article(article_id, extracted_topics)
            assignment_result["fast_lane"] = False

            logger.info(
                "Processed article %s: %s topic clusters assigned",
                article_id,
                assignment_result.get("total_assigned", 0),
            )

            if assignment_result.get("success"):
                self.record_topic_clustering_pass(article_id, "topics_assigned")
            else:
                self.record_topic_clustering_pass(article_id, "assignment_failed")

            return assignment_result

        except Exception as e:
            logger.error(f"Error processing article {article_id} for topic clustering: {e}")
            return {"success": False, "error": str(e)}
        finally:
            if conn:
                cur.close()
                conn.close()

    def record_feedback(
        self,
        assignment_id: int,
        is_correct: bool,
        feedback_notes: str = None,
        validated_by: str = None,
    ) -> dict[str, Any]:
        """Record feedback on a legacy article_topic_assignment (read-only graph)."""
        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()

            cur.execute(
                f"""
                UPDATE {self.schema}.article_topic_assignments
                SET is_validated = TRUE,
                    is_correct = %s,
                    feedback_notes = %s,
                    validated_at = CURRENT_TIMESTAMP,
                    validated_by = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING topic_id
            """,
                (is_correct, feedback_notes, validated_by, assignment_id),
            )

            result = cur.fetchone()
            if not result:
                return {"success": False, "error": "Assignment not found"}

            topic_id = result[0]
            conn.commit()

            cur.execute(
                f"""
                SELECT accuracy_score, confidence_score, review_count,
                       correct_assignments, incorrect_assignments
                FROM {self.schema}.topics
                WHERE id = %s
            """,
                (topic_id,),
            )

            topic_metrics = cur.fetchone()

            return {
                "success": True,
                "assignment_id": assignment_id,
                "topic_id": topic_id,
                "updated_accuracy": float(topic_metrics[0]) if topic_metrics[0] else 0.5,
                "updated_confidence": float(topic_metrics[1]) if topic_metrics[1] else 0.5,
                "review_count": topic_metrics[2] or 0,
                "correct_assignments": topic_metrics[3] or 0,
                "incorrect_assignments": topic_metrics[4] or 0,
            }

        except Exception as e:
            logger.error(f"Error recording feedback for assignment {assignment_id}: {e}")
            if conn:
                conn.rollback()
            return {"success": False, "error": str(e)}
        finally:
            if conn:
                cur.close()
                conn.close()

    def get_topics_needing_review(
        self, threshold: float = 0.6, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Legacy topics review helper (topics table is historical)."""
        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute(
                """
                SELECT * FROM get_topics_needing_review(%s)
                LIMIT %s
            """,
                (threshold, limit),
            )

            topics = [dict(row) for row in cur.fetchall()]
            return topics

        except Exception as e:
            logger.error(f"Error getting topics needing review: {e}")
            return []
        finally:
            if conn:
                cur.close()
                conn.close()


@dataclass
class TopicClusterBatchResult:
    processed: int = 0
    failed: int = 0
    fast_lane_hits: int = 0
    llm_extractions: int = 0
    topics_created: int = 0
    topics_assigned: int = 0
    errors: list[str] = field(default_factory=list)


async def process_articles_batch(
    service: TopicClusteringService,
    article_ids: list[int],
    *,
    concurrency: int = 5,
) -> TopicClusterBatchResult:
    """Process articles in parallel with bounded concurrency."""
    result = TopicClusterBatchResult()
    if not article_ids:
        return result

    sem = asyncio.Semaphore(max(1, concurrency))

    async def _one(aid: int) -> None:
        async with sem:
            try:
                out = await service.process_article(aid)
                if out.get("success"):
                    result.processed += 1
                    if out.get("fast_lane"):
                        result.fast_lane_hits += 1
                    else:
                        result.llm_extractions += 1
                    result.topics_created += len(out.get("created_topics", []))
                    result.topics_assigned += int(out.get("total_assigned", 0) or 0)
                else:
                    result.failed += 1
                    err = out.get("error") or "unknown"
                    result.errors.append(f"{aid}: {err}")
            except Exception as e:
                result.failed += 1
                result.errors.append(f"{aid}: {e}")

    await asyncio.gather(*[_one(aid) for aid in article_ids])
    return result
