"""
Journalist role for Newsroom Orchestrator v6.

Pattern detection (simple rules), investigation state machine.
Phase 2: emit PATTERN_DETECTED, INVESTIGATION_NEEDED; record investigations.
"""

import logging
from typing import Any

from orchestration.events.envelope import EventEnvelope
from orchestration.events.types import EventType

logger = logging.getLogger("orchestration")


def handle_article_ingested(envelope: EventEnvelope) -> None:
    """Optional: detect patterns (e.g. multiple entities) and emit INVESTIGATION_NEEDED."""
    payload = envelope.payload or {}
    domain_key = payload.get("domain_key")
    article_id = payload.get("article_id")
    logger.debug("Journalist: article_ingested domain=%s article_id=%s", domain_key, article_id)
    # Phase 2: query entity count, if >= threshold emit INVESTIGATION_NEEDED (via orchestrator.emit)
    # For now no-op; orchestrator does not pass self to handlers, so we cannot emit from here.
    # Handlers that need to emit can be wired with orchestrator reference or a callback.


def handle_pattern_detected(envelope: EventEnvelope) -> None:
    """Process PATTERN_DETECTED: record or escalate."""
    logger.info("Journalist: pattern_detected %s", envelope.payload)


def handle_investigation_needed(envelope: EventEnvelope) -> None:
    """Process INVESTIGATION_NEEDED: create investigation row, update state machine."""
    logger.info("Journalist: investigation_needed %s", envelope.payload)
