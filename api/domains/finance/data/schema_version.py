"""
Schema version tripwire for finance SQLite databases.
Logs clear warning if version mismatch; prevents silent schema drift.
"""

import logging
import sqlite3

try:
    from config.logging_config import get_component_logger
    logger = get_component_logger("finance")
except Exception:
    logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


def ensure_schema_version(conn: sqlite3.Connection, db_path: str, expected: int = SCHEMA_VERSION) -> None:
    """
    Ensure _schema_meta exists and has schema_version. On first run, set it.
    If version exists and doesn't match, log warning (tripwire).
    Call from _init_schema in each store.
    """
    conn.execute("CREATE TABLE IF NOT EXISTS _schema_meta (key TEXT PRIMARY KEY, value TEXT)")
    cur = conn.execute("SELECT value FROM _schema_meta WHERE key = 'schema_version'")
    row = cur.fetchone()
    if row is None:
        conn.execute("INSERT INTO _schema_meta (key, value) VALUES ('schema_version', ?)", (str(expected),))
        return
    try:
        actual = int(row[0])
        if actual != expected:
            logger.warning(
                "%s schema version %d does not match expected %d. Delete the file to recreate, or run migrations.",
                db_path,
                actual,
                expected,
            )
    except (ValueError, TypeError):
        pass
