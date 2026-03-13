"""
Event types for Newsroom Orchestrator v6.

Event-driven message bus: BREAKING_NEWS, PATTERN_DETECTED, INVESTIGATION_NEEDED, etc.
"""

from enum import Enum


class EventType(str, Enum):
    """Event types for the newsroom message bus."""

    # Ingestion
    ARTICLE_INGESTED = "article_ingested"
    BREAKING_NEWS = "breaking_news"
    SOURCE_FETCH_FAILED = "source_fetch_failed"

    # Analysis
    ARTICLE_ANALYZED = "article_analyzed"
    ENTITIES_EXTRACTED = "entities_extracted"
    TOPICS_ASSIGNED = "topics_assigned"

    # Investigation
    PATTERN_DETECTED = "pattern_detected"
    INVESTIGATION_NEEDED = "investigation_needed"
    INVESTIGATION_COMPLETED = "investigation_completed"

    # Synthesis & Publishing
    STORYLINE_UPDATED = "storyline_updated"
    NARRATIVE_SYNTHESIZED = "narrative_synthesized"
    DASHBOARD_UPDATED = "dashboard_updated"

    # System
    TASK_QUEUED = "task_queued"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
