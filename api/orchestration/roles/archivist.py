"""
Archivist role for Newsroom Orchestrator v6. Phase 3.

Historical pattern matching, knowledge graph, semantic search enhancement.

Stub: no-op for now; handlers log and return without side effects.
"""

import logging
from orchestration.events.envelope import EventEnvelope

logger = logging.getLogger("orchestration")


def handle_article_ingested(envelope: EventEnvelope) -> None:
    """Stub: historical context, reference linking. No-op; logs only."""
    logger.debug("Archivist: article_ingested (stub) %s", envelope.payload)
