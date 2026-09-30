"""
Storyline narrative finisher — ~70B editorial walkthrough over aggregated 8B/Mistral work.

See docs/_archive/retired_root_docs_2026_03/STORYLINE_70B_NARRATIVE_FINISHER.md. This module builds the finisher prompt and
calls Ollama via OllamaModelCaller with InvocationKind.STORYLINE_NARRATIVE_FINISH.

Loads storyline + linked articles + entities from the domain schema; optional timeline rows from
`public.chronological_events`; Wikipedia/GDELT RAG from `intelligence.storyline_rag_context`.
Persists `canonical_narrative` + `narrative_finisher_meta`.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shared.database.connection import get_ephemeral_db_connection_context
from shared.domain_registry import domain_key_to_schema, is_valid_domain_key
from shared.services.ollama_model_caller import get_ollama_model_caller
from shared.services.ollama_model_policy import InvocationKind

logger = logging.getLogger(__name__)

PROMPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "prompts"
    / "narrative"
    / "storyline_walkthrough.md"
)
PROMPT_VERSION = "storyline_walkthrough.v1"


def _schema_name(domain_key: str) -> str | None:
    if not is_valid_domain_key(domain_key):
        return None
    try:
        return domain_key_to_schema(domain_key)
    except KeyError:
        return None


def _load_walkthrough_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("storyline walkthrough prompt missing: %s", e)
        return (
            "Write an editorial walkthrough (lede, background, proposal, what happened, "
            "competing explanations, why it matters, open questions). Use only provided "
            "evidence. Output JSON after ---JSON--- with canonical_narrative and "
            "competing_theories."
        )


def _parse_json_maybe(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def _analysis_bones_from_row(
    description: str,
    analysis_summary: str,
    editorial_raw: Any,
) -> str:
    """Compact prior analysis for the walkthrough (description + analysis + editorial lede/analysis)."""
    parts: list[str] = []
    if description and str(description).strip():
        parts.append(f"Description:\n{str(description).strip()[:4000]}")
    if analysis_summary and str(analysis_summary).strip():
        parts.append(f"Analysis summary:\n{str(analysis_summary).strip()[:4000]}")
    ed = _parse_json_maybe(editorial_raw)
    if isinstance(ed, dict):
        lede = (ed.get("lede") or "").strip() if isinstance(ed.get("lede"), str) else ""
        analysis = (ed.get("analysis") or "").strip() if isinstance(ed.get("analysis"), str) else ""
        if lede:
            parts.append(f"Editorial lede:\n{lede[:3000]}")
        if analysis:
            parts.append(f"Editorial analysis:\n{analysis[:6000]}")
    elif editorial_raw and str(editorial_raw).strip() and not isinstance(ed, dict):
        parts.append(f"Editorial document:\n{str(editorial_raw).strip()[:4000]}")
    return "\n\n".join(parts).strip()

def _title_theme_tokens(title: str) -> set[str]:
    """Significant tokens from the storyline title for off-theme timeline filtering."""
    stop = {
        "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "as", "at", "by",
        "from", "with", "until", "amid", "after", "before", "over", "into", "no", "not",
        "is", "are", "was", "were", "be", "been", "s", "plan", "vows", "rejects", "says",
        # Global figures appear in many off-theme CE rows; alone they are not theme.
        "trump", "biden", "putin", "xi", "obama", "harris",
    }
    tokens = set()
    for raw in (title or "").lower().replace("'", " ").replace("-", " ").split():
        t = "".join(ch for ch in raw if ch.isalnum())
        if len(t) < 4 or t in stop:
            continue
        tokens.add(t)
    return tokens


def _timeline_bullet_on_theme(bullet: str, theme_tokens: set[str]) -> bool:
    """Keep bullets that share a distinctive title token; if title has no tokens, keep all."""
    if not theme_tokens:
        return True
    low = (bullet or "").lower()
    return any(tok in low for tok in theme_tokens)


@dataclass
class StorylineFinisherBundle:
    """Everything the finisher needs to see for one storyline (expand as wired to DB)."""

    domain_key: str
    schema_name: str
    storyline_id: int
    storyline_title: str
    storyline_status: str = ""
    existing_narrative: str = ""
    analysis_bones: str = ""
    article_summaries: list[dict[str, Any]] = field(default_factory=list)
    # e.g. [{"title": "...", "published_at": "...", "summary": "..."}]
    entity_highlights: list[str] = field(default_factory=list)
    context_labels: list[str] = field(default_factory=list)
    timeline_bullets: list[str] = field(default_factory=list)
    historical_context_rendered: str = ""
    rag_context_rendered: str = ""
    vault_context_rendered: str = ""


def _strip_json_code_fence(blob: str) -> str:
    s = blob.strip()
    if s.startswith("```"):
        first = s.find("\n")
        if first != -1:
            s = s[first + 1 :]
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3].rstrip()
    return s.strip()


def parse_finisher_response(raw_text: str) -> tuple[dict[str, Any] | None, str | None]:
    """
    Extract JSON after the line ---JSON--- (see build_finisher_prompt).

    Falls back to a trailing JSON object, or markdown-only walkthrough as canonical_narrative.
    Strips common chain-of-thought preambles from thinking models.
    Returns (parsed_dict, error_reason). error_reason is None on success.
    """
    if not raw_text or not raw_text.strip():
        return None, "empty_response"

    original = raw_text.strip()

    def _try_json_blob(blob: str) -> dict[str, Any] | None:
        rest = _strip_json_code_fence(blob)
        try:
            data = json.loads(rest)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    # Prefer explicit ---JSON--- marker on the original payload first.
    marker = "---JSON---"
    if marker in original:
        prose, rest = original.rsplit(marker, 1)
        data = _try_json_blob(rest)
        if data is not None:
            if not (data.get("canonical_narrative") or "").strip() and prose.strip():
                # Prefer markdown walkthrough ahead of the marker when JSON omits body.
                cut = prose
                for m in ("## Lede", "## lede"):
                    idx = cut.find(m)
                    if idx >= 0:
                        cut = cut[idx:]
                        break
                data["canonical_narrative"] = cut.strip()[:12000]
            return data, None
        logger.warning("finisher JSON parse failed after marker")

    # Trailing JSON object without marker
    start_i = original.rfind("{")
    end_i = original.rfind("}")
    if start_i >= 0 and end_i > start_i:
        data = _try_json_blob(original[start_i : end_i + 1])
        if data is not None and (
            data.get("canonical_narrative") or data.get("competing_theories") is not None
        ):
            return data, None

    # Markdown walkthrough recovery: drop CoT preamble, keep from ## Lede onward.
    text = original
    for m in ("</think>", "</thinking>"):
        idx = text.find(m)
        if idx >= 0:
            text = text[idx + len(m) :].strip()
    lede_idx = text.find("## Lede")
    if lede_idx < 0:
        lede_idx = text.lower().find("## lede")
    if lede_idx >= 0:
        text = text[lede_idx:]
    body = text.strip()
    if "## " in body and ("lede" in body.lower() or "background" in body.lower()):
        return {
            "canonical_narrative": body[:12000],
            "competing_theories": [],
            "open_questions": [],
            "suggested_new_entities": [],
            "suggested_new_context_hooks": [],
            "sections_to_deprecate_or_trim": [],
            "insufficient_evidence": False,
            "gaps": ["model_omitted_json_marker"],
        }, None

    return None, "no_json_marker"



def _load_rag_rendered_sync(conn, domain_key: str, storyline_id: int) -> str:
    """Best-effort sync read of stored wiki/GDELT context for the finisher prompt."""
    try:
        from services.storyline_rag_context_service import render_rag_context_for_llm

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT rag_data
                FROM intelligence.storyline_rag_context
                WHERE domain_key = %s AND storyline_id = %s
                ORDER BY updated_at DESC NULLS LAST
                LIMIT 1
                """,
                (domain_key, int(storyline_id)),
            )
            row = cur.fetchone()
        if not row:
            return ""
        rag_data = _parse_json_maybe(row[0]) if not isinstance(row[0], dict) else row[0]
        return render_rag_context_for_llm(rag_data if isinstance(rag_data, dict) else None, max_chars=6000)
    except Exception as e:
        logger.debug("finisher RAG sync load skipped: %s", e)
        return ""


def load_finisher_bundle_from_db(
    domain_key: str,
    storyline_id: int,
    *,
    max_articles: int = 50,
    max_entities: int = 60,
    max_timeline: int = 80,
    rag_context_rendered: str | None = None,
) -> StorylineFinisherBundle | None:
    """
    Load storyline row, linked articles (summaries), top entities, chrono bullets, RAG.

    Returns None if domain invalid, no connection, or storyline missing.
    Pass ``rag_context_rendered`` when the async path already ensured/enhanced RAG.
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
                           canonical_narrative
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
                editorial_document = row[6]
                key_entities_raw = row[7]
                canonical_narrative = row[8] or ""

                analysis_bones = _analysis_bones_from_row(
                    description, analysis_summary, editorial_document
                )
                existing_parts = [
                    p.strip()
                    for p in (canonical_narrative, analysis_bones)
                    if p and str(p).strip()
                ]
                existing_narrative = "\n\n".join(existing_parts)

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
                    SELECT a.id, a.title, a.url, a.source_domain, a.published_at, a.summary
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
                    aid, atitle, url, source_domain, published_at, summary = r
                    article_ids.append(int(aid))
                    article_summaries.append(
                        {
                            "id": aid,
                            "title": atitle,
                            "url": url,
                            "source_domain": source_domain,
                            "published_at": published_at.isoformat() if published_at else None,
                            "summary": (summary or "")[:4000],
                        }
                    )

                entity_highlights: list[str] = []
                entity_ids: list[int] = []
                if article_ids:
                    cur.execute(
                        f"""
                        SELECT ec.id, ec.canonical_name, ec.entity_type,
                               COUNT(ae.article_id) AS mention_count
                        FROM {schema}.article_entities ae
                        JOIN {schema}.entity_canonical ec ON ec.id = ae.canonical_entity_id
                        WHERE ae.article_id = ANY(%s)
                        GROUP BY ec.id, ec.canonical_name, ec.entity_type
                        ORDER BY mention_count DESC
                        LIMIT %s
                        """,
                        (article_ids, max_entities),
                    )
                    for eid, name, etype, cnt in cur.fetchall():
                        label = (name or "").strip()
                        if not label:
                            continue
                        if eid is not None:
                            entity_ids.append(int(eid))
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

                theme_tokens = _title_theme_tokens(title)
                if theme_tokens and timeline_bullets:
                    filtered = [b for b in timeline_bullets if _timeline_bullet_on_theme(b, theme_tokens)]
                    if filtered:
                        timeline_bullets = filtered
                    else:
                        # Prefer empty over off-theme spillover (articles/RAG/bones carry the story).
                        logger.info(
                            "finisher timeline theme filter dropped all %s bullets for storyline %s",
                            len(timeline_bullets),
                            storyline_id,
                        )
                        timeline_bullets = []

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

                rag_rendered = (rag_context_rendered or "").strip()
                if not rag_rendered:
                    rag_rendered = _load_rag_rendered_sync(conn, domain_key, storyline_id)

                vault_rendered = ""
                if entity_ids:
                    try:
                        from domains.reader.services.vault_context_pack import (
                            build_vault_pack_for_entity_ids,
                            render_vault_context_pack_for_llm,
                        )

                        vpack = build_vault_pack_for_entity_ids(
                            domain_key, entity_ids[:16], hops=2, max_notes=10
                        )
                        vault_rendered = render_vault_context_pack_for_llm(
                            vpack, max_chars=6000
                        )
                    except Exception as ve:
                        logger.debug("finisher vault_context skipped: %s", ve)

                return StorylineFinisherBundle(
                    domain_key=domain_key,
                    schema_name=schema,
                    storyline_id=storyline_id,
                    storyline_title=title,
                    storyline_status=status,
                    existing_narrative=existing_narrative,
                    analysis_bones=analysis_bones,
                    article_summaries=article_summaries,
                    entity_highlights=entity_highlights,
                    context_labels=uniq_contexts,
                    timeline_bullets=timeline_bullets,
                    historical_context_rendered=historical_rendered,
                    rag_context_rendered=rag_rendered,
                    vault_context_rendered=vault_rendered,
                )
    except Exception as e:
        logger.exception("load_finisher_bundle_from_db failed: %s", e)
        return None


def build_finisher_prompt(bundle: StorylineFinisherBundle) -> str:
    """
    Editorial walkthrough prompt: integrate bones + RAG into a durable canonical narrative.
    """
    instructions = _load_walkthrough_prompt()
    articles_block = json.dumps(bundle.article_summaries, indent=2)[:24000]
    entities = "\n".join(f"- {e}" for e in bundle.entity_highlights[:80])
    contexts = "\n".join(f"- {c}" for c in bundle.context_labels[:80])
    timeline = "\n".join(f"- {t}" for t in bundle.timeline_bullets[:120])
    analysis = (bundle.analysis_bones or bundle.existing_narrative or "")[:12000]
    rag = (bundle.rag_context_rendered or "").strip()[:6000] or "(none loaded)"
    vault = (bundle.vault_context_rendered or "").strip()[:6000] or "(none loaded)"
    historical = (
        bundle.historical_context_rendered[:14000]
        if bundle.historical_context_rendered
        else "(none loaded)"
    )

    return f"""{instructions}

---
Prompt version: {PROMPT_VERSION}

Storyline id: {bundle.storyline_id}
Domain: {bundle.domain_key}
Title: {bundle.storyline_title}
Status: {bundle.storyline_status}

Prior analysis / bones (may be draft or template-heavy):
---
{analysis or "(none)"}
---

Article-level material (titles, dates, short summaries from the fast pipeline):
{articles_block}

Notable entities (from extraction):
{entities or "(none listed)"}

Context labels:
{contexts or "(none listed)"}

Timeline / event bullets (filter off-theme noise per hard rules):
{timeline or "(none listed)"}

Established facts and chronological spine (durable memory; may include older events):
{historical}

Living vault (Obsidian longform / relational background for this arc — prefer this over inventing history):
{vault}

External RAG context (Wikipedia / GDELT — background only; do not invent beyond this):
{rag}

FINAL INSTRUCTION: Do NOT write chain-of-thought, scratchpads, or "thinking process" text.
Start the response with `## Lede` for THIS title only ({bundle.storyline_title}).
Ignore timeline or RAG material that is not about this story. Use living vault for durable
arc background when present. After the markdown sections,
output a line with exactly ---JSON--- and the JSON object. Do not omit the ---JSON--- marker.
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
    """Parse ---JSON--- block from headline refiner output."""
    if not raw_text or not raw_text.strip():
        return None, "empty_response"
    marker = "---JSON---"
    if marker not in raw_text:
        return None, "no_json_marker"
    _, rest = raw_text.rsplit(marker, 1)
    rest = _strip_json_code_fence(rest)
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
        urgency="high",
        approx_prompt_chars=approx_prompt_chars if approx_prompt_chars is not None else len(prompt),
    )
    logger.info(
        "storyline_narrative_finish storyline_id=%s model=%s chars=%s rag_chars=%s",
        bundle.storyline_id,
        result.model,
        len(prompt),
        len(bundle.rag_context_rendered or ""),
    )
    out: dict[str, Any] = {
        "success": True,
        "storyline_id": bundle.storyline_id,
        "domain_key": bundle.domain_key,
        "model": result.model,
        "raw_text": result.text,
        "prompt_version": PROMPT_VERSION,
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
    Ensure RAG context when possible, load bundle from DB, run finisher.
    On missing storyline returns success=False.
    """
    rag_rendered = ""
    try:
        from services.storyline_rag_context_service import (
            ensure_storyline_rag_context,
            render_rag_context_for_llm,
        )

        rag_data = await ensure_storyline_rag_context(domain_key, storyline_id)
        if isinstance(rag_data, dict):
            rag_rendered = render_rag_context_for_llm(rag_data, max_chars=6000)
    except Exception as e:
        logger.debug("ensure_storyline_rag_context before finisher skipped: %s", e)

    bundle = load_finisher_bundle_from_db(
        domain_key,
        storyline_id,
        max_articles=max_articles,
        rag_context_rendered=rag_rendered or None,
    )
    if not bundle:
        return {
            "success": False,
            "storyline_id": storyline_id,
            "domain_key": domain_key,
            "error": "storyline_not_found_or_load_failed",
        }
    return await run_narrative_finish(bundle, parse_json=parse_json)


def persist_narrative_finish_to_db(
    domain_key: str, storyline_id: int, run_result: dict[str, Any]
) -> bool:
    """
    Persist ~70B finisher output to `{schema}.storylines` (migration 181 columns).
    Empty canonical_narrative in parsed output leaves prior canonical text unchanged.
    """
    schema = _schema_name(domain_key)
    if not schema:
        return False
    parsed = run_result.get("parsed")
    if not isinstance(parsed, dict):
        parsed = {}
    from shared.llm_text_sanitize import strip_json_fence, strip_llm_wrapping_artifacts

    # Keep multi-section markdown intact — sanitize_on_persist/narrative collapses to one line.
    canonical_raw = (parsed.get("canonical_narrative") or "").strip()
    canonical = strip_json_fence(canonical_raw)
    if len(canonical) > 12000:
        canonical = canonical[:11980].rstrip() + "\n…"
    # Only apply light JSON/fence cleanup when the body is not already markdown sections.
    if canonical and "## " not in canonical and not canonical.lower().startswith("lede"):
        canonical = strip_llm_wrapping_artifacts(canonical, max_length=12000)
    meta: dict[str, Any] = {
        "prompt_version": run_result.get("prompt_version") or PROMPT_VERSION,
        "suggested_new_entities": parsed.get("suggested_new_entities"),
        "suggested_new_context_hooks": parsed.get("suggested_new_context_hooks"),
        "sections_to_deprecate_or_trim": parsed.get("sections_to_deprecate_or_trim"),
        "open_questions": parsed.get("open_questions"),
        "competing_theories": parsed.get("competing_theories"),
        "insufficient_evidence": parsed.get("insufficient_evidence"),
        "gaps": parsed.get("gaps"),
        "parse_error": run_result.get("parse_error"),
        "model": run_result.get("model"),
    }
    raw = run_result.get("raw_text") or ""
    if raw:
        meta["raw_excerpt"] = raw[:4000]

    try:
        with get_ephemeral_db_connection_context() as conn:
            with conn.cursor() as cur:
                # Bump storyline.updated_at only when canonical text is applied (new narrative), not
                # on meta-only / empty refresh passes — keeps "last updated" aligned with real change.
                if canonical:
                    cur.execute(
                        f"""
                        UPDATE {schema}.storylines
                        SET
                            canonical_narrative = COALESCE(NULLIF(%s, ''), canonical_narrative),
                            narrative_finisher_meta = %s::jsonb,
                            narrative_finisher_model = %s,
                            narrative_finisher_at = NOW(),
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (canonical, json.dumps(meta), run_result.get("model"), storyline_id),
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


def apply_sections_to_deprecate_or_trim(
    text: Any,
    spans: list[str] | None,
) -> tuple[str, int, list[str]]:
    """
    Remove deprecated narrative spans from stored prose (core-prune auto-apply).

    Returns ``(new_text, applied_count, unmatched_spans)``.
    Non-string inputs (e.g. jsonb ``editorial_document``) are left unchanged and
    every span is reported unmatched so callers can queue HITL trims.
    """
    if not isinstance(text, str):
        return "", 0, [str(s) for s in (spans or []) if s]
    out = text
    applied = 0
    unmatched: list[str] = []
    for raw in spans or []:
        span = (raw or "").strip()
        if len(span) < 24:
            if span:
                unmatched.append(span)
            continue
        if span in out:
            out = out.replace(span, "", 1)
            applied += 1
            continue
        # Soft match: collapse whitespace differences for a single occurrence.
        soft = re.sub(r"\s+", " ", span)
        soft_out = re.sub(r"\s+", " ", out)
        idx = soft_out.find(soft)
        if idx < 0:
            unmatched.append(span)
            continue
        # Map soft index back approximately via original span remove if unique-ish
        # Fallback: leave unmatched when we cannot safely locate in original text.
        unmatched.append(span)
    if applied:
        out = re.sub(r"\n{3,}", "\n\n", out).strip()
    return out, applied, unmatched


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
