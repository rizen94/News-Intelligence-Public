"""
FRED as primary source for commodity (gold, silver, platinum) history and latest observation.
Uses FRED series IDs from config; returns normalized observations for history/spot.
"""

import logging
from datetime import datetime, timedelta, timezone

try:
    from config.logging_config import get_component_logger
    logger = get_component_logger("finance")
except Exception:
    logger = logging.getLogger(__name__)

from config.settings import (
    FRED_API_KEY,
    FRED_GOLD_SERIES_ID,
    FRED_SILVER_SERIES_ID,
    FRED_PLATINUM_SERIES_ID,
)
from domains.finance.data_sources.fred import get_client
from shared.data_result import DataResult

FRED_SERIES_BY_METAL = {
    "gold": FRED_GOLD_SERIES_ID,
    "silver": FRED_SILVER_SERIES_ID,
    "platinum": FRED_PLATINUM_SERIES_ID,
}

DEFAULT_UNIT = "USD/toz"


def get_fred_series_id(metal: str) -> str | None:
    """Return configured FRED series ID for metal, or None if not configured."""
    series_id = FRED_SERIES_BY_METAL.get((metal or "").lower())
    return (series_id or "").strip() or None


def fetch_commodity_history_from_fred(
    metal: str,
    start: str,
    end: str,
    store: bool = False,
) -> DataResult[list[dict]]:
    """
    Fetch commodity observations from FRED for the given date range.
    Returns list of {"date": str, "value": float, "unit": str, "source_id": str}.
    """
    series_id = get_fred_series_id(metal)
    if not series_id:
        return DataResult.fail("No FRED series configured for this metal", "config")
    if not FRED_API_KEY:
        return DataResult.fail("FRED_API_KEY not set", "auth")

    client = get_client()
    result = client.fetch_observations(series_id, start=start, end=end, store=store)
    if not result.success:
        return result
    raw = result.data or []
    out = []
    for o in raw:
        out.append({
            "date": o.get("date", ""),
            "value": o["value"],
            "unit": DEFAULT_UNIT,
            "source_id": f"fred_{series_id}",
        })
    return DataResult.ok(out)


def fetch_commodity_spot_from_fred(metal: str) -> DataResult[dict]:
    """
    Fetch latest observation from FRED as spot (last ~7 days, take most recent).
    Returns {"price": float, "unit": str, "date": str, "source_id": str} or failure.
    """
    end_dt = datetime.now(timezone.utc).date()
    start_dt = end_dt - timedelta(days=7)
    start = start_dt.strftime("%Y-%m-%d")
    end = end_dt.strftime("%Y-%m-%d")
    result = fetch_commodity_history_from_fred(metal, start=start, end=end, store=False)
    if not result.success or not result.data:
        return DataResult.fail(
            result.error or "No FRED observations",
            result.error_type or "no_data",
        )
    obs = sorted(result.data, key=lambda o: o.get("date", ""), reverse=True)
    latest = obs[0]
    return DataResult.ok({
        "price": latest["value"],
        "unit": latest.get("unit", DEFAULT_UNIT),
        "date": latest.get("date", ""),
        "source_id": latest.get("source_id", "fred"),
    })
