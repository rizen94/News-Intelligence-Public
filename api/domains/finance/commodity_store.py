"""
Generic commodity store for non-gold metals (silver, platinum, future metals).
Backed by market_data_store, using source=\"commodity_manual\" and symbol=<metal>.

Used to:
- Import long-range history from CSV/other sources (manual backfill).
- Append daily spot observations (from metals.dev or other providers).
- Serve history for /finance/commodity/{commodity}/history without hitting external APIs.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Dict

from domains.finance.data.market_data_store import upsert_observations, get_series
from shared.data_result import DataResult

SOURCE_COMMODITY_MANUAL = "commodity_manual"


def normalize_observation(obs: Dict) -> Dict:
    """
    Normalize a raw observation to market_data_store format:
    {\"date\": str, \"value\": float, \"metadata\": dict}.
    """
    date_str = obs.get("date")
    value = obs.get("value")
    if not date_str or value is None:
        raise ValueError("Observation must include 'date' and 'value'")
    metadata = obs.get("metadata") or {}
    return {
        "date": date_str,
        "value": float(value),
        "metadata": metadata,
    }


def upsert_manual_observations(metal: str, observations: List[Dict]) -> DataResult[bool]:
    """
    Upsert one or more observations for a commodity into the manual store.
    Metal is the symbol; observations should include date/value/unit.
    """
    if not observations:
        return DataResult.ok(True)
    to_store = [normalize_observation(o) for o in observations]
    return upsert_observations(SOURCE_COMMODITY_MANUAL, metal.lower(), to_store)


def get_manual_history(
    metal: str,
    days: int = 90,
) -> List[Dict]:
    """
    Get historical observations for a commodity from the manual store.
    Returns list of {\"date\": str, \"value\": float, \"unit\": str, \"source_id\": str}.
    """
    end_dt = datetime.now(timezone.utc).date()
    start_dt = end_dt - timedelta(days=max(1, days))
    start = start_dt.strftime("%Y-%m-%d")
    end = end_dt.strftime("%Y-%m-%d")
    res = get_series(
        SOURCE_COMMODITY_MANUAL,
        metal.lower(),
        start_date=start,
        end_date=end,
    )
    if not isinstance(res, DataResult) or not res.success:
        return []
    out: List[Dict] = []
    for row in res.data or []:
        meta = row.get("metadata") or {}
        out.append(
            {
                "date": row.get("date"),
                "value": row.get("value"),
                "unit": meta.get("unit", "USD/toz"),
                "source_id": meta.get("source_id", SOURCE_COMMODITY_MANUAL),
            }
        )
    return out

