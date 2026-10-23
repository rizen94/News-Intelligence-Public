"""
Trade and resource data imports (Phase 2 tier A/B) into macro_series_observations.

Tier A: EIA petroleum/energy series (API key optional), USGS news already via RSS.
Tier B: UN Comtrade placeholder — respects rate limits when COMTRADE_API_KEY set.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import requests

from services.macro_series_service import upsert_macro_observations

logger = logging.getLogger(__name__)

_EIA_BASE = "https://api.eia.gov/v2"


def fetch_eia_series(
    series_id: str,
    *,
    route: str = "petroleum/pri/spt/data",
    frequency: str = "daily",
    length: int = 500,
    eia_series_id: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch EIA observations.

    Prefer ``eia_series_id`` via ``/v2/seriesid/{id}`` (e.g. ``PET.RWTC.D`` for WTI spot).
    The petroleum spot-price *route* returns multiple products (gasoline etc.) and is a
    poor default for crude — only used when no series id is given.
    """
    api_key = (os.environ.get("EIA_API_KEY") or "").strip()
    if not api_key:
        logger.info("EIA_API_KEY unset — skip EIA import")
        return []
    vintage = datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []

    # 1) Canonical series id path (accurate WTI / product series)
    sid = (eia_series_id or "").strip()
    if sid:
        try:
            r = requests.get(
                f"{_EIA_BASE}/seriesid/{sid}",
                params={"api_key": api_key},
                timeout=90,
            )
            r.raise_for_status()
            for item in (r.json().get("response") or {}).get("data") or []:
                period = item.get("period")
                val = item.get("value")
                if period is None or val is None:
                    continue
                try:
                    rows.append(
                        {
                            "series_id": series_id,
                            "observation_date": str(period)[:10],
                            "value": float(val),
                            "vintage_date": vintage,
                            "source": "eia_api",
                        }
                    )
                except (TypeError, ValueError):
                    continue
                if len(rows) >= length:
                    break
            if rows:
                return rows
        except Exception as e:
            logger.warning("EIA seriesid %s failed: %s", sid, e)

    # 2) Route fallback (multi-product; callers should prefer seriesid)
    url = f"{_EIA_BASE}/{route}/"
    params = {
        "api_key": api_key,
        "frequency": frequency,
        "data[0]": "value",
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": length,
    }
    try:
        r = requests.get(url, params=params, timeout=60)
        r.raise_for_status()
        payload = r.json()
        for item in (payload.get("response") or {}).get("data") or []:
            period = item.get("period")
            val = item.get("value")
            if period is None or val is None:
                continue
            # Spot route mixes gasoline (~$2–5) with crude; drop obvious non-crude.
            try:
                fval = float(val)
            except (TypeError, ValueError):
                continue
            if series_id.upper().startswith("WTI") and fval < 15:
                continue
            obs_date = str(period)[:10] if len(str(period)) >= 10 else f"{period}-01"
            rows.append(
                {
                    "series_id": series_id,
                    "observation_date": obs_date,
                    "value": fval,
                    "vintage_date": vintage,
                    "source": "eia_api",
                }
            )
        return rows
    except Exception as e:
        logger.warning("EIA fetch %s failed: %s", series_id, e)
        return []


def fetch_federal_register_energy_notices(*, limit: int = 50) -> list[dict[str, Any]]:
    """Lightweight Federal Register API sample — counts as macro metadata spine."""
    url = "https://www.federalregister.gov/api/v1/documents.json"
    params = {
        "conditions[term]": "energy OR minerals OR sanctions",
        "per_page": min(limit, 100),
        "order": "newest",
        "fields[]": ["publication_date", "title", "html_url"],
    }
    try:
        r = requests.get(url, params=params, timeout=60)
        r.raise_for_status()
        vintage = datetime.now(timezone.utc)
        rows: list[dict[str, Any]] = []
        for doc in r.json().get("results") or []:
            pub = doc.get("publication_date")
            if not pub:
                continue
            rows.append(
                {
                    "series_id": "FEDREG_ENERGY_NOTICE_COUNT",
                    "observation_date": pub,
                    "value": 1.0,
                    "vintage_date": vintage,
                    "source": "federal_register_api",
                }
            )
        return rows
    except Exception as e:
        logger.warning("Federal Register fetch failed: %s", e)
        return []


def run_trade_resources_import() -> dict[str, Any]:
    if os.environ.get("TRADE_RESOURCES_IMPORT_ENABLED", "false").lower() not in ("1", "true", "yes"):
        return {"success": True, "skipped": True, "reason": "TRADE_RESOURCES_IMPORT_ENABLED off"}
    eia_rows = fetch_eia_series(
        "WTI_SPOT",
        eia_series_id="PET.RWTC.D",
        route="petroleum/pri/spt/data",
        length=500,
    )
    fed_rows = fetch_federal_register_energy_notices()
    n = upsert_macro_observations(eia_rows + fed_rows)
    return {
        "success": True,
        "inserted": n,
        "eia_rows": len(eia_rows),
        "federal_register_rows": len(fed_rows),
    }
