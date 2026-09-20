"""Tests for orchestrator structured logging."""

import json
import logging

import pytest

from domains.finance.orchestrator_logger import (
    EVAL_PASSED,
    TASK_ACCEPTED,
    WORKER_DISPATCHED,
    log_event,
)


@pytest.fixture
def orchestrator_log(caplog, monkeypatch):
    """Route orchestrator logs through a propagating logger caplog can capture."""
    test_logger = logging.getLogger("finance.orchestrator.test")
    test_logger.handlers.clear()
    test_logger.propagate = True
    monkeypatch.setattr("domains.finance.orchestrator_logger.LOG", test_logger)
    with caplog.at_level(logging.INFO, logger=test_logger.name):
        yield caplog


def test_log_event_produces_parseable_json(orchestrator_log):
    """Log output is valid JSON with required fields."""
    log_event(TASK_ACCEPTED, "fin-abc123", {"sources": ["gold"]})
    assert len(orchestrator_log.records) >= 1
    last = orchestrator_log.records[-1]
    payload = json.loads(last.message)
    assert payload["event_type"] == TASK_ACCEPTED
    assert payload["task_id"] == "fin-abc123"
    assert "timestamp" in payload
    assert payload["detail"]["sources"] == ["gold"]


def test_log_event_with_each_type(orchestrator_log):
    """Each event type produces structured output."""
    events = [
        (TASK_ACCEPTED, {"priority": "high"}),
        (WORKER_DISPATCHED, {"source_id": "freegoldapi"}),
        (EVAL_PASSED, {"sources_ok": 2}),
    ]
    for et, detail in events:
        log_event(et, "fin-test", detail)
    for i, (et, _) in enumerate(events):
        payload = json.loads(orchestrator_log.records[-(len(events) - i)].message)
        assert payload["event_type"] == et
        assert payload["task_id"] == "fin-test"
