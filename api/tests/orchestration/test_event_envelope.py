"""Unit tests for event envelope and EventType."""

import pytest
from orchestration.events.types import EventType
from orchestration.events.envelope import EventEnvelope


def test_event_type_values():
    assert EventType.ARTICLE_INGESTED.value == "article_ingested"
    assert EventType.BREAKING_NEWS.value == "breaking_news"
    assert EventType.PATTERN_DETECTED.value == "pattern_detected"


def test_envelope_creation():
    env = EventEnvelope(
        event_type=EventType.ARTICLE_INGESTED,
        payload={"domain_key": "politics", "article_id": 42},
        priority=2,
        domain="politics",
        deduplication_key="politics:42",
    )
    assert env.event_type == EventType.ARTICLE_INGESTED
    assert env.payload["article_id"] == 42
    assert env.deduplication_key == "politics:42"
    assert env.event_id
    assert env.timestamp


def test_envelope_to_dict():
    env = EventEnvelope(
        event_type=EventType.BREAKING_NEWS,
        payload={"title": "Test"},
        priority=1,
    )
    d = env.to_dict()
    assert d["event_type"] == "breaking_news"
    assert d["payload"]["title"] == "Test"
    assert d["priority"] == 1
    assert "event_id" in d
    assert "timestamp" in d


def test_envelope_from_dict():
    d = {
        "event_id": "abc-123",
        "event_type": "article_ingested",
        "payload": {"domain_key": "finance", "article_id": 1},
        "priority": 3,
        "deduplication_key": "finance:1",
    }
    env = EventEnvelope.from_dict(d)
    assert env.event_id == "abc-123"
    assert env.event_type == EventType.ARTICLE_INGESTED
    assert env.payload["article_id"] == 1
    assert env.deduplication_key == "finance:1"


def test_envelope_roundtrip():
    env = EventEnvelope(
        event_type=EventType.PATTERN_DETECTED,
        payload={"pattern": "test"},
        domain="science-tech",
    )
    d = env.to_dict()
    env2 = EventEnvelope.from_dict(d)
    assert env2.event_type == env.event_type
    assert env2.payload == env.payload
    assert env2.domain == env.domain
