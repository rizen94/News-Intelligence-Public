"""
Report assembly API — GET /api/{domain}/report.
Returns lead storylines with 5W1H editorial and key_actors, investigations, recent events, daily brief.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Path, Query

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Report"])


def _get_schema_for_domain(domain: str) -> Optional[str]:
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT schema_name FROM domains WHERE domain_key = %s", (domain,))
            row = cur.fetchone()
            return row[0] if row else None
    except Exception as e:
        logger.debug("schema for domain %s: %s", domain, e)
        return None
    finally:
        conn.close()


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
) -> Dict[str, Any]:
    """Assemble report payload: lead storylines (5W1H + key_actors), investigations, recent events, daily_brief."""
    schema = _get_schema_for_domain(domain)
    if not schema:
        return {"success": False, "data": None, "message": "Domain not found"}

    conn = get_db_connection()
    if not conn:
        return {"success": False, "data": None, "message": "Database unavailable"}

    try:
        domain_key = domain
        lead_storylines: List[Dict[str, Any]] = []
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
                conn.close()
                return {
                    "success": True,
                    "data": {
                        "lead_storylines": [],
                        "investigations": _fetch_investigations(conn, domain_key),
                        "recent_events": _fetch_recent_events(conn, domain_key),
                        "daily_brief": None,
                        "time_of_day": _time_of_day(),
                        "domain": domain,
                    },
                    "message": None,
                }

            storyline_ids = [r[0] for r in storyline_rows]
            article_ids_by_storyline: Dict[int, List[int]] = {}
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
                sid, title, description, updated_at, article_count, status, editorial_document = (
                    row[0], row[1], row[2], row[3], row[4], row[5], row[6]
                )
                article_ids = article_ids_by_storyline.get(sid) or []
                key_actors: List[Dict[str, Any]] = []
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
                    profile_map: Dict[int, int] = {}
                    if canonical_ids:
                        cur.execute(
                            """
                            SELECT canonical_entity_id, id FROM intelligence.entity_profiles
                            WHERE domain_key = %s AND canonical_entity_id = ANY(%s)
                            """,
                            (domain_key, canonical_ids),
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
                                role_in_story = (w.get("role") or w.get("background") or "")
                                break
                        key_actors.append({
                            "name": name,
                            "type": r[2] or "subject",
                            "description": r[3] or "",
                            "role_in_story": role_in_story,
                            "profile_id": profile_map.get(r[0]),
                            "canonical_entity_id": r[0],
                        })
                ed = editorial_document
                if ed and isinstance(ed, dict):
                    pass
                else:
                    ed = None
                phase = (status or "Developing").capitalize()
                if phase not in ("Breaking", "Developing", "Analysis"):
                    phase = "Developing"
                lead_storylines.append({
                    "id": sid,
                    "title": title or "",
                    "editorial_document": ed,
                    "key_actors": key_actors,
                    "phase": phase,
                    "source_count": article_count or 0,
                    "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else str(updated_at),
                })

        investigations = _fetch_investigations(conn, domain_key)
        recent_events = _fetch_recent_events(conn, domain_key)
        daily_brief = _fetch_daily_brief(conn, domain_key)

        conn.close()
        return {
            "success": True,
            "data": {
                "lead_storylines": lead_storylines,
                "investigations": investigations,
                "recent_events": recent_events,
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


def _fetch_investigations(conn, domain_key: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, event_name, event_type, status, editorial_briefing
                FROM intelligence.tracked_events
                WHERE domain_key = %s
                ORDER BY updated_at DESC NULLS LAST
                LIMIT 20
                """,
                (domain_key,),
            )
            for r in cur.fetchall():
                out.append({
                    "id": r[0],
                    "name": r[1] or "",
                    "type": r[2] or "",
                    "status": r[3] or "active",
                    "briefing": r[4],
                })
    except Exception as e:
        logger.debug("_fetch_investigations: %s", e)
    return out


def _fetch_recent_events(conn, domain_key: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, event_name, occurred_at, event_type
                FROM intelligence.tracked_events
                WHERE domain_key = %s AND occurred_at IS NOT NULL
                ORDER BY occurred_at DESC
                LIMIT 15
                """,
                (domain_key,),
            )
            for r in cur.fetchall():
                out.append({
                    "id": r[0],
                    "title": r[1] or "",
                    "date": r[2].isoformat() if hasattr(r[2], "isoformat") else str(r[2]) if r[2] else "",
                    "type": r[3] or "",
                })
    except Exception as e:
        logger.debug("_fetch_recent_events: %s", e)
    return out


def _fetch_daily_brief(conn, domain_key: str) -> Optional[str]:
    """Return latest daily brief content if table exists; otherwise None."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT content FROM intelligence.daily_briefs
                WHERE domain_key = %s
                ORDER BY generated_at DESC
                LIMIT 1
                """,
                (domain_key,),
            )
            row = cur.fetchone()
            if row and row[0]:
                return row[0]
    except Exception:
        pass
    return None
