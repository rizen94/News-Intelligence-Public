"""PostgreSQL savepoint helpers — keep transactions usable after row-level failures."""

from __future__ import annotations

import logging
import re
from typing import Any

from psycopg2 import extensions

logger = logging.getLogger(__name__)

_SAVEPOINT_NAME_RE = re.compile(r"[^a-zA-Z0-9_]")


def sanitize_savepoint_name(name: str) -> str:
    return _SAVEPOINT_NAME_RE.sub("_", (name or "sp")[:60])


def transaction_in_error(conn) -> bool:
    try:
        return conn.get_transaction_status() == extensions.TRANSACTION_STATUS_INERROR
    except Exception:
        return False


def rollback_transaction(conn) -> None:
    try:
        conn.rollback()
    except Exception as e:
        logger.debug("rollback_transaction: %s", e)


def rollback_to_savepoint(cur, conn, savepoint: str) -> None:
    sp = sanitize_savepoint_name(savepoint)
    try:
        cur.execute(f"ROLLBACK TO SAVEPOINT {sp}")
        cur.execute(f"RELEASE SAVEPOINT {sp}")
    except Exception:
        rollback_transaction(conn)


def run_in_savepoint(cur, conn, savepoint: str, fn) -> bool:
    """Run callable inside a savepoint; return False on failure."""
    sp = sanitize_savepoint_name(savepoint)
    if transaction_in_error(conn):
        rollback_transaction(conn)
    try:
        cur.execute(f"SAVEPOINT {sp}")
        fn()
        cur.execute(f"RELEASE SAVEPOINT {sp}")
        return True
    except Exception:
        rollback_to_savepoint(cur, conn, sp)
        return False


def execute_with_savepoint(
    cur,
    conn,
    savepoint: str,
    sql: str,
    params: Any = None,
) -> bool:
    """
    Run one statement inside a savepoint.

    Returns True on success. On failure rolls back to the savepoint so the
    outer transaction can continue.
    """
    sp = sanitize_savepoint_name(savepoint)
    if transaction_in_error(conn):
        rollback_transaction(conn)
    try:
        cur.execute(f"SAVEPOINT {sp}")
        cur.execute(sql, params)
        cur.execute(f"RELEASE SAVEPOINT {sp}")
        return True
    except Exception:
        rollback_to_savepoint(cur, conn, sp)
        return False
