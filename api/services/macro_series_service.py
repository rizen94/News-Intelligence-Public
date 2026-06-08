"""
Macro series observation store — vintage-aware upserts from FRED/ALFRED and CSV imports.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from shared.database.connection import get_db_connection_context, get_ui_db_connection_context

from services.alfred_client import default_longitudinal_series, fetch_series_vintage

logger = logging.getLogger(__name__)


def upsert_macro_observations(rows: list[dict[str, Any]]) -> int:
    """Insert macro observations; skip duplicates on unique constraint."""
    if not rows:
        return 0
    inserted = 0
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for row in rows:
                obs_date = row.get("observation_date")
                if not obs_date:
                    continue
                vintage = row.get("vintage_date")
                if isinstance(vintage, datetime):
                    vintage_ts = vintage
                else:
                    vintage_ts = datetime.now(timezone.utc)
                try:
                    cur.execute(
                        """
                        INSERT INTO intelligence.macro_series_observations
                            (series_id, observation_date, value, vintage_date, source, metadata)
                        VALUES (%s, %s::date, %s, %s, %s, %s::jsonb)
                        ON CONFLICT (series_id, observation_date, vintage_date, source) DO NOTHING
                        """,
                        (
                            row.get("series_id"),
                            obs_date,
                            row.get("value"),
                            vintage_ts,
                            row.get("source") or "fred",
                            "{}",
                        ),
                    )
                    if cur.rowcount:
                        inserted += 1
                except Exception as e:
                    logger.debug("macro upsert skip: %s", e)
        conn.commit()
    return inserted


def refresh_longitudinal_macro_series(
    *,
    series_ids: list[str] | None = None,
    observation_start: str = "1970-01-01",
) -> dict[str, Any]:
    """Pull ALFRED/FRED for configured series and upsert."""
    ids = series_ids or default_longitudinal_series()
    total_inserted = 0
    per_series: dict[str, int] = {}
    for sid in ids:
        rows = fetch_series_vintage(sid, observation_start=observation_start)
        n = upsert_macro_observations(rows)
        per_series[sid] = n
        total_inserted += n
    return {"success": True, "inserted": total_inserted, "per_series": per_series}


def get_macro_series_for_arc(
    series_ids: list[str],
    *,
    as_of_date: datetime | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Latest vintage per observation_date on or before as_of_date."""
    if not series_ids:
        return []
    as_of = as_of_date or datetime.now(timezone.utc)
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT ON (series_id, observation_date)
                    series_id, observation_date, value, vintage_date, source
                FROM intelligence.macro_series_observations
                WHERE series_id = ANY(%s)
                  AND vintage_date <= %s
                ORDER BY series_id, observation_date, vintage_date DESC
                LIMIT %s
                """,
                (series_ids, as_of, limit),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
