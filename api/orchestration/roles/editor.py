"""
Editor role for Newsroom Orchestrator v6.

Quality scoring, narrative synthesis, publishing decisions.
Phase 2: apply quality threshold, trigger narrative update.
"""

import logging
from typing import Any

from orchestration.events.envelope import EventEnvelope
from orchestration.events.types import EventType

logger = logging.getLogger("orchestration")


def handle_article_ingested(envelope: EventEnvelope, orchestrator: Any = None) -> None:
    """Optional: check quality threshold, filter low-quality."""
    payload = envelope.payload or {}
    logger.debug("Editor: article_ingested domain=%s article_id=%s", payload.get("domain_key"), payload.get("article_id"))


def handle_breaking_news(envelope: EventEnvelope, orchestrator: Any = None) -> None:
    """Prioritize breaking news for dashboard/alert."""
    logger.info("Editor: breaking_news %s", envelope.payload)
