"""
Arc historical context — point-in-time bundle for slow reports.

Extends storyline historical memory to arc scope: reference events, living facts,
external events, macro series, active storylines (entity QID overlap).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from shared.database.connection import get_db_connection_context, get_ui_db_connection_context
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema

from services.arc_catalog_service import get_arc_definition
from services.macro_series_service import get_macro_series_for_arc
from services.reference_events_loader import list_reference_events

logger = logging.getLogger(__name__)


def build_arc_historical_context(
    arc_id: str,
    as_of_date: datetime | None = None,
    *,
    max_reference_events: int = 80,
    max_facts: int = 120,
    max_external_events: int = 100,
) -> dict[str, Any]:
    """
    Merge reference + living layers scoped to as_of_date (UTC).
    Post-cutoff versioned_facts and reference events are excluded.
    """
    as_of = as_of_date or datetime.now(timezone.utc)
    arc = get_arc_definition(arc_id)
    if not arc:
        return {"success": False, "error": "arc_not_found", "arc_id": arc_id}

    entity_qids = list(arc.get("primary_entity_qids") or [])
    macro_ids = list(arc.get("primary_macro_series_ids") or [])

    reference_events = [
        e
        for e in list_reference_events(arc_id=arc_id, limit=max_reference_events)
        if _event_on_or_before(e.get("event_date"), as_of)
        and _ingestion_on_or_before(e.get("ingestion_date"), as_of)
    ]

    macro_observations = get_macro_series_for_arc(macro_ids, as_of_date=as_of)

    living_facts = _load_living_facts(entity_qids, as_of, limit=max_facts)
    external_events = _load_external_events(as_of, limit=max_external_events)
    storylines = _load_linked_storylines(entity_qids, as_of)
    chronological_events = _load_chronological_events(entity_qids, as_of)
    sanctions_actions = _load_sanctions_actions(entity_qids, as_of)

    from services.arc_catalog_service import resolve_current_chapter

    chapter = resolve_current_chapter(arc_id, as_of.date())

    return {
        "success": True,
        "arc_id": arc_id,
        "as_of_date": as_of.isoformat(),
        "arc": arc,
        "current_chapter": chapter,
        "reference_events": reference_events,
        "living_facts": living_facts,
        "macro_observations": macro_observations,
        "external_events": external_events,
        "chronological_events": chronological_events,
        "sanctions_actions": sanctions_actions,
        "linked_storylines": storylines,
        "entity_qids": entity_qids,
    }


def _parse_iso_dt(iso: str | datetime | None) -> datetime | None:
    if iso is None:
        return None
    if isinstance(iso, datetime):
        dt = iso
    else:
        try:
            dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _event_on_or_before(iso: str | datetime | None, as_of: datetime) -> bool:
    dt = _parse_iso_dt(iso)
    if dt is None:
        return False
    return dt <= as_of


def _ingestion_on_or_before(iso: str | datetime | None, as_of: datetime) -> bool:
    """Allow rows without ingestion_date; otherwise enforce point-in-time."""
    if iso is None:
        return True
    dt = _parse_iso_dt(iso)
    return dt is not None and dt <= as_of


def _load_living_facts(
    entity_qids: list[str],
    as_of: datetime,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    if not entity_qids:
        return []
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    with get_ui_db_connection_context() as conn:
        for dk in get_pipeline_active_domain_keys():
            schema = resolve_domain_schema(dk)
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT vf.id, vf.fact_text, vf.valid_from, vf.valid_to,
                               vf.event_date, vf.ingestion_date, vf.vintage_date,
                               ec.canonical_name
                        FROM intelligence.versioned_facts vf
                        JOIN intelligence.entity_profiles ep ON ep.id = vf.entity_profile_id
                        JOIN {schema}.entity_canonical ec ON ec.id = ep.canonical_entity_id
                        WHERE ep.domain_key = %s
                          AND ec.wikidata_qid = ANY(%s)
                          AND vf.valid_from <= %s
                          AND (vf.valid_to IS NULL OR vf.valid_to > %s)
                          AND (vf.ingestion_date IS NULL OR vf.ingestion_date <= %s)
                          AND vf.superseded_by_id IS NULL
                        ORDER BY vf.valid_from DESC
                        LIMIT %s
                        """,
                        (dk, entity_qids, as_of, as_of, as_of, limit),
                    )
                    cols = [d[0] for d in cur.description]
                    for row in cur.fetchall():
                        d = dict(zip(cols, row))
                        fid = d.get("id")
                        if fid in seen:
                            continue
                        seen.add(fid)
                        for k in (
                            "valid_from",
                            "valid_to",
                            "event_date",
                            "ingestion_date",
                            "vintage_date",
                        ):
                            if d.get(k) and hasattr(d[k], "isoformat"):
                                d[k] = d[k].isoformat()
                        d["domain_key"] = dk
                        out.append(d)
            except Exception as e:
                logger.debug("arc living_facts %s: %s", schema, e)
    out.sort(key=lambda x: x.get("valid_from") or "", reverse=True)
    return out[:limit]


def _load_external_events(as_of: datetime, *, limit: int) -> list[dict[str, Any]]:
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, source, external_id, event_date, title, summary,
                       country_code, event_type, fatalities, entity_qids
                FROM intelligence.external_events
                WHERE event_date <= %s
                ORDER BY event_date DESC
                LIMIT %s
                """,
                (as_of, limit),
            )
            cols = [d[0] for d in cur.description]
            rows = []
            for row in cur.fetchall():
                d = dict(zip(cols, row))
                if d.get("event_date"):
                    d["event_date"] = d["event_date"].isoformat()
                rows.append(d)
            return rows


def _load_linked_storylines(
    entity_qids: list[str],
    as_of: datetime,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Storylines whose entities overlap arc QIDs (via canonical wikidata_qid)."""
    if not entity_qids:
        return []
    out: list[dict[str, Any]] = []
    with get_ui_db_connection_context() as conn:
        for dk in get_pipeline_active_domain_keys():
            schema = resolve_domain_schema(dk)
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT DISTINCT s.id, s.title, s.status, s.updated_at
                        FROM {schema}.storylines s
                        JOIN {schema}.story_entity_index sei ON sei.storyline_id = s.id
                        JOIN {schema}.entity_canonical ec ON lower(ec.canonical_name) = lower(sei.entity_name)
                        WHERE ec.wikidata_qid = ANY(%s)
                          AND s.updated_at <= %s
                        ORDER BY s.updated_at DESC
                        LIMIT %s
                        """,
                        (entity_qids, as_of, limit),
                    )
                    for sid, title, status, updated_at in cur.fetchall():
                        out.append(
                            {
                                "domain_key": dk,
                                "storyline_id": sid,
                                "title": title,
                                "status": status,
                                "updated_at": updated_at.isoformat() if updated_at else None,
                            }
                        )
            except Exception as e:
                logger.debug("arc storylines %s: %s", schema, e)
    return out[:limit]


def _load_chronological_events(
    entity_qids: list[str],
    as_of: datetime,
    *,
    limit: int = 60,
) -> list[dict[str, Any]]:
    if not entity_qids:
        return []
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    with get_ui_db_connection_context() as conn:
        for dk in get_pipeline_active_domain_keys():
            schema = resolve_domain_schema(dk)
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT ce.id, ce.title, ce.description,
                               ce.actual_event_date, ce.event_date, ce.storyline_id
                        FROM public.chronological_events ce
                        WHERE ce.storyline_id IN (
                            SELECT DISTINCT s.id::text
                            FROM {schema}.storylines s
                            JOIN {schema}.story_entity_index sei ON sei.storyline_id = s.id
                            JOIN {schema}.entity_canonical ec
                              ON lower(ec.canonical_name) = lower(sei.entity_name)
                            WHERE ec.wikidata_qid = ANY(%s)
                        )
                          AND COALESCE(ce.actual_event_date, ce.event_date, ce.created_at) <= %s
                        ORDER BY COALESCE(ce.actual_event_date, ce.event_date) DESC NULLS LAST
                        LIMIT %s
                        """,
                        (entity_qids, as_of, limit),
                    )
                    cols = [d[0] for d in cur.description]
                    for row in cur.fetchall():
                        d = dict(zip(cols, row))
                        cid = d.get("id")
                        if cid in seen:
                            continue
                        seen.add(cid)
                        for k in ("actual_event_date", "event_date"):
                            if d.get(k) and hasattr(d[k], "isoformat"):
                                d[k] = d[k].isoformat()
                        d["domain_key"] = dk
                        out.append(d)
            except Exception as e:
                logger.debug("arc chronological_events %s: %s", schema, e)
    out.sort(
        key=lambda x: x.get("actual_event_date") or x.get("event_date") or "",
        reverse=True,
    )
    return out[:limit]


def _load_sanctions_actions(
    entity_qids: list[str],
    as_of: datetime,
    *,
    limit: int = 40,
) -> list[dict[str, Any]]:
    if not entity_qids:
        return []
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, source, external_id, action_date, action_type,
                       entity_qids, entity_names, program, summary, ingestion_date
                FROM intelligence.sanctions_actions
                WHERE action_date <= %s
                  AND entity_qids && %s::text[]
                ORDER BY action_date DESC
                LIMIT %s
                """,
                (as_of, entity_qids, limit),
            )
            cols = [d[0] for d in cur.description]
            rows = []
            for row in cur.fetchall():
                d = dict(zip(cols, row))
                for k in ("action_date", "ingestion_date"):
                    if d.get(k) and hasattr(d[k], "isoformat"):
                        d[k] = d[k].isoformat()
                rows.append(d)
            return rows
