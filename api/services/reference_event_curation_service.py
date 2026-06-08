"""
Reference event curation — operator create and append-only corrections (Phase 6).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from shared.database.connection import get_db_connection_context, get_ui_db_connection_context

from services.reference_events_loader import _parse_event_date

logger = logging.getLogger(__name__)


def create_reference_event(payload: dict[str, Any], *, curator: str = "operator") -> dict[str, Any]:
    title = (payload.get("title") or "").strip()
    summary = (payload.get("summary") or "").strip()
    if not title or not summary:
        return {"success": False, "error": "title and summary required"}
    precision = (payload.get("date_precision") or "day").strip().lower()
    try:
        event_dt = _parse_event_date(str(payload.get("event_date") or ""), precision)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    end_dt = None
    if payload.get("end_date"):
        try:
            end_dt = _parse_event_date(str(payload["end_date"]), precision)
        except ValueError:
            end_dt = None

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.reference_events (
                    event_date, end_date, date_precision, title, summary, category,
                    entity_qids, sources, confidence, curator, arc_ids, metadata,
                    ingestion_date, vintage_date
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s::text[], %s::jsonb, %s, %s, %s::text[], %s::jsonb,
                    NOW(), %s
                )
                RETURNING id
                """,
                (
                    event_dt,
                    end_dt,
                    precision,
                    title,
                    summary[:2000],
                    payload.get("category"),
                    payload.get("entity_qids") or [],
                    json.dumps(payload.get("sources") or []),
                    payload.get("confidence") or "curated",
                    curator,
                    payload.get("arc_ids") or [],
                    json.dumps(payload.get("metadata") or {}),
                    event_dt,
                ),
            )
            new_id = cur.fetchone()[0]
        conn.commit()
    return {"success": True, "id": new_id}


def supersede_reference_event(
    reference_event_id: int,
    payload: dict[str, Any],
    *,
    curator: str = "operator",
    correction_type: str = "supersede",
) -> dict[str, Any]:
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, event_date, end_date, date_precision, title, summary, category,
                       entity_qids, sources, confidence, curator, arc_ids, metadata
                FROM intelligence.reference_events
                WHERE id = %s AND superseded_by_id IS NULL
                """,
                (reference_event_id,),
            )
            row = cur.fetchone()
            if not row:
                return {"success": False, "error": "reference_event_not_found"}
            cols = [d[0] for d in cur.description]
            prior = dict(zip(cols, row))
            for k in ("event_date", "end_date"):
                if prior.get(k) and hasattr(prior[k], "isoformat"):
                    prior[k] = prior[k].isoformat()

    merged = {**prior, **{k: v for k, v in payload.items() if v is not None}}
    created = create_reference_event(
        {
            "event_date": merged.get("event_date"),
            "end_date": merged.get("end_date"),
            "date_precision": merged.get("date_precision") or "day",
            "title": merged.get("title"),
            "summary": merged.get("summary"),
            "category": merged.get("category"),
            "entity_qids": merged.get("entity_qids"),
            "sources": merged.get("sources"),
            "confidence": merged.get("confidence") or "verified",
            "arc_ids": merged.get("arc_ids"),
            "metadata": {**(merged.get("metadata") or {}), "supersedes_id": reference_event_id},
        },
        curator=curator,
    )
    if not created.get("success"):
        return created

    new_id = created["id"]
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.reference_events
                SET superseded_by_id = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (new_id, reference_event_id),
            )
            cur.execute(
                """
                INSERT INTO intelligence.reference_event_corrections (
                    reference_event_id, correction_type, prior_snapshot,
                    new_reference_event_id, curator, notes
                ) VALUES (%s, %s, %s::jsonb, %s, %s, %s)
                """,
                (
                    reference_event_id,
                    correction_type,
                    json.dumps(prior),
                    new_id,
                    curator,
                    payload.get("notes"),
                ),
            )
        conn.commit()
    return {"success": True, "superseded_id": reference_event_id, "new_id": new_id}


def flag_reference_event(
    reference_event_id: int,
    *,
    flag_type: str = "missed_coverage",
    notes: str | None = None,
    curator: str = "operator",
) -> dict[str, Any]:
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.reference_event_flags (
                    reference_event_id, flag_type, notes, curator
                ) VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (reference_event_id, flag_type, notes, curator),
            )
            fid = cur.fetchone()[0]
        conn.commit()
    return {"success": True, "flag_id": fid}


def list_reference_event_flags(*, limit: int = 100) -> list[dict[str, Any]]:
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT f.id, f.reference_event_id, f.flag_type, f.notes, f.curator, f.created_at,
                       re.title, re.event_date
                FROM intelligence.reference_event_flags f
                LEFT JOIN intelligence.reference_events re ON re.id = f.reference_event_id
                ORDER BY f.created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            cols = [d[0] for d in cur.description]
            out = []
            for row in cur.fetchall():
                d = dict(zip(cols, row))
                if d.get("created_at"):
                    d["created_at"] = d["created_at"].isoformat()
                if d.get("event_date"):
                    d["event_date"] = d["event_date"].isoformat()
                out.append(d)
            return out
