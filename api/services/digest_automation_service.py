"""
Digest automation — scheduled weekly (and optional daily) digest generation.
Generates weekly briefings via DailyBriefingService, persists to weekly_digests,
and exposes latest digests for GET /api/products/weekly_digest.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

_digest_service: Any = None


def _get_daily_briefing_service():
    """Lazy init DailyBriefingService with shared db_config."""
    from shared.database.connection import get_db_config
    from modules.ml.daily_briefing_service import DailyBriefingService
    return DailyBriefingService(get_db_config())


def _last_completed_week() -> tuple[date, date]:
    """Return (week_start, week_end) for the most recently completed Monday–Sunday."""
    today = date.today()
    # Monday = 0; so days_since_monday
    days_since_monday = today.weekday()
    this_monday = today - timedelta(days=days_since_monday)
    last_monday = this_monday - timedelta(days=7)
    last_sunday = last_monday + timedelta(days=6)
    return (last_monday, last_sunday)


def _weekly_digest_exists(week_start: date) -> bool:
    """Return True if weekly_digests already has a row for this week_start."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM weekly_digests WHERE week_start = %s LIMIT 1",
                (week_start,),
            )
            return cur.fetchone() is not None
    except Exception as e:
        logger.debug("weekly_digests check failed (table may not exist): %s", e)
        return False
    finally:
        conn.close()


def _run_weekly_briefing_sync(week_start: date) -> Optional[Dict[str, Any]]:
    """Generate weekly briefing for the given week (sync). Returns weekly_briefing dict or None."""
    try:
        svc = _get_daily_briefing_service()
        week_start_dt = datetime.combine(week_start, datetime.min.time())
        return svc.generate_weekly_briefing(week_start_dt)
    except Exception as e:
        logger.warning("Weekly briefing generation failed: %s", e)
        return None


def _insert_weekly_digest(
    week_start: date,
    week_end: date,
    weekly_briefing: Dict[str, Any],
) -> Optional[str]:
    """Map weekly_briefing to weekly_digests columns and INSERT. Enriches with editorial ledes."""
    if not weekly_briefing or "error" in weekly_briefing:
        return None
    summary = weekly_briefing.get("weekly_summary") or {}
    trend = weekly_briefing.get("trend_analysis") or {}
    total_articles = int(summary.get("total_articles", 0))
    top_categories = summary.get("top_categories") or {}
    top_trending = [{"topic": k, "count": v} for k, v in list(top_categories.items())[:20]]
    quality_metrics = trend if isinstance(trend, dict) else {}
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            # Pull editorial ledes from storylines updated this week
            editorial_suggestions = []
            for schema in ("politics", "finance", "science_tech"):
                try:
                    cur.execute(f"""
                        SELECT id, title, editorial_document->>'lede' as lede
                        FROM {schema}.storylines
                        WHERE updated_at >= %s
                          AND editorial_document IS NOT NULL
                          AND editorial_document->>'lede' IS NOT NULL
                          AND editorial_document->>'lede' != ''
                        ORDER BY updated_at DESC
                        LIMIT 5
                    """, (week_start,))
                    for row in cur.fetchall():
                        editorial_suggestions.append({
                            "domain": schema.replace("_", "-"),
                            "storyline_id": row[0],
                            "title": row[1],
                            "lede": row[2],
                        })
                except Exception:
                    pass

            cur.execute(
                """
                INSERT INTO weekly_digests
                (week_start, week_end, total_articles_analyzed, new_stories_suggested,
                 existing_stories_updated, top_trending_topics, story_suggestions, quality_metrics)
                VALUES (%s, %s, %s, 0, 0, %s, %s, %s)
                RETURNING digest_id
                """,
                (
                    week_start,
                    week_end,
                    total_articles,
                    json.dumps(top_trending),
                    json.dumps(editorial_suggestions),
                    json.dumps(quality_metrics),
                ),
            )
            row = cur.fetchone()
            digest_id = str(row[0]) if row else None
        conn.commit()
        return digest_id
    except Exception as e:
        logger.warning("Insert weekly_digest failed: %s", e)
        conn.rollback()
        return None
    finally:
        conn.close()


class DigestService:
    """
    Digest generation and retrieval. generate_digest_if_needed() produces
    a weekly digest for the last completed week when missing and stores it.
    """

    async def generate_digest_if_needed(self) -> None:
        """
        If the last completed week has no row in weekly_digests, generate
        the weekly briefing and insert. Runs sync briefing in executor.
        """
        week_start, week_end = _last_completed_week()
        if _weekly_digest_exists(week_start):
            logger.debug("Digest already exists for week %s", week_start)
            return
        logger.info("Generating weekly digest for %s to %s", week_start, week_end)
        loop = asyncio.get_event_loop()
        try:
            weekly_briefing = await loop.run_in_executor(
                None,
                lambda: _run_weekly_briefing_sync(week_start),
            )
            if weekly_briefing:
                digest_id = await loop.run_in_executor(
                    None,
                    lambda: _insert_weekly_digest(week_start, week_end, weekly_briefing),
                )
                if digest_id:
                    logger.info("Weekly digest created: %s (week %s)", digest_id, week_start)
        except Exception as e:
            logger.warning("generate_digest_if_needed failed: %s", e)

    def get_latest_weekly_digests(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return latest weekly_digests rows for GET /api/products/weekly_digest."""
        conn = get_db_connection()
        if not conn:
            return []
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT digest_id, week_start, week_end, total_articles_analyzed,
                           new_stories_suggested, existing_stories_updated,
                           top_trending_topics, story_suggestions, quality_metrics, created_at
                    FROM weekly_digests
                    ORDER BY week_start DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall()
            def _norm_json(val, default):
                if val is None:
                    return default
                if isinstance(val, (list, dict)):
                    return val
                return default

            return [
                {
                    "digest_id": str(r[0]),
                    "week_start": r[1].isoformat() if r[1] else None,
                    "week_end": r[2].isoformat() if r[2] else None,
                    "total_articles_analyzed": r[3] or 0,
                    "new_stories_suggested": r[4] or 0,
                    "existing_stories_updated": r[5] or 0,
                    "top_trending_topics": _norm_json(r[6], []),
                    "story_suggestions": _norm_json(r[7], []),
                    "quality_metrics": _norm_json(r[8], {}),
                    "created_at": r[9].isoformat() if r[9] else None,
                }
                for r in rows
            ]
        except Exception as e:
            logger.debug("get_latest_weekly_digests failed: %s", e)
            return []
        finally:
            conn.close()


def get_digest_service() -> DigestService:
    """Return singleton digest service for automation_manager and products API."""
    global _digest_service
    if _digest_service is None:
        _digest_service = DigestService()
    return _digest_service
