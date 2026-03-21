"""
Investigation report service — journalism-style dossier from a tracked event.

Uses event + chronicles + full context text to generate:
- Executive summary
- Timeline of developments
- Key entities and roles
- Sources
- What we know / what's uncertain

Supports iterative improvement: regenerate when new contexts or chronicles are added.
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from shared.database.connection import get_db_connection
from shared.services.llm_service import LLMService, ModelType

logger = logging.getLogger(__name__)

DOSSIER_PROMPT = """You are a senior investigative journalist writing a dossier on a developing story.

INVESTIGATION: {event_name}
Type: {event_type}
Geographic scope: {geographic_scope}
Time span: {time_span}

CHRONICLE SUMMARIES (analyst summaries for each update):
{chronicle_block}

SUPPORTING CONTEXTS (evidence from sources; each has a title and excerpt):
{context_block}

Write a journalism-style investigation report in markdown with these sections:

## Executive Summary
2-4 sentences: what this story is, current status, and why it matters.

## Timeline of Developments
Chronological list of key developments with dates. Use the chronicle summaries and context excerpts. Note when multiple sources corroborate.

## Key Entities & Roles
Who or what is central to this story (people, organisations, places). One line each.

## Sources
List the sources/outlets that appear in the contexts (if evident from titles or metadata).

## What We Know
Bullet points of established facts supported by the evidence.

## What's Uncertain
Open questions, conflicting reports, or gaps in the evidence.

Use a neutral, factual tone. Prefer short sentences. Do not invent facts beyond what the evidence suggests."""


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

            placeholders = ",".join(["%s"] * len(context_ids))
            cur.execute(
                f"""
                SELECT id, title, content, metadata, created_at
                FROM intelligence.contexts
                WHERE id IN ({placeholders})
                ORDER BY created_at ASC
                """,
                tuple(context_ids),
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


def _build_context_block(contexts: dict[int, dict]) -> str:
    lines = []
    for cid, ctx in sorted(contexts.items(), key=lambda x: x[1].get("created_at") or ""):
        title = ctx.get("title") or f"Context #{cid}"
        content = ctx.get("content") or "(No content)"
        created = ctx.get("created_at") or ""
        lines.append(f"[Context #{cid}] {title}\nDate: {created}\n{content}\n")
    return "\n---\n".join(lines) if lines else "No context text."


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
    contexts = data.get("contexts") or {}

    chronicle_block = _build_chronicle_block(chronicles, contexts)
    context_block = _build_context_block(contexts)

    # Escape braces in user content so .format() does not interpret { or } as placeholders
    def _escape_braces(s: str) -> str:
        return (s or "").replace("{", "{{").replace("}", "}}")

    prompt = DOSSIER_PROMPT.format(
        event_name=_escape_braces(event_name),
        event_type=_escape_braces(event_type),
        geographic_scope=_escape_braces(geographic_scope),
        time_span=_escape_braces(time_span),
        chronicle_block=_escape_braces(chronicle_block),
        context_block=_escape_braces(context_block),
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
        "context_ids_included": data.get("context_ids") or [],
        "chronicle_count": len(chronicles),
        "context_count": len(contexts),
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
        conn = get_db_connection()
        if not conn:
            continue
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
            refreshed += 1
            logger.info(f"Refreshed investigation report for event_id={event_id}")
        except Exception as e:
            logger.warning(f"refresh_stale_investigation_reports: save event_id={event_id}: {e}")
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass
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
        conn = get_db_connection()
        if not conn:
            continue
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
            created += 1
            logger.info(f"Created initial investigation report for event_id={event_id}")
        except Exception as e:
            logger.warning(f"create_initial_reports_for_new_events: save event_id={event_id}: {e}")
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass
    return created
