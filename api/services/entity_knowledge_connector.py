"""
High-level entity–knowledge connector: one entry point to resolve an entity name
to a description and link from multiple sources (local Wikipedia, Wikipedia API,
Knowledge Graph, optional Wikidata). Call this instead of calling Wikipedia/KG
services directly so we can add or reorder sources in one place.

Usage:
  from services.entity_knowledge_connector import resolve_entity_knowledge

  result = resolve_entity_knowledge("Federal Reserve", entity_type="organization")
  if result:
      description = result["description"]
      url = result["url"]
      source = result["source"]  # "wikipedia" | "knowledge_graph" | ...
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Source keys callers can pass to resolve_entity_knowledge(sources=(...))
SOURCE_WIKIPEDIA = "wikipedia"
SOURCE_KNOWLEDGE_GRAPH = "knowledge_graph"


def resolve_entity_knowledge(
    name: str,
    entity_type: Optional[str] = None,
    sources: Optional[Tuple[str, ...]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Resolve an entity name to a description and link using configured sources.

    Tries each source in order; returns the first non-empty result so callers
    get a single, consistent shape. Use this for entity enrichment, backfill,
    and dossier synthesis instead of calling Wikipedia/KG services directly.

    Args:
        name: Entity canonical name or alias (e.g. "Federal Reserve", "GOP").
        entity_type: Optional hint ("person", "organization", etc.) for future
            disambiguation or source preference; not yet used.
        sources: Which sources to try, in order. Default: ("wikipedia", "knowledge_graph").
            Use ("wikipedia",) to avoid KG API calls.

    Returns:
        Dict with: description (str), url (str), title (str), source (str),
        wikipedia_page_id (int | None if from Wikipedia), raw (dict from source).
        None if no source returned a usable result.
    """
    if not name or not str(name).strip():
        return None
    name_clean = str(name).strip()
    if sources is None:
        sources = (SOURCE_WIKIPEDIA, SOURCE_KNOWLEDGE_GRAPH)

    for source in sources:
        if source == SOURCE_WIKIPEDIA:
            out = _resolve_wikipedia(name_clean)
        elif source == SOURCE_KNOWLEDGE_GRAPH:
            out = _resolve_knowledge_graph(name_clean)
            if out and (out.get("description") or out.get("extract")):
                try:
                    from services.wikipedia_knowledge_service import cache_knowledge_graph_result
                    cache_knowledge_graph_result(name_clean, out)
                except Exception:
                    pass
        else:
            logger.debug("Unknown entity knowledge source: %s", source)
            continue
        if out and (out.get("description") or out.get("extract")):
            return _normalize_result(out, source)
    return None


def _normalize_result(raw_out: Dict[str, Any], source: str) -> Dict[str, Any]:
    """Map source-specific dict to a common shape."""
    description = raw_out.get("description") or raw_out.get("extract") or ""
    if isinstance(description, str) and len(description) > 5000:
        description = description[:5000].rsplit(" ", 1)[0] + "…"
    return {
        "description": description,
        "url": raw_out.get("url") or "",
        "title": raw_out.get("title") or "",
        "source": source,
        "wikipedia_page_id": raw_out.get("page_id") if source == SOURCE_WIKIPEDIA else None,
        "raw": raw_out,
    }


def _resolve_wikipedia(name: str) -> Optional[Dict[str, Any]]:
    """Local wikipedia_knowledge first, then API search fallback."""
    try:
        from services.wikipedia_knowledge_service import lookup_entity_with_fallback
        summary = lookup_entity_with_fallback(name)
        if not summary or not (summary.get("extract") or summary.get("description")):
            return None
        return {
            "title": summary.get("title", ""),
            "extract": summary.get("extract", ""),
            "url": summary.get("url", ""),
            "page_id": summary.get("page_id"),
        }
    except Exception as e:
        logger.debug("Wikipedia resolve for %s: %s", name, e)
        return None


def _resolve_knowledge_graph(name: str) -> Optional[Dict[str, Any]]:
    """First hit from Google Knowledge Graph API (if key configured)."""
    try:
        from modules.ml.rag_external_services import KnowledgeGraphService
        import os
        api_key = os.environ.get("KG_API_KEY") or os.environ.get("GOOGLE_KNOWLEDGE_GRAPH_API_KEY")
        if not api_key or api_key in ("your_kg_api_key_here", ""):
            return None
        kg = KnowledgeGraphService(api_key)
        entities = kg.search_entities(name, limit=1)
        if not entities:
            return None
        e = entities[0]
        desc = e.get("detailed_description") or e.get("description") or ""
        if not desc:
            return None
        return {
            "title": e.get("name", ""),
            "description": desc,
            "url": e.get("url", ""),
        }
    except Exception as e:
        logger.debug("Knowledge Graph resolve for %s: %s", name, e)
        return None


def resolve_entity_knowledge_batch(
    names: List[str],
    sources: Optional[Tuple[str, ...]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Batch version: resolve multiple names. Returns dict name -> result (same shape
    as resolve_entity_knowledge). Only includes names that resolved; missing names
    are omitted. Uses local Wikipedia batch where possible to reduce API calls.
    """
    if not names:
        return {}
    # Prefer Wikipedia batch for Wikipedia source when it's first
    use_sources = sources or (SOURCE_WIKIPEDIA, SOURCE_KNOWLEDGE_GRAPH)
    result = {}
    if use_sources and use_sources[0] == SOURCE_WIKIPEDIA:
        try:
            from services.wikipedia_knowledge_service import lookup_batch
            found = lookup_batch(names)
            for n, summary in found.items():
                if summary and (summary.get("extract") or summary.get("description")):
                    result[n] = _normalize_result({
                        "title": summary.get("title", ""),
                        "extract": summary.get("extract", ""),
                        "url": summary.get("url", ""),
                        "page_id": summary.get("page_id"),
                    }, SOURCE_WIKIPEDIA)
        except Exception as e:
            logger.debug("Wikipedia batch resolve: %s", e)
        names = [n for n in names if n.strip() and n not in result]
    for name in names:
        if name in result:
            continue
        resolved = resolve_entity_knowledge(name, sources=use_sources)
        if resolved:
            result[name.strip()] = resolved
    return result
