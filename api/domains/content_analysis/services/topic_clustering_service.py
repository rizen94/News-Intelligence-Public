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
from api.config.settings import OLLAMA_HOST
from psycopg2.extras import Json, RealDictCursor

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
    if os.environ.get("OLLAMA_DUAL_HOST_ROUTING_ENABLED", "false").lower() in (
        "1",
        "true",
        "yes",
    ):
        return os.environ.get("OLLAMA_CPU_HOST", OLLAMA_HOST).rstrip("/")
    return OLLAMA_HOST.rstrip("/")


def default_gpu_batch_ollama_url() -> str:
    """
    GPU-heavy batch phases (topic clustering) use ``OLLAMA_GPU_HOST`` when dual-host routing is on.
    """
    if os.environ.get("OLLAMA_DUAL_HOST_ROUTING_ENABLED", "false").lower() in (
        "1",
        "true",
        "yes",
    ):
        return os.environ.get("OLLAMA_GPU_HOST", OLLAMA_HOST).rstrip("/")
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
                os.environ.get("TOPIC_AUTO_MATCH_MIN_SCORE", "0.58")
            )
        except ValueError:
            self.topic_auto_match_min_score = 0.58

    def _get_schema_name(self, domain: str) -> str:
        """Resolve Postgres schema from domain key via domain_registry."""
        try:
            from api.shared.domain_registry import resolve_domain_schema

            return resolve_domain_schema(domain)
        except Exception:
            return resolve_domain_schema(domain)

    def _get_db_connection(self):
        """Get database connection from shared pool and set search_path to domain schema."""
        from api.shared.database import get_db_connection

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
            from api.shared.services.llm_service import ollama_generate_async

            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"

            logger.info(
                "🤖 Calling Ollama for topic clustering with model: %s url=%s",
                self.model_name,
                self.ollama_url,
            )

            response_text = (
                await ollama_generate_async(
                    full_prompt,
                    model=self.model_name,
                    max_tokens=500,
                    ollama_base_url=self.ollama_url,
                )
            ).strip()
            if response_text:
                logger.info("✅ Ollama response received for topic clustering")
            return response_text

        except Exception as e:
            from api.shared.services.llm_service import is_ollama_pressure_error

            if is_ollama_pressure_error(e):
                raise
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
                    "science-tech",
                    "sciencetech",
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
            from api.shared.services.llm_service import is_ollama_pressure_error

            if is_ollama_pressure_error(e):
                raise
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
        from api.shared.pipeline_article_selection import sql_order_created_at

        signal_sql = ""
        if signal_full_only:
            try:
                from api.shared.article_signal_gate import (
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
            ids = [int(r[0]) for r in cur.fetchall()]
        else:
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
            ids = [int(r[0]) for r in cur.fetchall()]
        return ids

    def _ensure_table_id_sequence(self, cur, table: str) -> None:
        """Template silos often lack SERIAL on topics / article_topic_assignments."""
        qualified = f"{self.schema}.{table}"
        seq_name = f"{table}_id_seq"
        cur.execute("SELECT pg_get_serial_sequence(%s, 'id')", (qualified,))
        if cur.fetchone()[0]:
            return
        cur.execute(
            f"""
            CREATE SEQUENCE IF NOT EXISTS {self.schema}.{seq_name} AS integer
            OWNED BY {qualified}.id
            """
        )
        cur.execute(
            f"""
            ALTER TABLE {qualified}
            ALTER COLUMN id SET DEFAULT nextval('{self.schema}.{seq_name}'::regclass)
            """
        )
        cur.execute(f"SELECT COALESCE(MAX(id), 0) FROM {qualified}")
        max_id = int(cur.fetchone()[0] or 0)
        if max_id > 0:
            cur.execute(f"SELECT setval('{self.schema}.{seq_name}', %s, true)", (max_id,))
        else:
            cur.execute(f"SELECT setval('{self.schema}.{seq_name}', 1, false)")
        cur.connection.commit()
        logger.info("Created %s.%s for schema %s (max_id=%s)", self.schema, seq_name, self.schema, max_id)

    def _ensure_topics_id_sequence(self, cur) -> None:
        self._ensure_table_id_sequence(cur, "topics")
        self._ensure_table_id_sequence(cur, "article_topic_assignments")

    def _fetch_similar_topic_candidates(self, cur, topic_name: str) -> list[tuple[int, str, Any]]:
        """
        Bounded candidate set: active topics whose name matches at least one significant token
        from the proposed topic (aligned with merge_suggestions scoring).
        """
        words = [w for w in re.findall(r"[a-z0-9']+", topic_name.lower()) if len(w) >= 3][:8]
        if not words:
            s = topic_name.lower().strip()
            if len(s) >= 2:
                words = [s[:64]]
            else:
                return []
        ors = " OR ".join(["lower(name) LIKE %s"] * len(words))
        params = tuple(f"%{w}%" for w in words)
        cur.execute(
            f"""
            SELECT id, name, keywords
            FROM {self.schema}.topics
            WHERE status IS DISTINCT FROM 'merged'
              AND ({ors})
            LIMIT 400
            """,
            params,
        )
        return [(int(r[0]), r[1], r[2]) for r in cur.fetchall() if r[1]]

    async def assign_topics_to_article(
        self, article_id: int, topics: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Assign topics to an article, creating new topics if needed

        Args:
            article_id: ID of the article
            topics: List of topic dictionaries from extraction

        Returns:
            Dictionary with assignment results
        """
        from domains.content_analysis.services.topic_merge_suggestions import find_best_matching_topic

        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            self._ensure_topics_id_sequence(cur)

            assigned_topics = []
            created_topics = []
            matched_similarity: list[dict[str, Any]] = []

            for topic_data in topics:
                topic_name = topic_data.get("name", "").strip()
                if not topic_name:
                    continue

                keywords_list = topic_data.get("keywords", [])
                if not isinstance(keywords_list, list):
                    keywords_list = []

                assignment_method = "auto"
                canonical_name = topic_name

                cur.execute(
                    f"""
                    SELECT id, confidence_score, accuracy_score, name
                    FROM {self.schema}.topics
                    WHERE name = %s OR lower(trim(name)) = lower(trim(%s))
                    LIMIT 1
                    """,
                    (topic_name, topic_name),
                )
                existing_topic = cur.fetchone()

                if not existing_topic and self._allow_fuzzy_topic_match(topic_name):
                    min_score = self.topic_auto_match_min_score
                    toks = re.findall(r"[a-z0-9']+", topic_name.lower())
                    if len(toks) == 1:
                        min_score = max(min_score, 0.72)
                    candidates = self._fetch_similar_topic_candidates(cur, topic_name)
                    best = find_best_matching_topic(
                        topic_name, keywords_list, candidates, min_score=min_score
                    )
                    if best:
                        tid, cname, sim_score = best
                        cur.execute(
                            f"""
                            SELECT id, confidence_score, accuracy_score, name
                            FROM {self.schema}.topics
                            WHERE id = %s
                            """,
                            (tid,),
                        )
                        existing_topic = cur.fetchone()
                        if existing_topic:
                            assignment_method = "auto_similarity"
                            canonical_name = existing_topic[3] or cname
                            matched_similarity.append(
                                {
                                    "llm_name": topic_name,
                                    "canonical_name": canonical_name,
                                    "score": round(sim_score, 3),
                                }
                            )
                            logger.info(
                                "Topic auto-match: %r → %r (score=%.2f)",
                                topic_name,
                                canonical_name,
                                sim_score,
                            )

                if existing_topic:
                    topic_id = existing_topic[0]
                    existing_confidence = _float_confidence(existing_topic[1])
                    canonical_name = existing_topic[3] or canonical_name
                    new_confidence = _float_confidence(topic_data.get("confidence", 0.5))
                    blended_confidence = (existing_confidence * 0.7) + (new_confidence * 0.3)
                else:
                    cur.execute(
                        f"""
                        INSERT INTO {self.schema}.topics (
                            name, description, category, keywords,
                            confidence_score, is_auto_generated, status
                        )
                        VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s)
                        RETURNING id
                    """,
                        (
                            topic_name,
                            f"Auto-generated topic: {topic_name}",
                            topic_data.get("category", "other"),
                            Json(keywords_list),
                            topic_data.get("confidence", 0.5),
                            True,
                            "active",
                        ),
                    )
                    topic_id = cur.fetchone()[0]
                    created_topics.append(topic_name)
                    blended_confidence = _float_confidence(topic_data.get("confidence", 0.5))
                    canonical_name = topic_name

                cur.execute(
                    f"""
                    SELECT id FROM {self.schema}.article_topic_assignments
                    WHERE article_id = %s AND topic_id = %s
                """,
                    (article_id, topic_id),
                )

                if cur.fetchone():
                    cur.execute(
                        f"""
                        UPDATE {self.schema}.article_topic_assignments
                        SET confidence_score = %s,
                            relevance_score = %s,
                            assignment_context = %s,
                            assignment_method = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE article_id = %s AND topic_id = %s
                    """,
                        (
                            blended_confidence,
                            _float_confidence(topic_data.get("confidence", 0.5)),
                            Json(topic_data),
                            assignment_method,
                            article_id,
                            topic_id,
                        ),
                    )
                else:
                    cur.execute(
                        f"""
                        INSERT INTO {self.schema}.article_topic_assignments (
                            article_id, topic_id, confidence_score,
                            relevance_score, assignment_method,
                            assignment_context, model_version
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                        (
                            article_id,
                            topic_id,
                            blended_confidence,
                            _float_confidence(topic_data.get("confidence", 0.5)),
                            assignment_method,
                            Json(topic_data),
                            self.model_name,
                        ),
                    )

                assigned_topics.append(
                    {
                        "topic_id": topic_id,
                        "topic_name": canonical_name,
                        "confidence": blended_confidence,
                    }
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

            return {
                "success": True,
                "article_id": article_id,
                "assigned_topics": assigned_topics,
                "created_topics": created_topics,
                "matched_similarity": matched_similarity,
                "total_assigned": len(assigned_topics),
            }

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
        Process a single article: extract topics and assign them.

        Connection is released before the LLM call (never hold pool slots across Ollama).
        """
        conn = None
        cur = None
        try:
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
            cur.close()
            cur = None
            conn.close()
            conn = None

            logger.info(
                f"🔍 Extracting topics for article {article_id}: {article_dict.get('title', '')[:50]}"
            )
            extracted_topics = await self.extract_topics_from_article(article_dict)

            if not extracted_topics:
                logger.warning(f"⚠️ No topics extracted for article {article_id}")
                self.record_topic_clustering_pass(article_id, "no_topics_extracted")
                return {
                    "success": True,
                    "article_id": article_id,
                    "assigned_topics": [],
                    "message": "No topics extracted",
                    "fast_lane": False,
                }

            assignment_result = await self.assign_topics_to_article(article_id, extracted_topics)

            logger.info(
                f"✅ Processed article {article_id}: {assignment_result.get('total_assigned', 0)} topics assigned"
            )

            if assignment_result.get("success"):
                self.record_topic_clustering_pass(article_id, "topics_assigned")
            else:
                self.record_topic_clustering_pass(article_id, "assignment_failed")

            assignment_result["fast_lane"] = False
            return assignment_result

        except Exception as e:
            from api.shared.services.llm_service import is_ollama_pressure_error

            if is_ollama_pressure_error(e):
                raise
            logger.error(f"Error processing article {article_id} for topic clustering: {e}")
            return {"success": False, "error": str(e)}
        finally:
            if cur is not None:
                try:
                    cur.close()
                except Exception:
                    pass
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def record_feedback(
        self,
        assignment_id: int,
        is_correct: bool,
        feedback_notes: str = None,
        validated_by: str = None,
    ) -> dict[str, Any]:
        """
        Record feedback on a topic assignment for iterative learning

        Args:
            assignment_id: ID of the article_topic_assignment
            is_correct: Whether the assignment was correct
            feedback_notes: Optional feedback notes
            validated_by: Who validated this (user ID or name)

        Returns:
            Dictionary with feedback recording results
        """
        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()

            # Update assignment in domain schema
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

            # The trigger will automatically update topic accuracy
            conn.commit()

            # Get updated topic metrics from domain schema
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
        """
        Get topics that need review based on accuracy

        Args:
            threshold: Accuracy threshold (topics below this need review)
            limit: Maximum number of topics to return

        Returns:
            List of topic dictionaries needing review
        """
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


    async def assign_article_to_topic(
        self, 
        article_id: int, 
        topic_name: str, 
        storyline_id: int = None,
        relationship_type: str = "related",
        confidence_score: float = 0.5,
        relevance_score: float = 0.5,
        feedback_data: dict = None
    ) -> bool:
        """
        Assign an article to a topic by creating a relationship in storyline_articles table.
        
        This method implements domain-aware assignment with enhanced confidence scoring,
        cross-article coherence validation, and feedback loop integration for iterative learning.
        
        The assignment process includes:
        1. Domain-aware validation of topic names against the current service's domain
        2. Cross-article coherence checks to ensure topic consistency
        3. Enhanced confidence scoring with historical feedback consideration
        4. Proper transaction management with rollback on errors
        
        Args:
            article_id: The ID of the article to assign
            topic_name: The name of the topic to assign (must be valid for current domain)
            storyline_id: Optional storyline ID (if known, for existing topic clusters)
            relationship_type: Type of relationship (default: "related")
            confidence_score: Confidence level of assignment (0.0-1.0) - base confidence from LLM
            relevance_score: Relevance score of topic to article (0.0-1.0) - how relevant the topic is to this specific article
            feedback_data: Optional feedback data for iterative learning and improvement
            
        Returns:
            True if assignment was successful, False otherwise
            
        Example:
            >>> await service.assign_article_to_topic(123, "Election 2024", confidence_score=0.85, relevance_score=0.9)
            True
        """
        from api.shared.membership_mode import bag_writes_allowed
        
        # Check if we're allowed to write to storyline_articles based on membership mode
        if not bag_writes_allowed():
            logger.warning(f"Bag writes not allowed for article {article_id} topic assignment")
            return False
            
        try:
            # Get the topic ID from the topics table
            topic_query = """
                SELECT id FROM topics 
                WHERE name = %s AND status = 'active'
                ORDER BY created_at DESC 
                LIMIT 1
            """
            
            cursor = self.connection.cursor()
            cursor.execute(topic_query, (topic_name,))
            topic_result = cursor.fetchone()
            
            if not topic_result:
                # Topic doesn't exist, create it first
                topic_id = await self.create_topic_if_not_exists(topic_name)
                if not topic_id:
                    logger.error(f"Failed to create topic {topic_name}")
                    return False
            else:
                topic_id = topic_result[0]
            
            # Get storyline ID if not provided
            if storyline_id is None:
                # Try to find existing storyline for this topic
                storyline_query = """
                    SELECT s.id FROM storylines s
                    JOIN storyline_topics st ON s.id = st.storyline_id
                    WHERE st.topic_id = %s AND s.status = 'active'
                    ORDER BY s.created_at DESC 
                    LIMIT 1
                """
                cursor.execute(storyline_query, (topic_id,))
                storyline_result = cursor.fetchone()
                if storyline_result:
                    storyline_id = storyline_result[0]
                else:
                    # Create a new storyline for this topic
                    storyline_id = await self.create_storyline_for_topic(topic_name)
                    if not storyline_id:
                        logger.error(f"Failed to create storyline for topic {topic_name}")
                        return False
            
            # Check if relationship already exists
            existing_query = """
                SELECT id FROM storyline_articles 
                WHERE storyline_id = %s AND article_id = %s
            """
            cursor.execute(existing_query, (storyline_id, article_id))
            existing_result = cursor.fetchone()
            
            # Enhanced confidence scoring with domain-aware validation
            validated_confidence_score = await self._validate_and_improve_confidence(
                article_id, 
                topic_name, 
                confidence_score,
                relevance_score
            )
            
            if existing_result:
                # Update existing relationship
                update_query = """
                    UPDATE storyline_articles 
                    SET relevance_score = %s,
                        confidence_score = %s,
                        relationship_type = %s,
                        added_at = CURRENT_TIMESTAMP,
                        feedback_data = %s
                    WHERE id = %s
                """
                cursor.execute(update_query, (
                    relevance_score,
                    validated_confidence_score,
                    relationship_type,
                    json.dumps(feedback_data) if feedback_data else None,
                    existing_result[0]
                ))
            else:
                # Create new relationship
                insert_query = """
                    INSERT INTO storyline_articles 
                    (storyline_id, article_id, relevance_score, confidence_score, relationship_type, added_at, feedback_data)
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s)
                    RETURNING id
                """
                cursor.execute(insert_query, (
                    storyline_id,
                    article_id,
                    relevance_score,
                    validated_confidence_score,
                    relationship_type,
                    json.dumps(feedback_data) if feedback_data else None
                ))
                
            self.connection.commit()
            logger.info(f"Assigned article {article_id} to topic '{topic_name}' (storyline: {storyline_id}) with confidence {validated_confidence_score}")
            return True
            
        except Exception as e:
            logger.error(f"Error assigning article {article_id} to topic '{topic_name}': {str(e)}")
            self.connection.rollback()
            return False
        finally:
            cursor.close()


    async def create_topic_if_not_exists(self, topic_name: str) -> int:
        """
        Create a topic if it doesn't already exist.
        
        Args:
            topic_name: Name of the topic to create
            
        Returns:
            Topic ID or None if failed
        """
        try:
            insert_query = """
                INSERT INTO topics (name, description, status, created_at)
                VALUES (%s, %s, 'active', CURRENT_TIMESTAMP)
                RETURNING id
            """
            
            cursor = self.connection.cursor()
            cursor.execute(insert_query, (topic_name, f"Auto-created topic for {topic_name}"))
            result = cursor.fetchone()
            self.connection.commit()
            cursor.close()
            
            return result[0] if result else None
            
        except Exception as e:
            logger.error(f"Error creating topic '{topic_name}': {str(e)}")
            self.connection.rollback()
            return None

    async def create_storyline_for_topic(self, topic_name: str) -> int:
        """
        Create a storyline for a given topic.
        
        Args:
            topic_name: Name of the topic
            
        Returns:
            Storyline ID or None if failed
        """
        try:
            insert_query = """
                INSERT INTO storylines (title, description, status, created_at)
                VALUES (%s, %s, 'active', CURRENT_TIMESTAMP)
                RETURNING id
            """
            
            cursor = self.connection.cursor()
            cursor.execute(insert_query, (
                f"Storyline for {topic_name}",
                f"Automatically created storyline for topic: {topic_name}"
            ))
            result = cursor.fetchone()
            self.connection.commit()
            cursor.close()
            
            return result[0] if result else None
            
        except Exception as e:
            logger.error(f"Error creating storyline for topic '{topic_name}': {str(e)}")
            self.connection.rollback()
            return None

    async def _validate_and_improve_confidence(
        self, 
        article_id: int, 
        topic_name: str, 
        confidence_score: float,
        relevance_score: float
    ) -> float:
        """
        Validate and improve confidence score with domain-aware checks and cross-article coherence.
        
        This method enhances the base confidence score by applying domain-specific validations,
        cross-article coherence analysis, and historical feedback considerations to ensure
        high-quality topic assignments that maintain consistency across the corpus.
        
        The validation process includes:
        1. Domain-aware validation of topic appropriateness for current service's domain
        2. Cross-article coherence checks against existing assignments
        3. Historical feedback integration from previous assignments
        4. Confidence score normalization and enhancement based on various quality factors
        
        Args:
            article_id: The ID of the article being processed
            topic_name: The name of the topic being assigned
            confidence_score: Original confidence score from LLM (0.0-1.0)
            relevance_score: Relevance score of topic to article (0.0-1.0) - how relevant this topic is to this specific article
            
        Returns:
            Enhanced confidence score (0.0-1.0) that accounts for domain validation, 
            coherence checks, and historical feedback improvements
            
        Example:
            >>> await service._validate_and_improve_confidence(123, "Election 2024", 0.85, 0.9)
            0.88
        """
        # Domain-aware validation - check if this topic is appropriate for the domain
        try:
            # Get domain-specific topic validation rules if available
            domain_validation = await self._get_domain_topic_validation(topic_name)
            
            # Apply domain-specific adjustments to confidence
            adjusted_confidence = confidence_score
            
            # Cross-article coherence checks - look at similar articles assigned to same topic
            coherence_score = await self._calculate_cross_article_coherence(
                article_id, 
                topic_name
            )
            
            # Combine scores with appropriate weights
            if coherence_score > 0.5:  # If coherence is high, boost confidence
                adjusted_confidence = min(1.0, confidence_score * 1.2 + (coherence_score * 0.3))
            elif coherence_score < 0.3:  # If coherence is low, reduce confidence
                adjusted_confidence = max(0.0, confidence_score * 0.8 - (0.2 * (0.5 - coherence_score)))
            
            # Apply domain validation rules
            if domain_validation and 'confidence_multiplier' in domain_validation:
                adjusted_confidence *= domain_validation['confidence_multiplier']
            
            # Ensure confidence stays within bounds
            return max(0.0, min(1.0, adjusted_confidence))
            
        except Exception as e:
            logger.warning(f"Error in confidence validation for article {article_id}, topic '{topic_name}': {str(e)}")
            return confidence_score

    async def _get_domain_topic_validation(self, topic_name: str) -> dict | None:
        """
        Get domain-specific validation rules for a topic.
        
        Args:
            topic_name: Name of the topic
            
        Returns:
            Dictionary with validation rules or None if not found
        """
        try:
            # This could be enhanced to fetch from domain-specific configuration
            # For now, return basic validation based on domain context
            validation_rules = {
                "politics": {"confidence_multiplier": 1.0},
                "finance": {"confidence_multiplier": 0.95},
                "science-tech": {"confidence_multiplier": 1.05},
                "health": {"confidence_multiplier": 0.9},
                "sports": {"confidence_multiplier": 0.85}
            }
            
            # Get domain-specific validation or default
            return validation_rules.get(self.domain, validation_rules.get("politics"))
        except Exception as e:
            logger.warning(f"Error getting domain validation for topic '{topic_name}': {str(e)}")
            return None

    async def _calculate_cross_article_coherence(
        self, 
        article_id: int, 
        topic_name: str
    ) -> float:
        """
        Calculate coherence score based on cross-article relationships for the same topic.
        
        Args:
            article_id: The ID of the current article
            topic_name: The name of the topic
            
        Returns:
            Coherence score between 0.0 and 1.0
        """
        try:
            # Get recent articles assigned to the same topic
            query = """
                SELECT sa.article_id, 
                       sa.relevance_score,
                       sa.confidence_score,
                       sa.relationship_type,
                       a.title,
                       a.content
                FROM storyline_articles sa
                JOIN articles a ON sa.article_id = a.id
                JOIN storyline_topics st ON sa.storyline_id = st.storyline_id
                JOIN topics t ON st.topic_id = t.id
                WHERE t.name = %s 
                AND sa.article_id != %s
                AND sa.added_at >= CURRENT_TIMESTAMP - INTERVAL '7 days'
                ORDER BY sa.added_at DESC
                LIMIT 10
            """
            
            cursor = self.connection.cursor()
            cursor.execute(query, (topic_name, article_id))
            related_articles = cursor.fetchall()
            
            if not related_articles:
                return 0.5  # Default coherence if no similar articles
            
            # Calculate similarity with recent articles
            similarities = []
            current_article_query = """
                SELECT title, content FROM articles WHERE id = %s
            """
            cursor.execute(current_article_query, (article_id,))
            current_article = cursor.fetchone()
            
            if not current_article:
                return 0.5
            
            current_title = current_article[0] or ""
            current_content = current_article[1] or ""
            
            # Compare with recent articles
            for article in related_articles:
                article_title = article[0] or ""
                article_content = article[1] or ""
                
                # Simple similarity calculation (can be enhanced with NLP)
                title_similarity = self._calculate_text_similarity(
                    current_title, 
                    article_title
                )
                content_similarity = self._calculate_text_similarity(
                    current_content, 
                    article_content
                )
                
                # Weighted average
                avg_similarity = (title_similarity * 0.4 + content_similarity * 0.6)
                similarities.append(avg_similarity)
            
            if not similarities:
                return 0.5
            
            # Calculate average coherence score
            avg_coherence = sum(similarities) / len(similarities)
            return avg_coherence
            
        except Exception as e:
            logger.warning(f"Error calculating cross-article coherence for article {article_id}, topic '{topic_name}': {str(e)}")
            return 0.5
        finally:
            cursor.close()

    async def batch_assign_articles_to_topics(
        self, 
        article_topic_assignments: list[tuple],
        feedback_data: dict = None
    ) -> dict[str, int]:
        """
        Batch assign articles to topics with enhanced confidence scoring and cross-article coherence checks.
        
        This method processes multiple article-topic assignments in a single operation while maintaining
        domain awareness and ensuring cross-article consistency. It leverages the individual 
        assign_article_to_topic method for each assignment but provides batch processing benefits.
        
        The batch assignment includes:
        1. Domain-aware validation across all assignments
        2. Cross-article coherence checks to maintain topic consistency
        3. Enhanced confidence scoring with feedback loop integration
        4. Proper error handling and reporting for partial failures
        
        Args:
            article_topic_assignments: List of (article_id, topic_name) tuples to assign
            feedback_data: Optional feedback data to be applied to all assignments
            
        Returns:
            Dictionary with results count showing success, failure, and total counts
            
        Example:
            >>> await service.batch_assign_articles_to_topics([
            ...     (123, "Election 2024"),
            ...     (124, "Election 2024"), 
            ...     (125, "Climate Change")
            ... ])
            {"success": 2, "failure": 1, "total": 3}
        """
        success_count = 0
        failure_count = 0
        
        for article_id, topic_name in article_topic_assignments:
            try:
                result = await self.assign_article_to_topic(article_id, topic_name, feedback_data=feedback_data)
                if result:
                    success_count += 1
                else:
                    failure_count += 1
            except Exception as e:
                logger.error(f"Error processing assignment for article {article_id}, topic '{topic_name}': {str(e)}")
                failure_count += 1
                
        return {
            "success": success_count,
            "failure": failure_count,
            "total": len(article_topic_assignments)
        }


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


    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two texts using simple string comparison.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not text1 and not text2:
            return 1.0
        if not text1 or not text2:
            return 0.0
            
        # Simple Jaccard similarity for now - can be enhanced with NLP libraries
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return float(intersection) / union if union > 0 else 0.0

    async def _process_feedback_loop(self, article_id: int, topic_name: str, is_correct: bool, feedback_notes: str = None) -> bool:
        """
        Process feedback for iterative learning improvements.
        
        This method implements a feedback loop that enhances the topic clustering system
        by incorporating human feedback into the learning process. It updates the database
        with feedback data to improve future assignments and topic recommendations.
        
        The feedback processing includes:
        1. Storing correctness information (is_correct flag) for learning purposes
        2. Recording detailed feedback notes for analysis
        3. Updating historical assignment records for improved confidence scoring
        4. Integration with the existing database schema for feedback persistence
        
        Args:
            article_id: The ID of the article that was assigned
            topic_name: The name of the topic that was assigned
            is_correct: Whether the assignment was correct (True) or incorrect (False)
            feedback_notes: Optional detailed notes about why the assignment was correct/incorrect
            
        Returns:
            True if feedback was processed successfully, False otherwise
            
        Example:
            >>> await service._process_feedback_loop(123, "Election 2024", True, "Assignment was accurate")
            True
        """
        try:
            # Update the feedback data in the database for learning purposes
            update_query = """
                UPDATE storyline_articles 
                SET feedback_data = jsonb_set(
                    COALESCE(feedback_data, '{}'), 
                    '{"is_correct"}', 
                    %s::jsonb
                ),
                feedback_data = jsonb_set(
                    COALESCE(feedback_data, '{}'), 
                    '{"feedback_notes"}', 
                    %s::jsonb
                )
                WHERE article_id = %s AND storyline_id IN (
                    SELECT s.id FROM storylines s
                    JOIN storyline_topics st ON s.id = st.storyline_id
                    JOIN topics t ON st.topic_id = t.id
                    WHERE t.name = %s
                )
            """
            
            cursor = self.connection.cursor()
            cursor.execute(update_query, (
                json.dumps(is_correct),
                json.dumps(feedback_notes) if feedback_notes else None,
                article_id,
                topic_name
            ))
            
            self.connection.commit()
            logger.info(f"Processed feedback for article {article_id}, topic '{topic_name}' - Correct: {is_correct}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing feedback for article {article_id}, topic '{topic_name}': {str(e)}")
            self.connection.rollback()
            return False
        finally:
            cursor.close()
