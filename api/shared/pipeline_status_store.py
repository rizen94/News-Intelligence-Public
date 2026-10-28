"""Narrow pipeline_status table helpers (v10.1 interim eligibility store)."""

from __future__ import annotations

import logging
from typing import Any

from config.runtime import env_bool

logger = logging.getLogger(__name__)


def pipeline_status_enabled() -> bool:
    return env_bool("PIPELINE_STATUS_TABLE_ENABLED", True)


def upsert_pipeline_status(
    schema_name: str,
    article_id: int,
    phase_name: str,
    *,
    outcome: str | None = None,
    terminal_state: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    if not pipeline_status_enabled():
        return
    try:
        from shared.database.connection import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO intelligence.pipeline_status (
                        schema_name, article_id, phase_name, outcome, terminal_state, metadata, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, NOW())
                    ON CONFLICT (schema_name, article_id, phase_name)
                    DO UPDATE SET
                        outcome = EXCLUDED.outcome,
                        terminal_state = EXCLUDED.terminal_state,
                        metadata = intelligence.pipeline_status.metadata || EXCLUDED.metadata,
                        updated_at = NOW()
                    """,
                    (
                        schema_name,
                        article_id,
                        phase_name,
                        outcome,
                        terminal_state,
                        __import__("json").dumps(metadata or {}),
                    ),
                )
            conn.commit()
    except Exception as exc:
        logger.debug("upsert_pipeline_status %s/%s %s: %s", schema_name, article_id, phase_name, exc)


def sql_article_phase_pending_from_status(phase_name: str, article_alias: str = "a", schema_name: str = "") -> str:
    """Anti-join fragment: article lacks cleared pipeline_status row for phase."""
    if not pipeline_status_enabled():
        return "TRUE"
    return f"""NOT EXISTS (
        SELECT 1 FROM intelligence.pipeline_status ps
        WHERE ps.schema_name = '{schema_name}'
          AND ps.article_id = {article_alias}.id
          AND ps.phase_name = '{phase_name}'
          AND ps.terminal_state IN ('processed_with_output', 'processed_empty_legitimate')
    )"""
