"""
RAG Generation Module - LLM Generation and Context Building
LLM integration, prompt generation, and answer generation
Extracted from enhanced_rag_service.py
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import requests

from .base import BaseRAGService

logger = logging.getLogger(__name__)

# Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
EMBEDDING_MODEL = os.getenv("RAG_EMBEDDING_MODEL", "nomic-embed-text")
LLM_MODEL = os.getenv("RAG_LLM_MODEL", "llama3.1:8b")

# RAG parameters
TOP_K_ARTICLES = 10
TOP_K_ENTITIES = 5
CONTEXT_WINDOW_HOURS = 72
MIN_RELEVANCE_SCORE = 0.3


@dataclass
class RAGChunk:
    """A chunk of content for RAG retrieval"""

    content: str
    source_type: str  # article, entity, terminology, external
    source_id: str | None = None
    source_title: str | None = None
    source_url: str | None = None
    relevance_score: float = 0.0
    domain: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RAGResult:
    """Result from RAG retrieval and generation"""

    query: str
    domain: str
    answer: str
    chunks_used: list[RAGChunk]
    domain_context: Any | None = None  # DomainContext type
    confidence: float = 0.0
    sources_cited: list[str] = field(default_factory=list)
    processing_time_ms: float = 0.0


class RAGGenerationModule:
    """
    RAG Generation Module - LLM generation and context building

    Provides:
    - Embedding generation
    - Context prompt building
    - LLM answer generation
    - Confidence scoring
    """

    def __init__(self, base_service: BaseRAGService):
        """
        Initialize generation module

        Args:
            base_service: Base RAG service for database access
        """
        self.base_service = base_service
        self.db_config = base_service.db_config
        self.embedding_cache: dict[str, list[float]] = {}
        self.logger = logging.getLogger(__name__)

    def get_db_connection(self):
        """Get database connection from shared pool."""
        from shared.database.connection import get_db_connection as _get_conn

        return _get_conn()

    def generate_embedding(self, text: str) -> list[float] | None:
        """Generate embedding for text using Ollama"""
        if not text:
            return None

        # Check cache
        cache_key = f"{EMBEDDING_MODEL}:{hash(text[:500])}"
        if cache_key in self.embedding_cache:
            return self.embedding_cache[cache_key]

        try:
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/embeddings",
                json={
                    "model": EMBEDDING_MODEL,
                    "prompt": text[:2000],  # Limit context
                },
                timeout=30,
            )
            if response.status_code == 200:
                embedding = response.json().get("embedding", [])
                if embedding:
                    self.embedding_cache[cache_key] = embedding
                    return embedding
        except Exception as e:
            self.logger.warning(f"Embedding generation failed: {e}")

        return None

    def cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        if not vec1 or not vec2:
            return 0.0

        a = np.array(vec1)
        b = np.array(vec2)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(np.dot(a, b) / (norm_a * norm_b))

    def generate_context_prompt(
        self, query: str, chunks: list[RAGChunk], domain_context: Any | None = None
    ) -> str:
        """
        Generate a context-enriched prompt for the LLM.

        Args:
            query: The query to answer
            chunks: Retrieved RAG chunks
            domain_context: Domain context (optional)

        Returns:
            Formatted prompt string
        """
        # Build context sections
        context_parts = []

        # Domain context
        if domain_context:
            context_parts.append("=== DOMAIN CONTEXT ===")
            if hasattr(domain_context, "historical_context"):
                context_parts.append(domain_context.historical_context)

            if hasattr(domain_context, "timeline_context") and domain_context.timeline_context:
                context_parts.append(f"\nTimeline: {domain_context.timeline_context}")

            if (
                hasattr(domain_context, "geopolitical_context")
                and domain_context.geopolitical_context
            ):
                context_parts.append(f"\nGeopolitical: {domain_context.geopolitical_context}")

            if hasattr(domain_context, "economic_context") and domain_context.economic_context:
                context_parts.append(f"\nEconomic: {domain_context.economic_context}")

        # Source chunks
        article_chunks = [c for c in chunks if c.source_type == "article"]
        if article_chunks:
            context_parts.append("\n=== RELEVANT NEWS ARTICLES ===")
            for i, chunk in enumerate(article_chunks[:5], 1):
                context_parts.append(f"\n[Source {i}]: {chunk.content[:800]}")

        # Entity knowledge
        entity_chunks = [c for c in chunks if c.source_type == "entity"]
        if entity_chunks:
            context_parts.append("\n=== DOMAIN ENTITIES ===")
            for chunk in entity_chunks[:3]:
                context_parts.append(f"\n{chunk.content}")

        # Terminology
        term_chunks = [c for c in chunks if c.source_type == "terminology"]
        if term_chunks:
            context_parts.append("\n=== KEY TERMS ===")
            for chunk in term_chunks[:5]:
                context_parts.append(f"- {chunk.content}")

        context = "\n".join(context_parts)

        # Build final prompt
        domain_name = (
            domain_context.domain
            if domain_context and hasattr(domain_context, "domain")
            else "general"
        )
        prompt = f"""You are an expert analyst for the {domain_name} domain.
Use the following context to answer the question accurately and comprehensively.
Cite specific sources when possible.

{context}

=== QUESTION ===
{query}

=== INSTRUCTIONS ===
1. Provide a clear, well-structured answer
2. Reference specific articles or entities when relevant
3. Note any important context or caveats
4. Keep the response focused and informative

Answer:"""

        return prompt

    def generate_answer(self, prompt: str, max_tokens: int = 500) -> tuple[str, float]:
        """
        Generate an answer using the LLM.

        Args:
            prompt: The prompt to send to the LLM
            max_tokens: Maximum tokens to generate

        Returns:
            Tuple of (answer, confidence_score)
        """
        try:
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": LLM_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": 0.7,
                    },
                },
                timeout=60,
            )

            if response.status_code == 200:
                result = response.json()
                answer = result.get("response", "").strip()

                # Estimate confidence based on response characteristics
                confidence = 0.5
                if len(answer) > 100:
                    confidence += 0.2
                if "[Source" in answer or "according to" in answer.lower():
                    confidence += 0.1
                if answer and not answer.endswith("..."):
                    confidence += 0.1

                return answer, min(confidence, 0.95)

        except Exception as e:
            self.logger.error(f"LLM generation failed: {e}")

        return "Unable to generate a response at this time.", 0.0
