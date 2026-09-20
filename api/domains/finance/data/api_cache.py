"""
Finance domain — SQLite API cache for FRED/EDGAR responses.
Siloed from main PostgreSQL api_cache.
"""

import sqlite3
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

try:
    from config.logging_config import get_component_logger
    logger = get_component_logger("finance")
except Exception:
    logger = logging.getLogger(__name__)

from config.settings import FINANCE_CACHE_DB
from domains.finance.data.schema_version import ensure_schema_version, SCHEMA_VERSION

DEFAULT_TTL_SECONDS = 3600  # 1 hour for FRED
FRED_TTL = 86400            # 24h for market data
EDGAR_TTL = 3600 * 12       # 12h for filings


def _init_schema(conn: sqlite3.Connection) -> None:
    ensure_schema_version(conn, str(FINANCE_CACHE_DB), SCHEMA_VERSION)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_cache (
            cache_key TEXT PRIMARY KEY,
            service TEXT NOT NULL,
            query_hash TEXT,
            response_data TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_api_cache_service ON api_cache(service)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_api_cache_expires ON api_cache(expires_at)")
    conn.commit()


def _hash_query(service: str, params: dict) -> str:
    data = json.dumps({"service": service, "params": params}, sort_keys=True, default=str)
    return hashlib.sha256(data.encode()).hexdigest()


def get(service: str, params: dict) -> Any | None:
    """Get cached response for service+params. Returns None on miss or expiry."""
    key = _hash_query(service, params)
    try:
        conn = sqlite3.connect(str(FINANCE_CACHE_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT response_data, expires_at FROM api_cache WHERE cache_key = ?",
            (key,)
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        expires = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > expires:
            return None
        return json.loads(row["response_data"])
    except Exception as e:
        logger.warning("Finance API cache get failed: %s", e)
        return None


def set(service: str, params: dict, data: Any, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> bool:
    """Store response in cache."""
    key = _hash_query(service, params)
    expires = datetime.now(timezone.utc).timestamp() + ttl_seconds
    expires_str = datetime.fromtimestamp(expires, tz=timezone.utc).isoformat()
    try:
        conn = sqlite3.connect(str(FINANCE_CACHE_DB))
        _init_schema(conn)
        conn.execute(
            """INSERT OR REPLACE INTO api_cache (cache_key, service, query_hash, response_data, expires_at)
               VALUES (?, ?, ?, ?, ?)""",
            (key, service, key[:16], json.dumps(data, default=str), expires_str)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.warning("Finance API cache set failed: %s", e)
        return False


def prune_expired() -> int:
    """Remove expired entries. Returns count deleted."""
    try:
        conn = sqlite3.connect(str(FINANCE_CACHE_DB))
        cur = conn.execute(
            "DELETE FROM api_cache WHERE expires_at < ?",
            (datetime.now(timezone.utc).isoformat(),)
        )
        n = cur.rowcount
        conn.commit()
        conn.close()
        return n
    except Exception as e:
        logger.warning("Finance API cache prune failed: %s", e)
        return 0
