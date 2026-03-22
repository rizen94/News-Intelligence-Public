"""
FRED as primary source for commodity (metals, oil, gas) history and latest observation.
Series ID and unit from commodity registry (and env override for FRED_*_SERIES_ID).
"""

import logging
from datetime import datetime, timedelta, timezone

try:
    from config.logging_config import get_component_logger

    logger = get_component_logger("finance")
except Exception:
    logger = logging.getLogger(__name__)

from config.settings import FRED_API_KEY
from shared.data_result import DataResult

from domains.finance.commodity_registry import get_fred_series_id as registry_get_fred_series_id
from domains.finance.commodity_registry import get_unit as registry_get_unit
from domains.finance.data_sources.fred import get_client


def get_fred_series_id(commodity: str) -> str | None:
    """Return FRED series ID for commodity from registry (and env override)."""
    return registry_get_fred_series_id((commodity or "").lower())


def fetch_commodity_history_from_fred(
    commodity: str,
    start: str,
    end: str,
    store: bool = False,
) -> DataResult[list[dict]]:
    """
    Fetch commodity observations from FRED for the given date range.
    Returns list of {"date": str, "value": float, "unit": str, "source_id": str}.
    Series ID and unit from commodity registry.
    """
    series_id = get_fred_series_id(commodity)
    if not series_id:
        return DataResult.fail("No FRED series configured for this commodity", "config")
    if not FRED_API_KEY:
        return DataResult.fail("FRED_API_KEY not set", "auth")

    unit = registry_get_unit((commodity or "").lower())
    client = get_client()
    result = client.fetch_observations(series_id, start=start, end=end, store=store)
    if not result.success:
        return result
    raw = result.data or []
    out = []
    for o in raw:
        out.append(
            {
                "date": o.get("date", ""),
                "value": o["value"],
                "unit": unit,
                "source_id": f"fred_{series_id}",
            }
        )
    return DataResult.ok(out)


def get_stored_fred_commodity_history(
    commodity: str,
    start: str,
    end: str,
) -> list[dict]:
    """
    Read previously persisted FRED observations from market_data_store (source=fred, symbol=series_id).
    Used when live FRED is unavailable or returns empty but a prior fetch stored data.
    """
    series_id = get_fred_series_id(commodity)
    if not series_id:
        return []
    try:
        from domains.finance.data.market_data_store import get_series
    except Exception:
        return []
    r = get_series("fred", series_id, start_date=start, end_date=end)
    if not isinstance(r, DataResult) or not r.success or not r.data:
        return []
    unit = registry_get_unit((commodity or "").lower())
    out: list[dict] = []
    for row in r.data:
        meta = row.get("metadata") or {}
        out.append(
            {
                "date": row.get("date") or "",
                "value": row.get("value"),
                "unit": meta.get("unit") or unit,
                "source_id": meta.get("source_id") or f"fred_{series_id}",
            }
        )
    return out


def fetch_commodity_spot_from_fred(commodity: str) -> DataResult[dict]:
    """
    Fetch latest observation from FRED as spot (last ~7 days, take most recent).
    Returns {"price": float, "unit": str, "date": str, "source_id": str} or failure.
    """
    end_dt = datetime.now(timezone.utc).date()
    start_dt = end_dt - timedelta(days=7)
    start = start_dt.strftime("%Y-%m-%d")
    end = end_dt.strftime("%Y-%m-%d")
    result = fetch_commodity_history_from_fred(commodity, start=start, end=end, store=False)
    if not result.success or not result.data:
        return DataResult.fail(
            result.error or "No FRED observations",
            result.error_type or "no_data",
        )
    unit = registry_get_unit((commodity or "").lower())
    obs = sorted(result.data, key=lambda o: o.get("date", ""), reverse=True)
    latest = obs[0]
    return DataResult.ok(
        {
            "price": latest["value"],
            "unit": latest.get("unit", unit),
            "date": latest.get("date", ""),
            "source_id": latest.get("source_id", "fred"),
        }
    )
