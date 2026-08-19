"""Time-of-day framing for the daily report (no DB)."""

from __future__ import annotations

from datetime import datetime

FRAMING = {
    "morning": "While you were sleeping · Day ahead",
    "midday": "Midday update · Quick scan",
    "evening": "This evening · What it means",
    "weekend": "Week in review · Deeper reads",
}


def time_of_day(now: datetime | None = None) -> str:
    dt = now or datetime.now()
    if dt.weekday() >= 5:
        return "weekend"
    if dt.hour < 12:
        return "morning"
    if dt.hour < 17:
        return "midday"
    return "evening"
