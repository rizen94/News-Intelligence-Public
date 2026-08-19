"""Daily report assembly — events, episode movement, published stories."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from shared.database.connection import get_db_connection
from shared.domain_registry import domain_key_to_schema

from shared.daily_framing import FRAMING, time_of_day

logger = logging.getLogger(__name__)

_DATE_MIN_OFFSET = 400
_DATE_MAX_OFFSET = 2


def _parse_day(raw: str | None) -> date:
    if not raw:
        return date.today()
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return date.today()


def assemble_daily(
    domain_key: str,
    *,
    day: str | None = None,
    since: str | None = None,
    limit: int = 40,
) -> dict[str, Any]:
    try:
        schema = domain_key_to_schema(domain_key)
    except KeyError:
        return {"ok": False, "error": "domain_not_found"}

    report_day = _parse_day(day)
    tod = time_of_day()
    conn = get_db_connection()
    if not conn:
        return {"ok": False, "error": "database_unavailable"}

    since_ts = None
    if since:
        try:
            since_ts = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError:
            since_ts = None

    lo = date.today() - timedelta(days=_DATE_MIN_OFFSET)
    hi = date.today() + timedelta(days=_DATE_MAX_OFFSET)
    cap = max(1, min(int(limit), 80))

    moved: list[dict[str, Any]] = []
    new_today: list[dict[str, Any]] = []
    published: list[dict[str, Any]] = []
    quiet: list[dict[str, Any]] = []
    event_count = 0
    rejected_future = 0
    briefing_enqueued = 0

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM public.chronological_events ce
                WHERE ce.actual_event_date IS NOT NULL
                  AND (ce.actual_event_date < %s OR ce.actual_event_date > %s)
                """,
                (lo, hi),
            )
            rejected_future = int((cur.fetchone() or [0])[0] or 0)

            cur.execute(
                """
                SELECT COUNT(*) FROM public.chronological_events ce
                WHERE ce.actual_event_date = %s
                  AND EXISTS (
                    SELECT 1 FROM intelligence.event_episode_links eel
                    WHERE eel.event_id = ce.id
                      AND eel.domain_key = %s
                      AND eel.inference_stage <> 'quarantined'
                  )
                """,
                (report_day, domain_key),
            )
            event_count = int((cur.fetchone() or [0])[0] or 0)

            moved_filter = "eel.created_at::date = %s OR ce.actual_event_date = %s"
            moved_params: list[Any] = [domain_key, lo, hi, report_day, report_day, cap]
            if since_ts:
                moved_filter = "eel.created_at >= %s OR ce.actual_event_date = %s"
                moved_params = [domain_key, lo, hi, since_ts, report_day, cap]

            cur.execute(
                f"""
                SELECT s.id, s.title, s.episode_state,
                       COUNT(DISTINCT eel.event_id)::int AS new_links,
                       MAX(ce.actual_event_date) AS last_event_date,
                       (ARRAY_AGG(ce.title ORDER BY ce.actual_event_date DESC NULLS LAST, ce.id DESC))[1]
                         AS latest_event
                FROM {schema}.storylines s
                JOIN intelligence.event_episode_links eel
                  ON eel.domain_key = %s
                 AND eel.episode_id = s.id
                 AND eel.inference_stage <> 'quarantined'
                JOIN public.chronological_events ce ON ce.id = eel.event_id
                WHERE COALESCE(ce.actual_event_date, CURRENT_DATE) BETWEEN %s AND %s
                  AND ({moved_filter})
                  AND COALESCE(s.story_kind, '') <> 'container_index'
                  AND s.merged_into_id IS NULL
                GROUP BY s.id, s.title, s.episode_state
                ORDER BY new_links DESC, last_event_date DESC NULLS LAST
                LIMIT %s
                """,
                moved_params,
            )
            for row in cur.fetchall() or []:
                moved.append(
                    {
                        "episode_id": int(row[0]),
                        "title": row[1] or f"Episode #{row[0]}",
                        "episode_state": row[2],
                        "new_event_count": int(row[3] or 0),
                        "last_event_date": row[4].isoformat() if row[4] else None,
                        "latest_event": row[5],
                    }
                )

            cur.execute(
                f"""
                SELECT s.id, s.title, s.episode_state
                FROM {schema}.storylines s
                WHERE s.created_at::date = %s
                  AND COALESCE(s.story_kind, '') <> 'container_index'
                  AND s.merged_into_id IS NULL
                ORDER BY s.id DESC
                LIMIT %s
                """,
                (report_day, cap),
            )
            for row in cur.fetchall() or []:
                new_today.append(
                    {
                        "episode_id": int(row[0]),
                        "title": row[1] or f"Episode #{row[0]}",
                        "episode_state": row[2],
                    }
                )

            cur.execute(
                """
                SELECT id, title, lede, published_at, package_id
                FROM intelligence.news_stories
                WHERE status = 'published'
                  AND %s = ANY(domain_keys)
                  AND COALESCE(published_at, created_at)::date = %s
                ORDER BY published_at DESC NULLS LAST
                LIMIT %s
                """,
                (domain_key, report_day, cap),
            )
            for row in cur.fetchall() or []:
                published.append(
                    {
                        "story_id": int(row[0]),
                        "title": row[1] or f"Story {row[0]}",
                        "lede": row[2],
                        "published_at": row[3].isoformat() if row[3] else None,
                        "package_id": int(row[4]) if row[4] else None,
                    }
                )

            # Attach published story to moved episodes when the package shares the episode id
            if moved:
                ep_ids = [m["episode_id"] for m in moved]
                cur.execute(
                    f"""
                    SELECT ns.id, ns.title, p.metadata->>'storyline_id' AS sid
                    FROM intelligence.news_stories ns
                    JOIN intelligence.editorial_packages p ON p.id = ns.package_id
                    WHERE ns.status = 'published'
                      AND %s = ANY(ns.domain_keys)
                      AND COALESCE(p.metadata->>'storyline_id', '') ~ '^[0-9]+$'
                      AND (p.metadata->>'storyline_id')::bigint = ANY(%s)
                    """,
                    (domain_key, ep_ids),
                )
                by_ep: dict[int, dict[str, Any]] = {}
                for row in cur.fetchall() or []:
                    try:
                        by_ep[int(row[2])] = {"story_id": int(row[0]), "story_title": row[1]}
                    except (TypeError, ValueError):
                        continue
                for item in moved:
                    if item["episode_id"] in by_ep:
                        item.update(by_ep[item["episode_id"]])

            cur.execute(
                f"""
                SELECT s.id, s.title, s.episode_state, s.updated_at
                FROM {schema}.storylines s
                WHERE COALESCE(s.episode_state, '') IN ('cooling', 'dormant')
                  AND COALESCE(s.story_kind, '') <> 'container_index'
                  AND s.merged_into_id IS NULL
                ORDER BY s.updated_at DESC NULLS LAST
                LIMIT %s
                """,
                (min(20, cap),),
            )
            for row in cur.fetchall() or []:
                quiet.append(
                    {
                        "episode_id": int(row[0]),
                        "title": row[1] or f"Episode #{row[0]}",
                        "episode_state": row[2],
                        "updated_at": row[3].isoformat() if row[3] else None,
                    }
                )
    except Exception as e:
        logger.warning("assemble_daily query failed domain=%s: %s", domain_key, e)
        conn.close()
        return {"ok": False, "error": str(e)}
    finally:
        try:
            conn.close()
        except Exception:
            pass

    try:
        from services.expectation_tracking_service import list_expectations

        expectations = list_expectations(domain_key=domain_key, status="open", limit=15)
        open_ep = {int(q["episode_id"]) for q in quiet if q.get("episode_id")}
        for exp in expectations:
            sid = exp.get("storyline_id")
            if sid and int(sid) not in open_ep:
                quiet.append(
                    {
                        "episode_id": int(sid),
                        "title": exp.get("expected_outcome") or exp.get("claim_text") or "Open expectation",
                        "episode_state": "watch",
                        "due_date": str(exp.get("due_date") or ""),
                    }
                )
    except Exception as e:
        logger.debug("daily quiet expectations: %s", e)

    try:
        from services.content_refinement_queue_service import (
            JOB_TIMELINE_BRIEFING,
            enqueue_content_refinement,
        )

        for item in moved[:10]:
            res = enqueue_content_refinement(
                domain_key,
                int(item["episode_id"]),
                JOB_TIMELINE_BRIEFING,
                priority="low",
                metadata={"source": "daily_report"},
            )
            if res.get("success") and not res.get("already_queued"):
                briefing_enqueued += 1
    except Exception as e:
        logger.debug("daily briefing enqueue: %s", e)

    return {
        "ok": True,
        "domain": domain_key,
        "date": report_day.isoformat(),
        "time_of_day": tod,
        "framing": FRAMING[tod],
        "counts": {
            "events": event_count,
            "moved": len(moved),
            "new": len(new_today),
            "published": len(published),
            "quiet_watch": len(quiet),
            "rejected_out_of_range_dates": rejected_future,
            "briefings_enqueued": briefing_enqueued,
        },
        "moved_today": moved,
        "new_today": new_today,
        "published": published,
        "quiet_watch": quiet,
    }
