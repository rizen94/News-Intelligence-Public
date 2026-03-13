"""
Cross-domain linking for Newsroom Orchestrator v6.

Shared entity detection, temporal correlation. Phase 2.
"""

import logging
from typing import Any, Callable, Optional

from orchestration.events.envelope import EventEnvelope
from orchestration.events.types import EventType

logger = logging.getLogger("orchestration")


def handle_article_ingested(
    envelope: EventEnvelope,
    get_db_connection: Optional[Callable] = None,
) -> None:
    """
    Optionally check if entity appears in another domain; record cross_domain_links.
    Phase 2: name-normalized entity matching across domains.
    """
    payload = envelope.payload or {}
    domain_key = payload.get("domain_key")
    article_id = payload.get("article_id")
    logger.debug("Cross-domain: article_ingested domain=%s article_id=%s", domain_key, article_id)
