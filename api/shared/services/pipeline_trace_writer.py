"""
Write pipeline_traces + pipeline_checkpoints (same schema as Monitoring \"Trigger pipeline\").
Used by system_monitoring routes and OrchestratorCoordinator RSS runs.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from shared.database.connection import get_ui_db_connection

logger = logging.getLogger(__name__)


def log_pipeline_trace(
    trace_id: str,
    stage: str,
    status: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Log pipeline trace to database. Uses pipeline_traces + pipeline_checkpoints schema."""
    try:
        conn = get_ui_db_connection()
        if not conn:
            return

        metadata = metadata or {}
        checkpoint_status = "failed" if status == "error" else status
        error_msg = str(metadata.get("error", "")) if status == "error" else None
        perf_json = json.dumps(metadata)

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO pipeline_traces (trace_id, start_time)
                    VALUES (%s, NOW())
                    ON CONFLICT (trace_id) DO NOTHING
                """,
                    (trace_id,),
                )

                checkpoint_id = f"{trace_id}_{stage}_{uuid.uuid4().hex[:12]}"
                cur.execute(
                    """
                    INSERT INTO pipeline_checkpoints (checkpoint_id, trace_id, stage, status, timestamp, error_message, metadata)
                    VALUES (%s, %s, %s, %s, NOW(), %s, %s::jsonb)
                """,
                    (checkpoint_id, trace_id, stage, checkpoint_status, error_msg, perf_json),
                )

                if status in ("completed", "error"):
                    cur.execute(
                        """
                        UPDATE pipeline_traces
                        SET end_time = NOW(),
                            success = (%s = 'completed'),
                            error_stage = CASE WHEN %s = 'error' THEN %s ELSE NULL END,
                            performance_metrics = COALESCE(performance_metrics, '{}'::jsonb) || %s::jsonb
                        WHERE trace_id = %s
                    """,
                        (status, status, stage, perf_json, trace_id),
                    )
                conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.error("Error logging pipeline trace: %s", e)
