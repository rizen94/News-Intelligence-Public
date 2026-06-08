"""
Three-window pipeline schedule (local timezone, default America/New_York).

Windows (half-open [start, end) on the hour):
  - **nightly_heavy**: daily backlog drain + GPU synthesis (default 00:00–07:00)
  - **weekday_daytime**: Mon–Fri full RSS + automation (default 07:00–16:00)
  - **quiet**: daily 16:00–00:00 and Sat/Sun 07:00–16:00 — pipeline paused, site stays up

Env:
  PIPELINE_SCHEDULE_TZ (or NIGHTLY_PIPELINE_TZ)
  PIPELINE_NIGHTLY_START_HOUR / PIPELINE_NIGHTLY_END_HOUR (fallback: NIGHTLY_PIPELINE_*)
  PIPELINE_DAYTIME_START_HOUR / PIPELINE_DAYTIME_END_HOUR (default 7 / 16)
  PIPELINE_QUIET_ALLOWED_PHASES (default health_check,pending_db_flush)
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

_DEFAULT_QUIET_ALLOWED = frozenset({"health_check", "pending_db_flush"})


def pipeline_schedule_tz() -> ZoneInfo:
    tz_name = (
        os.environ.get("PIPELINE_SCHEDULE_TZ")
        or os.environ.get("NIGHTLY_PIPELINE_TZ")
        or "America/New_York"
    ).strip() or "America/New_York"
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("America/New_York")


def _hour_env(primary: str, fallback: str, default: int) -> int:
    raw = os.environ.get(primary)
    if raw is None or not str(raw).strip():
        raw = os.environ.get(fallback)
    try:
        return int(raw if raw is not None and str(raw).strip() else default)
    except (TypeError, ValueError):
        return default


def nightly_start_hour() -> int:
    return _hour_env("PIPELINE_NIGHTLY_START_HOUR", "NIGHTLY_PIPELINE_START_HOUR", 0)


def nightly_end_hour() -> int:
    return _hour_env("PIPELINE_NIGHTLY_END_HOUR", "NIGHTLY_PIPELINE_END_HOUR", 7)


def daytime_start_hour() -> int:
    return _hour_env("PIPELINE_DAYTIME_START_HOUR", "", 7)


def daytime_end_hour() -> int:
    return _hour_env("PIPELINE_DAYTIME_END_HOUR", "", 16)


def _in_hour_window(now_local: datetime, start_h: int, end_h: int) -> bool:
    start = now_local.replace(hour=start_h, minute=0, second=0, microsecond=0)
    end = now_local.replace(hour=end_h, minute=0, second=0, microsecond=0)
    if start_h < end_h:
        return start <= now_local < end
    # Wrap midnight (not used by default schedule)
    return now_local >= start or now_local < end


def in_nightly_heavy_window(now_local: datetime | None = None) -> bool:
    """Daily heavy backlog + synthesis window (default 00:00–07:00 local)."""
    if now_local is None:
        now_local = datetime.now(pipeline_schedule_tz())
    return _in_hour_window(now_local, nightly_start_hour(), nightly_end_hour())


def in_weekday_daytime_window(now_local: datetime | None = None) -> bool:
    """Mon–Fri full ops window (default 07:00–16:00 local)."""
    if now_local is None:
        now_local = datetime.now(pipeline_schedule_tz())
    if now_local.weekday() >= 5:
        return False
    return _in_hour_window(now_local, daytime_start_hour(), daytime_end_hour())


def in_pipeline_quiet_window(now_local: datetime | None = None) -> bool:
    """
    Pipeline paused: daily 16:00–00:00 and weekend 07:00–16:00.
    Mutually exclusive with nightly_heavy and weekday_daytime when configured as 0–7 / 7–16.
    """
    if now_local is None:
        now_local = datetime.now(pipeline_schedule_tz())
    hour = now_local.hour
    if hour >= daytime_end_hour():
        return True
    if now_local.weekday() >= 5 and hour >= daytime_start_hour():
        return True
    return False


def active_pipeline_window(now_local: datetime | None = None) -> str:
    """One of nightly_heavy, weekday_daytime, quiet."""
    if now_local is None:
        now_local = datetime.now(pipeline_schedule_tz())
    if in_nightly_heavy_window(now_local):
        return "nightly_heavy"
    if in_weekday_daytime_window(now_local):
        return "weekday_daytime"
    return "quiet"


def _quiet_allowed_phases() -> frozenset[str]:
    raw = os.environ.get(
        "PIPELINE_QUIET_ALLOWED_PHASES",
        "health_check,pending_db_flush",
    ).strip()
    if not raw:
        return _DEFAULT_QUIET_ALLOWED
    return frozenset(x.strip() for x in raw.split(",") if x.strip())


def automation_phase_allowed(phase_name: str, *, now_local: datetime | None = None) -> bool:
    """Whether AutomationManager may schedule this phase under the operating schedule."""
    name = (phase_name or "").strip()
    if not name:
        return False
    if name in _quiet_allowed_phases():
        return True
    window = active_pipeline_window(now_local)
    if window == "quiet":
        return False
    return window in ("nightly_heavy", "weekday_daytime")


def rss_collection_allowed(*, now_local: datetime | None = None) -> bool:
    """Widow RSS + nightly kickoff: weekday daytime or nightly heavy, not quiet-only."""
    if now_local is None:
        now_local = datetime.now(pipeline_schedule_tz())
    return in_nightly_heavy_window(now_local) or in_weekday_daytime_window(now_local)


def db_adjacent_sync_allowed(*, now_local: datetime | None = None) -> bool:
    """context_sync / entity_profile_sync on Widow — same gates as pipeline automation."""
    if now_local is None:
        now_local = datetime.now(pipeline_schedule_tz())
    return not in_pipeline_quiet_window(now_local)


def pipeline_schedule_info(*, now_local: datetime | None = None) -> dict[str, Any]:
    """Snapshot for Monitor / validation scripts."""
    if now_local is None:
        now_local = datetime.now(pipeline_schedule_tz())
    zi = pipeline_schedule_tz()
    start_n = nightly_start_hour()
    end_n = nightly_end_hour()
    start_d = daytime_start_hour()
    end_d = daytime_end_hour()
    active = active_pipeline_window(now_local)

    next_transition: str | None = None
    next_window: str | None = None
    if active == "nightly_heavy":
        next_at = now_local.replace(hour=end_n, minute=0, second=0, microsecond=0)
        next_window = "weekday_daytime" if now_local.weekday() < 5 else "quiet"
        next_transition = next_at.isoformat()
    elif active == "weekday_daytime":
        next_at = now_local.replace(hour=end_d, minute=0, second=0, microsecond=0)
        next_window = "quiet"
        next_transition = next_at.isoformat()
    elif active == "quiet":
        if now_local.hour >= end_d:
            next_day = now_local + timedelta(days=1)
            next_at = next_day.replace(hour=start_n, minute=0, second=0, microsecond=0)
            next_window = "nightly_heavy"
        elif now_local.weekday() >= 5:
            next_at = now_local.replace(hour=end_d, minute=0, second=0, microsecond=0)
            next_window = "quiet"
        else:
            next_at = now_local.replace(hour=start_d, minute=0, second=0, microsecond=0)
            next_window = "weekday_daytime"
        next_transition = next_at.isoformat()

    return {
        "timezone": str(zi),
        "active_window": active,
        "in_nightly_heavy": in_nightly_heavy_window(now_local),
        "in_weekday_daytime": in_weekday_daytime_window(now_local),
        "in_quiet": in_pipeline_quiet_window(now_local),
        "nightly_window_local": f"{start_n:02d}:00–{end_n:02d}:00",
        "daytime_window_local": f"Mon–Fri {start_d:02d}:00–{end_d:02d}:00",
        "quiet_window_local": f"Daily {end_d:02d}:00–{start_n:02d}:00; Sat–Sun {start_d:02d}:00–{end_d:02d}:00",
        "rss_collection_allowed": rss_collection_allowed(now_local=now_local),
        "automation_allowed_except_essentials": active != "quiet",
        "quiet_allowed_phases": sorted(_quiet_allowed_phases()),
        "next_transition_local": next_transition,
        "next_window": next_window,
        "now_local": now_local.isoformat(),
    }
