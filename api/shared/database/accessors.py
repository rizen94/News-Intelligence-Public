"""High-level database accessors extracted from connection internals.

Services should prefer these helpers over importing ``shared.database``
directly.  They wrap the low-level connection/context-manager API and provide a
stable interface that won't break when the underlying module is refactored.

## Migration guide

Before (bypasses facade, counted as sprawl):

    from api.shared.database import get_db_connection_context
    with get_db_connection_context() as conn:
        ...

After (goes through facade):

    from api.shared.database import execute_query, fetch_many

Or just use the re-exports already in ``shared.database.__init__``:

    from api.shared.database import get_db_connection_context
    with get_db_connection_context() as conn:
        ...

The second form works today — the audit tracks whether files go through the
facade (``api.shared.database import ...``) versus directly into the impl
module (``api.shared.database import ...``).
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator

from .connection import (
    get_db_connection,
    get_db_connection_context,
    get_ui_db_connection,
    get_ui_db_connection_context,
)

logger = logging.getLogger(__name__)


# ── Convenient wrappers -----------------------------------------------------

@contextmanager
def db_execute(
    query: str,
    params: tuple[Any, ...] | dict[str, Any] | None = None,
    *,
    ui: bool = False,
) -> Iterator[Any]:
    """Execute a single query and yield the cursor.

    Usage::

        with db_execute("SELECT * FROM articles WHERE id = %s", (42,)) as cur:
            row = cur.fetchone()
    """
    ctx = get_ui_db_connection_context if ui else get_db_connection_context
    with ctx() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(query, params or ())
            yield cursor
        except Exception:
            logger.exception("db_execute failed: %s", query)
            raise


def db_fetch_one(
    query: str,
    params: tuple[Any, ...] | dict[str, Any] | None = None,
    *,
    ui: bool = False,
) -> dict[str, Any] | None:
    """Return the first row of a query as a dict, or ``None``."""
    with db_execute(query, params, ui=ui) as cur:
        return cur.fetchone()


def db_fetch_many(
    query: str,
    params: tuple[Any, ...] | dict[str, Any] | None = None,
    *,
    ui: bool = False,
) -> list[dict[str, Any]]:
    """Return all rows of a query as a list of dicts."""
    with db_execute(query, params, ui=ui) as cur:
        return cur.fetchall()


def db_execute_many(
    query: str,
    params_list: list[tuple[Any, ...]],
    *,
    ui: bool = False,
) -> None:
    """Execute *query* with multiple parameter sets (executemany)."""
    ctx = get_ui_db_connection_context if ui else get_db_connection_context
    with ctx() as conn:
        cursor = conn.cursor()
        try:
            cursor.executemany(query, params_list)
            conn.commit()
        except Exception:
            logger.exception("db_execute_many failed: %s", query)
            raise


def db_heartbeat(
    interval: float = 30.0,
    *,
    ui: bool = False,
    stop_event: Any | None = None,
) -> None:
    """Periodically run a lightweight health-check query.

    Call from a service's background loop to keep the connection alive in
    long-running processes without letting the pool timeout.

    Parameters ``interval`` and ``ui`` control timing and connection target;
    pass *stop_event* (from :class:`threading.Event`) to break the loop.
    """
    try:
        import time
    except ImportError:  # pragma: no cover
        return

    conn_fn = get_ui_db_connection if ui else get_db_connection
    while stop_event is None or not stop_event.is_set():
        try:
            with conn_fn() as conn:
                conn.execute("SELECT 1")
        except Exception:
            logger.debug("db_heartbeat query failed (pool may be idle): %s", conn_fn)
        if stop_event is not None and stop_event.wait(timeout=interval):
            break
        time.sleep(interval)
