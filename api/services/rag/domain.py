"""
RAG Domain Module - Domain Knowledge Integration
Domain-specific context retrieval and entity extraction
Extracted from enhanced_rag_service.py
"""

import logging
from typing import Any

from psycopg2.extras import RealDictCursor

from .base import BaseRAGService
from .generation import RAGChunk

logger = logging.getLogger(__name__)

# RAG parameters
TOP_K_ARTICLES = 10
TOP_K_ENTITIES = 5
CONTEXT_WINDOW_HOURS = 72
MIN_RELEVANCE_SCORE = 0.3


class RAGDomainModule:
    """
    RAG Domain Module - Domain knowledge integration

    Provides:
    - Domain context retrieval
    - Entity extraction and chunking
    - Terminology extraction
    - Domain-aware article retrieval
    """

    def __init__(self, base_service: BaseRAGService):
        """
        Initialize domain module

        Args:
            base_service: Base RAG service for database access
        """
        self.base_service = base_service
        self.db_config = base_service.db_config
        self.knowledge_service = None
        self._load_knowledge_service()
        self.logger = logging.getLogger(__name__)

    def _load_knowledge_service(self):
        """Load domain knowledge service"""
        try:
            from services.domain_knowledge_service import (
                DomainContext,
                DomainEntity,
                DomainKnowledgeService,
                get_domain_knowledge_service,
            )

            self.knowledge_service = get_domain_knowledge_service()
        except ImportError:
            logger.warning("Domain knowledge service not available")
            self.knowledge_service = None

    def get_db_connection(self):
        """Get database connection from shared pool."""
        from shared.database.connection import get_db_connection as _get_conn

        return _get_conn()

    def retrieve_relevant_articles(
        self,
        domain: str,
        query: str,
        query_embedding: list[float] | None = None,
        hours: int = CONTEXT_WINDOW_HOURS,
        limit: int = TOP_K_ARTICLES,
    ) -> list[RAGChunk]:
        """
        Retrieve relevant articles using hybrid search.

        Args:
            domain: Domain name (politics, finance, science-tech)
            query: Search query
            query_embedding: Optional query embedding for semantic search
            hours: Hours of history to search
            limit: Maximum number of articles

        Returns:
            List of RAGChunk objects
        """
        schema = domain.replace("-", "_")
        chunks = []

        try:
            conn = self.get_db_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Set search path
                cur.execute(f"SET search_path TO {schema}, public")

                # Get articles with embeddings
                cur.execute(
                    """
                    SELECT
                        a.id,
                        a.title,
                        a.content,
                        a.url,
                        a.source_name,
                        a.published_at,
                        a.embedding_vector,
                        a.extracted_entities
                    FROM articles a
                    WHERE a.published_at >= NOW() - INTERVAL '%s hours'
                      AND a.content IS NOT NULL
                      AND LENGTH(a.content) > 100
                    ORDER BY a.published_at DESC
                    LIMIT %s
                """,
                    (hours, limit * 3),
                )  # Get more for filtering

                articles = cur.fetchall()

                for article in articles:
                    relevance = 0.0

                    # Semantic similarity if we have embeddings
                    if query_embedding and article.get("embedding_vector"):
                        try:
                            from .generation import RAGGenerationModule

                            # Create temporary generation module for cosine similarity
                            gen_module = RAGGenerationModule(self.base_service)
                            article_emb = article["embedding_vector"]
                            if isinstance(article_emb, str):
                                import json

                                article_emb = json.loads(article_emb)
                            relevance = gen_module.cosine_similarity(query_embedding, article_emb)
                        except Exception:
                            pass

                    # Keyword matching fallback
                    if relevance < 0.1:
                        query_words = set(query.lower().split())
                        content_words = set(article.get("content", "").lower().split())
                        title_words = set(article.get("title", "").lower().split())
                        matches = len(query_words & (content_words | title_words))
                        relevance = min(matches / max(len(query_words), 1) * 0.5, 0.5)

                    if relevance >= MIN_RELEVANCE_SCORE or len(chunks) < limit:
                        chunk = RAGChunk(
                            content=self._create_article_chunk(article),
                            source_type="article",
                            source_id=str(article["id"]),
                            source_title=article.get("title", "Unknown"),
                            source_url=article.get("url"),
                            relevance_score=relevance,
                            domain=domain,
                            metadata={
                                "source_name": article.get("source_name"),
                                "published_at": str(article.get("published_at")),
                                "entities": article.get("extracted_entities"),
                            },
                        )
                        chunks.append(chunk)

                conn.close()

        except Exception as e:
            logger.error(f"Error retrieving articles: {e}")

        # Sort by relevance and limit
        chunks.sort(key=lambda c: c.relevance_score, reverse=True)
        return chunks[:limit]

    def _create_article_chunk(self, article: dict) -> str:
        """Create a formatted chunk from an article"""
        title = article.get("title", "No title")
        content = article.get("content", "")[:1000]  # Limit content
        source = article.get("source_name", "Unknown source")
        date = article.get("published_at", "")

        return f"Article: {title}\nSource: {source}\nDate: {date}\n\n{content}"

    def retrieve_domain_knowledge(
        self, domain: str, query: str
    ) -> tuple[list[RAGChunk], Any | None]:
        """
        Retrieve domain-specific knowledge chunks.

        Args:
            domain: Domain name
            query: Search query

        Returns:
            Tuple of (chunks, domain_context)
        """
        chunks = []

        if not self.knowledge_service:
            return chunks, None

        # Get domain context
        domain_context = self.knowledge_service.enrich_rag_context(domain=domain, text=query)

        # Add entity chunks
        if hasattr(domain_context, "entities_found"):
            for entity in domain_context.entities_found[:TOP_K_ENTITIES]:
                chunk = RAGChunk(
                    content=self._create_entity_chunk(entity),
                    source_type="entity",
                    source_id=entity.name,
                    source_title=entity.name,
                    relevance_score=entity.importance if hasattr(entity, "importance") else 0.5,
                    domain=domain,
                    metadata={
                        "entity_type": entity.entity_type
                        if hasattr(entity, "entity_type")
                        else "unknown",
                        "aliases": entity.aliases if hasattr(entity, "aliases") else [],
                    },
                )
                chunks.append(chunk)

        # Add terminology chunks
        if hasattr(domain_context, "domain_terminology"):
            for term, definition in domain_context.domain_terminology.items():
                chunk = RAGChunk(
                    content=f"Term: {term}\nDefinition: {definition}",
                    source_type="terminology",
                    source_id=term,
                    source_title=term,
                    relevance_score=0.4,
                    domain=domain,
                )
                chunks.append(chunk)

        return chunks, domain_context

    def _create_entity_chunk(self, entity: Any) -> str:
        """Create a formatted chunk from a domain entity"""
        parts = [
            f"Entity: {entity.name}",
            f"Type: {entity.entity_type if hasattr(entity, 'entity_type') else 'unknown'}",
        ]

        if hasattr(entity, "aliases") and entity.aliases:
            parts.append(f"Also known as: {', '.join(entity.aliases)}")

        if hasattr(entity, "description") and entity.description:
            parts.append(f"Description: {entity.description}")

        if hasattr(entity, "related_entities") and entity.related_entities:
            parts.append(f"Related to: {', '.join(entity.related_entities)}")

        return "\n".join(parts)

    def get_topic_context(self, domain: str, topic_name: str) -> dict[str, Any]:
        """
        Get enriched context for a topic.

        Args:
            domain: Domain name
            topic_name: Topic to get context for

        Returns:
            Dictionary with topic context
        """
        if not self.knowledge_service:
            return {
                "topic": topic_name,
                "domain": domain,
                "error": "Domain knowledge service not available",
            }

        # Get domain knowledge
        context = self.knowledge_service.enrich_rag_context(domain, topic_name)

        # Search knowledge base
        kb_results = self.knowledge_service.search_knowledge_base(domain, topic_name)

        return {
            "topic": topic_name,
            "domain": domain,
            "entities": [
                {
                    "name": e.name,
                    "type": e.entity_type if hasattr(e, "entity_type") else "unknown",
                    "description": e.description if hasattr(e, "description") else "",
                    "importance": e.importance if hasattr(e, "importance") else 0.5,
                }
                for e in (context.entities_found if hasattr(context, "entities_found") else [])
            ],
            "terminology": context.domain_terminology
            if hasattr(context, "domain_terminology")
            else {},
            "historical_context": context.historical_context
            if hasattr(context, "historical_context")
            else "",
            "related_topics": context.related_topics if hasattr(context, "related_topics") else [],
            "external_sources": context.external_sources
            if hasattr(context, "external_sources")
            else [],
            "knowledge_base_matches": kb_results,
        }
