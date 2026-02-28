"""
RAG Service - Consolidated RAG Operations
Combines basic RAG, advanced retrieval, LLM generation, and domain knowledge

This service consolidates:
- rag_service.py (basic RAG with Wikipedia/GDELT)
- enhanced_rag_service.py (enhanced RAG with domain knowledge)
- enhanced_rag_retrieval.py (advanced retrieval techniques)

All functionality is now available through a single RAGService class.
"""

from .base import BaseRAGService
from .retrieval import RAGRetrievalModule
from .generation import RAGGenerationModule, RAGChunk, RAGResult
from .domain import RAGDomainModule

import logging
import os
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Configuration
OLLAMA_BASE_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434')
EMBEDDING_MODEL = os.getenv('RAG_EMBEDDING_MODEL', 'nomic-embed-text')
LLM_MODEL = os.getenv('RAG_LLM_MODEL', 'llama3.1:8b')

# RAG parameters
TOP_K_ARTICLES = 10
TOP_K_ENTITIES = 5
CONTEXT_WINDOW_HOURS = 72
MIN_RELEVANCE_SCORE = 0.3


class RAGService(BaseRAGService):
    """
    Consolidated RAG Service
    
    Provides all RAG functionality:
    - Basic RAG operations (Wikipedia, GDELT)
    - Advanced retrieval (semantic, hybrid, query expansion)
    - LLM generation and context building
    - Domain knowledge integration
    
    Usage:
        from services.rag import RAGService
        
        service = RAGService()
        
        # Basic operations
        context = await service.enhance_storyline_context(storyline_id, title, articles)
        
        # Advanced retrieval
        articles = await service.retrieval.retrieve_relevant_articles(query)
        
        # Domain-aware query
        result = service.query(domain='politics', query='What is happening with...')
        
        # Storyline analysis
        analysis = service.analyze_storyline(domain='politics', storyline_id=1)
    """
    
    def __init__(self, db_config: dict = None):
        """Initialize consolidated RAG service"""
        super().__init__(db_config)
        self._retrieval_module = None
        self._generation_module = None
        self._domain_module = None
    
    @property
    def retrieval(self) -> RAGRetrievalModule:
        """Get retrieval module (lazy initialization)"""
        if self._retrieval_module is None:
            self._retrieval_module = RAGRetrievalModule(self)
        return self._retrieval_module
    
    @property
    def generation(self) -> RAGGenerationModule:
        """Get generation module (lazy initialization)"""
        if self._generation_module is None:
            self._generation_module = RAGGenerationModule(self)
        return self._generation_module
    
    @property
    def domain(self) -> RAGDomainModule:
        """Get domain module (lazy initialization)"""
        if self._domain_module is None:
            self._domain_module = RAGDomainModule(self)
        return self._domain_module
    
    def query(
        self,
        domain: str,
        query: str,
        hours: int = CONTEXT_WINDOW_HOURS,
        max_chunks: int = TOP_K_ARTICLES
    ) -> RAGResult:
        """
        Execute a full RAG query with domain knowledge enrichment.
        
        Args:
            domain: Domain name (politics, finance, science-tech)
            query: Query string
            hours: Hours of history to search
            max_chunks: Maximum chunks to retrieve
        
        Returns:
            RAGResult with answer, chunks, and metadata
        """
        from datetime import datetime
        
        start_time = datetime.now()

        # Generate query embedding
        query_embedding = self.generation.generate_embedding(query)

        # Retrieve domain knowledge
        knowledge_chunks, domain_context = self.domain.retrieve_domain_knowledge(domain, query)

        # Retrieve relevant articles
        article_chunks = self.domain.retrieve_relevant_articles(
            domain=domain,
            query=query,
            query_embedding=query_embedding,
            hours=hours,
            limit=max_chunks
        )

        # Combine and rank chunks
        all_chunks = article_chunks + knowledge_chunks
        all_chunks.sort(key=lambda c: c.relevance_score, reverse=True)
        selected_chunks = all_chunks[:max_chunks + TOP_K_ENTITIES]

        # Generate context-enriched prompt
        prompt = self.generation.generate_context_prompt(query, selected_chunks, domain_context)

        # Generate answer
        answer, confidence = self.generation.generate_answer(prompt)

        # Extract cited sources
        sources = []
        for chunk in selected_chunks:
            if chunk.source_title and chunk.source_type == 'article':
                sources.append(chunk.source_title)

        processing_time = (datetime.now() - start_time).total_seconds() * 1000

        return RAGResult(
            query=query,
            domain=domain,
            answer=answer,
            chunks_used=selected_chunks,
            domain_context=domain_context,
            confidence=confidence,
            sources_cited=sources[:5],
            processing_time_ms=processing_time
        )
    
    def analyze_storyline(
        self,
        domain: str,
        storyline_id: int,
        analysis_type: str = "summary"
    ) -> Dict[str, Any]:
        """
        Analyze a storyline using RAG with domain knowledge.
        
        Args:
            domain: Domain name
            storyline_id: Storyline ID
            analysis_type: Type of analysis (summary, impact, context)
        
        Returns:
            Dictionary with analysis results
        """
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        schema = domain.replace('-', '_')

        try:
            conn = self.get_db_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"SET search_path TO {schema}, public")

                # Get storyline info
                cur.execute("""
                    SELECT s.*, 
                           array_agg(DISTINCT a.title) as article_titles,
                           array_agg(DISTINCT a.content) as article_contents
                    FROM storylines s
                    LEFT JOIN storyline_articles sa ON s.id = sa.storyline_id
                    LEFT JOIN articles a ON sa.article_id = a.id
                    WHERE s.id = %s
                    GROUP BY s.id
                """, (storyline_id,))

                storyline = cur.fetchone()

                if not storyline:
                    return {"error": "Storyline not found"}

                conn.close()

            # Build analysis query based on type
            if analysis_type == "summary":
                query = f"Summarize the key developments in the storyline: {storyline.get('title', 'Unknown')}"
            elif analysis_type == "impact":
                query = f"What is the potential impact and significance of: {storyline.get('title', 'Unknown')}"
            elif analysis_type == "context":
                query = f"Provide historical and contextual background for: {storyline.get('title', 'Unknown')}"
            else:
                query = f"Analyze the storyline: {storyline.get('title', 'Unknown')}"

            # Run RAG query
            result = self.query(domain, query)

            return {
                "storyline_id": storyline_id,
                "storyline_title": storyline.get('title'),
                "analysis_type": analysis_type,
                "analysis": result.answer,
                "domain_entities": [
                    {"name": e.name, "type": e.entity_type if hasattr(e, 'entity_type') else 'unknown'}
                    for e in (result.domain_context.entities_found if result.domain_context and hasattr(result.domain_context, 'entities_found') else [])
                ],
                "sources_cited": result.sources_cited,
                "confidence": result.confidence,
                "processing_time_ms": result.processing_time_ms,
            }

        except Exception as e:
            logger.error(f"Storyline analysis error: {e}")
            return {"error": str(e)}
    
    def get_db_connection(self):
        """Get database connection"""
        return psycopg2.connect(**self.db_config)


# Global instance for backward compatibility
_rag_service_instance = None


def get_rag_service() -> RAGService:
    """
    Get global RAG service instance (backward compatibility)
    
    Note: This maintains compatibility with code that uses:
    from services.rag_service import get_rag_service
    """
    global _rag_service_instance
    if _rag_service_instance is None:
        _rag_service_instance = RAGService()
    return _rag_service_instance


def get_enhanced_rag_service() -> RAGService:
    """
    Get enhanced RAG service instance (backward compatibility)
    
    Note: This maintains backward compatibility for code that used:
    from services.enhanced_rag_service import get_enhanced_rag_service
    
    The enhanced_rag_service.py file has been consolidated into services/rag/__init__.py.
    """
    return get_rag_service()


# Export all public classes and functions
__all__ = [
    'RAGService',
    'BaseRAGService',
    'RAGRetrievalModule',
    'RAGGenerationModule',
    'RAGDomainModule',
    'RAGChunk',
    'RAGResult',
    'get_rag_service',
    'get_enhanced_rag_service',
]

