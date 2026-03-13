"""Unit and integration tests for Newsroom Orchestrator."""

import pytest
from unittest.mock import Mock
from orchestration.events.envelope import EventEnvelope
from orchestration.events.types import EventType
from orchestration.events.queue import InProcessEventQueue
from orchestration.base import NewsroomOrchestrator


def test_queue_put_get():
    q = InProcessEventQueue()
    env = EventEnvelope(
        event_type=EventType.ARTICLE_INGESTED,
        payload={"article_id": 1},
        priority=2,
        deduplication_key="politics:1",
    )
    q.put(env)
    assert q.qsize() == 1
    out = q.get(block=False)
    assert out is not None
    assert out.event_type == EventType.ARTICLE_INGESTED
    assert out.payload["article_id"] == 1
    assert q.qsize() == 0


def test_queue_priority_order():
    q = InProcessEventQueue()
    q.put(EventEnvelope(EventType.ARTICLE_INGESTED, {"a": 1}, priority=3))
    q.put(EventEnvelope(EventType.BREAKING_NEWS, {"b": 2}, priority=1))
    q.put(EventEnvelope(EventType.PATTERN_DETECTED, {"c": 3}, priority=2))
    first = q.get(block=False)
    assert first.event_type == EventType.BREAKING_NEWS
    second = q.get(block=False)
    assert second.event_type == EventType.PATTERN_DETECTED
    third = q.get(block=False)
    assert third.event_type == EventType.ARTICLE_INGESTED


def test_orchestrator_idempotency():
    """Same deduplication_key processed only once."""
    get_db = Mock(return_value=None)
    orch = NewsroomOrchestrator(get_db_connection=get_db, config={"enabled": True})
    seen = []

    def handler(env: EventEnvelope):
        seen.append(env.deduplication_key)

    orch.register_handler(EventType.ARTICLE_INGESTED, handler)
    orch.emit(
        EventEnvelope(
            event_type=EventType.ARTICLE_INGESTED,
            payload={},
            deduplication_key="politics:1",
        )
    )
    orch.emit(
        EventEnvelope(
            event_type=EventType.ARTICLE_INGESTED,
            payload={},
            deduplication_key="politics:1",
        )
    )
    # Process two events from queue (orchestrator loop would do this)
    for _ in range(2):
        env = orch._queue.get(block=False)
        if env:
            orch._handle_one(env)
    # Handler should have been called only once for politics:1 (second is skipped as already processed)
    assert len(seen) == 1
    assert seen[0] == "politics:1"


def test_orchestrator_get_status():
    get_db = Mock(return_value=None)
    orch = NewsroomOrchestrator(get_db_connection=get_db, config={"enabled": True})
    orch.is_running = False
    status = orch.get_status()
    assert status["enabled"] is True
    assert status["running"] is False
    assert status["queue_depth"] == 0
    assert "last_event_at" in status
