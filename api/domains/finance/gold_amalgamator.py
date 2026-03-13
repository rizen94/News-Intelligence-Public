"""
Gold price amalgamator — fetches from multiple sources, normalizes, stores, and exposes unified view.

Sources (preference order for USD):
- metals_dev: USD/toz historical + spot, requires METALS_DEV_API_KEY
- freegoldapi: USD/oz, no API key, historical + daily
- fred_iq12260: Export Price Index (Dec 2024=100), requires FRED_API_KEY

Stored under source="gold_amalgam", symbol=<source_id>.
Evidence ledger records each fetch with provenance for audit trail.
"""

import logging
from datetime import datetime, timedelta, timezone

try:
    from config.logging_config import get_component_logger
    logger = get_component_logger("finance")
except Exception:
    logger = logging.getLogger(__name__)

from domains.finance.data.market_data_store import upsert_observations, get_series
from domains.finance.data.evidence_ledger import record as ledger_record
from domains.finance.gold_sources import freegoldapi, fred_gold
from shared.data_result import DataResult


def _metals_dev_fetch(start: str | None = None, end: str | None = None) -> DataResult[list[dict]]:
    """Fetch gold timeseries from metals.dev (30-day windows). Same contract as freegoldapi.fetch."""
    try:
        from domains.finance.data_sources.metals_dev import fetch_timeseries
    except ImportError:
        return DataResult.fail("metals_dev adapter not available", "config")
    end_dt = datetime.strptime(end, "%Y-%m-%d").date() if end else datetime.now(timezone.utc).date()
    start_dt = datetime.strptime(start, "%Y-%m-%d").date() if start else (end_dt - timedelta(days=30))
    return fetch_timeseries(start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d"))


SOURCES = [
    ("metals_dev", _metals_dev_fetch, "USD/toz historical"),
    ("freegoldapi", freegoldapi.fetch, "USD/oz spot"),
    ("fred_iq12260", fred_gold.fetch, "Export price index"),
]
AMALGAM_SOURCE = "gold_amalgam"


def _normalize_for_store(obs: dict) -> dict:
    """Convert amalgam observation to market_data_store format."""
    return {
        "date": obs["date"],
        "value": obs["value"],
        "metadata": {
            "unit": obs.get("unit", ""),
            "source_id": obs.get("source_id", ""),
            **obs.get("metadata", {}),
        },
    }


def fetch_all(start: str | None = None, end: str | None = None, store: bool = True) -> dict[str, list[dict]]:
    """
    Fetch from all gold sources. Returns {source_id: [obs, ...]}.
    Optionally stores in market_data_store. Records provenance in evidence ledger (status=ok or error).
    """
    report_id = f"gold_fetch_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    results = {}
    for source_id, fetch_fn, desc in SOURCES:
        result = fetch_fn(start=start, end=end)
        if result.success:
            obs = result.data or []
            results[source_id] = obs
            if store and obs:
                to_store = [_normalize_for_store(o) for o in obs]
                up = upsert_observations(AMALGAM_SOURCE, source_id, to_store)
                if up.success:
                    logger.info("Gold amalgamator: %s fetched %d observations", source_id, len(obs))
                else:
                    logger.warning("Gold amalgamator: %s store failed: %s", source_id, up.error)
            dates = [o["date"] for o in obs if o.get("date")]
            ledger_record(
                report_id=report_id,
                source_type="gold_price",
                source_id=source_id,
                evidence_data={
                    "status": "ok",
                    "observations_count": len(obs),
                    "date_range": {"start": min(dates) if dates else None, "end": max(dates) if dates else None},
                    "unit": obs[0].get("unit", "") if obs else "",
                    "is_primary_usd_source": source_id == "freegoldapi",
                    "description": desc,
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        else:
            results[source_id] = []
            ledger_record(
                report_id=report_id,
                source_type="gold_price",
                source_id=source_id,
                evidence_data={
                    "status": "error",
                    "error_type": result.error_type,
                    "error": result.error,
                    "description": desc,
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                },
            )
    return results


def get_stored(source_id: str | None = None, start: str | None = None, end: str | None = None) -> dict:
    """
    Get stored gold data. If source_id is None, returns all sources.
    """
    if source_id:
        r = get_series(AMALGAM_SOURCE, source_id, start_date=start, end_date=end)
        return {source_id: r.data if r.success else []}

    # List all gold symbols and fetch each
    try:
        import sqlite3
        from config.settings import FINANCE_MARKET_DB
        conn = sqlite3.connect(str(FINANCE_MARKET_DB))
        cur = conn.execute(
            "SELECT DISTINCT symbol FROM market_series WHERE source = ? ORDER BY symbol",
            (AMALGAM_SOURCE,)
        )
        symbols = [r[0] for r in cur.fetchall()]
        conn.close()
    except Exception as e:
        logger.warning("Gold amalgamator get_stored failed: %s", e)
        return {}

    out = {}
    for sym in symbols:
        r = get_series(AMALGAM_SOURCE, sym, start_date=start, end_date=end)
        out[sym] = r.data if r.success else []
    return out


PREFERRED_SOURCE_ORDER = ["metals_dev", "freegoldapi", "fred_iq12260"]
USD_UNITS = ("USD/oz", "USD/toz")


def get_unified(
    prefer_unit: str = "USD/oz",
    start: str | None = None,
    end: str | None = None,
    fetch_if_empty: bool = True,
) -> list[dict]:
    """
    Get unified gold view. Prefers metals_dev (USD/toz) then freegoldapi (USD/oz) then FRED index.
    Returns list of {"date": str, "value": float, "unit": str, "source_id": str}.
    """
    stored = get_stored(start=start, end=end)

    by_source = {}
    for source_id, obs_list in stored.items():
        if not obs_list:
            continue
        unit = None
        for o in (obs_list or [])[:1]:
            unit = (o.get("metadata") or {}).get("unit", "")
            break
        formatted = []
        for o in obs_list:
            meta = o.get("metadata") or {}
            formatted.append({
                "date": o["date"],
                "value": o["value"],
                "unit": meta.get("unit", ""),
                "source_id": meta.get("source_id", source_id),
            })
        by_source[source_id] = (unit, formatted)

    for sid in PREFERRED_SOURCE_ORDER:
        if sid not in by_source:
            continue
        unit, formatted = by_source[sid]
        if prefer_unit in USD_UNITS:
            if unit in USD_UNITS:
                result = formatted
                break
        elif unit == prefer_unit:
            result = formatted
            break
    else:
        result = list(by_source.values())[0][1] if by_source else []

    if not result and fetch_if_empty:
        fetch_all(start=start, end=end, store=True)
        return get_unified(prefer_unit=prefer_unit, start=start, end=end, fetch_if_empty=False)
    return result


def get_history(days: int = 90, fetch_if_empty: bool = True) -> list[dict]:
    """
    Get historical daily gold prices for the last `days` days.
    Prefers metals_dev then freegoldapi then FRED. Returns list of {"date": str, "value": float, "unit": str, "source_id": str}.
    """
    end_dt = datetime.now(timezone.utc).date()
    start_dt = end_dt - timedelta(days=max(1, days))
    start = start_dt.strftime("%Y-%m-%d")
    end = end_dt.strftime("%Y-%m-%d")
    return get_unified(start=start, end=end, fetch_if_empty=fetch_if_empty)


def list_sources() -> list[dict]:
    """List configured gold sources and their status."""
    return [
        {"id": sid, "description": desc}
        for sid, _, desc in SOURCES
    ]
