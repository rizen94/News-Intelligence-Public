"""
ALFRED (Archival FRED) client — vintage-aware macro series pulls.

FRED returns latest revised values; ALFRED preserves observation vintages for
point-in-time macro queries. Falls back to FRED when ALFRED unavailable.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import requests

from config.settings import FRED_API_KEY, FRED_RATE_LIMIT_PER_MINUTE
from config.runtime import env_bool, env_float, env_int, env_pop, env_set, env_setdefault, env_str

logger = logging.getLogger(__name__)

ALFRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

_last_call_ts = 0.0


def _rate_limit() -> None:
    global _last_call_ts
    min_interval = 60.0 / max(1, int(FRED_RATE_LIMIT_PER_MINUTE or 120))
    elapsed = time.monotonic() - _last_call_ts
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    _last_call_ts = time.monotonic()


def fetch_series_vintage(
    series_id: str,
    *,
    observation_start: str | None = None,
    observation_end: str | None = None,
    realtime_start: str | None = None,
    realtime_end: str | None = None,
    api_key: str | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch observations with ALFRED vintage parameters (realtime_start/end).
    Returns list of dicts: observation_date, value, vintage_date (realtime_end).
    """
    key = api_key or FRED_API_KEY
    if not key:
        logger.warning("FRED_API_KEY not set — skipping ALFRED fetch for %s", series_id)
        return []

    params: dict[str, Any] = {
        "series_id": series_id,
        "api_key": key,
        "file_type": "json",
    }
    if observation_start:
        params["observation_start"] = observation_start
    if observation_end:
        params["observation_end"] = observation_end
    if realtime_start:
        params["realtime_start"] = realtime_start
    if realtime_end:
        params["realtime_end"] = realtime_end

    _rate_limit()
    try:
        r = requests.get(ALFRED_BASE, params=params, timeout=45)
        if r.status_code == 429:
            logger.warning("ALFRED rate limited for %s", series_id)
            return []
        r.raise_for_status()
        data = r.json()
        obs = data.get("observations") or []
        out: list[dict[str, Any]] = []
        for row in obs:
            if not isinstance(row, dict):
                continue
            val = row.get("value")
            if val in (None, ".", ""):
                continue
            try:
                numeric = float(val)
            except (TypeError, ValueError):
                continue
            vintage_raw = row.get("realtime_end") or row.get("realtime_start")
            vintage_dt = None
            if vintage_raw:
                try:
                    vintage_dt = datetime.strptime(str(vintage_raw)[:10], "%Y-%m-%d").replace(
                        tzinfo=timezone.utc
                    )
                except ValueError:
                    vintage_dt = datetime.now(timezone.utc)
            out.append(
                {
                    "series_id": series_id,
                    "observation_date": row.get("date"),
                    "value": numeric,
                    "vintage_date": vintage_dt or datetime.now(timezone.utc),
                    "source": "alfred" if realtime_start or realtime_end else "fred",
                }
            )
        return out
    except Exception as e:
        logger.warning("ALFRED fetch failed for %s: %s", series_id, e)
        return []


def default_longitudinal_series() -> list[str]:
    """Core macro series for MVP arcs (resource_geopolitics + tensions)."""
    raw = env_str(
        "LONGITUDINAL_MACRO_SERIES_IDS",
        "DCOILWTICO,DTWEXBGS,FEDFUNDS,UNRATE,CPIAUCSL,GEPUCURRENT,GPRHICU,GPRTOT",
    )
    return [s.strip() for s in raw.split(",") if s.strip()]
