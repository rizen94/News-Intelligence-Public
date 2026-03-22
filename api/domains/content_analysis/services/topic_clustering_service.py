"""
Topic Clustering and Auto-Tagging Service with Iterative Learning
Uses LLM to intelligently cluster articles by topic and learn from feedback
"""

import json
import logging
import re
from typing import Any

import httpx
from psycopg2.extras import Json, RealDictCursor

logger = logging.getLogger(__name__)


class TopicClusteringService:
    """
    Intelligent topic clustering service using LLM with iterative learning
    Now supports domain-aware operations via DomainAwareService
    """

    def __init__(
        self,
        db_config: dict[str, str],
        ollama_url: str = "http://localhost:11434",
        domain: str = "politics",
    ):
        """
        Initialize the topic clustering service

        Args:
            db_config: Database configuration dictionary
            ollama_url: URL of the Ollama service
            domain: Domain key (e.g., 'politics', 'finance', 'science-tech')
        """
        self.db_config = db_config
        self.ollama_url = ollama_url
        self.model_name = "llama3.1:8b"
        self.timeout = 120  # 2 minutes timeout
        self.domain = domain
        self.schema = self._get_schema_name(domain)

    def _get_schema_name(self, domain: str) -> str:
        """Convert domain key to schema name"""
        return domain.replace("-", "_")

    def _get_db_connection(self):
        """Get database connection from shared pool and set search_path to domain schema."""
        from shared.database.connection import get_db_connection

        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(f"SET search_path TO {self.schema}, public")
        return conn

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
                if dk in ("science-tech", "sciencetech"):
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
        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()

            assigned_topics = []
            created_topics = []

            for topic_data in topics:
                topic_name = topic_data.get("name", "").strip()
                if not topic_name:
                    continue

                # Check if topic exists in domain schema
                cur.execute(
                    f"SELECT id, confidence_score, accuracy_score FROM {self.schema}.topics WHERE name = %s",
                    (topic_name,),
                )
                existing_topic = cur.fetchone()

                if existing_topic:
                    topic_id = existing_topic[0]
                    # Use existing topic's confidence as base, blend with new confidence
                    existing_confidence = existing_topic[1] or 0.5
                    new_confidence = topic_data.get("confidence", 0.5)
                    blended_confidence = (existing_confidence * 0.7) + (new_confidence * 0.3)
                else:
                    # Create new topic in domain schema
                    # Convert keywords list to JSONB
                    keywords_list = topic_data.get("keywords", [])
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
                            Json(keywords_list),  # Convert to JSONB
                            topic_data.get("confidence", 0.5),
                            True,
                            "active",
                        ),
                    )
                    topic_id = cur.fetchone()[0]
                    created_topics.append(topic_name)
                    blended_confidence = topic_data.get("confidence", 0.5)

                # Check if assignment already exists in domain schema
                cur.execute(
                    f"""
                    SELECT id FROM {self.schema}.article_topic_assignments
                    WHERE article_id = %s AND topic_id = %s
                """,
                    (article_id, topic_id),
                )

                if cur.fetchone():
                    # Update existing assignment in domain schema
                    cur.execute(
                        f"""
                        UPDATE {self.schema}.article_topic_assignments
                        SET confidence_score = %s,
                            relevance_score = %s,
                            assignment_context = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE article_id = %s AND topic_id = %s
                    """,
                        (
                            blended_confidence,
                            topic_data.get("confidence", 0.5),
                            Json(topic_data),
                            article_id,
                            topic_id,
                        ),
                    )
                else:
                    # Create new assignment in domain schema
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
                            topic_data.get("confidence", 0.5),
                            "auto",
                            Json(topic_data),
                            self.model_name,
                        ),
                    )

                assigned_topics.append(
                    {
                        "topic_id": topic_id,
                        "topic_name": topic_name,
                        "confidence": blended_confidence,
                    }
                )

            # Update article's updated_at in domain schema (topic names are in assignment_context on assignments)
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
        Process a single article: extract topics and assign them

        Args:
            article_id: ID of the article to process

        Returns:
            Dictionary with processing results
        """
        try:
            conn = self._get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Get article from this service's domain schema
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

            # Extract topics using LLM
            logger.info(
                f"🔍 Extracting topics for article {article_id}: {article_dict.get('title', '')[:50]}"
            )
            extracted_topics = await self.extract_topics_from_article(article_dict)

            if not extracted_topics:
                logger.warning(f"⚠️ No topics extracted for article {article_id}")
                return {
                    "success": True,
                    "article_id": article_id,
                    "assigned_topics": [],
                    "message": "No topics extracted",
                }

            # Assign topics
            assignment_result = await self.assign_topics_to_article(article_id, extracted_topics)

            logger.info(
                f"✅ Processed article {article_id}: {assignment_result.get('total_assigned', 0)} topics assigned"
            )

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
