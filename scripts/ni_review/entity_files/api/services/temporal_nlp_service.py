"""
Temporal NLP Service for Chronological Event Extraction
Handles recognition and parsing of temporal expressions in article content
"""

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TemporalExpression:
    """Represents a temporal expression found in text"""

    raw_expression: str
    normalized_date: date | None
    expression_type: str  # 'relative', 'absolute', 'duration', 'period'
    confidence: float
    context_sentence: str
    character_start: int
    character_end: int
    parsed_components: dict[str, Any]


@dataclass
class ChronologicalEvent:
    """Represents a chronological event extracted from text"""

    title: str
    description: str
    actual_event_date: date | None
    relative_expression: str | None
    source_text: str
    source_paragraph: int
    source_sentence_start: int
    source_sentence_end: int
    confidence: float
    event_type: str
    importance_score: float
    entities: list[str]
    historical_context: str | None


class TemporalNLPService:
    """Service for extracting temporal expressions and chronological events from text"""

    def __init__(self):
        self.temporal_patterns = self._compile_temporal_patterns()
        self.historical_reference_patterns = self._compile_historical_patterns()
        self.event_indicators = self._compile_event_indicators()

    def _compile_temporal_patterns(self) -> dict[str, re.Pattern]:
        """Compile regex patterns for temporal expression recognition"""
        patterns = {
            # Relative time expressions
            "yesterday": re.compile(r"\b(yesterday)\b", re.IGNORECASE),
            "today": re.compile(r"\b(today)\b", re.IGNORECASE),
            "tomorrow": re.compile(r"\b(tomorrow)\b", re.IGNORECASE),
            "last_week": re.compile(r"\b(last\s+week)\b", re.IGNORECASE),
            "this_week": re.compile(r"\b(this\s+week)\b", re.IGNORECASE),
            "next_week": re.compile(r"\b(next\s+week)\b", re.IGNORECASE),
            "last_month": re.compile(r"\b(last\s+month)\b", re.IGNORECASE),
            "this_month": re.compile(r"\b(this\s+month)\b", re.IGNORECASE),
            "next_month": re.compile(r"\b(next\s+month)\b", re.IGNORECASE),
            "last_year": re.compile(r"\b(last\s+year)\b", re.IGNORECASE),
            "this_year": re.compile(r"\b(this\s+year)\b", re.IGNORECASE),
            "next_year": re.compile(r"\b(next\s+year)\b", re.IGNORECASE),
            # Numeric relative expressions
            "days_ago": re.compile(r"\b(\d+)\s+(days?)\s+ago\b", re.IGNORECASE),
            "weeks_ago": re.compile(r"\b(\d+)\s+(weeks?)\s+ago\b", re.IGNORECASE),
            "months_ago": re.compile(r"\b(\d+)\s+(months?)\s+ago\b", re.IGNORECASE),
            "years_ago": re.compile(r"\b(\d+)\s+(years?)\s+ago\b", re.IGNORECASE),
            "days_from_now": re.compile(r"\b(\d+)\s+(days?)\s+(from\s+now|hence)\b", re.IGNORECASE),
            "weeks_from_now": re.compile(
                r"\b(\d+)\s+(weeks?)\s+(from\s+now|hence)\b", re.IGNORECASE
            ),
            "months_from_now": re.compile(
                r"\b(\d+)\s+(months?)\s+(from\s+now|hence)\b", re.IGNORECASE
            ),
            "years_from_now": re.compile(
                r"\b(\d+)\s+(years?)\s+(from\s+now|hence)\b", re.IGNORECASE
            ),
            # Specific time periods
            "early_morning": re.compile(r"\b(early\s+morning)\b", re.IGNORECASE),
            "late_night": re.compile(r"\b(late\s+night)\b", re.IGNORECASE),
            "midday": re.compile(r"\b(midday|noon)\b", re.IGNORECASE),
            "evening": re.compile(r"\b(evening)\b", re.IGNORECASE),
            # Duration expressions
            "for_days": re.compile(r"\b(for\s+\d+\s+days?)\b", re.IGNORECASE),
            "for_weeks": re.compile(r"\b(for\s+\d+\s+weeks?)\b", re.IGNORECASE),
            "for_months": re.compile(r"\b(for\s+\d+\s+months?)\b", re.IGNORECASE),
            "for_years": re.compile(r"\b(for\s+\d+\s+years?)\b", re.IGNORECASE),
            # Absolute date patterns
            "month_day_year": re.compile(
                r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b",
                re.IGNORECASE,
            ),
            "day_month_year": re.compile(
                r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b",
                re.IGNORECASE,
            ),
            "year_month_day": re.compile(r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b"),
            "month_year": re.compile(
                r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b",
                re.IGNORECASE,
            ),
            # Time expressions
            "time_12h": re.compile(r"\b(\d{1,2}):(\d{2})\s*(AM|PM)\b", re.IGNORECASE),
            "time_24h": re.compile(r"\b(\d{1,2}):(\d{2})\b"),
        }
        return patterns

    def _compile_historical_patterns(self) -> dict[str, re.Pattern]:
        """Compile patterns for historical references"""
        patterns = {
            "previous_shutdown": re.compile(
                r"\b(previous|last)\s+(government\s+)?shutdown\b", re.IGNORECASE
            ),
            "last_time": re.compile(r"\b(last\s+time|previously|earlier)\b", re.IGNORECASE),
            "in_the_past": re.compile(
                r"\b(in\s+the\s+past|historically|traditionally)\b", re.IGNORECASE
            ),
            "years_ago_shutdown": re.compile(
                r"\b(\d{4})\s+(government\s+)?shutdown\b", re.IGNORECASE
            ),
            "administration_reference": re.compile(
                r"\b(previous|last|former)\s+administration\b", re.IGNORECASE
            ),
            "historical_event": re.compile(
                r"\b(in\s+\d{4}|during\s+\d{4}|back\s+in\s+\d{4})\b", re.IGNORECASE
            ),
        }
        return patterns

    def _compile_event_indicators(self) -> list[str]:
        """Compile indicators that suggest an event occurred"""
        return [
            "happened",
            "occurred",
            "took place",
            "began",
            "started",
            "ended",
            "concluded",
            "announced",
            "declared",
            "revealed",
            "disclosed",
            "reported",
            "confirmed",
            "launched",
            "initiated",
            "implemented",
            "enacted",
            "passed",
            "approved",
            "rejected",
            "denied",
            "blocked",
            "prevented",
            "stopped",
            "halted",
            "increased",
            "decreased",
            "rose",
            "fell",
            "grew",
            "declined",
            "won",
            "lost",
            "succeeded",
            "failed",
            "achieved",
            "accomplished",
        ]

    def extract_temporal_expressions(
        self, text: str, anchor_date: date = None
    ) -> list[TemporalExpression]:
        """Extract all temporal expressions from text"""
        if anchor_date is None:
            anchor_date = date.today()

        expressions = []

        # Split text into sentences for better context
        sentences = self._split_into_sentences(text)

        for sentence_idx, sentence in enumerate(sentences):
            sentence_expressions = self._extract_from_sentence(sentence, anchor_date, sentence_idx)
            expressions.extend(sentence_expressions)

        return expressions

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences"""
        # Simple sentence splitting - could be improved with more sophisticated NLP
        sentences = re.split(r"[.!?]+", text)
        return [s.strip() for s in sentences if s.strip()]

    def _extract_from_sentence(
        self, sentence: str, anchor_date: date, sentence_idx: int
    ) -> list[TemporalExpression]:
        """Extract temporal expressions from a single sentence"""
        expressions = []
        character_offset = 0

        for pattern_name, pattern in self.temporal_patterns.items():
            for match in pattern.finditer(sentence):
                raw_expression = match.group(0)
                character_start = match.start() + character_offset
                character_end = match.end() + character_offset

                # Parse the expression
                normalized_date, expression_type, confidence, components = (
                    self._parse_temporal_expression(raw_expression, pattern_name, anchor_date)
                )

                if normalized_date or expression_type != "unknown":
                    expression = TemporalExpression(
                        raw_expression=raw_expression,
                        normalized_date=normalized_date,
                        expression_type=expression_type,
                        confidence=confidence,
                        context_sentence=sentence,
                        character_start=character_start,
                        character_end=character_end,
                        parsed_components=components,
                    )
                    expressions.append(expression)

        return expressions

    def _parse_temporal_expression(
        self, expression: str, pattern_name: str, anchor_date: date
    ) -> tuple[date | None, str, float, dict[str, Any]]:
        """Parse a temporal expression and return normalized date and metadata"""
        expression = expression.lower().strip()
        components = {}
        confidence = 0.8

        if pattern_name in ["yesterday"]:
            normalized_date = anchor_date - timedelta(days=1)
            expression_type = "relative"
            components = {"direction": "past", "unit": "day", "amount": 1}

        elif pattern_name in ["today"]:
            normalized_date = anchor_date
            expression_type = "relative"
            components = {"direction": "present", "unit": "day", "amount": 0}

        elif pattern_name in ["tomorrow"]:
            normalized_date = anchor_date + timedelta(days=1)
            expression_type = "relative"
            components = {"direction": "future", "unit": "day", "amount": 1}

        elif pattern_name in ["last_week"]:
            normalized_date = anchor_date - timedelta(weeks=1)
            expression_type = "relative"
            components = {"direction": "past", "unit": "week", "amount": 1}

        elif pattern_name in ["this_week"]:
            # Start of current week
            days_since_monday = anchor_date.weekday()
            normalized_date = anchor_date - timedelta(days=days_since_monday)
            expression_type = "relative"
            components = {"direction": "present", "unit": "week", "amount": 0}

        elif pattern_name in ["next_week"]:
            normalized_date = anchor_date + timedelta(weeks=1)
            expression_type = "relative"
            components = {"direction": "future", "unit": "week", "amount": 1}

        elif pattern_name in ["last_month"]:
            # Approximate - could be more precise
            if anchor_date.month == 1:
                normalized_date = anchor_date.replace(year=anchor_date.year - 1, month=12)
            else:
                normalized_date = anchor_date.replace(month=anchor_date.month - 1)
            expression_type = "relative"
            components = {"direction": "past", "unit": "month", "amount": 1}

        elif pattern_name in ["last_year"]:
            normalized_date = anchor_date.replace(year=anchor_date.year - 1)
            expression_type = "relative"
            components = {"direction": "past", "unit": "year", "amount": 1}

        elif pattern_name in ["days_ago"]:
            match = re.search(r"(\d+)\s+days?\s+ago", expression)
            if match:
                days = int(match.group(1))
                normalized_date = anchor_date - timedelta(days=days)
                expression_type = "relative"
                components = {"direction": "past", "unit": "day", "amount": days}
            else:
                normalized_date = None
                expression_type = "unknown"
                confidence = 0.0

        elif pattern_name in ["weeks_ago"]:
            match = re.search(r"(\d+)\s+weeks?\s+ago", expression)
            if match:
                weeks = int(match.group(1))
                normalized_date = anchor_date - timedelta(weeks=weeks)
                expression_type = "relative"
                components = {"direction": "past", "unit": "week", "amount": weeks}
            else:
                normalized_date = None
                expression_type = "unknown"
                confidence = 0.0

        elif pattern_name in ["months_ago"]:
            match = re.search(r"(\d+)\s+months?\s+ago", expression)
            if match:
                months = int(match.group(1))
                # Approximate - could be more precise
                if anchor_date.month <= months:
                    normalized_date = anchor_date.replace(
                        year=anchor_date.year - 1, month=12 - (months - anchor_date.month)
                    )
                else:
                    normalized_date = anchor_date.replace(month=anchor_date.month - months)
                expression_type = "relative"
                components = {"direction": "past", "unit": "month", "amount": months}
            else:
                normalized_date = None
                expression_type = "unknown"
                confidence = 0.0

        elif pattern_name in ["years_ago"]:
            match = re.search(r"(\d+)\s+years?\s+ago", expression)
            if match:
                years = int(match.group(1))
                normalized_date = anchor_date.replace(year=anchor_date.year - years)
                expression_type = "relative"
                components = {"direction": "past", "unit": "year", "amount": years}
            else:
                normalized_date = None
                expression_type = "unknown"
                confidence = 0.0

        elif pattern_name in ["month_day_year"]:
            match = re.search(
                r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})",
                expression,
                re.IGNORECASE,
            )
            if match:
                month_name, day, year = match.groups()
                month_map = {
                    "january": 1,
                    "february": 2,
                    "march": 3,
                    "april": 4,
                    "may": 5,
                    "june": 6,
                    "july": 7,
                    "august": 8,
                    "september": 9,
                    "october": 10,
                    "november": 11,
                    "december": 12,
                }
                month = month_map[month_name.lower()]
                normalized_date = date(int(year), month, int(day))
                expression_type = "absolute"
                components = {"month": month, "day": int(day), "year": int(year)}
                confidence = 0.95
            else:
                normalized_date = None
                expression_type = "unknown"
                confidence = 0.0

        else:
            # Try to parse as absolute date
            try:
                normalized_date = datetime.strptime(expression, "%Y-%m-%d").date()
                expression_type = "absolute"
                components = {
                    "year": normalized_date.year,
                    "month": normalized_date.month,
                    "day": normalized_date.day,
                }
                confidence = 0.9
            except:
                normalized_date = None
                expression_type = "unknown"
                confidence = 0.0

        return normalized_date, expression_type, confidence, components

    def extract_chronological_events(
        self, text: str, article_title: str = "", source: str = ""
    ) -> list[ChronologicalEvent]:
        """Extract chronological events from text"""
        events = []

        # Extract temporal expressions first
        temporal_expressions = self.extract_temporal_expressions(text)

        # Split text into paragraphs and sentences
        paragraphs = text.split("\n\n")

        for para_idx, paragraph in enumerate(paragraphs):
            sentences = self._split_into_sentences(paragraph)

            for sent_idx, sentence in enumerate(sentences):
                # Check if sentence contains event indicators
                if self._contains_event_indicator(sentence):
                    # Find temporal expressions in this sentence
                    sentence_temporals = [
                        te for te in temporal_expressions if te.context_sentence == sentence
                    ]

                    if sentence_temporals:
                        # Extract event details
                        event = self._extract_event_from_sentence(
                            sentence,
                            sentence_temporals[0],
                            article_title,
                            source,
                            para_idx,
                            sent_idx,
                        )
                        if event:
                            events.append(event)

        return events

    def _contains_event_indicator(self, sentence: str) -> bool:
        """Check if sentence contains event indicators"""
        sentence_lower = sentence.lower()
        return any(indicator in sentence_lower for indicator in self.event_indicators)

    def _extract_event_from_sentence(
        self,
        sentence: str,
        temporal_expression: TemporalExpression,
        article_title: str,
        source: str,
        paragraph_idx: int,
        sentence_idx: int,
    ) -> ChronologicalEvent | None:
        """Extract event details from a sentence with temporal expression"""

        # Determine event type based on content
        event_type = self._classify_event_type(sentence)

        # Calculate importance score based on various factors
        importance_score = self._calculate_importance_score(sentence, temporal_expression)

        # Extract entities (simplified - could use more sophisticated NER)
        entities = self._extract_entities(sentence)

        # Look for historical context
        historical_context = self._extract_historical_context(sentence)

        # Create event title from sentence
        event_title = self._create_event_title(sentence, temporal_expression)

        # Create event description
        event_description = self._create_event_description(sentence, temporal_expression)

        return ChronologicalEvent(
            title=event_title,
            description=event_description,
            actual_event_date=temporal_expression.normalized_date,
            relative_expression=temporal_expression.raw_expression,
            source_text=sentence,
            source_paragraph=paragraph_idx,
            source_sentence_start=0,  # Would need character position calculation
            source_sentence_end=len(sentence),
            confidence=temporal_expression.confidence,
            event_type=event_type,
            importance_score=importance_score,
            entities=entities,
            historical_context=historical_context,
        )

    def _classify_event_type(self, sentence: str) -> str:
        """Classify the type of event based on sentence content"""
        sentence_lower = sentence.lower()

        if any(word in sentence_lower for word in ["shutdown", "shut down", "closure", "closed"]):
            return "government_action"
        elif any(
            word in sentence_lower for word in ["announced", "declared", "revealed", "disclosed"]
        ):
            return "announcement"
        elif any(
            word in sentence_lower for word in ["passed", "approved", "enacted", "legislation"]
        ):
            return "legislative"
        elif any(
            word in sentence_lower for word in ["meeting", "talks", "negotiations", "discussions"]
        ):
            return "diplomatic"
        elif any(word in sentence_lower for word in ["protest", "demonstration", "rally", "march"]):
            return "protest"
        elif any(word in sentence_lower for word in ["election", "vote", "voting", "ballot"]):
            return "electoral"
        else:
            return "general"

    def _calculate_importance_score(
        self, sentence: str, temporal_expression: TemporalExpression
    ) -> float:
        """Calculate importance score for an event"""
        score = 0.5  # Base score

        # Boost for high-confidence temporal expressions
        score += temporal_expression.confidence * 0.2

        # Boost for important keywords
        sentence_lower = sentence.lower()
        if any(
            word in sentence_lower
            for word in ["major", "significant", "important", "critical", "key"]
        ):
            score += 0.2
        if any(word in sentence_lower for word in ["crisis", "emergency", "urgent", "breaking"]):
            score += 0.3
        if any(word in sentence_lower for word in ["first", "only", "unprecedented", "historic"]):
            score += 0.2

        # Boost for specific event types
        if any(
            word in sentence_lower
            for word in ["shutdown", "government", "congress", "senate", "house"]
        ):
            score += 0.1

        return min(score, 1.0)

    def _extract_entities(self, sentence: str) -> list[str]:
        """Extract entities from sentence (simplified version)"""
        entities = []

        # Look for capitalized words that might be entities
        words = sentence.split()
        for word in words:
            if word[0].isupper() and len(word) > 2:
                # Clean up the word
                clean_word = re.sub(r"[^\w\s]", "", word)
                if clean_word and clean_word not in ["The", "This", "That", "These", "Those"]:
                    entities.append(clean_word)

        return entities[:5]  # Limit to 5 entities

    def _extract_historical_context(self, sentence: str) -> str | None:
        """Extract historical context references from sentence"""
        sentence.lower()

        for pattern_name, pattern in self.historical_patterns.items():
            if pattern.search(sentence):
                if pattern_name == "previous_shutdown":
                    return "References previous government shutdown"
                elif pattern_name == "years_ago_shutdown":
                    match = pattern.search(sentence)
                    if match:
                        year = match.group(1)
                        return f"References {year} government shutdown"
                elif pattern_name == "administration_reference":
                    return "References previous administration"
                elif pattern_name == "historical_event":
                    match = pattern.search(sentence)
                    if match:
                        year = match.group(1)
                        return f"References historical event from {year}"

        return None

    def _create_event_title(self, sentence: str, temporal_expression: TemporalExpression) -> str:
        """Create a concise event title from sentence"""
        # Take first part of sentence, clean it up
        words = sentence.split()[:10]  # First 10 words
        title = " ".join(words)

        # Remove common prefixes
        title = re.sub(r"^(The|A|An)\s+", "", title)

        # Capitalize first letter
        title = title[0].upper() + title[1:] if title else "Timeline Event"

        # Add temporal context if available
        if temporal_expression.raw_expression:
            title += f" ({temporal_expression.raw_expression})"

        return title

    def _create_event_description(
        self, sentence: str, temporal_expression: TemporalExpression
    ) -> str:
        """Create event description from sentence"""
        # Use the full sentence as description
        description = sentence.strip()

        # Add temporal context if not already present
        if temporal_expression.raw_expression not in description:
            description += f" (Occurred {temporal_expression.raw_expression})"

        return description


# Global instance
temporal_nlp_service = TemporalNLPService()
