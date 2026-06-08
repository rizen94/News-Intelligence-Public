"""
Slow report service — weekly arc briefs with citation density validation.

LLM writes connective prose only; dates/numbers come from structured context bundle.
Citation keys (REF-/VF-/MACRO-) are rewritten to registered cit_* IDs for the drawer.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from shared.database.connection import get_db_connection_context, get_ui_db_connection_context
from shared.services.ollama_model_caller import get_ollama_model_caller
from shared.services.ollama_model_policy import InvocationKind

from services.arc_feedback_service import get_feedback_prompt_boost
from services.arc_historical_context_service import build_arc_historical_context
from services.citation_marker_service import (
    build_marker_lookup,
    count_citation_markers,
    rewrite_citation_markers,
)
from services.embeddings_worker_service import search_embedding_chunks

logger = logging.getLogger(__name__)

_MIN_CITATION_DENSITY = float(os.environ.get("SLOW_REPORT_MIN_CITATION_DENSITY", "0.08"))
_REJECT_ON_FAIL = os.environ.get("SLOW_REPORT_REJECT_ON_VALIDATION_FAIL", "true").lower() in (
    "1",
    "true",
    "yes",
)
_SKIP_RETRIEVAL = os.environ.get("SLOW_REPORT_SKIP_RETRIEVAL", "false").lower() in ("1", "true", "yes")


def _register_citation(
    cur,
    *,
    source_type: str,
    source_table: str | None,
    source_row_id: int | None,
    source_url: str | None,
    quote: str | None,
    event_date,
    ingestion_date,
    vintage_date,
    confidence: float | None = None,
    metadata: dict | None = None,
) -> str:
    cid = f"cit_{uuid.uuid4().hex[:16]}"
    cur.execute(
        """
        INSERT INTO intelligence.citation_registry (
            citation_id, source_type, source_table, source_row_id, source_url,
            quote, confidence, event_date, ingestion_date, vintage_date, metadata
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        """,
        (
            cid,
            source_type,
            source_table,
            source_row_id,
            source_url,
            (quote or "")[:2000] if quote else None,
            confidence,
            event_date,
            ingestion_date,
            vintage_date,
            json.dumps(metadata or {}),
        ),
    )
    return cid


def _parse_sources_url(sources: Any) -> str | None:
    if isinstance(sources, list):
        for s in sources:
            if isinstance(s, dict) and s.get("url"):
                return str(s["url"])
    return None


def _build_structured_citations(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for ev in bundle.get("reference_events") or []:
        meta = ev.get("metadata") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        seed_id = meta.get("seed_id") or ev.get("id")
        sources = ev.get("sources")
        if isinstance(sources, str):
            try:
                sources = json.loads(sources)
            except Exception:
                sources = []
        citations.append(
            {
                "citation_key": f"REF-{seed_id}",
                "source_type": "reference_event",
                "source_table": "intelligence.reference_events",
                "source_row_id": ev.get("id"),
                "source_url": _parse_sources_url(sources),
                "quote": (ev.get("summary") or "")[:500],
                "event_date": ev.get("event_date"),
                "ingestion_date": ev.get("ingestion_date"),
                "layer": "reference",
            }
        )
    for fact in bundle.get("living_facts") or []:
        citations.append(
            {
                "citation_key": f"VF-{fact.get('id')}",
                "source_type": "versioned_fact",
                "source_table": "intelligence.versioned_facts",
                "source_row_id": fact.get("id"),
                "quote": (fact.get("fact_text") or "")[:500],
                "event_date": fact.get("event_date") or fact.get("valid_from"),
                "ingestion_date": fact.get("ingestion_date"),
                "vintage_date": fact.get("vintage_date"),
                "layer": "living",
            }
        )
    for obs in bundle.get("macro_observations") or []:
        citations.append(
            {
                "citation_key": f"MACRO-{obs.get('series_id')}-{obs.get('observation_date')}",
                "source_type": "macro_observation",
                "source_table": "intelligence.macro_series_observations",
                "quote": f"{obs.get('series_id')}: {obs.get('value')} ({obs.get('observation_date')})",
                "event_date": obs.get("observation_date"),
                "vintage_date": obs.get("vintage_date"),
                "layer": "macro",
            }
        )
    for ev in bundle.get("external_events") or []:
        citations.append(
            {
                "citation_key": f"EXT-{ev.get('source')}-{ev.get('id')}",
                "source_type": "external_event",
                "source_table": "intelligence.external_events",
                "source_row_id": ev.get("id"),
                "quote": (ev.get("summary") or ev.get("title") or "")[:500],
                "event_date": ev.get("event_date"),
                "layer": "external",
            }
        )
    for ce in bundle.get("chronological_events") or []:
        citations.append(
            {
                "citation_key": f"CE-{ce.get('id')}",
                "source_type": "chronological_event",
                "source_table": "public.chronological_events",
                "source_row_id": ce.get("id"),
                "quote": (ce.get("description") or ce.get("title") or "")[:500],
                "event_date": ce.get("event_date") or ce.get("actual_event_date"),
                "layer": "living",
            }
        )
    for sa in bundle.get("sanctions_actions") or []:
        citations.append(
            {
                "citation_key": f"SAN-{sa.get('id')}",
                "source_type": "sanctions_action",
                "source_table": "intelligence.sanctions_actions",
                "source_row_id": sa.get("id"),
                "quote": (sa.get("summary") or "")[:500],
                "event_date": sa.get("action_date"),
                "ingestion_date": sa.get("ingestion_date"),
                "layer": "reference",
            }
        )
    return citations


def _validate_citation_density(content: str, citations: list[dict]) -> dict[str, Any]:
    words = max(1, len(content.split()))
    markers = count_citation_markers(content)
    density = markers / words
    min_markers = max(3, len(citations) // 15)
    passed = density >= _MIN_CITATION_DENSITY or markers >= min_markers
    return {
        "word_count": words,
        "citation_markers": markers,
        "density": round(density, 4),
        "min_density_threshold": _MIN_CITATION_DENSITY,
        "passed": passed,
    }


def _default_retrieval_query(arc_id: str, bundle: dict[str, Any], chapter_name: str) -> str:
    arc = bundle.get("arc") or {}
    display = arc.get("display_name") or arc_id.replace("_", " ")
    return f"{display} {chapter_name} geopolitics resources policy developments"


async def generate_slow_report_async(
    arc_id: str,
    *,
    report_type: str = "weekly_brief",
    as_of_date: datetime | None = None,
    retrieval_query: str | None = None,
    force_persist: bool = False,
) -> dict[str, Any]:
    """Generate arc report (async); quarantine when validation fails unless force_persist."""
    as_of = as_of_date or datetime.now(timezone.utc)
    bundle = build_arc_historical_context(arc_id, as_of)
    if not bundle.get("success"):
        return bundle

    structured_citations = _build_structured_citations(bundle)
    chapter = bundle.get("current_chapter") or {}
    chapter_name = chapter.get("name") or "current period"
    feedback_boost = get_feedback_prompt_boost(arc_id)

    retrieval: list[dict[str, Any]] = []
    if not _SKIP_RETRIEVAL:
        q = retrieval_query or _default_retrieval_query(arc_id, bundle, chapter_name)
        try:
            retrieval = search_embedding_chunks(q, limit=8)
        except Exception as e:
            logger.debug("retrieval skip: %s", e)

    prompt = _build_prompt(
        arc_id, bundle, structured_citations, retrieval, chapter_name, feedback_boost
    )

    caller = get_ollama_model_caller()
    result = await caller.generate(
        prompt,
        kind=InvocationKind.LONG_SYNTHESIS,
        urgency="standard",
        approx_prompt_chars=len(prompt),
    )
    raw_content = (result.text or "").strip()
    if not raw_content:
        return {"success": False, "error": "empty_llm_response", "arc_id": arc_id}

    key_to_cid: dict[str, str] = {}
    registered: list[dict[str, Any]] = []

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for sc in structured_citations[:50]:
                cid = _register_citation(
                    cur,
                    source_type=sc.get("source_type") or "unknown",
                    source_table=sc.get("source_table"),
                    source_row_id=sc.get("source_row_id"),
                    source_url=sc.get("source_url"),
                    quote=sc.get("quote"),
                    event_date=sc.get("event_date"),
                    ingestion_date=sc.get("ingestion_date"),
                    vintage_date=sc.get("vintage_date"),
                    metadata={
                        "citation_key": sc.get("citation_key"),
                        "layer": sc.get("layer"),
                    },
                )
                key_to_cid[sc["citation_key"]] = cid
                registered.append({**sc, "citation_id": cid})

            marker_lookup = build_marker_lookup(registered)
            content, unresolved = rewrite_citation_markers(raw_content, marker_lookup)
            validation = _validate_citation_density(content, structured_citations)
            validation["unresolved_markers"] = unresolved
            if unresolved and _REJECT_ON_FAIL and not force_persist:
                validation["passed"] = False
            analogues = _load_prior_analogues(cur, arc_id)

            analogue_text = ""
            if analogues:
                analogue_text = "\n".join(
                    f"- (rhymes with) {a.get('description', '')[:200]}" for a in analogues[:3]
                )
                if "Prior analogues" in content and analogue_text:
                    content = content.replace(
                        "Prior analogues",
                        f"Prior analogues\n{analogue_text}\n",
                        1,
                    )

            sections = {
                "what_changed": _extract_section(content, "What changed"),
                "where_this_fits": _extract_section(content, "Where this fits"),
                "the_numbers": _extract_section(content, "The numbers"),
                "prior_analogues": analogues,
                "open_questions": _extract_section(content, "Open questions"),
            }

            persist_type = report_type
            if not validation.get("passed") and _REJECT_ON_FAIL and not force_persist:
                persist_type = "quarantine"
                validation["quarantined"] = True

            cur.execute(
                """
                INSERT INTO intelligence.arc_reports (
                    arc_id, generated_at, living_cutoff_date, report_type,
                    title, content_markdown, sections, citations, validation, metadata
                ) VALUES (%s, NOW(), %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb)
                RETURNING id
                """,
                (
                    arc_id,
                    as_of,
                    persist_type,
                    f"Weekly Brief — {arc_id.replace('_', ' ').title()}",
                    content,
                    json.dumps(sections),
                    json.dumps(registered),
                    json.dumps(validation),
                    json.dumps({"model": result.model, "raw_word_count": len(raw_content.split())}),
                ),
            )
            row = cur.fetchone()
            report_id = row[0] if row else None
        conn.commit()

    if persist_type == "quarantine":
        return {
            "success": False,
            "error": "validation_failed_quarantined",
            "arc_id": arc_id,
            "report_id": report_id,
            "validation": validation,
            "content_preview": content[:500],
        }

    return {
        "success": True,
        "arc_id": arc_id,
        "report_id": report_id,
        "validation": validation,
        "citations_count": len(registered),
        "content_preview": content[:500],
    }


def generate_slow_report(
    arc_id: str,
    *,
    report_type: str = "weekly_brief",
    as_of_date: datetime | None = None,
    retrieval_query: str | None = None,
    force_persist: bool = False,
) -> dict[str, Any]:
    """Sync wrapper for automation/scripts (no running event loop)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            generate_slow_report_async(
                arc_id,
                report_type=report_type,
                as_of_date=as_of_date,
                retrieval_query=retrieval_query,
                force_persist=force_persist,
            )
        )
    raise RuntimeError(
        "generate_slow_report() cannot run inside an event loop; use generate_slow_report_async()"
    )


def _build_prompt(
    arc_id: str,
    bundle: dict[str, Any],
    citations: list[dict],
    retrieval: list[dict],
    chapter_name: str,
    feedback_boost: str = "",
) -> str:
    cite_lines = "\n".join(
        f"- [{c['citation_key']}] ({c.get('layer', 'data')}) {c.get('quote', '')[:200]}"
        for c in citations[:30]
    )
    retrieval_lines = "\n".join(
        f"- {r.get('chunk_text', '')[:180]}" for r in retrieval[:6]
    )
    return f"""You are writing a slow-journalism Weekly Brief for arc `{arc_id}`.
Current chapter: {chapter_name}. As-of: {bundle.get('as_of_date')}.

RULES (mandatory):
- Use ONLY dates and numbers from the structured citations below — never invent dates.
- After each factual claim, insert [CIT:{{exact citation_key}}] — copy the key verbatim from the list below (including REF-ref_* prefixes).
- Use "rhymes with / analogous to" for pattern language — never predict future outcomes.
- Sections (use these exact headings on their own lines):
What changed
Where this fits
The numbers
Prior analogues
Open questions
- 800–1200 words total.

STRUCTURED CITATIONS (reference = curated history; living = pipeline facts):
{cite_lines}

RETRIEVAL SNIPPETS:
{retrieval_lines or '(none)'}

{feedback_boost}

Write the brief now:"""


def _extract_section(content: str, heading: str) -> str:
    pattern = rf"(?i)^{re.escape(heading)}\s*\n(.*?)(?=\n[A-Za-z].+\n|\Z)"
    m = re.search(pattern, content, re.DOTALL | re.MULTILINE)
    return m.group(1).strip() if m else ""


def _load_prior_analogues(cur, arc_id: str) -> list[dict[str, Any]]:
    from services.arc_analogue_service import load_arc_prior_analogues

    return load_arc_prior_analogues(cur, arc_id, limit=5)


def get_latest_arc_report(arc_id: str, *, include_quarantine: bool = False) -> dict[str, Any] | None:
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            if include_quarantine:
                cur.execute(
                    """
                    SELECT id, arc_id, generated_at, living_cutoff_date, report_type,
                           title, content_markdown, sections, citations, validation, metadata
                    FROM intelligence.arc_reports
                    WHERE arc_id = %s
                    ORDER BY generated_at DESC
                    LIMIT 1
                    """,
                    (arc_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT id, arc_id, generated_at, living_cutoff_date, report_type,
                           title, content_markdown, sections, citations, validation, metadata
                    FROM intelligence.arc_reports
                    WHERE arc_id = %s
                      AND report_type != 'quarantine'
                      AND COALESCE((validation->>'passed')::boolean, true) = true
                    ORDER BY generated_at DESC
                    LIMIT 1
                    """,
                    (arc_id,),
                )
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            d = dict(zip(cols, row))
            for k in ("generated_at", "living_cutoff_date"):
                if d.get(k) and hasattr(d[k], "isoformat"):
                    d[k] = d[k].isoformat()
            return d


def get_citation_provenance(citation_id: str) -> dict[str, Any] | None:
    from services.citation_marker_service import expand_citation_key_aliases

    lookup_keys = {citation_id}
    lookup_keys.update(expand_citation_key_aliases(citation_id))

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT citation_id, source_type, source_table, source_row_id, source_url,
                       quote, confidence, event_date, ingestion_date, vintage_date, metadata
                FROM intelligence.citation_registry
                WHERE citation_id = %s
                   OR metadata->>'citation_key' = ANY(%s)
                LIMIT 1
                """,
                (citation_id, list(lookup_keys)),
            )
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            d = dict(zip(cols, row))
            for k in ("event_date", "ingestion_date", "vintage_date"):
                if d.get(k) and hasattr(d[k], "isoformat"):
                    d[k] = d[k].isoformat()
            meta = d.get("metadata")
            if isinstance(meta, str):
                try:
                    d["metadata"] = json.loads(meta)
                except Exception:
                    pass
            return d
