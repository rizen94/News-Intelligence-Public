"""
FRED (Federal Reserve Economic Data) API client.
Uses FRED_API_KEY; caches via finance API cache; stores in market data store.
Returns DataResult for provenance and error diagnosis.
"""

import logging
import time

try:
    from config.logging_config import get_component_logger

    logger = get_component_logger("finance")
except Exception:
    logger = logging.getLogger(__name__)

from config.settings import FRED_API_KEY, FRED_RATE_LIMIT_PER_MINUTE
from shared.data_result import DataResult

from domains.finance.data.api_cache import FRED_TTL
from domains.finance.data.api_cache import get as cache_get
from domains.finance.data.api_cache import set as cache_set
from domains.finance.data.market_data_store import upsert_observations
from domains.finance.data_sources.base import DataSourceBase

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"


def _fetch_fred(
    series_id: str,
    start: str | None = None,
    end: str | None = None,
    api_key: str | None = None,
) -> DataResult[list[dict]]:
    """Raw FRED API call. Returns DataResult with observations or error."""
    key = api_key or FRED_API_KEY
    if not key:
        logger.warning("FRED_API_KEY not set — skipping fetch")
        return DataResult.fail("FRED_API_KEY not set", "auth")

    params = {"series_id": series_id, "api_key": key, "file_type": "json"}
    if start:
        params["observation_start"] = start
    if end:
        params["observation_end"] = end

    cache_params = {"series_id": series_id, "start": start, "end": end}
    cached = cache_get("fred", cache_params)
    if cached is not None:
        obs = cached.get("observations", [])
        return DataResult.ok(obs)

    t0 = time.perf_counter()
    try:
        import requests

        r = requests.get(FRED_BASE, params=params, timeout=30)
        duration_ms = (time.perf_counter() - t0) * 1000
        try:
            from shared.logging.activity_logger import log_external_call

            log_external_call(
                url=FRED_BASE,
                status="success" if r.status_code == 200 else "error",
                duration_ms=duration_ms,
                source="fred",
                series_id=series_id,
                status_code=r.status_code,
            )
        except Exception as _e:
            logger.debug("Activity log skip: %s", _e)
        if r.status_code == 429:
            return DataResult.fail("FRED rate limited (429)", "rate_limit")
        r.raise_for_status()
        data = r.json()
        obs = data.get("observations")
        if obs is None or not isinstance(obs, list):
            return DataResult.fail("Invalid FRED response schema", "parse")
        cache_set("fred", cache_params, {"observations": obs}, ttl_seconds=FRED_TTL)
        return DataResult.ok(obs)
    except Exception as e:
        duration_ms = (time.perf_counter() - t0) * 1000
        try:
            from shared.logging.activity_logger import log_external_call

            log_external_call(
                url=FRED_BASE,
                status="error",
                duration_ms=duration_ms,
                error=str(e),
                source="fred",
                series_id=series_id,
            )
        except Exception as _e:
            logger.debug("Activity log skip: %s", _e)
        logger.warning("FRED fetch failed for %s: %s", series_id, e)
        return DataResult.fail(str(e), "network")


class FREDDataSource(DataSourceBase):
    """FRED API data source."""

    def fetch_observations(
        self,
        series_id: str,
        start: str | None = None,
        end: str | None = None,
        store: bool = True,
    ) -> DataResult[list[dict]]:
        """Fetch FRED observations. Optionally store in market_data_store."""
        raw_result = _fetch_fred(series_id, start=start, end=end)
        if not raw_result.success:
            return raw_result
        raw = raw_result.data or []
        out = []
        for o in raw:
            v = o.get("value")
            if v in (".", ""):
                continue
            try:
                val = float(v)
            except (TypeError, ValueError):
                continue
            out.append(
                {
                    "date": o.get("date", ""),
                    "value": val,
                    "metadata": {
                        "realtime_start": o.get("realtime_start"),
                        "realtime_end": o.get("realtime_end"),
                    },
                }
            )
        if not out:
            return DataResult.fail("No valid observations in series", "no_data")
        if store:
            up = upsert_observations("fred", series_id, out)
            if not up.success:
                return DataResult.fail(up.error or "Store failed", "storage")
        return DataResult.ok(out)


def get_client(config: dict | None = None) -> FREDDataSource:
    """Factory: FRED client from config (e.g. sources.yaml entry)."""
    cfg = config or {
        "name": "Federal Reserve Economic Data",
        "rate_limit": {"per_minute": FRED_RATE_LIMIT_PER_MINUTE},
    }
    return FREDDataSource(cfg)
