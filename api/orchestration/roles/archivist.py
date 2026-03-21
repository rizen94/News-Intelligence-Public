"""
Archivist role for Newsroom Orchestrator v6.

Historical pattern matching, knowledge graph, semantic search enhancement.
On ARTICLE_INGESTED records recent article hint in processing_state for historical context.
"""

import json
import logging
from typing import Any

from shared.database.connection import get_db_connection

from orchestration.events.envelope import EventEnvelope

logger = logging.getLogger("orchestration")


def handle_article_ingested(envelope: EventEnvelope, orchestrator: Any = None) -> None:
    """Record recent article in processing_state for historical context and reference linking."""
    payload = envelope.payload or {}
    domain_key = payload.get("domain_key")
    article_id = payload.get("article_id")
    logger.debug("Archivist: article_ingested domain=%s article_id=%s", domain_key, article_id)

    conn = get_db_connection()
    if not conn:
        return
    try:
        from datetime import datetime, timezone

        ts = datetime.now(timezone.utc).isoformat()
        value = json.dumps({"domain_key": domain_key, "article_id": article_id, "at": ts})
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO orchestration.processing_state (key, value, updated_at)
                VALUES ('archivist:last_article', %s::jsonb, NOW())
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                """,
                (value,),
            )
        conn.commit()
    except Exception as e:
        logger.debug("Archivist: processing_state write failed: %s", e)
        conn.rollback()
    finally:
        conn.close()
