"""
Persist automation phase runs to public.automation_run_history (survives API restart).
Used by AutomationManager, optional cron heartbeat, and monitoring.
"""

from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def persist_automation_run_history(
    phase_name: str,
    started_at: datetime,
    finished_at: datetime,
    success: bool,
    error_message: str | None = None,
) -> None:
    """Insert one row into automation_run_history; falls back to pending_db_writes on failure."""
    try:
        from shared.database.connection import get_db_connection

        conn = get_db_connection()
        if not conn:
            return
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
        finally:
            conn.close()
    except Exception as e:
        logger.warning("persist automation_run_history failed (runs not recorded): %s", e)
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
