"""
RAG Query API Routes
Provides domain-aware retrieval-augmented generation endpoints.

Features:
- Domain-specific context queries
- Storyline analysis
- Topic enrichment
- Knowledge base search
- Cross-domain insights
"""

from fastapi import APIRouter, HTTPException, Path, Query, Body
from typing import Dict, Any, List, Optional
from shared.domain_registry import DOMAIN_PATH_PATTERN
from pydantic import BaseModel, Field
import logging

from services.rag import get_enhanced_rag_service, RAGResult
from services.domain_knowledge_service import get_domain_knowledge_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["RAG Queries"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class RAGQueryRequest(BaseModel):
    """Request model for RAG query"""
    query: str = Field(..., min_length=5, max_length=1000, description="The question or topic to analyze")
    hours: int = Field(72, ge=1, le=720, description="Hours of article history to consider")
    max_chunks: int = Field(10, ge=1, le=25, description="Maximum context chunks to use")


class RAGQueryResponse(BaseModel):
    """Response model for RAG query"""
    success: bool
    query: str
    domain: str
    answer: str
    confidence: float
    sources_cited: List[str]
    domain_entities: List[Dict[str, Any]]
    key_terms: Dict[str, str]
    related_topics: List[str]
    historical_context: str
    processing_time_ms: float


class StorylineAnalysisRequest(BaseModel):
    """Request model for storyline analysis"""
    analysis_type: str = Field("summary", description="Type: summary, impact, context, or full")


class TopicContextResponse(BaseModel):
    """Response model for topic context"""
    topic: str
    domain: str
    entities: List[Dict[str, Any]]
    terminology: Dict[str, str]
    historical_context: str
    related_topics: List[str]
    external_sources: List[Dict[str, str]]
    knowledge_base_matches: List[Dict[str, Any]]


class KnowledgeSearchRequest(BaseModel):
    """Request model for knowledge base search"""
    query: str = Field(..., min_length=2, max_length=200)
    limit: int = Field(10, ge=1, le=50)


# =============================================================================
# RAG QUERY ENDPOINTS
# =============================================================================

@router.post("/{domain}/rag/query", response_model=RAGQueryResponse)
async def rag_query(
    request: RAGQueryRequest,
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN)
):
    """
    Execute a domain-aware RAG query.

    This endpoint:
    1. Retrieves relevant articles from the domain
    2. Enriches with domain-specific knowledge (entities, terminology)
    3. Generates a contextual answer using the LLM
    4. Returns the answer with source citations and domain context
    """
    try:
        rag_service = get_enhanced_rag_service()
        result = rag_service.query(
            domain=domain,
            query=request.query,
            hours=request.hours,
            max_chunks=request.max_chunks
        )

        # Extract domain context details
        domain_context = result.domain_context
        entities = []
        key_terms = {}
        related_topics = []
        historical_context = ""

        if domain_context:
            entities = [
                {
                    "name": e.name,
                    "type": e.entity_type,
                    "importance": e.importance,
                }
                for e in domain_context.entities_found[:10]
            ]
            key_terms = domain_context.domain_terminology
            related_topics = domain_context.related_topics
            historical_context = domain_context.historical_context

        return RAGQueryResponse(
            success=True,
            query=result.query,
            domain=domain,
            answer=result.answer,
            confidence=result.confidence,
            sources_cited=result.sources_cited,
            domain_entities=entities,
            key_terms=key_terms,
            related_topics=related_topics,
            historical_context=historical_context,
            processing_time_ms=result.processing_time_ms
        )

    except Exception as e:
        logger.error(f"RAG query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/rag/quick", response_model=Dict[str, Any])
async def rag_quick_query(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    q: str = Query(..., min_length=5, max_length=500, description="Quick query"),
    hours: int = Query(48, ge=1, le=168)
):
    """
    Quick RAG query using GET method for simple questions.
    """
    try:
        rag_service = get_enhanced_rag_service()
        result = rag_service.query(
            domain=domain,
            query=q,
            hours=hours,
            max_chunks=5  # Smaller for quick queries
        )

        return {
            "success": True,
            "query": q,
            "answer": result.answer,
            "confidence": result.confidence,
            "sources": result.sources_cited[:3],
        }

    except Exception as e:
        logger.error(f"Quick RAG query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# STORYLINE ANALYSIS ENDPOINTS
# =============================================================================

@router.post("/{domain}/rag/storyline/{storyline_id}/analyze", response_model=Dict[str, Any])
async def analyze_storyline_with_rag(
    storyline_id: int = Path(..., gt=0),
    request: StorylineAnalysisRequest = Body(...),
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN)
):
    """
    Analyze a storyline using RAG with domain knowledge.

    Analysis types:
    - summary: Key developments and current state
    - impact: Potential consequences and significance
    - context: Historical background and related events
    - full: Comprehensive analysis combining all aspects
    """
    try:
        rag_service = get_enhanced_rag_service()

        if request.analysis_type == "full":
            # Combine multiple analysis types
            summary = rag_service.analyze_storyline(domain, storyline_id, "summary")
            impact = rag_service.analyze_storyline(domain, storyline_id, "impact")
            context = rag_service.analyze_storyline(domain, storyline_id, "context")

            return {
                "success": True,
                "storyline_id": storyline_id,
                "analysis_type": "full",
                "summary": summary.get("analysis", ""),
                "impact": impact.get("analysis", ""),
                "context": context.get("analysis", ""),
                "domain_entities": summary.get("domain_entities", []),
                "sources_cited": list(set(
                    summary.get("sources_cited", []) +
                    impact.get("sources_cited", []) +
                    context.get("sources_cited", [])
                )),
                "confidence": (
                    summary.get("confidence", 0) +
                    impact.get("confidence", 0) +
                    context.get("confidence", 0)
                ) / 3,
            }
        else:
            result = rag_service.analyze_storyline(
                domain=domain,
                storyline_id=storyline_id,
                analysis_type=request.analysis_type
            )

            if "error" in result:
                raise HTTPException(status_code=404, detail=result["error"])

            return {
                "success": True,
                **result
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Storyline analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# TOPIC CONTEXT ENDPOINTS
# =============================================================================

@router.get("/{domain}/rag/topic/{topic_name}", response_model=TopicContextResponse)
async def get_topic_context(
    topic_name: str = Path(..., min_length=2),
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN)
):
    """
    Get enriched context for a topic.

    Returns domain knowledge including:
    - Relevant entities
    - Terminology definitions
    - Historical context
    - Related topics
    - External sources
    """
    try:
        rag_service = get_enhanced_rag_service()
        result = rag_service.get_topic_context(domain, topic_name)

        return TopicContextResponse(**result)

    except Exception as e:
        logger.error(f"Topic context error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# KNOWLEDGE BASE ENDPOINTS
# =============================================================================

@router.post("/{domain}/rag/knowledge/search", response_model=Dict[str, Any])
async def search_knowledge_base(
    request: KnowledgeSearchRequest,
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN)
):
    """
    Search the domain knowledge base.

    Searches entities and terminology for relevant matches.
    """
    try:
        knowledge_service = get_domain_knowledge_service()
        results = knowledge_service.search_knowledge_base(
            domain=domain,
            query=request.query,
            limit=request.limit
        )

        return {
            "success": True,
            "domain": domain,
            "query": request.query,
            "results": results,
            "total_found": len(results),
        }

    except Exception as e:
        logger.error(f"Knowledge search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/rag/knowledge/entities", response_model=Dict[str, Any])
async def list_domain_entities(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    entity_type: Optional[str] = Query(None, description="Filter by entity type")
):
    """
    List all entities in the domain knowledge base.
    """
    try:
        knowledge_service = get_domain_knowledge_service()
        schema = domain.replace('-', '_')
        kb = knowledge_service.knowledge_bases.get(domain, knowledge_service.knowledge_bases.get(schema, {}))
        entities = kb.get('entities', {})

        result = []
        for key, entity in entities.items():
            if entity_type and entity.entity_type != entity_type:
                continue
            result.append({
                "name": entity.name,
                "type": entity.entity_type,
                "aliases": entity.aliases,
                "description": entity.description,
                "importance": entity.importance,
            })

        # Sort by importance
        result.sort(key=lambda e: e['importance'], reverse=True)

        return {
            "success": True,
            "domain": domain,
            "entity_type_filter": entity_type,
            "entities": result,
            "total": len(result),
        }

    except Exception as e:
        logger.error(f"List entities error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/rag/knowledge/terminology", response_model=Dict[str, Any])
async def get_domain_terminology(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN)
):
    """
    Get all terminology definitions for a domain.
    """
    try:
        knowledge_service = get_domain_knowledge_service()
        schema = domain.replace('-', '_')
        kb = knowledge_service.knowledge_bases.get(domain, knowledge_service.knowledge_bases.get(schema, {}))
        terminology = kb.get('terminology', {})

        return {
            "success": True,
            "domain": domain,
            "terminology": terminology,
            "total_terms": len(terminology),
        }

    except Exception as e:
        logger.error(f"Get terminology error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/rag/knowledge/sources", response_model=Dict[str, Any])
async def get_domain_sources(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    source_type: Optional[str] = Query(None, description="Filter by source type")
):
    """
    Get external reference sources for a domain.
    """
    try:
        knowledge_service = get_domain_knowledge_service()
        sources = knowledge_service.get_relevant_sources(domain, source_type)

        return {
            "success": True,
            "domain": domain,
            "source_type_filter": source_type,
            "sources": sources,
            "total": len(sources),
        }

    except Exception as e:
        logger.error(f"Get sources error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# CROSS-DOMAIN INSIGHTS
# =============================================================================

@router.post("/rag/cross-domain", response_model=Dict[str, Any])
async def cross_domain_query(
    request: RAGQueryRequest
):
    """
    Execute a query across all domains for cross-domain insights.

    Useful for topics that span politics, finance, and technology.
    """
    try:
        rag_service = get_enhanced_rag_service()
        domains = ['politics', 'finance', 'science-tech']

        results = {}
        all_entities = []
        all_sources = []

        for domain in domains:
            result = rag_service.query(
                domain=domain,
                query=request.query,
                hours=request.hours,
                max_chunks=request.max_chunks // 2  # Split across domains
            )
            results[domain] = {
                "answer": result.answer,
                "confidence": result.confidence,
                "sources": result.sources_cited,
            }
            if result.domain_context:
                all_entities.extend([
                    {"domain": domain, "name": e.name, "type": e.entity_type}
                    for e in result.domain_context.entities_found[:3]
                ])
            all_sources.extend(result.sources_cited)

        # Generate combined insight
        combined_prompt = f"""Based on insights from multiple domains (politics, finance, technology), provide a synthesized answer to: {request.query}

Politics perspective: {results['politics']['answer'][:300]}
Finance perspective: {results['finance']['answer'][:300]}
Technology perspective: {results['science-tech']['answer'][:300]}

Synthesize these perspectives into a cohesive cross-domain insight:"""

        combined_answer, confidence = rag_service.generate_answer(combined_prompt)

        return {
            "success": True,
            "query": request.query,
            "synthesized_answer": combined_answer,
            "domain_results": results,
            "cross_domain_entities": all_entities[:10],
            "all_sources": list(set(all_sources)),
            "overall_confidence": sum(r["confidence"] for r in results.values()) / len(domains),
        }

    except Exception as e:
        logger.error(f"Cross-domain query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ENTITY LOOKUP
# =============================================================================

@router.get("/{domain}/rag/entity/{entity_name}", response_model=Dict[str, Any])
async def get_entity_details(
    entity_name: str = Path(..., min_length=2),
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN)
):
    """
    Get detailed information about a specific entity.
    """
    try:
        knowledge_service = get_domain_knowledge_service()
        entity = knowledge_service.get_entity_details(domain, entity_name)

        if not entity:
            raise HTTPException(
                status_code=404,
                detail=f"Entity '{entity_name}' not found in {domain} knowledge base"
            )

        return {
            "success": True,
            "domain": domain,
            "entity": {
                "name": entity.name,
                "type": entity.entity_type,
                "aliases": entity.aliases,
                "description": entity.description,
                "importance": entity.importance,
                "related_entities": entity.related_entities,
                "external_refs": entity.external_refs,
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Entity lookup error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

