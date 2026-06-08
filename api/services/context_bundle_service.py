"""
Unified context bundle for storyline/arc synthesis — structured SQL memory + pgvector retrieval.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from shared.database.connection import get_db_connection
from shared.domain_registry import resolve_domain_schema

from services.embeddings_worker_service import search_embedding_chunks
from services.slow_report_service import _build_structured_citations as _build_arc_structured_citations
from services.storyline_historical_context_service import (
    build_storyline_historical_context,
    render_historical_context_for_llm,
)

logger = logging.getLogger(__name__)


def _parse_metadata(val: Any) -> dict[str, Any]:
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _build_storyline_structured_citations(historical_context: dict[str, Any]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    if not historical_context.get("success"):
        return citations

    for fact in historical_context.get("versioned_facts") or []:
        citations.append(
            {
                "citation_key": f"VF-{fact.get('id')}",
                "source_type": "versioned_fact",
                "source_table": "intelligence.versioned_facts",
                "source_row_id": fact.get("id"),
                "quote": (fact.get("fact_text") or "")[:500],
                "event_date": fact.get("valid_from"),
                "layer": "living",
            }
        )

    spine = historical_context.get("chronological_spine") or {}
    for ev in spine.get("events") or []:
        citations.append(
            {
                "citation_key": f"CE-{ev.get('id')}",
                "source_type": "chronological_event",
                "source_table": "public.chronological_events",
                "source_row_id": ev.get("id"),
                "quote": (ev.get("description") or ev.get("title") or "")[:500],
                "event_date": ev.get("event_date"),
                "layer": "living",
            }
        )

    for art in historical_context.get("articles") or []:
        citations.append(
            {
                "citation_key": f"ART-{art.get('id')}",
                "source_type": "article",
                "source_table": "articles",
                "source_row_id": art.get("id"),
                "quote": (art.get("title") or art.get("summary") or "")[:500],
                "event_date": art.get("published_at"),
                "layer": "living",
            }
        )
    return citations


def _build_retrieval_citations(retrieval_chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for idx, chunk in enumerate(retrieval_chunks):
        meta = _parse_metadata(chunk.get("metadata"))
        source_type = chunk.get("source_type") or "embedding_chunk"
        source_id = chunk.get("source_id") or ""
        row_id = meta.get("article_id") or meta.get("reference_event_id") or meta.get("context_id")
        if row_id is None and source_type == "article" and ":" in source_id:
            try:
                row_id = int(source_id.split(":", 1)[1])
            except (TypeError, ValueError):
                row_id = None

        key_parts = [source_type, str(source_id), str(chunk.get("chunk_index", idx))]
        citations.append(
            {
                "citation_key": f"RAG-{'-'.join(key_parts)}",
                "source_type": source_type,
                "source_table": "intelligence.embedding_chunks",
                "source_row_id": row_id,
                "quote": (chunk.get("chunk_text") or "")[:500],
                "event_date": chunk.get("event_date"),
                "layer": "retrieval",
                "similarity": chunk.get("similarity"),
                "domain_key": chunk.get("domain_key"),
            }
        )
    return citations


def _load_storyline_article_ids(domain_key: str, storyline_id: int) -> list[int]:
    schema = resolve_domain_schema(domain_key)
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT article_id FROM {schema}.storyline_articles
                WHERE storyline_id = %s
                """,
                (storyline_id,),
            )
            return [int(row[0]) for row in cur.fetchall() if row and row[0] is not None]
    except Exception as e:
        logger.debug("context_bundle storyline_article_ids %s: %s", storyline_id, e)
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _default_retrieval_query(
    *,
    query: str,
    historical_context: dict[str, Any] | None,
) -> str:
    q = (query or "").strip()
    if q:
        return q
    if historical_context and historical_context.get("success"):
        title = historical_context.get("storyline_title") or ""
        entities = historical_context.get("entities") or []
        names = " ".join(e.get("name", "") for e in entities[:5] if e.get("name"))
        return f"{title} {names}".strip()
    return "recent developments policy geopolitics"


def _render_for_prompt(
    *,
    historical_context: dict[str, Any] | None,
    retrieval_chunks: list[dict[str, Any]],
    structured_citations: list[dict[str, Any]],
) -> str:
    parts: list[str] = []

    if historical_context and historical_context.get("success"):
        rendered = historical_context.get("rendered") or render_historical_context_for_llm(
            historical_context
        )
        if rendered:
            parts.append("## Structured historical memory")
            parts.append(rendered.strip())

    cite_lines = [
        f"- [{c['citation_key']}] ({c.get('layer', 'data')}) {c.get('quote', '')[:200]}"
        for c in structured_citations[:30]
        if c.get("citation_key")
    ]
    if cite_lines:
        parts.append("\n## Structured citations (reference keys)")
        parts.extend(cite_lines)

    retrieval_lines = [
        f"- ({r.get('source_type', '?')}, sim={r.get('similarity', 0):.3f}) "
        f"{(r.get('chunk_text') or '')[:180]}"
        for r in retrieval_chunks[:12]
    ]
    if retrieval_lines:
        parts.append("\n## Retrieval snippets (pgvector)")
        parts.extend(retrieval_lines)

    return "\n".join(parts).strip()


class ContextBundleService:
    """Build unified context for briefing and storyline synthesis prompts."""

    async def build_context_bundle(
        self,
        *,
        storyline_id: int | None = None,
        arc_id: str | None = None,
        query: str,
        domain_key: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        max_retrieval_chunks: int = 12,
        max_historical_events: int = 50,
    ) -> dict[str, Any]:
        historical_context: dict[str, Any] | None = None
        structured_citations: list[dict[str, Any]] = []

        if storyline_id is not None and domain_key:
            historical_context = build_storyline_historical_context(
                domain_key,
                storyline_id,
                max_events=max_historical_events,
            )
            if historical_context.get("success"):
                structured_citations.extend(_build_storyline_structured_citations(historical_context))
        elif arc_id:
            from services.arc_historical_context_service import build_arc_historical_context

            historical_context = build_arc_historical_context(arc_id, datetime.now(timezone.utc))
            if historical_context.get("success"):
                structured_citations.extend(_build_arc_structured_citations(historical_context))

        retrieval_query = _default_retrieval_query(query=query, historical_context=historical_context)
        storyline_article_ids: list[int] | None = None
        if storyline_id is not None and domain_key:
            ids = _load_storyline_article_ids(domain_key, storyline_id)
            storyline_article_ids = ids or None

        retrieval_chunks: list[dict[str, Any]] = []
        try:
            retrieval_chunks = search_embedding_chunks(
                retrieval_query,
                limit=max_retrieval_chunks,
                source_types=["article", "context", "reference_event", "wikipedia"],
                domain_key=domain_key,
                date_from=date_from,
                date_to=date_to,
                storyline_article_ids=storyline_article_ids,
                keyword_hint=query if query and query != retrieval_query else None,
            )
        except Exception as e:
            logger.debug("context_bundle retrieval skip: %s", e)

        structured_citations.extend(_build_retrieval_citations(retrieval_chunks))
        rendered_for_prompt = _render_for_prompt(
            historical_context=historical_context,
            retrieval_chunks=retrieval_chunks,
            structured_citations=structured_citations,
        )

        return {
            "success": True,
            "storyline_id": storyline_id,
            "arc_id": arc_id,
            "domain_key": domain_key,
            "query": query,
            "historical_context": historical_context,
            "retrieval_chunks": retrieval_chunks,
            "structured_citations": structured_citations,
            "rendered_for_prompt": rendered_for_prompt,
            "built_at": datetime.now(timezone.utc).isoformat(),
        }


def build_context_bundle_sync(**kwargs: Any) -> dict[str, Any]:
    """Sync entry for callers without a running event loop."""
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(ContextBundleService().build_context_bundle(**kwargs))
    raise RuntimeError(
        "build_context_bundle_sync() cannot run inside an event loop; "
        "await ContextBundleService().build_context_bundle() instead"
    )
