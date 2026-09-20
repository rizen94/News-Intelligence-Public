"""
Finance domain — SQLite market data store for time series (FRED, etc.).
Uses DataResult to distinguish "no data" from "error".
"""

import sqlite3
import json
import logging
from typing import Any

try:
    from config.logging_config import get_component_logger
    logger = get_component_logger("finance")
except Exception:
    logger = logging.getLogger(__name__)

from config.settings import FINANCE_MARKET_DB
from shared.data_result import DataResult
from domains.finance.data.schema_version import ensure_schema_version, SCHEMA_VERSION


def _init_schema(conn: sqlite3.Connection) -> None:
    ensure_schema_version(conn, str(FINANCE_MARKET_DB), SCHEMA_VERSION)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS market_series (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            symbol TEXT NOT NULL,
            series_date TEXT NOT NULL,
            value REAL,
            metadata TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source, symbol, series_date)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_market_source_symbol ON market_series(source, symbol)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_market_series_date ON market_series(series_date)")
    conn.commit()


def upsert_observations(source: str, symbol: str, observations: list[dict]) -> DataResult[int]:
    """
    Insert or replace time series observations.
    Each observation: {"date": "YYYY-MM-DD", "value": float, "metadata": optional dict}
    """
    try:
        conn = sqlite3.connect(str(FINANCE_MARKET_DB))
        _init_schema(conn)
        count = 0
        for obs in observations:
            series_date = obs.get("date") or obs.get("series_date")
            value = obs.get("value")
            metadata = json.dumps(obs.get("metadata", {}), default=str)
            conn.execute(
                """INSERT OR REPLACE INTO market_series (source, symbol, series_date, value, metadata)
                   VALUES (?, ?, ?, ?, ?)""",
                (source, symbol, str(series_date), value, metadata)
            )
            count += 1
        conn.commit()
        conn.close()
        return DataResult.ok(count)
    except Exception as e:
        logger.warning("Market data upsert failed: %s", e)
        return DataResult.fail(str(e), "storage")


def get_series(
    source: str, symbol: str, start_date: str | None = None, end_date: str | None = None
) -> DataResult[list[dict]]:
    """Get time series for source+symbol. Optional date range."""
    try:
        conn = sqlite3.connect(str(FINANCE_MARKET_DB))
        conn.row_factory = sqlite3.Row
        query = "SELECT series_date, value, metadata FROM market_series WHERE source = ? AND symbol = ?"
        params = [source, symbol]
        if start_date:
            query += " AND series_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND series_date <= ?"
            params.append(end_date)
        query += " ORDER BY series_date"
        cur = conn.execute(query, params)
        rows = cur.fetchall()
        conn.close()
        data = [
            {"date": r["series_date"], "value": r["value"], "metadata": json.loads(r["metadata"] or "{}")}
            for r in rows
        ]
        return DataResult.ok(data)
    except Exception as e:
        logger.warning("Market data get failed: %s", e)
        return DataResult.fail(str(e), "storage")


def list_symbols(source: str) -> list[str]:
    """List symbols available for a source."""
    try:
        conn = sqlite3.connect(str(FINANCE_MARKET_DB))
        cur = conn.execute(
            "SELECT DISTINCT symbol FROM market_series WHERE source = ? ORDER BY symbol",
            (source,)
        )
        out = [r[0] for r in cur.fetchall()]
        conn.close()
        return out
    except Exception as e:
        logger.warning("Market data list symbols failed: %s", e)
        return []
