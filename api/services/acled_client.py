"""
ACLED client — normalized conflict events into intelligence.external_events.

Requires ACLED_API_KEY + ACLED_EMAIL (academic/non-commercial registration).
When credentials absent, returns empty batch (no-op).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import requests

from shared.database.connection import get_db_connection_context
from config.runtime import env_bool, env_float, env_int, env_pop, env_set, env_setdefault, env_str

logger = logging.getLogger(__name__)

ACLED_API = "https://api.acleddata.com/acled/read"


def _credentials() -> tuple[str, str] | None:
    key = (env_str("ACLED_API_KEY") or "").strip()
    email = (env_str("ACLED_EMAIL") or "").strip()
    if key and email:
        return key, email
    return None


def fetch_acled_page(
    *,
    page: int = 1,
    event_date_where: str | None = None,
    country: str | None = None,
) -> list[dict[str, Any]]:
    creds = _credentials()
    if not creds:
        logger.info("ACLED credentials not set — skipping fetch")
        return []
    key, email = creds
    params: dict[str, Any] = {
        "key": key,
        "email": email,
        "page": page,
        "limit": 500,
    }
    if event_date_where:
        params["event_date_where"] = event_date_where
    if country:
        params["country"] = country
    try:
        r = requests.get(ACLED_API, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        return data.get("data") or []
    except Exception as e:
        logger.warning("ACLED fetch failed: %s", e)
        return []


def normalize_acled_row(row: dict[str, Any]) -> dict[str, Any]:
    ed = row.get("event_date") or row.get("event_date_clean")
    event_dt = datetime.now(timezone.utc)
    if ed:
        try:
            event_dt = datetime.strptime(str(ed)[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    fatalities = row.get("fatalities")
    try:
        fatalities_int = int(fatalities) if fatalities not in (None, "") else None
    except (TypeError, ValueError):
        fatalities_int = None
    external_id = str(row.get("event_id") or row.get("data_id") or "")
    return {
        "source": "acled",
        "external_id": external_id,
        "event_date": event_dt,
        "title": (row.get("event_type") or "ACLED event")[:500],
        "summary": (row.get("notes") or row.get("sub_event_type") or "")[:2000],
        "country_code": (row.get("iso") or row.get("country") or "")[:8],
        "region": row.get("region"),
        "event_type": row.get("event_type"),
        "fatalities": fatalities_int,
        "entity_qids": [],
        "raw": row,
    }


def upsert_external_events(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    n = 0
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for row in rows:
                if not row.get("external_id"):
                    continue
                import json

                cur.execute(
                    """
                    INSERT INTO intelligence.external_events (
                        source, external_id, event_date, end_date, title, summary,
                        country_code, region, event_type, fatalities, entity_qids, raw,
                        ingestion_date, vintage_date
                    ) VALUES (
                        %s, %s, %s, NULL, %s, %s, %s, %s, %s, %s, %s::text[], %s::jsonb,
                        NOW(), NOW()
                    )
                    ON CONFLICT (source, external_id) DO UPDATE SET
                        event_date = EXCLUDED.event_date,
                        title = EXCLUDED.title,
                        summary = EXCLUDED.summary,
                        fatalities = EXCLUDED.fatalities,
                        raw = EXCLUDED.raw,
                        vintage_date = NOW()
                    """,
                    (
                        row["source"],
                        row["external_id"],
                        row["event_date"],
                        row["title"],
                        row.get("summary"),
                        row.get("country_code"),
                        row.get("region"),
                        row.get("event_type"),
                        row.get("fatalities"),
                        row.get("entity_qids") or [],
                        json.dumps(row.get("raw") or {}),
                    ),
                )
                n += 1
        conn.commit()
    return n


def run_acled_incremental_sync(*, max_pages: int = 3) -> dict[str, Any]:
    total = 0
    for page in range(1, max_pages + 1):
        raw_rows = fetch_acled_page(page=page)
        if not raw_rows:
            break
        normalized = [normalize_acled_row(r) for r in raw_rows]
        total += upsert_external_events(normalized)
    return {"success": True, "upserted": total}
