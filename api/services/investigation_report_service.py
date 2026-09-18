"""
Investigation report service — journalism-style dossier from a tracked event.

Uses event + chronicles + full context text to generate:
- Executive summary
- Timeline of developments
- Key entities and roles
- Sources
- What we know / what's uncertain

Supports iterative improvement: regenerate when new contexts or chronicles are added.

Large containers (contexts_total > INVESTIGATION_REPORT_ASYNC_THRESHOLD) enqueue a
durable job in intelligence.investigation_report_jobs and finish in the background;
clients poll GET /tracked_events/{id}/report for status/ready.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from config.runtime import env_int
from shared.database.connection import get_db_connection
from shared.services.llm_service import LLMService, ModelType

logger = logging.getLogger(__name__)

# Bound prompt size so sync POST /tracked_events/{id}/report stays under the API budget.
_MAX_REPORT_CONTEXTS = max(1, min(40, env_int("INVESTIGATION_REPORT_MAX_CONTEXTS", 12)))
# When linked contexts exceed this, POST returns 202 and generates in the background.
_ASYNC_THRESHOLD = max(
    1,
    env_int("INVESTIGATION_REPORT_ASYNC_THRESHOLD", _MAX_REPORT_CONTEXTS),
)
# Reclaim stuck running rows after API restart / worker death.
_STALE_RUNNING_SECONDS = max(60, env_int("INVESTIGATION_REPORT_JOB_STALE_SECONDS", 600))
# Soft coherence: when many contexts share almost no tokens with the event title, refuse merge.
_COHERENCE_MIN_CONTEXTS = 4
_COHERENCE_MIN_HIT_FRACTION = 0.25
_COHERENCE_TOKEN_MIN_LEN = 4
_JOB_IN_FLIGHT: dict[int, asyncio.Task] = {}
_STOPWORDS = frozenset(
    {
        "about",
        "after",
        "against",
        "among",
        "because",
        "before",
        "being",
        "between",
        "could",
        "during",
        "from",
        "have",
        "into",
        "other",
        "over",
        "same",
        "such",
        "than",
        "that",
        "their",
        "there",
        "these",
        "this",
        "those",
        "through",
        "under",
        "until",
        "what",
        "when",
        "where",
        "which",
        "while",
        "with",
        "would",
        "study",
        "report",
        "update",
        "news",
    }
)

DOSSIER_PROMPT = """You are a senior investigative journalist writing a dossier on a developing story.
Prioritize facts and provenance over polish. Do not invent dates, quotes, actors, or causal claims.

INVESTIGATION: {event_name}
Type: {event_type}
Geographic scope: {geographic_scope}
Time span: {time_span}

CHRONICLE SUMMARIES (analyst summaries for each update):
{chronicle_block}

SUPPORTING CONTEXTS (evidence from sources; each has a title and excerpt):
{context_block}

Write a journalism-style investigation report in markdown with these sections (in this order):

## What We Know
Bullet points of established facts supported by the evidence. Each bullet should be checkable against the contexts/chronicles above. Prefer short sentences.

## What's Uncertain
Open questions, conflicting reports, or gaps in the evidence. Explicitly flag when sources may be conflating distinct theaters (e.g. Red Sea / Houthi vs Strait of Hormuz).

## Sources
List the sources/outlets that appear in the contexts (if evident from titles or metadata). Note corroboration when multiple sources agree.

## Timeline of Developments
Chronological list of key developments with dates drawn only from the chronicle summaries and context excerpts. Note when multiple sources corroborate. Omit undated speculation.

## Key Entities & Roles
Who or what is central to this story (people, organisations, places). One line each.

## Executive Summary
2-4 sentences only after the evidence sections: what this story is, current status, and why it matters — grounded in What We Know.

{CROSS_DOMAIN_BLOCK}

Use a neutral, factual tone. Prefer short sentences. Do not invent facts beyond what the evidence suggests. If evidence is thin, say so in What's Uncertain rather than filling gaps with fluent prose."""

CROSS_DOMAIN_SECTION = """
CROSS-DOMAIN LINKS (related tracked_events from correlation graph — use only as background; primary evidence is above):
{cross_domain_block}
"""


def _strip_html(text: str, max_len: int = 2000) -> str:
    if not text:
        return ""
    s = re.sub(r"<[^>]+>", " ", text).strip()
    s = re.sub(r"\s+", " ", s)
    return s[:max_len] + ("..." if len(s) > max_len else "")


def _gather_event_data(event_id: int) -> dict[str, Any] | None:
    """Load event, chronicles, and full context text for all developments. Returns None if event not found."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, event_type, event_name, start_date, end_date, geographic_scope
                FROM intelligence.tracked_events
                WHERE id = %s
                """,
                (event_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            event = {
                "id": row[0],
                "event_type": row[1],
                "event_name": row[2],
                "start_date": str(row[3]) if row[3] else None,
                "end_date": str(row[4]) if row[4] else None,
                "geographic_scope": row[5],
            }
            cur.execute(
                """
                SELECT id, update_date, developments, analysis
                FROM intelligence.event_chronicles
                WHERE event_id = %s
                ORDER BY update_date ASC
                """,
                (event_id,),
            )
            chronicles = []
            context_ids = set()
            for r in cur.fetchall():
                devs = (
                    r[2]
                    if isinstance(r[2], list)
                    else (json.loads(r[2]) if isinstance(r[2], str) else [])
                )
                analysis = (
                    r[3]
                    if isinstance(r[3], dict)
                    else (json.loads(r[3]) if isinstance(r[3], str) else {})
                )
                for d in devs:
                    if isinstance(d, dict) and d.get("context_id") is not None:
                        context_ids.add(int(d["context_id"]))
                chronicles.append(
                    {
                        "id": r[0],
                        "update_date": str(r[1]) if r[1] else None,
                        "developments": devs,
                        "analysis": analysis,
                    }
                )
            event["chronicles"] = chronicles

            if not context_ids:
                conn.close()
                return event

            # Prefer newest contexts and bound SQL gather to the prompt budget (+slack).
            ordered_ids = sorted(context_ids)
            cur.execute(
                """
                SELECT id, title, content, metadata, created_at
                FROM intelligence.contexts
                WHERE id = ANY(%s)
                ORDER BY created_at DESC NULLS LAST, id DESC
                LIMIT %s
                """,
                (list(ordered_ids), int(_MAX_REPORT_CONTEXTS) * 2),
            )
            contexts_by_id = {}
            for r in cur.fetchall():
                meta = (
                    r[3]
                    if isinstance(r[3], dict)
                    else (json.loads(r[3]) if isinstance(r[3], str) else {})
                )
                contexts_by_id[r[0]] = {
                    "id": r[0],
                    "title": (r[1] or "")[:500],
                    "content": _strip_html(r[2] or "", 1200),
                    "metadata": meta,
                    "created_at": r[4].isoformat() if r[4] else None,
                }
            event["contexts"] = contexts_by_id
            event["context_ids"] = sorted(context_ids)
            event["contexts_total"] = len(context_ids)
        conn.close()
        return event
    except Exception as e:
        logger.warning(f"investigation_report gather_data: {e}")
        try:
            conn.close()
        except Exception:
            pass
        return None


def _build_chronicle_block(chronicles: list[dict], contexts: dict[int, dict]) -> str:
    lines = []
    for i, ch in enumerate(chronicles, 1):
        date_str = ch.get("update_date") or "Date unknown"
        analysis = ch.get("analysis") or {}
        summary = analysis.get("summary") or "No summary"
        devs = ch.get("developments") or []
        refs = []
        for d in devs:
            cid = d.get("context_id")
            if cid is not None and cid in contexts:
                refs.append(f"Context #{cid}: {contexts[cid].get('title', '')[:80]}")
        ref_line = " | ".join(refs[:5]) if refs else "No contexts"
        lines.append(f"{i}. [{date_str}] {summary}\n   Evidence: {ref_line}")
    return "\n\n".join(lines) if lines else "No chronicles."


def _build_cross_domain_link_block(event_id: int) -> str:
    """Summaries of other tracked_events meaningfully related via correlations."""
    conn = get_db_connection()
    if not conn:
        return ""
    lines: list[str] = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT domain_1, domain_2, correlation_type, correlation_strength, event_ids
                FROM intelligence.cross_domain_correlations
                WHERE %s = ANY(event_ids)
                  AND cardinality(COALESCE(event_ids, '{}')) BETWEEN 2 AND 12
                  AND correlation_type IN ('entity_overlap', 'thematic')
                ORDER BY discovered_at DESC NULLS LAST
                LIMIT 12
                """,
                (event_id,),
            )
            rows = cur.fetchall() or []
        other_ids: set[int] = set()
        for r in rows:
            eids = list(r[4]) if r[4] else []
            for eid in eids:
                if isinstance(eid, int) and eid != event_id:
                    other_ids.add(eid)
        if not other_ids:
            conn.close()
            return ""
        with conn.cursor() as cur:
            from services.event_tracking_service import development_title_matches_event

            cur.execute(
                "SELECT event_name FROM intelligence.tracked_events WHERE id = %s",
                (event_id,),
            )
            self_name_row = cur.fetchone()
            self_name = (self_name_row[0] if self_name_row else "") or ""
            cur.execute(
                """
                SELECT id, event_name, event_type, COALESCE(domain_keys, '{}') AS domain_keys
                FROM intelligence.tracked_events
                WHERE id = ANY(%s)
                """,
                (list(other_ids)[:30],),
            )
            for r in cur.fetchall() or []:
                if self_name and not development_title_matches_event(self_name, r[1]):
                    continue
                dks = ", ".join(list(r[3]) if r[3] else [])
                lines.append(f"- Event #{r[0]} ({r[2]}): {r[1] or ''} [domains: {dks}]")
                if len(lines) >= 8:
                    break
        conn.close()
    except Exception as e:
        logger.debug("_build_cross_domain_link_block: %s", e)
        try:
            conn.close()
        except Exception:
            pass
    return "\n".join(lines) if lines else ""


def _build_context_block(contexts: dict[int, dict]) -> str:
    lines = []
    for cid, ctx in sorted(contexts.items(), key=lambda x: x[1].get("created_at") or ""):
        title = ctx.get("title") or f"Context #{cid}"
        content = ctx.get("content") or "(No content)"
        created = ctx.get("created_at") or ""
        lines.append(f"[Context #{cid}] {title}\nDate: {created}\n{content}\n")
    return "\n---\n".join(lines) if lines else "No context text."


def _significant_tokens(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {
        t
        for t in tokens
        if len(t) >= _COHERENCE_TOKEN_MIN_LEN and t not in _STOPWORDS and not t.isdigit()
    }


def assess_context_coherence(
    event_name: str,
    contexts: dict[int, dict],
    *,
    min_contexts: int | None = None,
    min_hit_fraction: float | None = None,
) -> tuple[bool, str, dict[str, Any]]:
    """
    Cheap title-overlap gate before LLM synthesize.

    When many supporting contexts share almost no significant tokens with the
    tracked-event title, refuse a single merged dossier (kitchen-sink bags).
    """
    floor_n = int(min_contexts if min_contexts is not None else _COHERENCE_MIN_CONTEXTS)
    floor_frac = float(
        min_hit_fraction if min_hit_fraction is not None else _COHERENCE_MIN_HIT_FRACTION
    )
    meta: dict[str, Any] = {
        "contexts_checked": len(contexts or {}),
        "hit_count": 0,
        "hit_fraction": 1.0,
        "event_tokens": [],
    }
    if not contexts or len(contexts) < floor_n:
        return True, "ok_sparse", meta

    event_tokens = _significant_tokens(event_name)
    meta["event_tokens"] = sorted(event_tokens)[:24]
    if not event_tokens:
        return True, "ok_no_event_tokens", meta

    hits = 0
    for ctx in contexts.values():
        title_tokens = _significant_tokens(str(ctx.get("title") or ""))
        if event_tokens & title_tokens:
            hits += 1
    frac = hits / max(1, len(contexts))
    meta["hit_count"] = hits
    meta["hit_fraction"] = round(frac, 3)
    if frac < floor_frac:
        return (
            False,
            (
                f"Supporting contexts look thematically mixed with the event title "
                f"({hits}/{len(contexts)} title overlaps). Split the container or "
                f"refresh chronicles before generating a single dossier."
            ),
            meta,
        )
    return True, "ok", meta


def _select_contexts_for_prompt(contexts: dict[int, dict], max_n: int | None = None) -> dict[int, dict]:
    """Prefer newest contexts so container magnets do not explode prompt size."""
    limit = max_n if max_n is not None else _MAX_REPORT_CONTEXTS
    if not contexts or len(contexts) <= limit:
        return contexts
    ranked = sorted(
        contexts.items(),
        key=lambda x: x[1].get("created_at") or "",
        reverse=True,
    )
    return dict(ranked[:limit])


def async_report_threshold() -> int:
    return int(_ASYNC_THRESHOLD)


def should_generate_async(contexts_total: int | None, *, force: bool = False) -> bool:
    """True when POST should enqueue rather than wait for the LLM in-request."""
    if force:
        return True
    try:
        n = int(contexts_total or 0)
    except (TypeError, ValueError):
        n = 0
    return n > async_report_threshold()


def count_event_contexts(event_id: int) -> int | None:
    """Return linked context count for an event, or None if the event is missing."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM intelligence.tracked_events WHERE id = %s",
                (event_id,),
            )
            if not cur.fetchone():
                conn.close()
                return None
        conn.close()
    except Exception as e:
        logger.warning("count_event_contexts probe: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return None
    current = _current_context_ids_for_event(event_id)
    if current is None:
        return 0
    return len(current)


def get_investigation_report_job(event_id: int) -> dict[str, Any] | None:
    """Load durable job row, if the jobs table exists."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT event_id, status, error, contexts_total,
                       requested_at, started_at, finished_at, updated_at
                FROM intelligence.investigation_report_jobs
                WHERE event_id = %s
                """,
                (event_id,),
            )
            row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return {
            "event_id": row[0],
            "status": row[1],
            "error": row[2],
            "contexts_total": row[3],
            "requested_at": row[4].isoformat() if row[4] else None,
            "started_at": row[5].isoformat() if row[5] else None,
            "finished_at": row[6].isoformat() if row[6] else None,
            "updated_at": row[7].isoformat() if row[7] else None,
        }
    except Exception as e:
        logger.debug("get_investigation_report_job: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return None


def is_report_job_active(job: dict[str, Any] | None) -> bool:
    if not job:
        return False
    status = (job.get("status") or "").lower()
    if status not in ("queued", "running"):
        return False
    if status != "running":
        return True
    updated = job.get("updated_at") or job.get("started_at") or job.get("requested_at")
    if not updated:
        return True
    try:
        ts = datetime.fromisoformat(str(updated).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - ts).total_seconds()
        return age < _STALE_RUNNING_SECONDS
    except Exception:
        return True


def _upsert_report_job(
    event_id: int,
    status: str,
    *,
    error: str | None = None,
    contexts_total: int | None = None,
    mark_started: bool = False,
    mark_finished: bool = False,
) -> bool:
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.investigation_report_jobs
                    (event_id, status, error, contexts_total,
                     requested_at, started_at, finished_at, updated_at)
                VALUES (
                    %s, %s, %s, %s,
                    NOW(),
                    CASE WHEN %s THEN NOW() ELSE NULL END,
                    CASE WHEN %s THEN NOW() ELSE NULL END,
                    NOW()
                )
                ON CONFLICT (event_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    error = EXCLUDED.error,
                    contexts_total = COALESCE(EXCLUDED.contexts_total,
                                              intelligence.investigation_report_jobs.contexts_total),
                    requested_at = CASE
                        WHEN EXCLUDED.status = 'queued'
                        THEN NOW()
                        ELSE intelligence.investigation_report_jobs.requested_at
                    END,
                    started_at = CASE
                        WHEN %s THEN NOW()
                        WHEN EXCLUDED.status = 'queued' THEN NULL
                        ELSE intelligence.investigation_report_jobs.started_at
                    END,
                    finished_at = CASE
                        WHEN %s THEN NOW()
                        WHEN EXCLUDED.status IN ('queued', 'running') THEN NULL
                        ELSE intelligence.investigation_report_jobs.finished_at
                    END,
                    updated_at = NOW()
                """,
                (
                    event_id,
                    status,
                    error,
                    contexts_total,
                    mark_started,
                    mark_finished,
                    mark_started,
                    mark_finished,
                ),
            )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.warning("_upsert_report_job event_id=%s: %s", event_id, e)
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        return False


def save_investigation_report_result(result: dict[str, Any]) -> bool:
    """Persist a successful dossier to event_reports (+ saved_intel best-effort)."""
    if not result.get("success") or not result.get("report_md"):
        return False
    event_id = int(result["event_id"])
    conn = get_db_connection()
    if not conn:
        return False
    saved = False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.event_reports
                (event_id, report_md, generated_at, context_ids_included, chronicle_count, context_count)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (event_id) DO UPDATE SET
                    report_md = EXCLUDED.report_md,
                    generated_at = EXCLUDED.generated_at,
                    context_ids_included = EXCLUDED.context_ids_included,
                    chronicle_count = EXCLUDED.chronicle_count,
                    context_count = EXCLUDED.context_count
                """,
                (
                    event_id,
                    result["report_md"],
                    result["generated_at"],
                    result.get("context_ids_included") or [],
                    result.get("chronicle_count", 0),
                    result.get("context_count", 0),
                ),
            )
        conn.commit()
        conn.close()
        saved = True
    except Exception as e:
        logger.warning("save_investigation_report_result: %s", e)
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        return False

    try:
        from services.saved_intel_service import save_intel_output

        save_intel_output(
            content_type="event_report",
            subject_type="tracked_event",
            subject_id=event_id,
            content_md=result.get("report_md") or "",
            title=result.get("event_name"),
            metadata={
                "context_ids_included": result.get("context_ids_included") or [],
                "chronicle_count": result.get("chronicle_count", 0),
                "context_count": result.get("context_count", 0),
                "contexts_total": result.get("contexts_total"),
                "contexts_included": result.get("contexts_included"),
            },
            generated_at=result.get("generated_at"),
        )
    except Exception as e:
        logger.warning("save_intel_output event_report: %s", e)
    return saved


async def _run_investigation_report_job(event_id: int) -> None:
    """Background worker: mark running → generate → save → ready/failed."""
    try:
        _upsert_report_job(event_id, "running", mark_started=True)
        result = await generate_investigation_report(event_id)
        if not result.get("success"):
            _upsert_report_job(
                event_id,
                "failed",
                error=str(result.get("error") or "Report generation failed")[:2000],
                contexts_total=result.get("contexts_total"),
                mark_finished=True,
            )
            return
        if not save_investigation_report_result(result):
            _upsert_report_job(
                event_id,
                "failed",
                error="Failed to persist report",
                contexts_total=result.get("contexts_total"),
                mark_finished=True,
            )
            return
        _upsert_report_job(
            event_id,
            "ready",
            error=None,
            contexts_total=result.get("contexts_total"),
            mark_finished=True,
        )
        logger.info("Async investigation report ready for event_id=%s", event_id)
    except Exception as e:
        logger.exception("investigation_report job event_id=%s failed", event_id)
        _upsert_report_job(
            event_id,
            "failed",
            error=str(e)[:2000],
            mark_finished=True,
        )
    finally:
        task = _JOB_IN_FLIGHT.get(event_id)
        if task is not None and task.done():
            _JOB_IN_FLIGHT.pop(event_id, None)


def enqueue_investigation_report(
    event_id: int,
    *,
    contexts_total: int | None = None,
) -> dict[str, Any]:
    """
    Durable enqueue + schedule asyncio worker in this API process.

    Returns a status payload suitable for HTTP 202. If a non-stale job is already
    queued/running, returns that status without starting a duplicate worker.
    """
    existing = get_investigation_report_job(event_id)
    if is_report_job_active(existing):
        inflight = _JOB_IN_FLIGHT.get(event_id)
        if inflight is None or inflight.done():
            # Process restart left a durable queued/running row — resume worker.
            task = asyncio.create_task(
                _run_investigation_report_job(event_id),
                name=f"investigation_report_{event_id}",
            )
            _JOB_IN_FLIGHT[event_id] = task
        return {
            "success": True,
            "status": existing.get("status") if existing else "queued",
            "event_id": event_id,
            "contexts_total": (existing or {}).get("contexts_total", contexts_total),
            "async": True,
            "already_queued": True,
            "error": (existing or {}).get("error"),
            "requested_at": (existing or {}).get("requested_at"),
            "started_at": (existing or {}).get("started_at"),
        }

    ok = _upsert_report_job(
        event_id,
        "queued",
        error=None,
        contexts_total=contexts_total,
    )
    if not ok:
        return {
            "success": False,
            "status": "failed",
            "event_id": event_id,
            "contexts_total": contexts_total,
            "async": True,
            "error": "Could not enqueue report job (DB unavailable or migration 304 missing)",
        }

    task = asyncio.create_task(
        _run_investigation_report_job(event_id),
        name=f"investigation_report_{event_id}",
    )
    _JOB_IN_FLIGHT[event_id] = task
    return {
        "success": True,
        "status": "queued",
        "event_id": event_id,
        "contexts_total": contexts_total,
        "async": True,
        "already_queued": False,
    }


async def generate_investigation_report(event_id: int) -> dict[str, Any]:
    """
    Build dossier for a tracked event. Returns markdown report and metadata.
    """
    data = _gather_event_data(event_id)
    if not data:
        return {"success": False, "error": "Event not found or no data"}

    event_name = data.get("event_name") or "Unnamed investigation"
    event_type = data.get("event_type") or "other"
    geographic_scope = data.get("geographic_scope") or "Not specified"
    start = data.get("start_date") or "Unknown"
    end = data.get("end_date") or "Ongoing"
    time_span = f"{start} to {end}"

    chronicles = data.get("chronicles") or []
    contexts_all = data.get("contexts") or {}
    contexts_total = int(data.get("contexts_total") or len(contexts_all) or 0)
    if not chronicles and not contexts_all:
        return {
            "success": False,
            "error": "No chronicles or contexts yet; refresh chronicles before generating a report",
        }

    contexts = _select_contexts_for_prompt(contexts_all)
    coherent, coherence_reason, coherence_meta = assess_context_coherence(
        event_name, contexts_all
    )
    if not coherent:
        return {
            "success": False,
            "error": coherence_reason,
            "event_id": event_id,
            "event_name": event_name,
            "contexts_total": contexts_total,
            "contexts_included": 0,
            "context_count": 0,
            "coherence": coherence_meta,
        }

    if contexts_total > len(contexts) or len(contexts_all) > len(contexts):
        logger.info(
            "investigation_report event_id=%s capped contexts %s→%s",
            event_id,
            contexts_total or len(contexts_all),
            len(contexts),
        )

    chronicle_block = _build_chronicle_block(chronicles, contexts)
    context_block = _build_context_block(contexts)

    # Escape braces in user content so .format() does not interpret { or } as placeholders
    def _escape_braces(s: str) -> str:
        return (s or "").replace("{", "{{").replace("}", "}}")

    cross_raw = _build_cross_domain_link_block(event_id)
    if cross_raw.strip():
        cross_domain_block = CROSS_DOMAIN_SECTION.format(
            cross_domain_block=_escape_braces(cross_raw)
        )
    else:
        cross_domain_block = ""

    prompt = DOSSIER_PROMPT.format(
        event_name=_escape_braces(event_name),
        event_type=_escape_braces(event_type),
        geographic_scope=_escape_braces(geographic_scope),
        time_span=_escape_braces(time_span),
        chronicle_block=_escape_braces(chronicle_block),
        context_block=_escape_braces(context_block),
        CROSS_DOMAIN_BLOCK=cross_domain_block,
    )

    try:
        llm = LLMService()
        raw = await llm._call_ollama(ModelType.LLAMA_8B, prompt)
        report_md = raw.strip()
        await llm.close()
    except Exception as e:
        logger.warning(f"investigation_report LLM failed: {e}")
        return {"success": False, "error": str(e)}

    return {
        "success": True,
        "event_id": event_id,
        "event_name": event_name,
        "report_md": report_md,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "context_ids_included": sorted(contexts.keys()),
        "chronicle_count": len(chronicles),
        "context_count": len(contexts),
        "contexts_total": contexts_total or len(contexts_all),
        "contexts_included": len(contexts),
        "coherence": coherence_meta,
        "status": "ready",
    }


def _current_context_ids_for_event(event_id: int) -> list[int] | None:
    """Return sorted list of context IDs currently linked to this event via chronicles. None if event not found."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT developments FROM intelligence.event_chronicles
                WHERE event_id = %s
                """,
                (event_id,),
            )
            context_ids: set = set()
            for row in cur.fetchall():
                devs = row[0]
                if isinstance(devs, list):
                    for d in devs:
                        if isinstance(d, dict) and d.get("context_id") is not None:
                            context_ids.add(int(d["context_id"]))
                elif isinstance(devs, str):
                    try:
                        arr = json.loads(devs)
                        for d in arr if isinstance(arr, list) else []:
                            if isinstance(d, dict) and d.get("context_id") is not None:
                                context_ids.add(int(d["context_id"]))
                    except Exception:
                        pass
            conn.close()
            return sorted(context_ids) if context_ids else []
    except Exception as e:
        logger.warning(f"_current_context_ids_for_event: {e}")
        try:
            conn.close()
        except Exception:
            pass
        return None


async def refresh_stale_investigation_reports(limit: int = 3) -> int:
    """
    Find events whose report is out of date (current context set != report's context_ids_included),
    regenerate the report for each (up to limit), and save. Returns number of reports refreshed.
    Called by the orchestrator/automation so investigation reports improve over time as new context is added.
    """
    conn = get_db_connection()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT event_id, context_ids_included
                FROM intelligence.event_reports
                ORDER BY generated_at ASC
                """
            )
            rows = cur.fetchall()
        conn.close()
    except Exception as e:
        logger.warning(f"refresh_stale_investigation_reports: list failed: {e}")
        try:
            conn.close()
        except Exception:
            pass
        return 0

    stale: list[int] = []
    for event_id, included in rows:
        included_set = set(included) if included else set()
        current = _current_context_ids_for_event(event_id)
        if current is None:
            continue
        if set(current) != included_set:
            stale.append(event_id)
        if len(stale) >= limit:
            break

    refreshed = 0
    for event_id in stale:
        result = await generate_investigation_report(event_id)
        if not result.get("success"):
            logger.warning(f"refresh report event_id={event_id}: {result.get('error')}")
            continue
        if save_investigation_report_result(result):
            refreshed += 1
            logger.info(f"Refreshed investigation report for event_id={event_id}")
    return refreshed


async def create_initial_reports_for_new_events(limit: int = 5) -> int:
    """
    Find tracked_events that have no row in event_reports, generate a report for each (up to limit), and save.
    Returns number of new reports created. Called by investigation_report_refresh so new events get dossiers.
    """
    conn = get_db_connection()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT te.id FROM intelligence.tracked_events te
                WHERE NOT EXISTS (
                    SELECT 1 FROM intelligence.event_reports er WHERE er.event_id = te.id
                )
                ORDER BY te.id DESC
                LIMIT %s
                """,
                (limit,),
            )
            event_ids = [r[0] for r in cur.fetchall()]
        conn.close()
    except Exception as e:
        logger.warning(f"create_initial_reports_for_new_events: list failed: {e}")
        try:
            conn.close()
        except Exception:
            pass
        return 0

    created = 0
    for event_id in event_ids:
        result = await generate_investigation_report(event_id)
        if not result.get("success"):
            logger.warning(f"create_initial report event_id={event_id}: {result.get('error')}")
            continue
        if save_investigation_report_result(result):
            created += 1
            logger.info(f"Created initial investigation report for event_id={event_id}")
    return created
