"""
Event chronicle builder — T2.1.
For a tracked_event, gather developments from storylines (in event domain_keys),
compute momentum_score, write one event_chronicles row.
Reuses: intelligence.tracked_events, intelligence.event_chronicles, {domain}.storylines.
"""

import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)


def _run_scheduled_chronicle_updates(
    max_events: int,
    get_db_connection_fn: Any | None = None,
) -> int:
    """
    Used by OrchestratorCoordinator: fetch up to max_events tracked event IDs,
    run build_chronicle_for_event for each, return number successfully updated.
    """
    fn = get_db_connection_fn or get_db_connection
    conn = fn() if callable(fn) else None
    if not conn:
        return 0
    event_ids: list[int] = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM intelligence.tracked_events ORDER BY id LIMIT %s",
                (max_events,),
            )
            event_ids = [r[0] for r in cur.fetchall()]
    except Exception as e:
        logger.debug("_run_scheduled_chronicle_updates: fetch events failed: %s", e)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    updated = 0
    for eid in event_ids:
        result = build_chronicle_for_event(eid)
        if result.get("success"):
            updated += 1
    return updated


DOMAIN_TO_SCHEMA = {
    "politics": "politics",
    "finance": "finance",
    "science-tech": "science_tech",
}


def build_chronicle_for_event(
    event_id: int,
    update_date: date | None = None,
    developments_days: int = 7,
    max_storylines_per_domain: int = 15,
) -> dict[str, Any]:
    """
    Build one event_chronicles row for the given tracked_event.
    - Loads event (domain_keys, event_name); for each domain_key queries that schema's
      storylines updated in the last developments_days; builds developments list.
    - momentum_score: min(1.0, count_developments / 10) or 0.5 if none.
    - Writes to intelligence.event_chronicles.
    Returns { "success": True, "chronicle_id": int, "developments_count": int, "momentum_score": float }
    or { "success": False, "error": str }.
    """
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database unavailable"}

    update_date = update_date or date.today()
    since = (datetime.now(timezone.utc) - timedelta(days=developments_days)).date()

    try:
        with conn.cursor() as cur:
            row = None
            try:
                cur.execute(
                    """
                    SELECT id, event_type, event_name, start_date, end_date, geographic_scope,
                           key_participant_entity_ids, milestones, domain_keys
                    FROM intelligence.tracked_events
                    WHERE id = %s
                    """,
                    (event_id,),
                )
                row = cur.fetchone()
            except Exception:
                cur.execute(
                    """
                    SELECT id, event_type, event_name, start_date, end_date, geographic_scope,
                           key_participant_entity_ids, milestones
                    FROM intelligence.tracked_events
                    WHERE id = %s
                    """,
                    (event_id,),
                )
                row = cur.fetchone()
            if not row:
                return {"success": False, "error": f"Tracked event {event_id} not found"}

            # domain_keys: column may not exist (migration 156)
            domain_keys_raw = row[8] if len(row) > 8 else None
            if isinstance(domain_keys_raw, list):
                domain_keys = [str(d) for d in domain_keys_raw]
            elif domain_keys_raw:
                domain_keys = [str(domain_keys_raw)]
            else:
                domain_keys = ["politics", "finance", "science-tech"]

            developments: list[dict[str, Any]] = []
            for dk in domain_keys:
                schema = DOMAIN_TO_SCHEMA.get(dk)
                if not schema:
                    continue
                try:
                    cur.execute(
                        f"""
                        SELECT id, title, updated_at, analysis_summary
                        FROM "{schema}".storylines
                        WHERE updated_at >= %s
                        ORDER BY updated_at DESC
                        LIMIT %s
                        """,
                        (since, max_storylines_per_domain),
                    )
                    for srow in cur.fetchall():
                        sid, title, updated_at, summary = srow
                        developments.append(
                            {
                                "storyline_id": sid,
                                "domain_key": dk,
                                "title": (title or "")[:200],
                                "updated_at": updated_at.isoformat() if updated_at else None,
                                "summary_snippet": (summary or "")[:300] if summary else None,
                            }
                        )
                except Exception as e:
                    logger.debug("event_chronicle_builder: skip domain %s: %s", dk, e)

            momentum_score = min(1.0, len(developments) / 10.0) if developments else 0.5
            analysis = {"developments_count": len(developments), "domains_queried": domain_keys}
            predictions: list[Any] = []

            cur.execute(
                """
                INSERT INTO intelligence.event_chronicles
                (event_id, update_date, developments, analysis, predictions, momentum_score)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    event_id,
                    update_date,
                    json.dumps(developments),
                    json.dumps(analysis),
                    json.dumps(predictions),
                    round(momentum_score, 2),
                ),
            )
            chronicle_id = cur.fetchone()[0]
            conn.commit()
        conn.close()
        return {
            "success": True,
            "chronicle_id": chronicle_id,
            "developments_count": len(developments),
            "momentum_score": round(momentum_score, 2),
        }
    except Exception as e:
        logger.exception("build_chronicle_for_event: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)}
