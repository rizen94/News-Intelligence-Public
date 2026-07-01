"""
Credit spread dashboard — FRED OAS series + recession overlay + ETF yield spreads.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from config.settings import FRED_API_KEY
from domains.finance.data_sources.fred import get_client

logger = logging.getLogger(__name__)

# FRED series (validated on FRED as of 2026-06)
FRED_HY_OAS_SERIES = "BAMLH0A0HYM2"
FRED_IG_OAS_SERIES = "BAMLC0A0CM"
FRED_RECESSION_SERIES = "USREC"

SpreadKind = Literal["hy", "ig"]
SpreadStatus = Literal["Normal", "Elevated", "Warning", "Danger", "Crisis"]

HY_THRESHOLDS_BPS: list[tuple[float, SpreadStatus]] = [
    (300, "Normal"),
    (450, "Elevated"),
    (600, "Warning"),
    (800, "Danger"),
]

IG_THRESHOLDS_BPS: list[tuple[float, SpreadStatus]] = [
    (100, "Normal"),
    (150, "Elevated"),
    (200, "Warning"),
]

FRED_ICE_WINDOW_NOTE = (
    "ICE BofA index series on FRED are limited to a rolling ~3-year window "
    "(since April 2026). Longer history requires ICE Data Indices directly."
)


def percent_to_bps(value: float) -> float:
    """FRED OAS values are percent; dashboard uses basis points."""
    return round(value * 100.0, 2)


def compute_spread_status(spread_bps: float, kind: SpreadKind) -> SpreadStatus:
    """Map spread level to interpretive status."""
    thresholds = HY_THRESHOLDS_BPS if kind == "hy" else IG_THRESHOLDS_BPS
    for limit, status in thresholds:
        if spread_bps < limit:
            return status
    return "Crisis"


def fetch_fred_spread_series(
    series_id: str,
    start: str,
    end: str,
    *,
    store: bool = True,
) -> list[dict[str, Any]]:
    """Fetch one FRED series and return [{date, value_bps}]."""
    if not FRED_API_KEY:
        return []
    client = get_client()
    result = client.fetch_observations(series_id, start=start, end=end, store=store)
    if not result.success or not result.data:
        logger.warning("FRED fetch failed for %s: %s", series_id, result.error)
        return []
    out: list[dict[str, Any]] = []
    for row in result.data:
        date = row.get("date")
        value = row.get("value")
        if not date or value is None:
            continue
        out.append({"date": date, "value_bps": percent_to_bps(float(value))})
    return out


def fetch_recession_periods(start: str, end: str) -> list[dict[str, str]]:
    """Fetch USREC and convert value=1 runs into {start, end} intervals."""
    if not FRED_API_KEY:
        return []
    client = get_client()
    result = client.fetch_observations(
        FRED_RECESSION_SERIES, start=start, end=end, store=False
    )
    if not result.success or not result.data:
        logger.warning("USREC fetch failed: %s", result.error)
        return []

    periods: list[dict[str, str]] = []
    in_recession = False
    period_start: str | None = None

    for row in result.data:
        date = row.get("date")
        value = row.get("value")
        if not date:
            continue
        try:
            active = float(value) >= 1.0
        except (TypeError, ValueError):
            active = False
        if active and not in_recession:
            in_recession = True
            period_start = date
        elif not active and in_recession and period_start:
            periods.append({"start": period_start, "end": date})
            in_recession = False
            period_start = None

    if in_recession and period_start:
        periods.append({"start": period_start, "end": end})

    return periods


def _latest_bps(observations: list[dict[str, Any]]) -> float | None:
    if not observations:
        return None
    return observations[-1].get("value_bps")


def _data_window_note(requested_days: int, hy: list, ig: list) -> str | None:
    if requested_days > 365 * 3 and (hy or ig):
        return FRED_ICE_WINDOW_NOTE
    if not hy and not ig and requested_days > 0:
        return "No FRED observations returned. Set FRED_API_KEY and verify series access."
    return None


def build_fred_credit_spread_payload(days: int) -> dict[str, Any]:
    """Build HY/IG OAS history with recession shading metadata."""
    days = max(1, min(days, 365 * 10))
    end_dt = datetime.now(timezone.utc).date()
    start_dt = end_dt - timedelta(days=days)
    start = start_dt.strftime("%Y-%m-%d")
    end = end_dt.strftime("%Y-%m-%d")

    hy_spread = fetch_fred_spread_series(FRED_HY_OAS_SERIES, start, end)
    ig_spread = fetch_fred_spread_series(FRED_IG_OAS_SERIES, start, end)
    recession_periods = fetch_recession_periods(start, end)

    hy_bps = _latest_bps(hy_spread)
    ig_bps = _latest_bps(ig_spread)
    latest: dict[str, Any] = {}
    if hy_bps is not None:
        latest["hy_bps"] = hy_bps
        latest["hy_status"] = compute_spread_status(hy_bps, "hy")
    if ig_bps is not None:
        latest["ig_bps"] = ig_bps
        latest["ig_status"] = compute_spread_status(ig_bps, "ig")

    return {
        "hy_spread": hy_spread,
        "ig_spread": ig_spread,
        "recession_periods": recession_periods,
        "latest": latest,
        "series_ids": {
            "hy_oas": FRED_HY_OAS_SERIES,
            "ig_oas": FRED_IG_OAS_SERIES,
            "recession": FRED_RECESSION_SERIES,
        },
        "days": days,
        "data_window_note": _data_window_note(days, hy_spread, ig_spread),
    }


def build_etf_credit_spread_payload() -> dict[str, Any]:
    """Build HYG-TLT and LQD-TLT ETF yield spread snapshot."""
    from domains.finance.data_sources.yahoo_etf_yields import build_etf_spread_snapshot

    return build_etf_spread_snapshot()
