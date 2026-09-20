"""
Storyline narrative finisher — ~70B editorial pass over aggregated 8B/Mistral work.

See docs/_archive/retired_root_docs_2026_03/STORYLINE_70B_NARRATIVE_FINISHER.md. This module builds the finisher prompt and
calls Ollama via OllamaModelCaller with InvocationKind.STORYLINE_NARRATIVE_FINISH.

Loads storyline + linked articles + entities from the domain schema; optional timeline rows from
`public.chronological_events`. Persistence of outputs (columns / automation) remains TODO.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from shared.database.connection import get_ephemeral_db_connection_context
from shared.domain_registry import domain_key_to_schema, is_valid_domain_key
from shared.services.ollama_model_caller import get_ollama_model_caller
from shared.services.ollama_model_policy import InvocationKind

logger = logging.getLogger(__name__)


def _schema_name(domain_key: str) -> str | None:
    if not is_valid_domain_key(domain_key):
        return None
    try:
        return domain_key_to_schema(domain_key)
    except KeyError:
        return None


@dataclass
class StorylineFinisherBundle:
    """Everything the finisher needs to see for one storyline (expand as wired to DB)."""

    domain_key: str
    schema_name: str
    storyline_id: int
    storyline_title: str
    storyline_status: str = ""
    existing_narrative: str = ""
    article_summaries: list[dict[str, Any]] = field(default_factory=list)
    # e.g. [{"title": "...", "published_at": "...", "summary": "..."}]
    entity_highlights: list[str] = field(default_factory=list)
    context_labels: list[str] = field(default_factory=list)
    timeline_bullets: list[str] = field(default_factory=list)
    historical_context_rendered: str = ""
    external_rag_rendered: str = ""
    causal_scaffold_rendered: str = ""


def parse_finisher_response(raw_text: str) -> tuple[dict[str, Any] | None, str | None]:
    """
    Extract JSON after the ---JSON--- marker (see build_finisher_prompt).

    Marker matching is tolerant of whitespace/newlines and case
    (e.g. --- JSON ---, ---\\nJSON---). Returns (parsed_dict, error_reason);
    error_reason is None on success.
    """
    from shared.llm_text_sanitize import split_after_json_marker, strip_json_fence

    if not raw_text or not raw_text.strip():
        return None, "empty_response"
    rest = split_after_json_marker(raw_text)
    if rest is None:
        return None, "no_json_marker"
    rest = strip_json_fence(rest)
    try:
        data = json.loads(rest)
    except json.JSONDecodeError as e:
        logger.warning("finisher JSON parse failed: %s", e)
        return None, f"json_decode_error:{e}"
    if not isinstance(data, dict):
        return None, "json_not_object"
    return data, None


def load_finisher_bundle_from_db(
    domain_key: str,
    storyline_id: int,
    *,
    max_articles: int = 50,
    max_entities: int = 60,
    max_timeline: int = 80,
) -> StorylineFinisherBundle | None:
    """
    Load storyline row, linked articles (summaries), top entities, and optional chrono bullets.

    Returns None if domain invalid, no connection, or storyline missing.
    """
    schema = _schema_name(domain_key)
    if not schema:
        logger.warning("load_finisher_bundle_from_db: invalid domain_key=%s", domain_key)
        return None

    try:
        with get_ephemeral_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, title, description, status, analysis_summary,
                           background_information, editorial_document, key_entities,
                           COALESCE(canonical_narrative, ''),
                           COALESCE(narrative_finisher_meta, '{{}}'::jsonb),
                           COALESCE(quality_metrics, '{{}}'::jsonb)
                    FROM {schema}.storylines
                    WHERE id = %s
                    """,
                    (storyline_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None

                title = row[1] or ""
                description = row[2] or ""
                status = row[3] or ""
                analysis_summary = row[4] or ""
                background_information = row[5]
                editorial_document = row[6] or ""
                key_entities_raw = row[7]
                canonical_narrative = row[8] or ""
                finisher_meta_raw = row[9]
                quality_metrics_raw = row[10]

                prefer_regen = False
                kitchen_sink_flag: bool | None = None
                try:
                    finisher_meta = (
                        json.loads(finisher_meta_raw)
                        if isinstance(finisher_meta_raw, str)
                        else finisher_meta_raw
                    )
                    if isinstance(finisher_meta, dict):
                        prefer_regen = bool(finisher_meta.get("prefer_regenerate_from_keepers"))
                        prune_meta = finisher_meta.get("core_prune")
                        if isinstance(prune_meta, dict) and prune_meta.get(
                            "prefer_regenerate_from_keepers"
                        ):
                            prefer_regen = True
                        if isinstance(prune_meta, dict) and prune_meta.get("kitchen_sink"):
                            kitchen_sink_flag = True
                except Exception:
                    pass
                try:
                    qm = (
                        json.loads(quality_metrics_raw)
                        if isinstance(quality_metrics_raw, str)
                        else quality_metrics_raw
                    )
                    if isinstance(qm, dict):
                        if qm.get("prefer_regenerate_from_keepers"):
                            prefer_regen = True
                        if qm.get("kitchen_sink"):
                            kitchen_sink_flag = True
                except Exception:
                    pass

                parts = [description, analysis_summary, editorial_document, canonical_narrative]
                existing_narrative = "\n\n".join(p.strip() for p in parts if p and str(p).strip())
                evidence_summary = (
                    canonical_narrative or analysis_summary or description or ""
                )

                context_labels: list[str] = []
                if background_information:
                    try:
                        bg = (
                            json.loads(background_information)
                            if isinstance(background_information, str)
                            else background_information
                        )
                        if isinstance(bg, dict):
                            for k in ("contexts", "context_labels", "themes", "tags"):
                                v = bg.get(k)
                                if isinstance(v, list):
                                    context_labels.extend(str(x) for x in v if x)
                                elif isinstance(v, str) and v.strip():
                                    context_labels.append(v.strip())
                        elif isinstance(bg, list):
                            context_labels.extend(str(x) for x in bg if x)
                    except (json.JSONDecodeError, TypeError):
                        pass

                if key_entities_raw is not None:
                    try:
                        ke = (
                            json.loads(key_entities_raw)
                            if isinstance(key_entities_raw, str)
                            else key_entities_raw
                        )
                        if isinstance(ke, list):
                            context_labels.extend(str(x) for x in ke if x)
                        elif isinstance(ke, dict):
                            for k, v in ke.items():
                                context_labels.append(f"{k}: {v}" if v is not None else str(k))
                    except (json.JSONDecodeError, TypeError):
                        pass

                cur.execute(
                    f"""
                    SELECT a.id, a.title, a.url, a.source_domain, a.published_at, a.summary,
                           COALESCE(sa.relationship_type, '')
                    FROM {schema}.articles a
                    JOIN {schema}.storyline_articles sa ON a.id = sa.article_id
                    WHERE sa.storyline_id = %s
                      AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                    ORDER BY a.published_at DESC NULLS LAST
                    LIMIT %s
                    """,
                    (storyline_id, max_articles),
                )
                article_rows = list(cur.fetchall())
                article_rows.reverse()

                article_summaries: list[dict[str, Any]] = []
                article_ids: list[int] = []
                for r in article_rows:
                    aid, atitle, url, source_domain, published_at, summary, rel_type = r
                    article_ids.append(int(aid))
                    article_summaries.append(
                        {
                            "id": aid,
                            "title": atitle,
                            "url": url,
                            "source_domain": source_domain,
                            "published_at": published_at.isoformat() if published_at else None,
                            "summary": (summary or "")[:4000],
                            "relationship_type": (rel_type or "").strip().lower(),
                            "entities": set(),
                        }
                    )

                # Event-core: annotate typed TE membership for I2 evidence selection
                try:
                    from services.event_core_membership_service import (
                        event_core_membership_enabled,
                    )

                    if event_core_membership_enabled() and article_ids:
                        cur.execute(
                            """
                            SELECT eam.article_id, eam.membership_type, eam.anchor_ref
                            FROM intelligence.event_article_membership eam
                            WHERE eam.domain_key = %s
                              AND eam.article_id = ANY(%s)
                            """,
                            (domain_key, article_ids),
                        )
                        by_id = {int(a["id"]): a for a in article_summaries}
                        for aid, mtype, aref in cur.fetchall() or []:
                            row_a = by_id.get(int(aid))
                            if not row_a:
                                continue
                            row_a["event_core_typed"] = True
                            row_a["membership_type"] = (mtype or "").strip()
                            row_a["anchor_ref"] = aref
                except Exception as ec_ann:
                    logger.debug("finisher event-core annotate: %s", ec_ann)

                # Optional per-article entities for keeper fit scoring
                if article_ids:
                    try:
                        cur.execute(
                            f"""
                            SELECT ae.article_id, LOWER(ec.canonical_name)
                            FROM {schema}.article_entities ae
                            JOIN {schema}.entity_canonical ec ON ec.id = ae.canonical_entity_id
                            WHERE ae.article_id = ANY(%s)
                              AND ec.canonical_name IS NOT NULL
                            LIMIT 2000
                            """,
                            (article_ids,),
                        )
                        by_id = {int(a["id"]): a for a in article_summaries}
                        for aid, name in cur.fetchall():
                            row_a = by_id.get(int(aid))
                            if row_a and name:
                                row_a["entities"].add(str(name).strip().lower())
                    except Exception as ee:
                        logger.debug("finisher article entities optional: %s", ee)

                try:
                    from services.storyline_core_prune_service import (
                        filter_articles_for_keeper_evidence,
                    )

                    before_n = len(article_summaries)
                    article_summaries = filter_articles_for_keeper_evidence(
                        storyline_title=title,
                        storyline_summary=evidence_summary,
                        articles=article_summaries,
                        prefer_regenerate_from_keepers=prefer_regen,
                        kitchen_sink=kitchen_sink_flag,
                    )
                    article_ids = [int(a["id"]) for a in article_summaries if a.get("id")]
                    if before_n and len(article_summaries) < before_n:
                        logger.info(
                            "finisher keeper-only evidence %s/%s: %s → %s articles",
                            domain_key,
                            storyline_id,
                            before_n,
                            len(article_summaries),
                        )
                except Exception as ke:
                    logger.debug("finisher keeper filter skipped: %s", ke)

                # Drop set() entities before JSON prompt serialization
                for a in article_summaries:
                    a.pop("entities", None)
                    a.pop("relationship_type", None)

                entity_highlights: list[str] = []
                if article_ids:
                    cur.execute(
                        f"""
                        SELECT ec.canonical_name, ec.entity_type, COUNT(ae.article_id) AS mention_count
                        FROM {schema}.article_entities ae
                        JOIN {schema}.entity_canonical ec ON ec.id = ae.canonical_entity_id
                        WHERE ae.article_id = ANY(%s)
                        GROUP BY ec.id, ec.canonical_name, ec.entity_type
                        ORDER BY mention_count DESC
                        LIMIT %s
                        """,
                        (article_ids, max_entities),
                    )
                    for name, etype, cnt in cur.fetchall():
                        label = (name or "").strip()
                        if not label:
                            continue
                        entity_highlights.append(f"{label} ({etype or 'subject'}), mentions={cnt}")

                timeline_bullets: list[str] = []
                try:
                    cur.execute(
                        """
                        SELECT title, description, actual_event_date, importance_score
                        FROM public.chronological_events
                        WHERE storyline_id = %s
                        ORDER BY actual_event_date NULLS LAST, id ASC
                        LIMIT %s
                        """,
                        (str(storyline_id), max_timeline),
                    )
                    for t, desc, adate, imp in cur.fetchall():
                        line = (t or "").strip()
                        if adate:
                            line = f"{adate.isoformat()}: {line}"
                        if desc and str(desc).strip():
                            line += f" — {(desc or '')[:240]}"
                        if imp is not None:
                            line += f" [importance={imp}]"
                        if line:
                            timeline_bullets.append(line)
                except Exception as te:
                    logger.debug("chronological_events optional load skipped: %s", te)

                seen_ctx = set()
                uniq_contexts = []
                for c in context_labels:
                    c = str(c).strip()
                    if c and c not in seen_ctx:
                        seen_ctx.add(c)
                        uniq_contexts.append(c)

                historical_rendered = ""
                try:
                    from services.storyline_historical_context_service import (
                        build_storyline_historical_context,
                        render_historical_context_for_llm,
                    )

                    hctx = build_storyline_historical_context(
                        domain_key, storyline_id, conn=conn
                    )
                    if hctx.get("success"):
                        historical_rendered = render_historical_context_for_llm(hctx)
                except Exception as he:
                    logger.debug("finisher historical_context skipped: %s", he)

                external_rag_rendered = ""
                try:
                    from services.storyline_rag_context_service import render_rag_context_for_llm
                    from shared.database.connection import get_db_connection as _gdbc
                    from shared.domain_registry import normalize_domain_key
                    import json as _json

                    # Prefer stored row (ensure usually ran in queue before this load).
                    _conn = _gdbc()
                    rag_data = None
                    if _conn:
                        try:
                            with _conn.cursor() as _cur:
                                _cur.execute(
                                    """
                                    SELECT rag_data FROM intelligence.storyline_rag_context
                                    WHERE domain_key = %s AND storyline_id = %s
                                    """,
                                    (normalize_domain_key(domain_key), int(storyline_id)),
                                )
                                _row = _cur.fetchone()
                                if _row and _row[0]:
                                    rag_data = (
                                        _json.loads(_row[0]) if isinstance(_row[0], str) else _row[0]
                                    )
                        finally:
                            _conn.close()
                    if isinstance(rag_data, dict):
                        external_rag_rendered = render_rag_context_for_llm(
                            rag_data, max_chars=3500
                        )
                except Exception as re:
                    logger.debug("finisher external RAG skipped: %s", re)

                causal_scaffold_rendered = ""
                try:
                    from services.narrative_reasoning_service import build_narrative_scaffold

                    scaffold = build_narrative_scaffold(
                        domain_key=domain_key,
                        storyline_id=int(storyline_id),
                        max_edges=8,
                    )
                    if scaffold.get("has_typed_edges"):
                        edges = scaffold.get("causal_edges") or []
                        lines = [scaffold.get("prompt_preamble") or ""]
                        for e in edges[:8]:
                            lines.append(
                                f"- edge#{e.get('id')}: {e.get('cause_kind')}:{e.get('cause_id')} "
                                f"--{e.get('relation')}→ {e.get('effect_kind')}:{e.get('effect_id')} "
                                f"(grade={e.get('evidence_grade')}, conf={e.get('confidence')})"
                            )
                        causal_scaffold_rendered = "\n".join(lines).strip()
                except Exception as ce:
                    logger.debug("finisher causal scaffold skipped: %s", ce)

                return StorylineFinisherBundle(
                    domain_key=domain_key,
                    schema_name=schema,
                    storyline_id=storyline_id,
                    storyline_title=title,
                    storyline_status=status,
                    existing_narrative=existing_narrative,
                    article_summaries=article_summaries,
                    entity_highlights=entity_highlights,
                    context_labels=uniq_contexts,
                    timeline_bullets=timeline_bullets,
                    historical_context_rendered=historical_rendered,
                    external_rag_rendered=external_rag_rendered,
                    causal_scaffold_rendered=causal_scaffold_rendered,
                )
    except Exception as e:
        logger.exception("load_finisher_bundle_from_db failed: %s", e)
        return None


def build_finisher_prompt(bundle: StorylineFinisherBundle) -> str:
    """
    Editor-style prompt: integrate lower-tier work, produce durable narrative + structured deltas.
    """
    articles_block = json.dumps(bundle.article_summaries, indent=2)[:24000]
    entities = "\n".join(f"- {e}" for e in bundle.entity_highlights[:80])
    contexts = "\n".join(f"- {c}" for c in bundle.context_labels[:80])
    timeline = "\n".join(f"- {t}" for t in bundle.timeline_bullets[:120])

    return f"""You are the senior narrative editor for a news intelligence system. Smaller models (8B/7B) already produced summaries, entities, and drafts. Your job is the FINAL pass: a coherent, durable storyline narrative that can stand for weeks, integrating evidence and trimming noise.

Storyline id: {bundle.storyline_id}
Domain: {bundle.domain_key}
Title: {bundle.storyline_title}
Status: {bundle.storyline_status}

Existing narrative / notes (may be draft or stale):
---
{bundle.existing_narrative[:12000]}
---

Article-level material (titles, dates, short summaries from the fast pipeline):
{articles_block}

Notable entities (from extraction):
{entities or "(none listed)"}

Context labels:
{contexts or "(none listed)"}

Timeline / event bullets (if any):
{timeline or "(none listed)"}

Established facts and full chronological spine (durable memory; may include events older than 30 days):
{bundle.historical_context_rendered[:14000] if bundle.historical_context_rendered else "(none loaded)"}

External background (Wikipedia / GDELT — pipeline-stored; may be empty):
{bundle.external_rag_rendered[:3500] if bundle.external_rag_rendered else "(none loaded)"}

Typed causal edges (cite edge_id when asserting causation; omit if empty):
{bundle.causal_scaffold_rendered[:4000] if bundle.causal_scaffold_rendered else "(none — do not invent causal claims)"}

Tasks:
1) Write a refined **canonical narrative** (4–12 short paragraphs): what this storyline IS, how it evolved, who/what matters, and what is uncertain. Name specific companies, officials, sectors, or commodities when sources support it; explain implications for markets, policy, or affected sectors — not boilerplate about "related coverage."
2) Suggest **new** entities or themes worth linking (not already obvious in lists).
3) Call out **redundant or misleading** prior phrases to remove or soften in stored copy.
4) Return **valid JSON only** after a line containing exactly ---JSON--- with this shape:
{{
  "canonical_narrative": "markdown or plain text",
  "suggested_new_entities": ["..."],
  "suggested_new_context_hooks": ["..."],
  "sections_to_deprecate_or_trim": ["short quotes or phrases to remove from stored storyline text"],
  "open_questions": ["..."]
}}
"""


def build_headline_refiner_prompt(
    domain_key: str,
    draft_title: str,
    draft_description: str,
    article_lines: list[str],
) -> str:
    """
    Short ~70B editorial pass: one headline + optional description from draft + evidence lines.
    """
    lines = "\n".join(f"- {t[:600]}" for t in article_lines[:18] if t and str(t).strip())
    return f"""You are a senior news desk editor. Given a draft storyline label and source material, produce ONE polished headline (max ~12 words) and a one-sentence description if helpful.

Domain: {domain_key}
Draft title (may be awkward): {draft_title}
Draft description: {draft_description or "(none)"}

Evidence (headlines / summaries):
{lines or "(none)"}

Rules: Use clear subject–verb–object news style; no clickbait; preserve factual scope implied by the sources. Name specific companies/sectors when present; state market or sector implications in the description — never bare "Reports" or "Earnings" without context.

Reply with ONLY valid JSON after a line containing exactly ---JSON---
{{
  "title": "Polished headline here",
  "description": "One sentence or empty string"
}}
"""


def parse_headline_refiner_response(raw_text: str) -> tuple[dict[str, Any] | None, str | None]:
    """Parse ---JSON--- block from headline refiner output (tolerant marker variants)."""
    from shared.llm_text_sanitize import split_after_json_marker, strip_json_fence

    if not raw_text or not raw_text.strip():
        return None, "empty_response"
    rest = split_after_json_marker(raw_text)
    if rest is None:
        return None, "no_json_marker"
    rest = strip_json_fence(rest)
    try:
        data = json.loads(rest)
    except json.JSONDecodeError as e:
        logger.warning("headline refiner JSON parse failed: %s", e)
        return None, f"json_decode_error:{e}"
    if not isinstance(data, dict):
        return None, "json_not_object"
    return data, None


async def refine_storyline_headline_with_70b(
    domain_key: str,
    draft_title: str,
    draft_description: str,
    article_lines: list[str],
) -> dict[str, Any]:
    """
    Editorial headline pass using the narrative finisher model (~70B per policy).

    Returns dict with keys: success, title, description, model, parse_error, raw_text.
    """
    prompt = build_headline_refiner_prompt(
        domain_key, draft_title, draft_description, article_lines
    )
    caller = get_ollama_model_caller()
    result = await caller.generate(
        prompt,
        kind=InvocationKind.STORYLINE_NARRATIVE_FINISH,
        urgency="standard",
        approx_prompt_chars=len(prompt),
    )
    out: dict[str, Any] = {
        "success": bool(result.text and result.text.strip()),
        "title": "",
        "description": "",
        "model": result.model,
        "raw_text": result.text,
        "parse_error": None,
    }
    if not result.text:
        return out
    parsed, err = parse_headline_refiner_response(result.text)
    out["parse_error"] = err
    if isinstance(parsed, dict):
        from shared.llm_text_sanitize import sanitize_briefing_title, strip_llm_wrapping_artifacts

        out["title"] = sanitize_briefing_title((parsed.get("title") or "").strip())
        out["description"] = strip_llm_wrapping_artifacts(
            (parsed.get("description") or "").strip(), max_length=500
        )
        out["success"] = bool(out["title"])
    return out


async def run_narrative_finish(
    bundle: StorylineFinisherBundle,
    *,
    approx_prompt_chars: int | None = None,
    parse_json: bool = True,
) -> dict[str, Any]:
    """
    Run the finisher model. Returns raw result dict; caller persists when ready.

    When parse_json is True, attempts to parse the ---JSON--- block into `parsed`.
    Persistence: `persist_narrative_finish_to_db` (typically after queue worker runs this).
    """
    prompt = build_finisher_prompt(bundle)
    caller = get_ollama_model_caller()
    result = await caller.generate(
        prompt,
        kind=InvocationKind.STORYLINE_NARRATIVE_FINISH,
        urgency="standard",
        approx_prompt_chars=approx_prompt_chars if approx_prompt_chars is not None else len(prompt),
    )
    logger.info(
        "storyline_narrative_finish storyline_id=%s model=%s chars=%s",
        bundle.storyline_id,
        result.model,
        len(prompt),
    )
    out: dict[str, Any] = {
        "success": True,
        "storyline_id": bundle.storyline_id,
        "domain_key": bundle.domain_key,
        "model": result.model,
        "raw_text": result.text,
    }
    if parse_json and result.text:
        parsed, err = parse_finisher_response(result.text)
        out["parsed"] = parsed
        out["parse_error"] = err
    return out


async def run_narrative_finish_from_db(
    domain_key: str,
    storyline_id: int,
    *,
    max_articles: int = 50,
    parse_json: bool = True,
) -> dict[str, Any]:
    """
    Load bundle from DB, run finisher. On missing storyline returns success=False.
    """
    bundle = load_finisher_bundle_from_db(domain_key, storyline_id, max_articles=max_articles)
    if not bundle:
        return {
            "success": False,
            "storyline_id": storyline_id,
            "domain_key": domain_key,
            "error": "storyline_not_found_or_load_failed",
        }
    return await run_narrative_finish(bundle, parse_json=parse_json)


def apply_sections_to_deprecate_or_trim(
    text: str,
    sections: list[Any] | None,
    *,
    min_span_len: int = 12,
) -> tuple[str, list[str], list[str]]:
    """
    Remove matching spans from stored narrative text when safe exact/near-exact match.

    Returns (new_text, applied_spans, unmatched_spans).
    Unmatched spans should be queued for HITL rather than fuzzy-destroyed.
    """
    if not text:
        return text or "", [], list(
            str(s).strip() for s in (sections or []) if s and str(s).strip()
        )
    applied: list[str] = []
    unmatched: list[str] = []
    out = text
    for raw in sections or []:
        span = str(raw or "").strip()
        if len(span) < min_span_len:
            if span:
                unmatched.append(span)
            continue
        if span in out:
            out = out.replace(span, "")
            applied.append(span)
            continue
        # Soft normalize whitespace for near-exact match
        collapsed_span = " ".join(span.split())
        collapsed_out = " ".join(out.split())
        if collapsed_span and collapsed_span in collapsed_out:
            pattern = re.compile(
                re.escape(span).replace(r"\ ", r"\s+"),
                re.IGNORECASE,
            )
            new_out, n = pattern.subn("", out, count=1)
            if n:
                out = new_out
                applied.append(span)
                continue
            unmatched.append(span)
        else:
            unmatched.append(span)
    # Collapse excessive blank lines left by removals
    while "\n\n\n" in out:
        out = out.replace("\n\n\n", "\n\n")
    return out.strip(), applied, unmatched


def persist_narrative_finish_to_db(
    domain_key: str, storyline_id: int, run_result: dict[str, Any]
) -> bool:
    """
    Persist ~70B finisher output to `{schema}.storylines` (migration 181 columns).
    Empty canonical_narrative in parsed output leaves prior canonical text unchanged.
    Applies ``sections_to_deprecate_or_trim`` to stored narrative fields when safe.
    """
    schema = _schema_name(domain_key)
    if not schema:
        return False
    parsed = run_result.get("parsed")
    if not isinstance(parsed, dict):
        parsed = {}
    from shared.llm_text_sanitize import sanitize_on_persist

    canonical = sanitize_on_persist(
        (parsed.get("canonical_narrative") or "").strip(), "narrative"
    )
    trim_sections = parsed.get("sections_to_deprecate_or_trim")
    if not isinstance(trim_sections, list):
        trim_sections = []

    meta: dict[str, Any] = {
        "suggested_new_entities": parsed.get("suggested_new_entities"),
        "suggested_new_context_hooks": parsed.get("suggested_new_context_hooks"),
        "sections_to_deprecate_or_trim": trim_sections,
        "open_questions": parsed.get("open_questions"),
        "parse_error": run_result.get("parse_error"),
        "model": run_result.get("model"),
    }
    raw = run_result.get("raw_text") or ""
    if raw:
        meta["raw_excerpt"] = raw[:4000]

    try:
        with get_ephemeral_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT COALESCE(canonical_narrative, ''),
                           COALESCE(analysis_summary, ''),
                           COALESCE(editorial_document::text, ''),
                           COALESCE(narrative_finisher_meta, '{{}}'::jsonb)
                    FROM {schema}.storylines
                    WHERE id = %s
                    """,
                    (storyline_id,),
                )
                prior = cur.fetchone()
                prior_canon = (prior[0] if prior else "") or ""
                prior_analysis = (prior[1] if prior else "") or ""
                prior_editorial = (prior[2] if prior else "") or ""
                prior_meta = prior[3] if prior else {}
                if isinstance(prior_meta, str):
                    try:
                        prior_meta = json.loads(prior_meta)
                    except Exception:
                        prior_meta = {}
                if not isinstance(prior_meta, dict):
                    prior_meta = {}

                # Prefer regenerate-from-keepers when recent prune dropped a large share
                prune_meta = prior_meta.get("core_prune") if isinstance(prior_meta, dict) else None
                prefer_regen = bool(
                    isinstance(prune_meta, dict)
                    and prune_meta.get("prefer_regenerate_from_keepers")
                )
                meta["prefer_regenerate_from_keepers"] = prefer_regen

                base_canon = canonical if canonical else prior_canon
                applied_all: list[str] = []
                unmatched_all: list[str] = []
                analysis_changed = False
                editorial_changed = False
                new_analysis = prior_analysis
                new_editorial = prior_editorial
                if trim_sections:
                    base_canon, a1, u1 = apply_sections_to_deprecate_or_trim(
                        base_canon, trim_sections
                    )
                    new_analysis, a2, u2 = apply_sections_to_deprecate_or_trim(
                        prior_analysis, trim_sections
                    )
                    new_editorial, a3, u3 = apply_sections_to_deprecate_or_trim(
                        prior_editorial, trim_sections
                    )
                    applied_all = a1 + a2 + a3
                    unmatched_all = u1 + u2 + u3
                    analysis_changed = bool(a2)
                    editorial_changed = bool(a3)
                    meta["trim_applied"] = applied_all[:40]
                    meta["trim_unmatched"] = unmatched_all[:40]

                if unmatched_all:
                    # Never enqueue trim_narrative_chunk — not in action CHECK.
                    # Unmatched spans stay in meta for HITL / audit only.
                    meta["trim_hitl_pending"] = unmatched_all[:20]
                    logger.info(
                        "finisher trim unmatched spans=%s storyline=%s (meta only, no membership enqueue)",
                        len(unmatched_all),
                        storyline_id,
                    )

                text_changed = bool(canonical) or bool(applied_all)
                if text_changed:
                    cur.execute(
                        f"""
                        UPDATE {schema}.storylines
                        SET
                            canonical_narrative = COALESCE(NULLIF(%s, ''), canonical_narrative),
                            analysis_summary = CASE
                                WHEN %s THEN %s ELSE analysis_summary END,
                            editorial_document = CASE
                                WHEN %s THEN %s ELSE editorial_document END,
                            narrative_finisher_meta = %s::jsonb,
                            narrative_finisher_model = %s,
                            narrative_finisher_at = NOW(),
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            base_canon,
                            analysis_changed,
                            new_analysis,
                            editorial_changed,
                            new_editorial,
                            json.dumps(meta),
                            run_result.get("model"),
                            storyline_id,
                        ),
                    )
                else:
                    cur.execute(
                        f"""
                        UPDATE {schema}.storylines
                        SET
                            narrative_finisher_meta = %s::jsonb,
                            narrative_finisher_model = %s,
                            narrative_finisher_at = NOW()
                        WHERE id = %s
                        """,
                        (json.dumps(meta), run_result.get("model"), storyline_id),
                    )
            conn.commit()
        return True
    except Exception as e:
        logger.exception("persist_narrative_finish_to_db: %s", e)
        return False


async def run_narrative_finish_placeholder_from_db(
    storyline_id: int,
    schema_name: str,
    domain_key: str,
) -> dict[str, Any]:
    """
    Backward-compatible entry: `schema_name` is ignored; loading uses `domain_key` only.
    Prefer `run_narrative_finish_from_db(domain_key, storyline_id)`.
    """
    _ = schema_name
    return await run_narrative_finish_from_db(domain_key, storyline_id)
