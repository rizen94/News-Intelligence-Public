"""
PDF / document ingest metrics for monitoring (`intelligence.processed_documents`).

Aligns with `backlog_metrics._count_document_processing_backlog` for pending rows.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


def get_document_pipeline_metrics() -> dict[str, Any]:
    """
    Snapshot: pending extraction, recently completed extractions, permanent failures.

    Safe on error (returns zeros + error string).
    """
    out: dict[str, Any] = {
        "pending_extraction": 0,
        "extracted_last_24h": 0,
        "permanent_failed_total": 0,
        "error": None,
    }
    try:
        from shared.database.connection import get_db_connection

        conn = get_db_connection()
        if not conn:
            out["error"] = "no_db_connection"
            return out
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        try:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '5s'")
                cur.execute(
                    """
                    SELECT COUNT(*) FROM intelligence.processed_documents
                    WHERE source_url IS NOT NULL AND source_url != ''
                      AND (extracted_sections IS NULL OR extracted_sections = '[]'::jsonb)
                      AND (metadata IS NULL OR (metadata->'processing'->>'permanent_failure') IS DISTINCT FROM 'true')
                    """
                )
                out["pending_extraction"] = int(cur.fetchone()[0] or 0)
                cur.execute(
                    """
                    SELECT COUNT(*) FROM intelligence.processed_documents
                    WHERE extracted_sections IS NOT NULL
                      AND extracted_sections != '[]'::jsonb
                      AND updated_at >= %s
                    """,
                    (since,),
                )
                out["extracted_last_24h"] = int(cur.fetchone()[0] or 0)
                cur.execute(
                    """
                    SELECT COUNT(*) FROM intelligence.processed_documents
                    WHERE (metadata->'processing'->>'permanent_failure') = 'true'
                    """
                )
                out["permanent_failed_total"] = int(cur.fetchone()[0] or 0)
        finally:
            conn.close()
    except Exception as e:
        logger.debug("get_document_pipeline_metrics: %s", e)
        out["error"] = str(e)[:200]
    return out
