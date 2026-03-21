"""
Metals.dev API adapter — historical timeseries, spot, and authority (LBMA, MCX, IBJA) prices.
Uses METALS_DEV_API_KEY; caches aggressively to stay within free-tier quota (100 req/month).
Returns DataResult for observations; spot/authority return structured dicts for UI.
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone

try:
    from config.logging_config import get_component_logger

    logger = get_component_logger("finance")
except Exception:
    logger = logging.getLogger(__name__)

from config.paths import FINANCE_DATA_DIR
from config.settings import METALS_DEV_API_KEY
from shared.data_result import DataResult

from domains.finance.data_sources.base import DataSourceBase

BASE_URL = "https://api.metals.dev/v1"
TIMESERIES_WINDOW_DAYS = 30
CACHE_TTL_TIMESERIES = 86400 * 30
CACHE_TTL_SPOT = 3600
CACHE_TTL_AUTHORITY = 3600

# Simple monthly budget tracking for free-tier usage.
USAGE_FILE = FINANCE_DATA_DIR / "metals_dev_usage.json"
METALS_DEV_MONTHLY_QUOTA = int(os.environ.get("METALS_DEV_MONTHLY_QUOTA", "100"))
_tracked_metals_env = os.environ.get("METALS_DEV_TRACKED_METALS", "gold,silver,platinum")
TRACKED_METALS = [m.strip().lower() for m in _tracked_metals_env.split(",") if m.strip()]


def _load_usage() -> dict:
    try:
        with open(USAGE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_usage(data: dict) -> None:
    try:
        USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(USAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        logger.warning("Metals.dev usage tracking save failed: %s", e)


def _can_call_metal(metal: str) -> bool:
    """
    Enforce approximate monthly budget across metals.
    - Global quota: METALS_DEV_MONTHLY_QUOTA (default 100).
    - Per-metal quota: floor(quota / max(1, len(TRACKED_METALS))).
    """
    try:
        if METALS_DEV_MONTHLY_QUOTA <= 0:
            return True  # disabled
        metal = (metal or "").lower()
        now = datetime.now(timezone.utc)
        month_key = now.strftime("%Y-%m")
        data = _load_usage()
        month_usage = data.get(month_key) or {"total": 0, "per_metal": {}}
        total = int(month_usage.get("total", 0))
        per_metal = month_usage.get("per_metal") or {}
        metal_count = int(per_metal.get(metal, 0))
        metals_count = max(1, len(TRACKED_METALS))
        per_metal_quota = max(1, METALS_DEV_MONTHLY_QUOTA // metals_count)
        if total >= METALS_DEV_MONTHLY_QUOTA or metal_count >= per_metal_quota:
            logger.info(
                "Metals.dev budget exhausted for %s: total=%d/%d, metal=%d/%d",
                metal,
                total,
                METALS_DEV_MONTHLY_QUOTA,
                metal_count,
                per_metal_quota,
            )
            return False
        # Reserve this call
        month_usage["total"] = total + 1
        per_metal[metal] = metal_count + 1
        month_usage["per_metal"] = per_metal
        data[month_key] = month_usage
        _save_usage(data)
        return True
    except Exception as e:
        logger.warning("Metals.dev budget check failed (allowing call): %s", e)
        return True


def _cache_get(service: str, params: dict):
    from domains.finance.data.api_cache import get as cache_get

    return cache_get(service, params)


def _cache_set(service: str, params: dict, value: dict, ttl: int):
    from domains.finance.data.api_cache import set as cache_set

    return cache_set(service, params, value, ttl_seconds=ttl)


def _request(path: str, params: dict) -> DataResult[dict]:
    api_key = METALS_DEV_API_KEY
    if not api_key:
        return DataResult.fail("METALS_DEV_API_KEY not set", "auth")
    # Respect monthly budget per metal when possible
    metal = (params.get("metal") or params.get("authority") or "").lower()
    if metal and not _can_call_metal(metal):
        return DataResult.fail(f"Metals.dev monthly budget exhausted for {metal}", "rate_limit")
    params = dict(params)
    params["api_key"] = api_key
    url = f"{BASE_URL}{path}"
    t0 = time.perf_counter()
    try:
        import requests

        r = requests.get(url, params=params, timeout=30)
        duration_ms = (time.perf_counter() - t0) * 1000
        try:
            from shared.logging.activity_logger import log_external_call

            log_external_call(
                url=url,
                status="success" if r.status_code == 200 else "error",
                duration_ms=duration_ms,
                source="metals_dev",
                status_code=r.status_code,
            )
        except Exception:
            pass
        if r.status_code == 429:
            return DataResult.fail("Metals.dev rate limited (429)", "rate_limit")
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "failure":
            return DataResult.fail(
                data.get("error_message", "API failure"),
                data.get("error_code", "api_error"),
            )
        return DataResult.ok(data)
    except Exception as e:
        logger.warning("Metals.dev request failed %s: %s", path, e)
        return DataResult.fail(str(e), "network")


def fetch_timeseries(start_date: str, end_date: str, metal: str = "gold") -> DataResult[list[dict]]:
    """
    Fetch daily historical metal prices. API allows max 30 days per request.
    metal: gold, silver, or platinum. Returns list of {"date": str, "value": float, "unit": str, ...}.
    """
    metal = (metal or "gold").lower()
    cache_params = {
        "endpoint": "timeseries",
        "metal": metal,
        "start_date": start_date,
        "end_date": end_date,
    }
    cached = _cache_get("metals_dev", cache_params)
    if cached is not None and isinstance(cached.get("observations"), list):
        return DataResult.ok(cached["observations"])

    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    if (end - start).days > TIMESERIES_WINDOW_DAYS:
        out = []
        cur = start
        while cur <= end:
            window_end = min(cur + timedelta(days=TIMESERIES_WINDOW_DAYS - 1), end)
            res = fetch_timeseries(
                cur.strftime("%Y-%m-%d"), window_end.strftime("%Y-%m-%d"), metal=metal
            )
            if not res.success:
                return res
            out.extend(res.data or [])
            cur = window_end + timedelta(days=1)
        out.sort(key=lambda o: o["date"])
        return DataResult.ok(out)

    raw = _request("timeseries", {"start_date": start_date, "end_date": end_date})
    if not raw.success:
        return raw
    rates = (raw.data or {}).get("rates") or {}
    observations = []
    for date_str, day_data in rates.items():
        if not isinstance(day_data, dict):
            continue
        metals = day_data.get("metals") or {}
        val = metals.get(metal)
        if val is None:
            continue
        try:
            value = float(val)
        except (TypeError, ValueError):
            continue
        observations.append(
            {
                "date": date_str,
                "value": value,
                "unit": "USD/toz",
                "source_id": "metals_dev",
                "metadata": {"currencies": day_data.get("currencies"), "metals": metals},
            }
        )
    observations.sort(key=lambda o: o["date"])
    _cache_set("metals_dev", cache_params, {"observations": observations}, CACHE_TTL_TIMESERIES)
    return DataResult.ok(observations)


def fetch_spot(metal: str = "gold", currency: str = "USD") -> DataResult[dict]:
    """
    Fetch current spot for one metal. Returns dict with price, bid, ask, high, low, change, change_percent.
    """
    cache_params = {"endpoint": "spot", "metal": metal, "currency": currency}
    cached = _cache_get("metals_dev", cache_params)
    if cached is not None and isinstance(cached.get("rate"), dict):
        return DataResult.ok(cached)

    raw = _request("metal/spot", {"metal": metal, "currency": currency})
    if not raw.success:
        return raw
    rate = (raw.data or {}).get("rate") or {}
    out = {
        "metal": metal,
        "currency": raw.data.get("currency", currency),
        "unit": (raw.data or {}).get("unit", "toz"),
        "timestamp": (raw.data or {}).get("timestamp"),
        "price": rate.get("price"),
        "bid": rate.get("bid"),
        "ask": rate.get("ask"),
        "high": rate.get("high"),
        "low": rate.get("low"),
        "change": rate.get("change"),
        "change_percent": rate.get("change_percent"),
    }
    _cache_set("metals_dev", cache_params, out, CACHE_TTL_SPOT)
    return DataResult.ok(out)


def fetch_authority(authority: str, currency: str = "USD") -> DataResult[dict]:
    """
    Fetch prices from an authority (lbma, mcx, ibja). Returns dict with authority, timestamp, rates.
    """
    cache_params = {"endpoint": "authority", "authority": authority, "currency": currency}
    cached = _cache_get("metals_dev", cache_params)
    if cached is not None and isinstance(cached.get("rates"), dict):
        return DataResult.ok(cached)

    raw = _request("metal/authority", {"authority": authority, "currency": currency})
    if not raw.success:
        return raw
    out = {
        "authority": raw.data.get("authority", authority),
        "currency": raw.data.get("currency", currency),
        "timestamp": raw.data.get("timestamp"),
        "rates": raw.data.get("rates") or {},
    }
    _cache_set("metals_dev", cache_params, out, CACHE_TTL_AUTHORITY)
    return DataResult.ok(out)


class MetalsDevDataSource(DataSourceBase):
    """Metals.dev API data source; implements fetch_observations for registry compatibility."""

    def fetch_observations(self, series_id: str, **kwargs) -> DataResult[list[dict]]:
        if series_id == "timeseries":
            start = kwargs.get("start_date") or kwargs.get("start")
            end = kwargs.get("end_date") or kwargs.get("end")
            if not start or not end:
                return DataResult.fail("start_date and end_date required for timeseries", "params")
            return fetch_timeseries(start, end)
        if series_id == "spot":
            metal = kwargs.get("metal", "gold")
            res = fetch_spot(metal=metal)
            if not res.success:
                return res
            r = res.data or {}
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            return DataResult.ok(
                [
                    {
                        "date": date_str,
                        "value": r.get("price"),
                        "unit": "USD/toz",
                        "source_id": "metals_dev",
                        "metadata": r,
                    }
                ]
            )
        if series_id == "authority":
            authority = kwargs.get("authority", "lbma")
            res = fetch_authority(authority=authority)
            if not res.success:
                return res
            r = res.data or {}
            rates = r.get("rates") or {}
            observations = []
            for key, val in rates.items():
                if isinstance(val, (int, float)):
                    observations.append(
                        {
                            "date": r.get("timestamp", "")[:10],
                            "value": float(val),
                            "unit": "USD/toz",
                            "source_id": f"metals_dev_{authority}",
                            "metadata": {"rate_key": key, "authority": authority},
                        }
                    )
            return DataResult.ok(observations)
        return DataResult.fail(f"Unknown series_id: {series_id}", "params")


def get_client(config: dict | None = None) -> MetalsDevDataSource:
    """Factory: Metals.dev client from config (e.g. sources.yaml entry)."""
    cfg = config or {"name": "Metals.dev"}
    return MetalsDevDataSource(cfg)
