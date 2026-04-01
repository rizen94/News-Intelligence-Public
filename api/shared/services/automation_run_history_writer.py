"""
Persist automation phase runs to public.automation_run_history (survives API restart).
Used by AutomationManager, optional cron heartbeat, and monitoring.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)

_RETRYABLE_TYPES: tuple = ()
try:
    import psycopg2

    _RETRYABLE_TYPES = (psycopg2.OperationalError, psycopg2.InterfaceError)
except Exception:
    _RETRYABLE_TYPES = ()


def persist_automation_run_history(
    phase_name: str,
    started_at: datetime,
    finished_at: datetime,
    success: bool,
    error_message: str | None = None,
    *,
    pool: str | None = None,
) -> None:
    """Insert one row into automation_run_history; retries transient DB errors, then pending_db_writes.

    ``pool`` is ``worker`` | ``ui`` | ``health``. When omitted, ``health_check`` uses the **health** pool
    so history writes succeed when the worker pool is saturated.
    """
    if pool is None:
        pool = "health" if phase_name == "health_check" else "worker"

    sleeps_before_attempt = (0.0, 0.15, 0.5, 1.0)
    last_err: Exception | None = None

    for attempt in range(len(sleeps_before_attempt)):
        if sleeps_before_attempt[attempt]:
            time.sleep(sleeps_before_attempt[attempt])
        try:
            from shared.database.connection import (
                get_db_connection,
                get_health_db_connection,
                get_ui_db_connection,
            )

            if pool == "health":
                conn = get_health_db_connection()
            elif pool == "ui":
                conn = get_ui_db_connection()
            else:
                conn = get_db_connection()
            if not conn:
                raise RuntimeError("no_db_connection")
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO automation_run_history (phase_name, started_at, finished_at, success, error_message)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (phase_name, started_at, finished_at, success, error_message),
                    )
                conn.commit()
                return
            finally:
                conn.close()
        except Exception as e:
            last_err = e
            if _RETRYABLE_TYPES and isinstance(e, _RETRYABLE_TYPES):
                logger.warning(
                    "persist automation_run_history transient failure (attempt %s/%s): %s",
                    attempt + 1,
                    len(sleeps_before_attempt),
                    e,
                )
                continue
            break

    if last_err is not None:
        logger.warning("persist automation_run_history failed (runs not recorded): %s", last_err)
    try:
        from shared.database.pending_db_writes import enqueue_automation_run_history

        enqueue_automation_run_history(
            phase_name,
            started_at.isoformat() if started_at else "",
            finished_at.isoformat() if finished_at else "",
            success,
            error_message,
        )
    except Exception as qe:
        logger.warning("pending_db_writes enqueue also failed: %s", qe)
