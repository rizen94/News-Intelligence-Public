"""
Report assembly API — GET /api/{domain}/report.
Returns lead storylines with 5W1H editorial and key_actors, investigations, recent events, daily brief.
"""

import logging
from typing import Any

from fastapi import APIRouter, Path, Query
from shared.database.connection import get_db_connection
from shared.domain_registry import domain_key_to_schema, schema_to_domain_key, url_schema_pairs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Report"])

# `tracked_events.domain_keys` may use URL keys, legacy `schema_name`, or mixed forms — normalize via registry.


def _domain_keys_matching_path(path_domain: str) -> list[str]:
    """All tokens that may appear in intelligence.tracked_events.domain_keys for this URL domain."""
    keys: list[str] = [path_domain]
    try:
        schema = domain_key_to_schema(path_domain)
    except KeyError:
        if path_domain == "science_tech":
            keys.append("science-tech")
        return list(dict.fromkeys(keys))
    for dk in schema_to_domain_key(schema):
        keys.append(dk)
    if schema not in keys:
        keys.append(schema)
    return list(dict.fromkeys(keys))


def _path_segment_for_db_domain_key(db_key: str) -> str:
    """Route segment for links (registry URL key preferred)."""
    from shared.domain_registry import get_domain_entries

    for e in get_domain_entries():
        if e["domain_key"] == db_key:
            return db_key
        if str(e["schema_name"]) == db_key:
            return e["domain_key"]
    if db_key == "science_tech":
        return "science-tech"
    return db_key


def _get_schema_for_domain(domain: str) -> str | None:
    try:
        return domain_key_to_schema(domain)
    except KeyError:
        return None


def _time_of_day() -> str:
    from datetime import datetime

    h = datetime.now().hour
    d = datetime.now().weekday()
    if d >= 5:
        return "weekend"
    if h < 12:
        return "morning"
    if h < 17:
        return "midday"
    return "evening"


@router.get("/{domain}/report")
def get_report(
    domain: str = Path(..., description="Domain key (e.g. politics, finance, science-tech)"),
    lead_limit: int = Query(10, ge=1, le=30, description="Max lead storylines to return"),
) -> dict[str, Any]:
    """Assemble report payload: lead storylines (5W1H + key_actors), investigations, recent events, daily_brief."""
    schema = _get_schema_for_domain(domain)
    if not schema:
        return {"success": False, "data": None, "message": "Domain not found"}

    conn = get_db_connection()
    if not conn:
        return {"success": False, "data": None, "message": "Database unavailable"}

    try:
        domain_key = domain
        lead_storylines: list[dict[str, Any]] = []
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, title, description, updated_at, article_count, status, editorial_document
                FROM {schema}.storylines
                WHERE title IS NOT NULL AND TRIM(title) != ''
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (lead_limit,),
            )
            storyline_rows = cur.fetchall()
            if not storyline_rows:
                inv = _fetch_investigations(conn, domain_key)
                rev = _fetch_recent_events(conn, domain_key)
                primary_ids = {r["id"] for r in inv} | {r["id"] for r in rev}
                related = _fetch_related_cross_domain(
                    conn, domain_key, schema, primary_ids, set()
                )
                conn.close()
                return {
                    "success": True,
                    "data": {
                        "lead_storylines": [],
                        "investigations": inv,
                        "recent_events": rev,
                        "related_cross_domain": related,
                        "daily_brief": None,
                        "time_of_day": _time_of_day(),
                        "domain": domain,
                    },
                    "message": None,
                }

            storyline_ids = [r[0] for r in storyline_rows]
            article_ids_by_storyline: dict[int, list[int]] = {}
            cur.execute(
                f"""
                SELECT storyline_id, article_id FROM {schema}.storyline_articles
                WHERE storyline_id = ANY(%s)
                """,
                (storyline_ids,),
            )
            for sid, aid in cur.fetchall():
                article_ids_by_storyline.setdefault(sid, []).append(aid)

            for row in storyline_rows:
                sid, title, _description, updated_at, article_count, status, editorial_document = (
                    row[0],
                    row[1],
                    row[2],
                    row[3],
                    row[4],
                    row[5],
                    row[6],
                )
                article_ids = article_ids_by_storyline.get(sid) or []
                key_actors: list[dict[str, Any]] = []
                if article_ids:
                    cur.execute(
                        f"""
                        SELECT ec.id, ec.canonical_name, ec.entity_type, ec.description,
                               COUNT(ae.article_id) AS mention_count
                        FROM {schema}.article_entities ae
                        JOIN {schema}.entity_canonical ec ON ec.id = ae.canonical_entity_id
                        WHERE ae.article_id = ANY(%s)
                        GROUP BY ec.id, ec.canonical_name, ec.entity_type, ec.description
                        ORDER BY mention_count DESC
                        """,
                        (article_ids,),
                    )
                    entity_rows = cur.fetchall()
                    canonical_ids = [r[0] for r in entity_rows]
                    profile_map: dict[int, int] = {}
                    if canonical_ids:
                        prof_domains = _domain_keys_matching_path(domain_key)
                        cur.execute(
                            """
                            SELECT canonical_entity_id, id FROM intelligence.entity_profiles
                            WHERE domain_key = ANY(%s) AND canonical_entity_id = ANY(%s)
                            """,
                            (prof_domains, canonical_ids),
                        )
                        for r in cur.fetchall():
                            profile_map[r[0]] = r[1]
                    who_list = []
                    if editorial_document and isinstance(editorial_document, dict):
                        who_list = editorial_document.get("who") or []
                    for r in entity_rows:
                        name = r[1] or ""
                        role_in_story = ""
                        for w in who_list:
                            if isinstance(w, dict) and (w.get("name") or "").strip() == name:
                                role_in_story = w.get("role") or w.get("background") or ""
                                break
                        key_actors.append(
                            {
                                "name": name,
                                "type": r[2] or "subject",
                                "description": r[3] or "",
                                "role_in_story": role_in_story,
                                "profile_id": profile_map.get(r[0]),
                                "canonical_entity_id": r[0],
                            }
                        )
                ed = editorial_document
                if ed and isinstance(ed, dict):
                    pass
                else:
                    ed = None
                phase = (status or "Developing").capitalize()
                if phase not in ("Breaking", "Developing", "Analysis"):
                    phase = "Developing"
                lead_storylines.append(
                    {
                        "id": sid,
                        "title": title or "",
                        "editorial_document": ed,
                        "key_actors": key_actors,
                        "phase": phase,
                        "source_count": article_count or 0,
                        "updated_at": updated_at.isoformat()
                        if hasattr(updated_at, "isoformat")
                        else str(updated_at),
                    }
                )

        investigations = _fetch_investigations(conn, domain_key)
        recent_events = _fetch_recent_events(conn, domain_key)
        daily_brief = _fetch_daily_brief(conn, domain_key)
        primary_event_ids = {r["id"] for r in investigations} | {r["id"] for r in recent_events}
        lead_canonical_ids: set[int] = set()
        for ls in lead_storylines:
            for actor in ls.get("key_actors") or []:
                cid = actor.get("canonical_entity_id")
                if isinstance(cid, int):
                    lead_canonical_ids.add(cid)
                elif isinstance(cid, float) and cid == int(cid):
                    lead_canonical_ids.add(int(cid))
        related_cross_domain = _fetch_related_cross_domain(
            conn, domain_key, schema, primary_event_ids, lead_canonical_ids
        )

        conn.close()
        return {
            "success": True,
            "data": {
                "lead_storylines": lead_storylines,
                "investigations": investigations,
                "recent_events": recent_events,
                "related_cross_domain": related_cross_domain,
                "daily_brief": daily_brief,
                "time_of_day": _time_of_day(),
                "domain": domain,
            },
            "message": None,
        }
    except Exception as e:
        logger.warning("get_report failed: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "data": None, "message": str(e)}


def _db_domain_keys_for_correlations(path_domain: str) -> list[str]:
    """Tokens that may appear in cross_domain_correlations.domain_1 / domain_2 (legacy rows differ)."""
    return _domain_keys_matching_path(path_domain)


def _fetch_investigations(conn, path_domain: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    keys = _domain_keys_matching_path(path_domain)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, event_name, event_type, status, editorial_briefing,
                       COALESCE(domain_keys, '{}') AS domain_keys
                FROM intelligence.tracked_events
                WHERE COALESCE(domain_keys, '{}') && %s::text[]
                ORDER BY updated_at DESC NULLS LAST
                LIMIT 20
                """,
                (keys,),
            )
            for r in cur.fetchall():
                dkeys = list(r[5]) if r[5] else []
                out.append(
                    {
                        "id": r[0],
                        "name": r[1] or "",
                        "type": r[2] or "",
                        "status": r[3] or "active",
                        "briefing": r[4],
                        "domain_keys": dkeys,
                    }
                )
    except Exception as e:
        logger.debug("_fetch_investigations: %s", e)
    return out


def _event_sort_date(start_date: Any, updated_at: Any) -> Any:
    if start_date is not None:
        return start_date
    return updated_at


def _fetch_recent_events(conn, path_domain: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    keys = _domain_keys_matching_path(path_domain)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, event_name, start_date, updated_at, event_type,
                       COALESCE(domain_keys, '{}') AS domain_keys
                FROM intelligence.tracked_events
                WHERE COALESCE(domain_keys, '{}') && %s::text[]
                  AND (start_date IS NOT NULL OR updated_at IS NOT NULL)
                ORDER BY COALESCE(start_date, (updated_at AT TIME ZONE 'UTC')::date) DESC NULLS LAST,
                         updated_at DESC NULLS LAST
                LIMIT 15
                """,
                (keys,),
            )
            for r in cur.fetchall():
                sort_dt = _event_sort_date(r[2], r[3])
                out.append(
                    {
                        "id": r[0],
                        "title": r[1] or "",
                        "date": sort_dt.isoformat()
                        if hasattr(sort_dt, "isoformat")
                        else str(sort_dt)
                        if sort_dt
                        else "",
                        "type": r[4] or "",
                        "domain_keys": list(r[5]) if r[5] else [],
                    }
                )
    except Exception as e:
        logger.debug("_fetch_recent_events: %s", e)
    return out


def _fetch_related_cross_domain(
    conn,
    path_domain: str,
    current_schema: str,
    primary_event_ids: set[int],
    lead_canonical_ids: set[int],
    *,
    max_events: int = 10,
    max_storylines: int = 8,
) -> dict[str, Any]:
    """
    Events linked via cross_domain_correlations and storylines in other schemas
    sharing entities with lead storylines.
    """
    events_out: list[dict[str, Any]] = []
    storylines_out: list[dict[str, Any]] = []
    db_keys = _db_domain_keys_for_correlations(path_domain)
    keys_for_path = set(_domain_keys_matching_path(path_domain))

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT event_ids, domain_1, domain_2, correlation_strength, correlation_type
                FROM intelligence.cross_domain_correlations
                WHERE domain_1 = ANY(%s) OR domain_2 = ANY(%s)
                ORDER BY discovered_at DESC NULLS LAST, correlation_strength DESC NULLS LAST
                LIMIT 40
                """,
                (db_keys, db_keys),
            )
            corr_rows = cur.fetchall() or []

        extra_ids: list[tuple[int, str, float | None]] = []
        seen_corr_eids: set[int] = set()
        for row in corr_rows:
            eids_raw, strength, ctype = row[0], row[3], row[4]
            eids = list(eids_raw) if isinstance(eids_raw, list) else []
            link_reason = f"correlation:{ctype or 'cross_domain'}"
            for eid in eids:
                if not isinstance(eid, int):
                    continue
                if eid in primary_event_ids or eid in seen_corr_eids:
                    continue
                seen_corr_eids.add(eid)
                extra_ids.append((eid, link_reason, strength))
                if len(extra_ids) >= max_events * 3:
                    break

        seen_e: set[int] = set()
        if extra_ids:
            with conn.cursor() as cur:
                for eid, link_reason, strength in extra_ids:
                    if eid in seen_e or len(events_out) >= max_events:
                        break
                    seen_e.add(eid)
                    cur.execute(
                        """
                        SELECT id, event_name, start_date, updated_at, event_type,
                               COALESCE(domain_keys, '{}') AS domain_keys
                        FROM intelligence.tracked_events
                        WHERE id = %s
                        """,
                        (eid,),
                    )
                    er = cur.fetchone()
                    if not er:
                        continue
                    dkeys = list(er[5]) if er[5] else []
                    origin_db = next(
                        (k for k in dkeys if k not in keys_for_path),
                        dkeys[0] if dkeys else path_domain,
                    )
                    sort_dt = _event_sort_date(er[2], er[3])
                    events_out.append(
                        {
                            "id": er[0],
                            "title": er[1] or "",
                            "date": sort_dt.isoformat()
                            if hasattr(sort_dt, "isoformat")
                            else str(sort_dt)
                            if sort_dt
                            else "",
                            "type": er[4] or "",
                            "origin_domain": _path_segment_for_db_domain_key(str(origin_db)),
                            "link_reason": link_reason,
                            "correlation_strength": float(strength)
                            if strength is not None
                            else None,
                            "suggested_domain": _path_segment_for_db_domain_key(str(origin_db)),
                        }
                    )

        if lead_canonical_ids:
            canon_list = list(lead_canonical_ids)[:40]
            for dom_seg, schema_name in url_schema_pairs():
                if schema_name == current_schema or len(storylines_out) >= max_storylines:
                    continue
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            f"""
                            SELECT DISTINCT s.id, s.title, s.updated_at
                            FROM {schema_name}.storylines s
                            JOIN {schema_name}.storyline_articles sa ON sa.storyline_id = s.id
                            JOIN {schema_name}.article_entities ae ON ae.article_id = sa.article_id
                            WHERE ae.canonical_entity_id = ANY(%s)
                              AND s.title IS NOT NULL AND TRIM(s.title) != ''
                            ORDER BY s.updated_at DESC NULLS LAST
                            LIMIT 4
                            """,
                            (canon_list,),
                        )
                        for sr in cur.fetchall():
                            if len(storylines_out) >= max_storylines:
                                break
                            storylines_out.append(
                                {
                                    "id": sr[0],
                                    "title": sr[1] or "",
                                    "updated_at": sr[2].isoformat()
                                    if hasattr(sr[2], "isoformat")
                                    else str(sr[2]),
                                    "origin_domain": dom_seg,
                                    "link_reason": "shared_entity",
                                }
                            )
                except Exception as ex:
                    logger.debug("_fetch_related_cross_domain storylines %s: %s", schema_name, ex)
    except Exception as e:
        logger.debug("_fetch_related_cross_domain: %s", e)

    return {"events": events_out, "storylines": storylines_out}


def _fetch_daily_brief(conn, path_domain: str) -> str | None:
    """Return latest daily brief content if table exists; otherwise None."""
    try:
        keys = _domain_keys_matching_path(path_domain)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT content FROM intelligence.daily_briefs
                WHERE domain_key = ANY(%s)
                ORDER BY generated_at DESC
                LIMIT 1
                """,
                (keys,),
            )
            row = cur.fetchone()
            if row and row[0]:
                return row[0]
    except Exception:
        pass
    return None
