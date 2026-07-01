"""
Read-only reconciliation between tracked_events, chronological_events, and storylines.

Validates whether a future table merge is safe — does not mutate rows.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from shared.database.connection import get_db_connection_context
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema

logger = logging.getLogger(__name__)

_DATE_WINDOW_DAYS = 14


def _parse_storyline_ref(storyline_id_val: str | None) -> dict[str, Any] | None:
    if not storyline_id_val:
        return None
    raw = str(storyline_id_val).strip()
    if ":" in raw:
        schema, sid = raw.split(":", 1)
        domain_key = schema.replace("_", "-")
        try:
            return {"domain": domain_key, "storyline_id": int(sid), "schema": schema}
        except ValueError:
            return None
    return None


def _confidence_label(score: float) -> str:
    if score >= 0.65:
        return "high"
    if score >= 0.35:
        return "medium"
    return "low"


def _entity_ids_for_tracked_event(cur, event_id: int) -> set[int]:
    cur.execute(
        """
        SELECT COALESCE(key_participant_entity_ids, '[]'::jsonb)
        FROM intelligence.tracked_events
        WHERE id = %s
        """,
        (event_id,),
    )
    row = cur.fetchone()
    if not row:
        return set()
    raw = row[0]
    ids = json.loads(raw) if isinstance(raw, str) else (raw or [])
    return {int(x) for x in ids if isinstance(x, (int, float))}


def _chronological_for_storyline_id(
    cur,
    storyline_id: int | None,
    since: datetime | None,
    *,
    limit: int = 15,
) -> list[dict[str, Any]]:
    if not storyline_id:
        return []
    params: list[Any] = [storyline_id]
    date_clause = ""
    if since:
        date_clause = " AND ce.event_date >= %s"
        params.append(since.date())
    params.append(limit)
    cur.execute(
        f"""
        SELECT ce.id, ce.title, ce.event_date, ce.storyline_id
        FROM public.chronological_events ce
        WHERE ce.storyline_id = %s{date_clause}
        ORDER BY ce.event_date DESC NULLS LAST, ce.id DESC
        LIMIT %s
        """,
        tuple(params),
    )
    out: list[dict[str, Any]] = []
    for cid, title, event_date, sl_id in cur.fetchall():
        out.append(
            {
                "chronological_event_id": int(cid),
                "event_title": title,
                "event_date": event_date.isoformat() if event_date else None,
                "storyline_id": sl_id,
                "entity_overlap_score": 1.0,
                "linker_source": "story_continuation",
            }
        )
    return out


def _chronological_candidates_for_tracked(
    cur,
    te_storyline_id: str | None,
    since: datetime | None,
) -> list[dict[str, Any]]:
    """Fast v1: chronological atoms via shared storyline_id only."""
    ref = _parse_storyline_ref(te_storyline_id)
    if not ref:
        return []
    return _chronological_for_storyline_id(cur, ref.get("storyline_id"), since)


def list_event_reconciliation(
    *,
    limit: int = 50,
    offset: int = 0,
    domain_key: str | None = None,
    since_days: int = _DATE_WINDOW_DAYS,
) -> dict[str, Any]:
    """Paginated reconciliation rows keyed by tracked_event."""
    since = datetime.utcnow() - timedelta(days=max(1, since_days))
    rows: list[dict[str, Any]] = []
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                domain_clause = ""
                params: list[Any] = [limit, offset]
                if domain_key:
                    domain_clause = " AND %s = ANY(COALESCE(te.domain_keys, '{}'))"
                    params = [domain_key, limit, offset]
                cur.execute(
                    f"""
                    SELECT te.id, te.event_name, te.storyline_id,
                           COALESCE(te.domain_keys, '{{}}')
                    FROM intelligence.tracked_events te
                    WHERE te.updated_at >= %s{domain_clause}
                    ORDER BY te.updated_at DESC NULLS LAST, te.id DESC
                    LIMIT %s OFFSET %s
                    """,
                    (since, *([domain_key] if domain_key else []), limit, offset),
                )
                tracked_rows = cur.fetchall()
                for te_id, te_name, te_storyline_id, domain_keys in tracked_rows:
                    chrono = _chronological_candidates_for_tracked(
                        cur, te_storyline_id, since
                    )
                    storyline_refs: list[dict[str, Any]] = []
                    ref = _parse_storyline_ref(te_storyline_id)
                    if ref:
                        storyline_refs.append(ref)
                    best_overlap = max(
                        (c["entity_overlap_score"] for c in chrono), default=0.0
                    )
                    linker_sources: list[str] = []
                    if te_storyline_id:
                        linker_sources.append("event_tracking")
                    if chrono:
                        linker_sources.append("story_continuation")
                    if not chrono and not te_storyline_id:
                        linker_sources.append("unlinked")
                    rows.append(
                        {
                            "tracked_event_id": int(te_id),
                            "tracked_event_name": te_name,
                            "domain_keys": list(domain_keys or []),
                            "chronological_event_ids": [
                                c["chronological_event_id"] for c in chrono[:10]
                            ],
                            "chronological_events": chrono[:10],
                            "storyline_refs": storyline_refs[:5],
                            "entity_overlap_score": round(best_overlap, 3),
                            "confidence": _confidence_label(best_overlap),
                            "linker_sources": linker_sources,
                        }
                    )
    except Exception as e:
        logger.warning("list_event_reconciliation: %s", e)
        return {"items": [], "limit": limit, "offset": offset, "error": str(e)}
    return {"items": rows, "limit": limit, "offset": offset}


def get_reconciliation_for_tracked_event(tracked_event_id: int) -> dict[str, Any] | None:
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, event_name, storyline_id, COALESCE(domain_keys, '{}')
                    FROM intelligence.tracked_events
                    WHERE id = %s
                    """,
                    (tracked_event_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                te_id, te_name, te_storyline_id, domain_keys = row
                since = datetime.utcnow() - timedelta(days=365)
                chrono = _chronological_candidates_for_tracked(cur, te_storyline_id, since)
                ref = _parse_storyline_ref(te_storyline_id)
                storyline_refs = [ref] if ref else []
                best_overlap = max(
                    (c["entity_overlap_score"] for c in chrono), default=0.0
                )
                linker_sources: list[str] = []
                if te_storyline_id:
                    linker_sources.append("event_tracking")
                if chrono:
                    linker_sources.append("story_continuation")
                if not chrono and not te_storyline_id:
                    linker_sources.append("unlinked")
                return {
                    "found": True,
                    "tracked_event_id": int(te_id),
                    "tracked_event_name": te_name,
                    "domain_keys": list(domain_keys or []),
                    "chronological_event_ids": [c["chronological_event_id"] for c in chrono[:10]],
                    "chronological_events": chrono[:10],
                    "storyline_refs": storyline_refs[:5],
                    "entity_overlap_score": round(best_overlap, 3),
                    "confidence": _confidence_label(best_overlap),
                    "linker_sources": linker_sources,
                }
    except Exception as e:
        logger.warning("get_reconciliation_for_tracked_event: %s", e)
        return {"found": False, "tracked_event_id": tracked_event_id, "error": str(e)}


def get_reconciliation_for_storyline(domain_key: str, storyline_id: int) -> dict[str, Any]:
    """Tracked events and chronological atoms linked to a domain storyline."""
    schema = resolve_domain_schema(domain_key)
    storyline_ref = f"{schema}:{storyline_id}"
    tracked: list[dict[str, Any]] = []
    chronological: list[dict[str, Any]] = []
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, event_name, storyline_id
                    FROM intelligence.tracked_events
                    WHERE storyline_id = %s OR storyline_id LIKE %s
                    ORDER BY updated_at DESC NULLS LAST
                    LIMIT 20
                    """,
                    (storyline_ref, f"%:{storyline_id}"),
                )
                for tid, name, sl in cur.fetchall():
                    tracked.append(
                        {
                            "tracked_event_id": int(tid),
                            "tracked_event_name": name,
                            "storyline_id": sl,
                        }
                    )
                cur.execute(
                    """
                    SELECT id, title, event_date
                    FROM public.chronological_events
                    WHERE storyline_id = %s
                    ORDER BY event_date DESC NULLS LAST
                    LIMIT 30
                    """,
                    (storyline_id,),
                )
                for cid, title, ed in cur.fetchall():
                    chronological.append(
                        {
                            "chronological_event_id": int(cid),
                            "event_title": title,
                            "event_date": ed.isoformat() if ed else None,
                        }
                    )
    except Exception as e:
        logger.warning("get_reconciliation_for_storyline: %s", e)
        return {
            "domain": domain_key,
            "storyline_id": storyline_id,
            "tracked_events": [],
            "chronological_events": [],
            "error": str(e),
        }
    return {
        "domain": domain_key,
        "storyline_id": storyline_id,
        "tracked_events": tracked,
        "chronological_events": chronological,
    }
