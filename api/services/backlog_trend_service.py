"""Daily backlog snapshots for steady-state trend alerts."""

from __future__ import annotations

from config.runtime import env_str
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_STATE_KEY = "backlog_daily_snapshots"


def record_daily_snapshot(pending: dict[str, int]) -> None:
    """Append today's pending totals to automation_state (keep 14 days)."""
    if env_str("BULK_CATCHUP_ACTIVE", "").lower() in ("1", "true", "yes"):
        return
    try:
        from shared.database.connection import get_db_connection_context

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT value FROM public.automation_state WHERE key = %s",
                    (_STATE_KEY,),
                )
                row = cur.fetchone()
                hist: list[dict[str, Any]] = []
                if row and row[0]:
                    raw = row[0]
                    if isinstance(raw, list):
                        hist = list(raw)
                    elif isinstance(raw, str):
                        hist = json.loads(raw)
                    elif isinstance(raw, dict):
                        hist = raw.get("days") or []
                hist = [h for h in hist if h.get("date") != today]
                hist.append({"date": today, "pending": dict(pending)})
                hist = hist[-14:]
                cur.execute(
                    """
                    INSERT INTO public.automation_state (key, value, updated_at)
                    VALUES (%s, %s::jsonb, NOW())
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                    """,
                    (_STATE_KEY, json.dumps(hist)),
                )
            conn.commit()
    except Exception as e:
        logger.debug("record_daily_snapshot: %s", e)


def backlog_trend_alert(pending: dict[str, int]) -> list[str]:
    """
    Return alert strings when any major phase backlog grew over 7-day window.
    Skipped during BULK_CATCHUP_ACTIVE.
    """
    if env_str("BULK_CATCHUP_ACTIVE", "").lower() in ("1", "true", "yes"):
        return []
    alerts: list[str] = []
    watch = (
        "entity_extraction",
        "context_sync",
        "claim_extraction",
        "event_tracking",
        "embeddings_worker",
    )
    try:
        from shared.database.connection import get_ui_db_connection_context

        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT value FROM public.automation_state WHERE key = %s",
                    (_STATE_KEY,),
                )
                row = cur.fetchone()
        if not row or not row[0]:
            return alerts
        hist = row[0] if isinstance(row[0], list) else json.loads(row[0])
        if len(hist) < 3:
            return alerts
        oldest = hist[0].get("pending") or {}
        for ph in watch:
            old_v = int(oldest.get(ph) or 0)
            new_v = int(pending.get(ph) or 0)
            if new_v > old_v + max(50, old_v * 0.1):
                alerts.append(f"backlog_trend_rising:{ph}:{old_v}->{new_v}")
    except Exception as e:
        logger.debug("backlog_trend_alert: %s", e)
    return alerts
