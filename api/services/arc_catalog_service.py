"""
Arc catalog — load historical_arcs.yaml, sync arc_definitions, schedule reports.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from shared.database.connection import get_db_connection_context, get_ui_db_connection_context

logger = logging.getLogger(__name__)

_ARCS_PATH = Path(__file__).resolve().parent.parent / "config" / "historical_arcs.yaml"


def _load_arcs_yaml() -> dict[str, Any]:
    if not _ARCS_PATH.is_file():
        return {"arcs": []}
    with open(_ARCS_PATH) as f:
        return yaml.safe_load(f) or {"arcs": []}


def sync_arc_definitions_from_yaml() -> dict[str, Any]:
    """Upsert arc_definitions from historical_arcs.yaml."""
    data = _load_arcs_yaml()
    arcs = data.get("arcs") or []
    synced = 0
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for arc in arcs:
                if not isinstance(arc, dict):
                    continue
                arc_id = (arc.get("arc_id") or "").strip()
                if not arc_id:
                    continue
                cur.execute(
                    """
                    INSERT INTO intelligence.arc_definitions (
                        arc_id, display_name, description, start_date, end_date,
                        primary_entity_qids, primary_macro_series_ids, chapters, metadata, is_active
                    ) VALUES (%s, %s, %s, %s::date, %s::date, %s::text[], %s::text[], %s::jsonb, %s::jsonb, %s)
                    ON CONFLICT (arc_id) DO UPDATE SET
                        display_name = EXCLUDED.display_name,
                        description = EXCLUDED.description,
                        start_date = EXCLUDED.start_date,
                        end_date = EXCLUDED.end_date,
                        primary_entity_qids = EXCLUDED.primary_entity_qids,
                        primary_macro_series_ids = EXCLUDED.primary_macro_series_ids,
                        chapters = EXCLUDED.chapters,
                        metadata = EXCLUDED.metadata,
                        is_active = EXCLUDED.is_active,
                        updated_at = NOW()
                    """,
                    (
                        arc_id,
                        arc.get("display_name") or arc_id,
                        arc.get("description"),
                        arc.get("start_date"),
                        arc.get("end_date"),
                        arc.get("primary_entity_qids") or [],
                        arc.get("primary_macro_series_ids") or [],
                        json.dumps(arc.get("chapters") or []),
                        json.dumps(arc.get("metadata") or {}),
                        arc.get("is_active", True),
                    ),
                )
                synced += 1
        conn.commit()
    return {"success": True, "synced": synced}


def get_arc_definition(arc_id: str) -> dict[str, Any] | None:
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT arc_id, display_name, description, start_date, end_date,
                       primary_entity_qids, primary_macro_series_ids, chapters, metadata, is_active
                FROM intelligence.arc_definitions
                WHERE arc_id = %s AND is_active = true
                """,
                (arc_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            d = dict(zip(cols, row))
            for k in ("start_date", "end_date"):
                if d.get(k) and hasattr(d[k], "isoformat"):
                    d[k] = d[k].isoformat()
            return d


def list_active_arcs() -> list[dict[str, Any]]:
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT arc_id, display_name, description, start_date, end_date, is_active
                FROM intelligence.arc_definitions
                WHERE is_active = true
                ORDER BY display_name
                """
            )
            cols = [d[0] for d in cur.description]
            out = []
            for row in cur.fetchall():
                d = dict(zip(cols, row))
                for k in ("start_date", "end_date"):
                    if d.get(k) and hasattr(d[k], "isoformat"):
                        d[k] = d[k].isoformat()
                out.append(d)
            return out


def resolve_current_chapter(arc_id: str, as_of: date | None = None) -> dict[str, Any] | None:
    arc = get_arc_definition(arc_id)
    if not arc:
        return None
    ref = as_of or datetime.now(timezone.utc).date()
    chapters = arc.get("chapters") or []
    if isinstance(chapters, str):
        try:
            chapters = yaml.safe_load(chapters) or []
        except Exception:
            chapters = []
    current = None
    for ch in chapters:
        if not isinstance(ch, dict):
            continue
        start = ch.get("start_date")
        end = ch.get("end_date")
        if not start:
            continue
        try:
            sd = date.fromisoformat(str(start)[:10])
        except ValueError:
            continue
        ed = None
        if end:
            try:
                ed = date.fromisoformat(str(end)[:10])
            except ValueError:
                ed = None
        if sd <= ref and (ed is None or ref <= ed):
            current = ch
    return current
