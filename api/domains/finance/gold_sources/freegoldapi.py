"""
FreeGoldAPI — no-key JSON endpoint, USD-normalized gold prices.
https://freegoldapi.com/data/latest.json
Returns DataResult for provenance and error diagnosis.
"""

import logging
import time

try:
    from config.logging_config import get_component_logger

    logger = get_component_logger("finance")
except Exception:
    logger = logging.getLogger(__name__)

from shared.data_result import DataResult

SOURCE_ID = "freegoldapi"
UNIT = "USD/oz"
URL = "https://freegoldapi.com/data/latest.json"


def fetch(start: str | None = None, end: str | None = None) -> DataResult[list[dict]]:
    """
    Fetch gold prices from FreeGoldAPI.
    Returns DataResult[list[dict]] with {"date": str, "value": float, "unit": str, "source_id": str, "metadata": dict}.
    """
    t0 = time.perf_counter()
    try:
        import requests

        r = requests.get(URL, timeout=30)
        duration_ms = (time.perf_counter() - t0) * 1000
        try:
            from shared.logging.activity_logger import log_external_call

            log_external_call(
                url=URL,
                status="success" if r.status_code == 200 else "error",
                duration_ms=duration_ms,
                source="freegoldapi",
                status_code=r.status_code,
            )
        except Exception as _e:
            logger.debug("Activity log skip: %s", _e)
        if r.status_code == 429:
            return DataResult.fail("FreeGoldAPI rate limited (429)", "rate_limit")
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, list):
            return DataResult.fail("FreeGoldAPI response not a list", "parse")
        out = []
        for item in data:
            date_str = item.get("date", "")
            if not date_str:
                continue
            try:
                val = float(item.get("price", 0))
            except (TypeError, ValueError):
                continue
            if start and date_str < start:
                continue
            if end and date_str > end:
                continue
            out.append(
                {
                    "date": date_str,
                    "value": val,
                    "unit": UNIT,
                    "source_id": SOURCE_ID,
                    "metadata": {"raw_source": item.get("source", "")},
                }
            )
        return DataResult.ok(out)
    except Exception as e:
        duration_ms = (time.perf_counter() - t0) * 1000
        try:
            from shared.logging.activity_logger import log_external_call

            log_external_call(
                url=URL,
                status="error",
                duration_ms=duration_ms,
                error=str(e),
                source="freegoldapi",
            )
        except Exception as _e:
            logger.debug("Activity log skip: %s", _e)
        logger.warning("FreeGoldAPI fetch failed: %s", e)
        return DataResult.fail(str(e), "network")
