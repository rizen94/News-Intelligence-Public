"""
Chief Editor role for Newsroom Orchestrator v6.

Resource optimization, strategic planning, adaptive learning.
Handles BREAKING_NEWS: records last breaking-news time in processing_state for priority/coordination.
"""

import json
import logging
from typing import Any

from shared.database.connection import get_db_connection

from orchestration.events.envelope import EventEnvelope

logger = logging.getLogger("orchestration")


def handle_breaking_news(envelope: EventEnvelope, orchestrator: Any = None) -> None:
    """Record breaking news in processing_state for priority and cross-domain coordination."""
    payload = envelope.payload or {}
    domain_key = payload.get("domain_key")
    article_id = payload.get("article_id")
    logger.debug("Chief Editor: breaking_news domain=%s article_id=%s", domain_key, article_id)

    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO orchestration.processing_state (key, value, updated_at)
                VALUES ('chief_editor:last_breaking_news', %s::jsonb, NOW())
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                """,
                (json.dumps({"domain_key": domain_key, "article_id": article_id, "event_id": envelope.event_id}),),
            )
        conn.commit()
    except Exception as e:
        logger.debug("Chief Editor: processing_state write failed: %s", e)
        conn.rollback()
    finally:
        conn.close()
