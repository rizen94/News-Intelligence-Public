"""
Register default event handlers for Newsroom Orchestrator v6.

Single place to wire roles to event types; avoids duplication in main.
"""

from typing import Any

from orchestration.events.types import EventType
from orchestration.roles import editor, journalist


def register_default_handlers(orchestrator: Any) -> None:
    """Register handlers for ARTICLE_INGESTED, BREAKING_NEWS, etc."""
    orchestrator.register_handler(EventType.ARTICLE_INGESTED, editor.handle_article_ingested)
    orchestrator.register_handler(EventType.BREAKING_NEWS, editor.handle_breaking_news)
    orchestrator.register_handler(EventType.PATTERN_DETECTED, journalist.handle_pattern_detected)
    orchestrator.register_handler(EventType.INVESTIGATION_NEEDED, journalist.handle_investigation_needed)
