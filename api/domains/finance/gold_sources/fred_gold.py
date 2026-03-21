"""
FRED gold-related series — IQ12260 (Export Price Index: Nonmonetary Gold).
Delegates to FRED adapter (which handles caching under 'fred'); no duplicate cache.
Returns DataResult for provenance and error diagnosis.
"""

import logging

try:
    from config.logging_config import get_component_logger

    logger = get_component_logger("finance")
except Exception:
    logger = logging.getLogger(__name__)

from config.settings import FRED_API_KEY, FRED_GOLD_SERIES_ID
from shared.data_result import DataResult

from domains.finance.data_sources.fred import get_client

SOURCE_ID = "fred_iq12260"
UNIT = "index"  # Dec 2024 = 100
FRED_SERIES = FRED_GOLD_SERIES_ID or "IQ12260"


def fetch(start: str | None = None, end: str | None = None) -> DataResult[list[dict]]:
    """
    Fetch FRED IQ12260 (Export Price Index: Nonmonetary Gold).
    Uses FRED adapter — caching handled there. Returns DataResult with normalized gold observations.
    """
    if not FRED_API_KEY:
        logger.debug("FRED_API_KEY not set — skipping fred_gold")
        return DataResult.fail("FRED_API_KEY not set", "auth")

    client = get_client()
    result = client.fetch_observations(FRED_SERIES, start=start, end=end, store=False)
    if not result.success:
        return result
    raw_obs = result.data or []
    out = []
    for o in raw_obs:
        meta = o.get("metadata") or {}
        out.append(
            {
                "date": o.get("date", ""),
                "value": o["value"],
                "unit": UNIT,
                "source_id": SOURCE_ID,
                "metadata": {
                    "realtime_start": meta.get("realtime_start"),
                    "realtime_end": meta.get("realtime_end"),
                },
            }
        )
    return DataResult.ok(out)
