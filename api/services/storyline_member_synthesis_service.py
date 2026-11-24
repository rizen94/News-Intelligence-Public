"""
Storyline narrative from cited members — citations are the summary source.

Reader: build multi-source prose from every on-topic storyline_articles row.
Pipeline: RAG / storyline_processing uses the same member filter + evidence text.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def _excerpt_from_article(raw: str, *, max_len: int = 520) -> str:
    from api.shared.llm_text_sanitize import html_to_visible_text

    prose = html_to_visible_text(str(raw or ""), max_length=max_len + 200)
    if not prose:
        return ""
    prose = re.sub(r"^##\s+[^\n]+\n+", "", prose.strip())
    paras = [p.strip() for p in re.split(r"\n\s*\n+", prose) if p.strip()]
    chunk = " ".join(paras[:2]) if paras else prose
    chunk = re.sub(r"\s+", " ", chunk).strip()
    if len(chunk) > max_len:
        chunk = chunk[: max_len - 1].rsplit(" ", 1)[0] + "…"
    return chunk


def build_reader_summary_from_members(
    story_title: str,
    citations: list[dict[str, Any]],
    *,
    max_members: int = 24,
    max_chars: int = 12000,
) -> str:
    """
    Unified reader summary sourced from all on-topic citations (not a one-line seed).

    Uses bullet attribution (colon), not excerpt-mash em-dash blocks, so coherence
    guards allow a long multi-source brief.
    """
    from api.shared.storyline_bag_hygiene import citations_aligned_with_story

    if not citations:
        return ""
    aligned = citations_aligned_with_story(story_title, citations, limit=max_members)
    pool = aligned if len(aligned) >= 2 else citations[:max_members]

    sorted_pool = sorted(
        pool,
        key=lambda c: str(c.get("published_at") or ""),
        reverse=True,
    )

    lede_parts: list[str] = []
    for cite in sorted_pool[:3]:
        ex = _excerpt_from_article(
            str(cite.get("summary") or cite.get("content") or ""), max_len=380
        )
        if len(ex) < 60:
            continue
        src = (cite.get("source_domain") or "").strip()
        if src:
            lede_parts.append(f"{ex} ({src})")
        else:
            lede_parts.append(ex)
        if len(" ".join(lede_parts)) > 700:
            break

    sections: list[str] = []
    if lede_parts:
        sections.append(
            "This storyline draws on "
            f"{len(pool)} cited source{'s' if len(pool) != 1 else ''}. "
            + " ".join(lede_parts[:2])
        )

    sections.append("\nFrom the reporting:\n")
    for cite in sorted_pool:
        headline = str(cite.get("title") or "Article").strip()
        src = str(cite.get("source_domain") or "unknown").strip()
        when = str(cite.get("published_at") or "")[:10]
        body = _excerpt_from_article(
            str(cite.get("summary") or cite.get("content") or ""), max_len=480
        )
        if len(body) < 50:
            continue
        date_bit = f", {when}" if when else ""
        sections.append(f"- {headline} ({src}{date_bit}): {body}")

    text = "\n".join(sections).strip()
    if len(text) > max_chars:
        text = text[: max_chars - 1].rsplit("\n", 1)[0] + "\n…"
    return text


def filter_members_on_topic(
    story_title: str,
    articles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Drop headline-off-topic rows before LLM synthesis."""
    from api.shared.storyline_bag_hygiene import article_title_aligns_with_story

    kept = [
        a
        for a in articles
        if article_title_aligns_with_story(
            story_title, str(a.get("title") or "")
        )
    ]
    return kept if len(kept) >= 2 else articles


def build_member_evidence_context(
    storyline_title: str,
    articles: list[dict[str, Any]],
    *,
    per_article_chars: int = 1200,
    max_articles: int = 30,
) -> str:
    """LLM context: every on-topic member with evidence text."""
    from services.article_content_enrichment_service import article_evidence_text

    on_topic = filter_members_on_topic(storyline_title, articles)
    lines = [
        f"Storyline title: {storyline_title}",
        f"On-topic member articles: {len(on_topic)} (of {len(articles)} linked)",
        "",
    ]
    for i, art in enumerate(on_topic[:max_articles], 1):
        title = art.get("title") or "Untitled"
        src = art.get("source_domain") or "unknown"
        pub = art.get("published_at") or ""
        body = article_evidence_text(
            art.get("summary"),
            art.get("content"),
            max_len=per_article_chars,
        )
        lines.append(f"--- Article {i}: {title}")
        lines.append(f"Source: {src} | Published: {pub}")
        if body:
            lines.append(body)
        lines.append("")
    return "\n".join(lines)


async def synthesize_and_persist_member_narrative(
    domain: str,
    storyline_id: int,
) -> dict[str, Any]:
    """
    RAG-style synthesis from storyline_articles only; writes editorial_document.
    """
    from api.shared.database import get_db_connection_context
    from api.shared.domain_registry import resolve_domain_schema
    from api.shared.services.llm_service import llm_service
    schema = resolve_domain_schema(domain)
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, title FROM {schema}.storylines
                WHERE id = %s AND merged_into_id IS NULL
                """,
                (storyline_id,),
            )
            row = cur.fetchone()
            if not row:
                return {"success": False, "error": "storyline not found"}
            title = str(row[1] or "")
            cur.execute(
                f"""
                SELECT a.id, a.title, a.content, a.summary, a.published_at,
                       a.source_domain, a.url
                FROM {schema}.articles a
                JOIN {schema}.storyline_articles sa ON sa.article_id = a.id
                WHERE sa.storyline_id = %s
                  AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                ORDER BY a.published_at DESC NULLS LAST
                """,
                (storyline_id,),
            )
            cols = [d[0] for d in cur.description]
            articles = [dict(zip(cols, r)) for r in (cur.fetchall() or [])]

    if len(articles) < 1:
        return {"success": False, "error": "no members"}

    context = build_member_evidence_context(title, articles)
    prompt = (
        f"{context}\n\n"
        "Write one coherent narrative for THIS storyline title using ONLY the articles above. "
        "Synthesize across sources; do not paste unrelated weekly-market stories. "
        "When multiple outlets report the same fact, state it once with combined attribution "
        "(e.g. Bloomberg and BBC) — do not repeat the same development in different words. "
        "Include: opening lede (4-6 sentences), key developments (numbered), "
        "stakeholders, and what to watch next. Attribute facts to sources inline."
    )
    result = await llm_service.generate_storyline_analysis(prompt)
    if not result.get("success") or not result.get("analysis"):
        return {"success": False, "error": result.get("error", "empty analysis")}

    analysis_text = str(result["analysis"]).strip()
    on_topic = filter_members_on_topic(title, articles)
    lede = analysis_text
    if "\n" in analysis_text:
        lede = analysis_text.split("\n\n", 1)[0].strip()[:1200]

    editorial_doc = {
        "lede": lede[:1200],
        "analysis": analysis_text,
        "developments": [],
        "sources": list({str(a.get("source_domain") or "") for a in on_topic if a.get("source_domain")}),
        "generated_at": datetime.now().isoformat(),
        "based_on_articles": [int(a["id"]) for a in on_topic if a.get("id")],
        "source": "member_citation_synthesis",
    }

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {schema}.storylines
                SET analysis_summary = %s,
                    master_summary = %s,
                    editorial_document = %s::jsonb,
                    document_status = 'rag_analyzed',
                    document_version = COALESCE(document_version, 0) + 1,
                    ml_processing_status = 'completed',
                    updated_at = NOW(),
                    last_refinement = NOW()
                WHERE id = %s
                """,
                (
                    analysis_text,
                    analysis_text,
                    json.dumps(editorial_doc),
                    storyline_id,
                ),
            )
        conn.commit()

    return {
        "success": True,
        "storyline_id": storyline_id,
        "articles_used": len(on_topic),
        "analysis_chars": len(analysis_text),
    }