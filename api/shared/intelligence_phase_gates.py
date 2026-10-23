"""Skip automation phases when target intelligence tables are empty (no writers / no data)."""

from __future__ import annotations

import logging

from config.runtime import env_bool
from shared.database.connection import get_db_connection_context

logger = logging.getLogger(__name__)

_TABLE_CACHE: dict[tuple[str, str], int | None] = {}


def _table_row_estimate(schema: str, table: str) -> int:
    key = (schema, table)
    if key in _TABLE_CACHE:
        return int(_TABLE_CACHE[key] or 0)
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '3s'")
                cur.execute(
                    """
                    SELECT COALESCE(c.reltuples, 0)::bigint
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = %s AND c.relname = %s
                    """,
                    (schema, table),
                )
                row = cur.fetchone()
                est = int(row[0] or 0) if row else 0
    except Exception as e:
        logger.debug("table_row_estimate %s.%s: %s", schema, table, e)
        est = 0
    _TABLE_CACHE[key] = est
    return est


def invalidate_intelligence_phase_gate_cache() -> None:
    _TABLE_CACHE.clear()


def should_skip_automation_phase(phase: str) -> bool:
    """Return True when the phase should not run (empty unwired targets)."""
    try:
        from config.feature_registry import feature_lifecycle, is_feature_enabled

        lc = feature_lifecycle(phase)
        if lc in ("under_developed", "archived", "deprecated"):
            return not is_feature_enabled(phase)
        if lc == "staged" and not is_feature_enabled(phase):
            return True
    except Exception:
        pass
    if phase == "arc_report_generation" or phase == "longitudinal_matview_refresh":
        if _table_row_estimate("intelligence", "arc_definitions") < 1:
            return True
    if phase == "embeddings_worker":
        if not env_bool("EMBEDDINGS_WORKER_FORCE_BACKFILL", False):
            if _table_row_estimate("intelligence", "embedding_chunks") < 1:
                return True
    return False
