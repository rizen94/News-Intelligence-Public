"""
Journalist role for Newsroom Orchestrator v6.

Pattern detection (simple rules), investigation state machine.
Emits INVESTIGATION_NEEDED when article entity count >= threshold; records investigations.
"""

import json
import logging
from typing import Any, Optional

from shared.database.connection import get_db_connection

from orchestration.events.envelope import EventEnvelope
from orchestration.events.types import EventType

logger = logging.getLogger("orchestration")

DOMAIN_SCHEMA = {"politics": "politics", "finance": "finance", "science-tech": "science_tech"}


def _schema_for_domain(domain_key: str) -> str:
    return DOMAIN_SCHEMA.get(domain_key, domain_key.replace("-", "_"))


def _get_entity_count_and_ids(conn, domain_key: str, article_id: int) -> tuple[int, list]:
    """Return (count, list of canonical_entity_id) for article. Empty list if table missing."""
    schema = _schema_for_domain(domain_key)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f'SELECT COUNT(*), COALESCE(array_agg(canonical_entity_id) FILTER (WHERE canonical_entity_id IS NOT NULL), ARRAY[]::integer[]) '
                f'FROM "{schema}".article_entities WHERE article_id = %s',
                (article_id,),
            )
            row = cur.fetchone()
        if row:
            count = row[0] or 0
            ids = list(row[1]) if row[1] else []
            return (count, ids)
    except Exception as e:
        logger.debug("Journalist entity count %s/%s: %s", domain_key, article_id, e)
    return (0, [])


def _investigation_trigger_threshold(config: dict) -> int:
    j = config.get("journalist") or {}
    triggers = j.get("investigation_triggers") or {}
    return int(triggers.get("multiple_entity_mentions", 3))


def handle_article_ingested(envelope: EventEnvelope, orchestrator: Any = None) -> None:
    """Detect patterns (e.g. multiple entities); if above threshold emit INVESTIGATION_NEEDED."""
    payload = envelope.payload or {}
    domain_key = payload.get("domain_key")
    article_id = payload.get("article_id")
    logger.debug("Journalist: article_ingested domain=%s article_id=%s", domain_key, article_id)

    if not domain_key or article_id is None or orchestrator is None:
        return

    conn = get_db_connection()
    if not conn:
        return
    try:
        count, entity_ids = _get_entity_count_and_ids(conn, domain_key, int(article_id))
        config = getattr(orchestrator, "config", None) or {}
        threshold = _investigation_trigger_threshold(config)
        if count >= threshold:
            inv_payload = {
                "domain_key": domain_key,
                "article_id": article_id,
                "entity_ids": entity_ids[:100],
                "pattern_confidence": 0.8,
                "trigger": "multiple_entity_mentions",
                "entity_count": count,
            }
            orchestrator.emit(
                EventEnvelope(
                    event_type=EventType.INVESTIGATION_NEEDED,
                    payload=inv_payload,
                    priority=2,
                    domain=domain_key,
                    deduplication_key=f"inv:{domain_key}:{article_id}",
                )
            )
            logger.info("Journalist: emitted INVESTIGATION_NEEDED domain=%s article_id=%s entities=%s", domain_key, article_id, count)
    finally:
        conn.close()


def handle_pattern_detected(envelope: EventEnvelope, orchestrator: Any = None) -> None:
    """Process PATTERN_DETECTED: record or escalate."""
    logger.info("Journalist: pattern_detected %s", envelope.payload)


def handle_investigation_needed(envelope: EventEnvelope, orchestrator: Any = None) -> None:
    """Process INVESTIGATION_NEEDED: insert into orchestration.investigations."""
    payload = envelope.payload or {}
    domain_key = payload.get("domain_key")
    entity_ids = payload.get("entity_ids") or []
    pattern_confidence = payload.get("pattern_confidence")
    if not domain_key:
        logger.debug("Journalist: investigation_needed missing domain_key")
        return

    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO orchestration.investigations
                (trigger_event_id, status, domain_key, entity_ids, pattern_confidence, notes, updated_at)
                VALUES (NULL, 'open', %s, %s, %s, %s, NOW())
                """,
                (
                    domain_key,
                    entity_ids if isinstance(entity_ids, list) else [],
                    float(pattern_confidence) if pattern_confidence is not None else None,
                    json.dumps({"article_id": payload.get("article_id"), "trigger": payload.get("trigger", "investigation_needed")}),
                ),
            )
        conn.commit()
        logger.info("Journalist: created investigation domain=%s", domain_key)
    except Exception as e:
        logger.warning("Journalist: insert investigation failed: %s", e)
        conn.rollback()
    finally:
        conn.close()
