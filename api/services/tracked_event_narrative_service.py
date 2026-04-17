"""
Tracked event narratives — domain-agnostic spine + per-domain lenses.

Pipeline:
1. ``global_narrative``: one LLM pass from event metadata + chronicles (no domain bias).
2. ``narrative_lenses``: each lens pass consumes **only** ``global_narrative`` (+ short metadata), not raw chronicles.

``domain_keys`` on ``intelligence.tracked_events`` is refreshed from linked contexts
(``event_chronicles.developments``) so cross-domain ingestion widens coverage over time.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from shared.database.connection import get_db_connection
from shared.domain_registry import get_active_domain_keys

logger = logging.getLogger(__name__)


def _normalize_tracked_domain_key_for_lens(key: str) -> str:
    k = str(key).lower().strip().replace("_", "-")
    if k in ("science-tech", "sciencetech", "science tech"):
        return "artificial-intelligence"
    return k


# Optional hints so lenses differ meaningfully when multiple domains apply.
LENS_FOCUS: dict[str, str] = {
    "politics": "Institutions, alliances, elections, sanctions, legislative/executive actions, diplomacy.",
    "finance": "Markets, rates, commodities, currencies, flows, credit, corporate exposure.",
    "artificial-intelligence": "AI systems, models, safety, compute, product launches, policy and market structure.",
    "medicine": "Trials, regulators, mechanisms, public health, access and evidence quality.",
    "environment-climate": "Climate science, energy transition, ecosystems, sustainability and policy.",
}


async def _llm_text(prompt: str, max_prompt_chars: int = 6000) -> str | None:
    try:
        from shared.services.llm_service import TaskType, llm_service

        result = await llm_service.generate_summary(
            prompt[:max_prompt_chars], task_type=TaskType.QUICK_SUMMARY
        )
        if result.get("success"):
            return (result.get("summary") or "").strip() or None
    except Exception as e:
        logger.debug("tracked_event_narrative LLM: %s", e)
    return None


def _gather_chronicle_bundle(conn, event_id: int) -> tuple[str, dict[str, Any]]:
    """Return (flattened chronicle text, last analysis dict if any)."""
    parts: list[str] = []
    analysis: dict[str, Any] = {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT developments, analysis, predictions, update_date
            FROM intelligence.event_chronicles
            WHERE event_id = %s
            ORDER BY update_date DESC
            LIMIT 8
            """,
            (event_id,),
        )
        rows = cur.fetchall() or []
    for c in rows:
        dev, ana, pred, cdate = c[0], c[1], c[2], c[3]
        block = []
        if cdate:
            block.append(f"Date: {cdate}")
        if dev:
            raw = dev if isinstance(dev, str) else json.dumps(dev)
            block.append(f"Developments: {raw[:2500]}")
        if ana:
            a = ana if isinstance(ana, dict) else {}
            if isinstance(ana, dict) and ana:
                analysis = ana
            block.append(f"Analysis: {(json.dumps(ana) if not isinstance(ana, str) else ana)[:1200]}")
        if pred:
            block.append(f"Predictions: {str(pred)[:500]}")
        if block:
            parts.append("\n".join(block))
    return "\n\n---\n\n".join(parts), analysis


def refresh_domain_keys_for_tracked_event(conn, event_id: int) -> list[str]:
    """
    Union ``domain_keys`` with ``domain_key`` values from all contexts referenced in
    chronicle ``developments``. Commits are the caller's responsibility.
    """
    context_ids: list[int] = []
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COALESCE(domain_keys, '{}') FROM intelligence.tracked_events WHERE id = %s",
            (event_id,),
        )
        row = cur.fetchone()
        existing: set[str] = set(row[0] or []) if row else set()

        cur.execute(
            "SELECT developments FROM intelligence.event_chronicles WHERE event_id = %s",
            (event_id,),
        )
        for (dev,) in cur.fetchall() or []:
            if not dev:
                continue
            data = dev
            if isinstance(dev, str):
                try:
                    data = json.loads(dev)
                except Exception:
                    continue
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("context_id") is not None:
                        try:
                            context_ids.append(int(item["context_id"]))
                        except (TypeError, ValueError):
                            pass

        if not context_ids:
            return sorted(existing)

        cur.execute(
            """
            SELECT DISTINCT domain_key FROM intelligence.contexts
            WHERE id = ANY(%s) AND domain_key IS NOT NULL AND TRIM(domain_key) != ''
            """,
            (context_ids,),
        )
        for (dk,) in cur.fetchall() or []:
            if dk:
                existing.add(str(dk).strip())

        new_list = sorted(existing)
        cur.execute(
            """
            UPDATE intelligence.tracked_events
            SET domain_keys = %s, updated_at = NOW()
            WHERE id = %s
            """,
            (new_list, event_id),
        )
    return new_list


async def generate_narrative_stack_for_event(event_id: int) -> dict[str, Any]:
    """
    Write ``global_narrative`` then ``narrative_lenses`` for one event.
    Lens keys = intersection of event ``domain_keys`` with active domains; if empty,
    all active domains get a lens (cross-domain default).
    """
    out: dict[str, Any] = {"event_id": event_id, "success": False}
    conn = get_db_connection()
    if not conn:
        out["error"] = "no_db_connection"
        return out

    try:
        refresh_domain_keys_for_tracked_event(conn, event_id)
        conn.commit()

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT event_name, event_type, start_date, end_date, geographic_scope,
                       COALESCE(domain_keys, '{}'), global_narrative, narrative_lenses,
                       updated_at, global_narrative_updated_at
                FROM intelligence.tracked_events
                WHERE id = %s
                """,
                (event_id,),
            )
            row = cur.fetchone()
        if not row:
            out["error"] = "not_found"
            conn.close()
            return out

        (
            event_name,
            event_type,
            start_date,
            end_date,
            geo,
            domain_keys,
            _gn_old,
            lenses_old,
            updated_at,
            gn_updated_at,
        ) = row

        active = list(get_active_domain_keys())
        allowed = set(active)
        dk_raw = [_normalize_tracked_domain_key_for_lens(k) for k in (domain_keys or [])]
        dk_set = set(dk_raw) & allowed
        if not dk_set:
            dk_set = set(active)

        chronicle_text, _ = _gather_chronicle_bundle(conn, event_id)
        if not chronicle_text.strip():
            out["error"] = "no_chronicles"
            conn.close()
            return out

        # Regenerate global narrative if event row changed after last global write
        need_global = not (gn_updated_at and updated_at and gn_updated_at >= updated_at)

        global_text: str | None = None
        if need_global:
            prompt = (
                f"You are writing a single DOMAIN-NEUTRAL intelligence narrative for this event.\n"
                f"Event: {event_name}\n"
                f"Type: {event_type}\n"
                f"Time span: {start_date or '?'} to {end_date or 'ongoing'}\n"
                f"Geography: {geo or 'N/A'}\n\n"
                f"Source material (chronicles — do not favor any one domain):\n{chronicle_text[:8000]}\n\n"
                "Write 2–4 paragraphs: what happened, who is involved, why it matters globally. "
                "Do not write separate 'politics' vs 'finance' sections; stay integrated. "
                "Plain text only, no markdown."
            )
            global_text = await _llm_text(prompt, 12000)
            if not global_text:
                out["error"] = "global_narrative_failed"
                conn.close()
                return out
        else:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT global_narrative FROM intelligence.tracked_events WHERE id = %s",
                    (event_id,),
                )
                r2 = cur.fetchone()
            global_text = (r2[0] or "").strip() if r2 else ""
            if not global_text:
                prompt = (
                    f"DOMAIN-NEUTRAL narrative for: {event_name} ({event_type}).\n"
                    f"Chronicles:\n{chronicle_text[:8000]}\n\n"
                    "2–4 paragraphs, integrated, plain text."
                )
                global_text = await _llm_text(prompt, 12000)
            if not global_text:
                out["error"] = "global_narrative_missing"
                conn.close()
                return out

        lenses: dict[str, str] = {}
        if isinstance(lenses_old, dict):
            lenses.update({k: str(v) for k, v in lenses_old.items() if isinstance(v, str)})

        for lens_key in sorted(dk_set):
            focus = LENS_FOCUS.get(
                lens_key,
                f"Developments most relevant to the {lens_key} desk.",
            )
            lens_prompt = (
                f"You are the {lens_key} desk editor. Write 1–2 short paragraphs.\n"
                f"Focus: {focus}\n\n"
                "RULES: Use ONLY the GLOBAL NARRATIVE below. Do not add new facts, names, or dates "
                "that are not clearly implied by it. If something is uncertain, say so briefly.\n\n"
                f"GLOBAL NARRATIVE:\n{global_text}\n\n"
                f"Event label: {event_name}\n"
                "Output plain text only."
            )
            lt = await _llm_text(lens_prompt, 8000)
            if lt:
                lenses[lens_key] = lt

        ver_sql = (
            "global_narrative_version = global_narrative_version + 1,"
            if need_global
            else "global_narrative_version = global_narrative_version,"
        )
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE intelligence.tracked_events
                SET global_narrative = %s,
                    narrative_lenses = %s,
                    {ver_sql}
                    global_narrative_updated_at = CASE WHEN %s THEN NOW() ELSE global_narrative_updated_at END,
                    narrative_lenses_updated_at = NOW(),
                    editorial_briefing = LEFT(%s, 1200),
                    briefing_status = COALESCE(briefing_status, 'draft')
                WHERE id = %s
                """,
                (
                    global_text,
                    json.dumps(lenses),
                    need_global,
                    global_text,
                    event_id,
                ),
            )
        conn.commit()
        conn.close()
        out["success"] = True
        out["lens_keys"] = list(lenses.keys())
        return out
    except Exception as e:
        logger.warning("generate_narrative_stack_for_event %s: %s", event_id, e)
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        out["error"] = str(e)[:200]
        return out


async def run_tracked_event_narrative_stack(limit: int = 5) -> dict[str, Any]:
    """
    Batch: events that have chronicles and need an update (stale narrative or empty global).
    """
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "no_db_connection", "processed": 0}

    ids: list[int] = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.id
                FROM intelligence.tracked_events e
                WHERE EXISTS (SELECT 1 FROM intelligence.event_chronicles ec WHERE ec.event_id = e.id)
                  AND (
                    e.global_narrative IS NULL
                    OR e.global_narrative = ''
                    OR e.updated_at > COALESCE(e.global_narrative_updated_at, 'epoch'::timestamptz)
                  )
                ORDER BY e.updated_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            ids = [r[0] for r in cur.fetchall() or []]
        conn.close()
    except Exception as e:
        logger.warning("run_tracked_event_narrative_stack list: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)[:200], "processed": 0}

    processed = 0
    errors: list[str] = []
    for eid in ids:
        r = await generate_narrative_stack_for_event(eid)
        if r.get("success"):
            processed += 1
        elif r.get("error"):
            errors.append(f"{eid}:{r['error']}")

    return {
        "success": True,
        "processed": processed,
        "candidates": len(ids),
        "errors": errors[:10],
    }
