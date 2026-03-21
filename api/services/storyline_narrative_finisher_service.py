"""
Storyline narrative finisher — ~70B editorial pass over aggregated 8B/Mistral work.

See docs/STORYLINE_70B_NARRATIVE_FINISHER.md. This module builds the finisher prompt and
calls Ollama via OllamaModelCaller with InvocationKind.STORYLINE_NARRATIVE_FINISH.

Loads storyline + linked articles + entities from the domain schema; optional timeline rows from
`public.chronological_events`. Persistence of outputs (columns / automation) remains TODO.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from shared.database.connection import get_db_connection
from shared.services.ollama_model_caller import get_ollama_model_caller
from shared.services.ollama_model_policy import InvocationKind

logger = logging.getLogger(__name__)

# Domain keys with per-domain schemas (avoid dynamic schema from untrusted input)
_ALLOWED_DOMAIN_KEYS = frozenset({"politics", "finance", "science-tech"})


def _schema_name(domain_key: str) -> Optional[str]:
    if domain_key not in _ALLOWED_DOMAIN_KEYS:
        return None
    return domain_key.replace("-", "_")


@dataclass
class StorylineFinisherBundle:
    """Everything the finisher needs to see for one storyline (expand as wired to DB)."""

    domain_key: str
    schema_name: str
    storyline_id: int
    storyline_title: str
    storyline_status: str = ""
    existing_narrative: str = ""
    article_summaries: List[Dict[str, Any]] = field(default_factory=list)
    # e.g. [{"title": "...", "published_at": "...", "summary": "..."}]
    entity_highlights: List[str] = field(default_factory=list)
    context_labels: List[str] = field(default_factory=list)
    timeline_bullets: List[str] = field(default_factory=list)


def _strip_json_code_fence(blob: str) -> str:
    s = blob.strip()
    if s.startswith("```"):
        first = s.find("\n")
        if first != -1:
            s = s[first + 1 :]
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3].rstrip()
    return s.strip()


def parse_finisher_response(raw_text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Extract JSON after the line ---JSON--- (see build_finisher_prompt).

    Returns (parsed_dict, error_reason). error_reason is None on success.
    """
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
) -> Optional[StorylineFinisherBundle]:
    """
    Load storyline row, linked articles (summaries), top entities, and optional chrono bullets.

    Returns None if domain invalid, no connection, or storyline missing.
    """
    schema = _schema_name(domain_key)
    if not schema:
        logger.warning("load_finisher_bundle_from_db: invalid domain_key=%s", domain_key)
        return None

    conn = get_db_connection()
    if not conn:
        logger.error("load_finisher_bundle_from_db: no DB connection")
        return None

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, title, description, status, analysis_summary,
                       background_information, editorial_document, key_entities
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

            parts = [description, analysis_summary, editorial_document]
            existing_narrative = "\n\n".join(p.strip() for p in parts if p and str(p).strip())

            context_labels: List[str] = []
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

            article_summaries: List[Dict[str, Any]] = []
            article_ids: List[int] = []
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

            entity_highlights: List[str] = []
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

            timeline_bullets: List[str] = []
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
            )
    except Exception as e:
        logger.exception("load_finisher_bundle_from_db failed: %s", e)
        return None
    finally:
        conn.close()


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

Tasks:
1) Write a refined **canonical narrative** (4–12 short paragraphs): what this storyline IS, how it evolved, who/what matters, and what is uncertain. Write for analysts re-opening this in a month — not a recap of today's headlines only.
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


async def run_narrative_finish(
    bundle: StorylineFinisherBundle,
    *,
    approx_prompt_chars: Optional[int] = None,
    parse_json: bool = True,
) -> Dict[str, Any]:
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
    out: Dict[str, Any] = {
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
) -> Dict[str, Any]:
    """
    Load bundle from DB, run finisher. On missing storyline returns success=False.
    """
    bundle = load_finisher_bundle_from_db(
        domain_key, storyline_id, max_articles=max_articles
    )
    if not bundle:
        return {
            "success": False,
            "storyline_id": storyline_id,
            "domain_key": domain_key,
            "error": "storyline_not_found_or_load_failed",
        }
    return await run_narrative_finish(bundle, parse_json=parse_json)


def persist_narrative_finish_to_db(domain_key: str, storyline_id: int, run_result: Dict[str, Any]) -> bool:
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
    canonical = (parsed.get("canonical_narrative") or "").strip()
    meta: Dict[str, Any] = {
        "suggested_new_entities": parsed.get("suggested_new_entities"),
        "suggested_new_context_hooks": parsed.get("suggested_new_context_hooks"),
        "sections_to_deprecate_or_trim": parsed.get("sections_to_deprecate_or_trim"),
        "open_questions": parsed.get("open_questions"),
        "parse_error": run_result.get("parse_error"),
        "model": run_result.get("model"),
    }
    raw = run_result.get("raw_text") or ""
    if raw:
        meta["raw_excerpt"] = raw[:4000]

    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
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
        conn.commit()
        return True
    except Exception as e:
        logger.exception("persist_narrative_finish_to_db: %s", e)
        conn.rollback()
        return False
    finally:
        conn.close()


async def run_narrative_finish_placeholder_from_db(
    storyline_id: int,
    schema_name: str,
    domain_key: str,
) -> Dict[str, Any]:
    """
    Backward-compatible entry: `schema_name` is ignored; loading uses `domain_key` only.
    Prefer `run_narrative_finish_from_db(domain_key, storyline_id)`.
    """
    _ = schema_name
    return await run_narrative_finish_from_db(domain_key, storyline_id)
