"""
Shared rules for commodity price history freshness (GET history, gold amalgamator).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

# Latest observation start-of-day UTC older than this → trigger a bounded refresh
DEFAULT_STALE_MAX_AGE_HOURS = 24.0
# When refreshing stale history, only re-fetch this many days (bounded API cost)
STALE_REFRESH_LOOKBACK_DAYS = 14


def latest_observation_date(observations: list[dict[str, Any]]) -> date | None:
    """Max YYYY-MM-DD from observations; None if none parse."""
    best: date | None = None
    for o in observations or []:
        d = o.get("date")
        if not d or not isinstance(d, str):
            continue
        try:
            parsed = datetime.strptime(d[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
        if best is None or parsed > best:
            best = parsed
    return best


def observations_stale(
    observations: list[dict[str, Any]],
    *,
    max_age_hours: float = DEFAULT_STALE_MAX_AGE_HOURS,
    now: datetime | None = None,
) -> bool:
    """
    True when the newest observation is older than max_age_hours relative to UTC now
    (using start-of-day UTC for the observation date).
    Empty or unparseable observations → False.
    """
    if not observations:
        return False
    latest = latest_observation_date(observations)
    if latest is None:
        return False
    utc = now or datetime.now(timezone.utc)
    if utc.tzinfo is None:
        utc = utc.replace(tzinfo=timezone.utc)
    latest_start = datetime.combine(latest, datetime.min.time(), tzinfo=timezone.utc)
    return (utc - latest_start) > timedelta(hours=max_age_hours)


def bounded_refresh_start_end(
    window_start: str,
    window_end: str,
    *,
    lookback_days: int = STALE_REFRESH_LOOKBACK_DAYS,
    now: datetime | None = None,
) -> tuple[str, str]:
    """
    Return (start, end) YYYY-MM-DD for a stale refresh: last `lookback_days` through window end,
    clipped to not start before the client's requested window start.
    """
    utc = now or datetime.now(timezone.utc)
    if utc.tzinfo is None:
        utc = utc.replace(tzinfo=timezone.utc)
    end_d = datetime.strptime(window_end[:10], "%Y-%m-%d").date()
    start_d = datetime.strptime(window_start[:10], "%Y-%m-%d").date()
    tail_start = end_d - timedelta(days=max(1, lookback_days))
    bounded_start = max(start_d, tail_start)
    return bounded_start.strftime("%Y-%m-%d"), end_d.strftime("%Y-%m-%d")
