"""
Shared Extraction Service — News Intelligence

Unified entry point for all AI-powered content extraction:
- Entity extraction (people, organizations, subjects, recurring events, dates, etc.)
- Event extraction (chronicle events with entities, timeframe, description)
- Sentiment analysis
- Quality scoring

This service consolidates extraction logic from multiple sources:
- ai_processing_service.py (deprecated shim)
- orchestrator_coordinator.py (inline extraction)
- Various pipeline phases

Benefits:
- Single entry point for all extraction operations
- Consistent return types via dataclasses
- Easy to test (mock the service, not multiple implementations)
- Extensible (add new extraction types without touching callers)

See docs/CODING_STYLE_GUIDE.md for API patterns.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class EntityExtractionResult:
    """
    Structured entity extraction result.
    
    Contains all entity types extracted from content:
    - people: Person entities with mentions and canonical IDs
    - organizations: Organization entities
    - subjects: Subject/topic entities
    - recurring_events: Recurring event entities (e.g., "earnings season")
    - dates: Date mentions
    - times: Time mentions
    - countries: Country entities
    - keywords: Extracted keywords
    """
    people: list[dict[str, Any]] = field(default_factory=list)
    organizations: list[dict[str, Any]] = field(default_factory=list)
    subjects: list[dict[str, Any]] = field(default_factory=list)
    recurring_events: list[dict[str, Any]] = field(default_factory=list)
    dates: list[dict[str, Any]] = field(default_factory=list)
    times: list[dict[str, Any]] = field(default_factory=list)
    countries: list[dict[str, Any]] = field(default_factory=list)
    keywords: list[dict[str, Any]] = field(default_factory=list)
    success: bool = True
    error: str | None = None


@dataclass
class EventExtractionResult:
    """
    Event extraction result.
    
    Contains chronicle events extracted from content:
    - events: List of event dicts with description, timeframe, entities, source
    """
    events: list[dict[str, Any]] = field(default_factory=list)
    success: bool = True
    error: str | None = None


@dataclass
class SentimentResult:
    """
    Sentiment analysis result.
    
    - score: Float 0.0–1.0 (0.5 = neutral, <0.5 negative, >0.5 positive)
    - label: String "positive", "negative", or "neutral"
    - confidence: Float 0.0–1.0
    """
    score: float = 0.5
    label: str = "neutral"
    confidence: float = 0.5
    success: bool = True
    error: str | None = None


@dataclass
class QualityResult:
    """
    Article quality score.
    
    - score: Float 0.0–1.0
    - factors: Dict of contributing factors (readability, depth, source_credibility, etc.)
    """
    score: float = 0.5
    factors: dict[str, float] = field(default_factory=dict)
    success: bool = True
    error: str | None = None


class SharedExtractionService:
    """
    Unified extraction service for all AI-powered content analysis.
    
    Centralizes:
    - Entity extraction (delegates to article_entity_extraction_service)
    - Event extraction (delegates to event_extraction_service)
    - Sentiment analysis (uses LLMService directly)
    - Quality scoring (uses content_quality_service)
    
    Provides a clean interface for orchestrator_coordinator.py and
    all pipeline phases.
    
    Example usage:
        extraction = SharedExtractionService()
        entities = await extraction.extract_entities(content, title)
        sentiment = await extraction.analyze_sentiment(content, title)
        quality = await extraction.score_quality(content, title)
        events = await extraction.extract_events(content, title, article_id=123)
    """

    def __init__(self):
        """Initialize extraction service with dependency injection."""
        # LLM service for direct model calls
        from shared.services.llm_service import LLMService
        self._llm = LLMService()
        
        # Entity extraction service
        from services.article_entity_extraction_service import (
            get_article_entity_extraction_service
        )
        self._entity_service = get_article_entity_extraction_service()
        
        # Event extraction service
        from services.event_extraction_service import EventExtractionService
        self._event_service = EventExtractionService()
        
        # Quality scoring service
        from services.content_quality_service import ContentQualityService
        self._quality_service = ContentQualityService()
    
    # =========================================================================
    # Entity Extraction
    # =========================================================================
    
    async def extract_entities(
        self,
        content: str,
        title: str = "",
        article_id: int | None = None,
        schema: str = "politics"
    ) -> EntityExtractionResult:
        """
        Extract structured entities from content.
        
        Extracts people, organizations, subjects, recurring events, dates,
        times, countries, and keywords from article content.
        
        Args:
            content: Article text content
            title: Article title (optional, improves extraction)
            article_id: Optional article ID for storing entities to DB
            schema: Database schema name (default: "politics")
        
        Returns:
            EntityExtractionResult with all extracted entity types.
        
        Example:
            result = await extraction.extract_entities(content, title)
            for person in result.people:
                print(person["name"], person["canonical_entity_id"])
        """
        try:
            # Delegate to the entity extraction service
            result = await self._entity_service.extract_entities_from_text(
                text=content,
                title=title,
                article_id=article_id,
                schema=schema
            )
            
            if not result or not isinstance(result, dict):
                return EntityExtractionResult(success=False, error="Invalid extraction result")
            
            return EntityExtractionResult(
                people=result.get("people", []),
                organizations=result.get("organizations", []),
                subjects=result.get("subjects", []),
                recurring_events=result.get("recurring_events", []),
                dates=result.get("dates", []),
                times=result.get("times", []),
                countries=result.get("countries", []),
                keywords=result.get("keywords", []),
                success=True
            )
            
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return EntityExtractionResult(success=False, error=str(e))
    
    # =========================================================================
    # Event Extraction
    # =========================================================================
    
    async def extract_events(
        self,
        content: str,
        title: str = "",
        article_id: int | None = None,
        schema: str = "politics"
    ) -> EventExtractionResult:
        """
        Extract chronicle events from content.
        
        Extracts events with description, timeframe, entities, and source
        attribution for chronological tracking.
        
        Args:
            content: Article text content
            title: Article title (optional)
            article_id: Optional article ID for storing events to DB
            schema: Database schema name (default: "politics")
        
        Returns:
            EventExtractionResult with list of extracted events.
        
        Example:
            result = await extraction.extract_events(content, title, article_id=123)
            for event in result.events:
                print(event["description"], event["timeframe"])
        """
        try:
            # Delegate to event extraction service
            result = await self._event_service.extract_events_from_article(
                article_id=article_id,
                content=content,
                title=title,
                schema=schema
            )
            
            if not result or not isinstance(result, dict):
                return EventExtractionResult(success=False, error="Invalid extraction result")
            
            return EventExtractionResult(
                events=result.get("events", []),
                success=result.get("success", True),
                error=result.get("error")
            )
            
        except Exception as e:
            logger.error(f"Event extraction failed: {e}")
            return EventExtractionResult(success=False, error=str(e))
    
    # =========================================================================
    # Sentiment Analysis
    # =========================================================================
    
    async def analyze_sentiment(
        self,
        content: str,
        title: str = ""
    ) -> SentimentResult:
        """
        Analyze sentiment of content.
        
        Returns sentiment score (0.0–1.0), label ("positive"/"negative"/"neutral"),
        and confidence (0.0–1.0).
        
        Args:
            content: Article text content
            title: Article title (optional, improves analysis)
        
        Returns:
            SentimentResult with score, label, and confidence.
        
        Example:
            result = await extraction.analyze_sentiment(content, title)
            if result.score > 0.6:
                print("Positive sentiment!")
            elif result.score < 0.4:
                print("Negative sentiment!")
        """
        try:
            # Use LLM service directly for sentiment analysis
            sentiment_data = await self._llm.analyze_sentiment(content, title or "")
            
            if not sentiment_data or not isinstance(sentiment_data, dict):
                return SentimentResult(success=False, error="Invalid sentiment result")
            
            score = sentiment_data.get("score", 0.5)
            
            # Determine label based on score
            if score >= 0.6:
                label = "positive"
            elif score <= 0.4:
                label = "negative"
            else:
                label = "neutral"
            
            return SentimentResult(
                score=score,
                label=label,
                confidence=sentiment_data.get("confidence", 0.5),
                success=True
            )
            
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return SentimentResult(success=False, error=str(e))
    
    # =========================================================================
    # Quality Scoring
    # =========================================================================
    
    async def score_quality(
        self,
        content: str,
        title: str = "",
        source_credibility_tier: int = 2,
        article_id: int | None = None
    ) -> QualityResult:
        """
        Score article quality.
        
        Computes quality score based on content analysis, readability, depth,
        and source credibility tier.
        
        Args:
            content: Article text content
            title: Article title (optional)
            source_credibility_tier: Source tier (1=high, 2=medium, 3=low)
            article_id: Optional article ID for full quality analysis
        
        Returns:
            QualityResult with score and contributing factors.
        
        Example:
            result = await extraction.score_quality(content, title, tier=1)
            print(f"Quality: {result.score:.2f}")
            print(f"Factors: {result.factors}")
        """
        try:
            # Use content quality service
            quality_data = await self._quality_service.score_article_quality(
                content=content,
                title=title,
                source_credibility_tier=source_credibility_tier,
                article_id=article_id
            )
            
            if not quality_data or not isinstance(quality_data, dict):
                return QualityResult(success=False, error="Invalid quality result")
            
            return QualityResult(
                score=quality_data.get("score", 0.5),
                factors=quality_data.get("factors", {}),
                success=quality_data.get("success", True),
                error=quality_data.get("error")
            )
            
        except Exception as e:
            logger.error(f"Quality scoring failed: {e}")
            return QualityResult(success=False, error=str(e))
    
    # =========================================================================
    # Batch Operations
    # =========================================================================
    
    async def extract_all(
        self,
        content: str,
        title: str = "",
        article_id: int | None = None,
        schema: str = "politics",
        source_credibility_tier: int = 2
    ) -> dict[str, Any]:
        """
        Extract all entity types, events, sentiment, and quality in one call.
        
        Runs all extraction operations in parallel for efficiency.
        
        Args:
            content: Article text content
            title: Article title (optional)
            article_id: Optional article ID for storing to DB
            schema: Database schema name (default: "politics")
            source_credibility_tier: Source tier for quality scoring
        
        Returns:
            Dict with keys: entities, events, sentiment, quality
        """
        try:
            # Run all extractions in parallel
            entities_task = self.extract_entities(content, title, article_id, schema)
            events_task = self.extract_events(content, title, article_id, schema)
            sentiment_task = self.analyze_sentiment(content, title)
            quality_task = self.score_quality(content, title, source_credibility_tier, article_id)
            
            entities, events, sentiment, quality = await asyncio.gather(
                entities_task, events_task, sentiment_task, quality_task
            )
            
            return {
                "entities": entities,
                "events": events,
                "sentiment": sentiment,
                "quality": quality
            }
            
        except Exception as e:
            logger.error(f"Batch extraction failed: {e}")
            return {
                "entities": EntityExtractionResult(success=False, error=str(e)),
                "events": EventExtractionResult(success=False, error=str(e)),
                "sentiment": SentimentResult(success=False, error=str(e)),
                "quality": QualityResult(success=False, error=str(e))
            }


# Singleton instance for convenience
_extraction_service_instance: SharedExtractionService | None = None


def get_shared_extraction_service() -> SharedExtractionService:
    """Get or create the shared extraction service singleton."""
    global _extraction_service_instance
    if _extraction_service_instance is None:
        _extraction_service_instance = SharedExtractionService()
    return _extraction_service_instance