"""
Yahoo Finance ETF yield fetch for credit spread calculator (HYG/TLT, LQD/TLT).
"""

from __future__ import annotations

import logging
import time
from typing import Any

from domains.finance.credit_spread_service import compute_spread_status

logger = logging.getLogger(__name__)

YAHOO_CACHE_TTL = 1800  # 30 minutes
CREDIT_ETFS = ("HYG", "LQD")
TREASURY_ETF = "TLT"


def _cache_get(params: dict) -> dict | None:
    try:
        from domains.finance.data.api_cache import get as cache_get

        return cache_get("yahoo_etf", params)
    except Exception:
        return None


def _cache_set(params: dict, payload: dict) -> None:
    try:
        from domains.finance.data.api_cache import set as cache_set

        cache_set("yahoo_etf", params, payload, ttl_seconds=YAHOO_CACHE_TTL)
    except Exception as exc:
        logger.debug("Yahoo ETF cache skip: %s", exc)


def _extract_yield_pct(info: dict[str, Any]) -> float | None:
    """Best-effort yield as percent from Yahoo info dict."""
    for key in ("yield", "dividendYield", "trailingAnnualDividendYield"):
        raw = info.get(key)
        if raw is None:
            continue
        try:
            val = float(raw)
        except (TypeError, ValueError):
            continue
        # Yahoo often returns yield as a fraction (0.0584 = 5.84%)
        if 0 < val < 1:
            val *= 100.0
        if val > 0:
            return round(val, 4)
    return None


def fetch_etf_yield_pct(ticker: str) -> float | None:
    """Fetch latest ETF yield (percent) via yfinance."""
    cache_params = {"ticker": ticker.upper(), "field": "yield"}
    cached = _cache_get(cache_params)
    if cached is not None and "yield_pct" in cached:
        return cached.get("yield_pct")

    try:
        import yfinance as yf
    except ImportError:
        logger.warning("yfinance not installed — ETF yields unavailable")
        return None

    t0 = time.perf_counter()
    try:
        info = yf.Ticker(ticker.upper()).info or {}
        yield_pct = _extract_yield_pct(info)
        if yield_pct is not None:
            _cache_set(cache_params, {"yield_pct": yield_pct})
        return yield_pct
    except Exception as exc:
        logger.warning("Yahoo ETF yield fetch failed for %s: %s", ticker, exc)
        return None
    finally:
        elapsed = (time.perf_counter() - t0) * 1000
        logger.debug("Yahoo ETF %s fetch %.0fms", ticker, elapsed)


def compute_etf_spread_bps(
    credit_etf: str,
    treasury_etf: str = TREASURY_ETF,
) -> dict[str, Any] | None:
    """(credit_yield - treasury_yield) * 100 in basis points."""
    credit_yield = fetch_etf_yield_pct(credit_etf)
    treasury_yield = fetch_etf_yield_pct(treasury_etf)
    if credit_yield is None or treasury_yield is None:
        return None
    spread_bps = round((credit_yield - treasury_yield) * 100.0, 2)
    kind = "hy" if credit_etf.upper() == "HYG" else "ig"
    return {
        "credit_etf": credit_etf.upper(),
        "treasury_etf": treasury_etf.upper(),
        "credit_yield_pct": credit_yield,
        "treasury_yield_pct": treasury_yield,
        "spread_bps": spread_bps,
        "status": compute_spread_status(spread_bps, kind),
    }


def build_etf_spread_snapshot() -> dict[str, Any]:
    """Current HYG-TLT and LQD-TLT spreads with component yields."""
    hy = compute_etf_spread_bps("HYG", TREASURY_ETF)
    ig = compute_etf_spread_bps("LQD", TREASURY_ETF)
    latest: dict[str, Any] = {}
    if hy:
        latest["hy_bps"] = hy["spread_bps"]
        latest["hy_status"] = hy["status"]
    if ig:
        latest["ig_bps"] = ig["spread_bps"]
        latest["ig_status"] = ig["status"]
    return {
        "hyg_tlt": hy,
        "lqd_tlt": ig,
        "latest": latest,
        "formula": "(credit_etf_yield_pct - TLT_yield_pct) * 100",
    }
