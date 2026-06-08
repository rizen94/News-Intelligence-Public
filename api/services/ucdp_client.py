"""
UCDP GED client — pre-1997 conflict backfill into intelligence.external_events.

Uses UCDP open API; no key required for basic GED downloads.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import requests

from services.acled_client import upsert_external_events

logger = logging.getLogger(__name__)

UCDP_GED_API = "https://ucdpapi.pcr.uu.se/api/gedevents/1"


def fetch_ucdp_events(*, pagesize: int = 100, page: int = 0) -> list[dict[str, Any]]:
    try:
        r = requests.get(
            UCDP_GED_API,
            params={"pagesize": pagesize, "page": page},
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("Result") or []
    except Exception as e:
        logger.warning("UCDP fetch failed: %s", e)
        return []


def normalize_ucdp_row(row: dict[str, Any]) -> dict[str, Any]:
    ed = row.get("date_start") or row.get("date_prec")
    event_dt = datetime.now(timezone.utc)
    if ed:
        try:
            event_dt = datetime.strptime(str(ed)[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    deaths = row.get("best") or row.get("deaths_a") or row.get("deaths_b")
    try:
        fatalities = int(deaths) if deaths is not None else None
    except (TypeError, ValueError):
        fatalities = None
    eid = str(row.get("id") or row.get("relid") or "")
    return {
        "source": "ucdp",
        "external_id": eid,
        "event_date": event_dt,
        "title": (row.get("type_of_violence") or "UCDP event")[:500],
        "summary": (row.get("conflict_name") or "")[:2000],
        "country_code": (row.get("country") or "")[:8],
        "region": row.get("region"),
        "event_type": row.get("type_of_violence"),
        "fatalities": fatalities,
        "entity_qids": [],
        "raw": row,
    }


def run_ucdp_backfill_batch(*, pages: int = 2, pagesize: int = 100) -> dict[str, Any]:
    total = 0
    for page in range(pages):
        rows = fetch_ucdp_events(page=page, pagesize=pagesize)
        if not rows:
            break
        normalized = [normalize_ucdp_row(r) for r in rows]
        total += upsert_external_events(normalized)
    return {"success": True, "upserted": total}
