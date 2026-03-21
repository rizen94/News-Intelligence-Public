"""Tests for orchestrator structured logging."""

import json
import logging

from domains.finance.orchestrator_logger import (
    EVAL_PASSED,
    TASK_ACCEPTED,
    WORKER_DISPATCHED,
    log_event,
)


def test_log_event_produces_parseable_json(caplog):
    """Log output is valid JSON with required fields."""
    caplog.set_level(logging.INFO)
    log_event(TASK_ACCEPTED, "fin-abc123", {"sources": ["gold"]})
    assert len(caplog.records) >= 1
    last = caplog.records[-1]
    payload = json.loads(last.message)
    assert payload["event_type"] == TASK_ACCEPTED
    assert payload["task_id"] == "fin-abc123"
    assert "timestamp" in payload
    assert payload["detail"]["sources"] == ["gold"]


def test_log_event_with_each_type(caplog):
    """Each event type produces structured output."""
    caplog.set_level(logging.INFO)
    events = [
        (TASK_ACCEPTED, {"priority": "high"}),
        (WORKER_DISPATCHED, {"source_id": "freegoldapi"}),
        (EVAL_PASSED, {"sources_ok": 2}),
    ]
    for et, detail in events:
        log_event(et, "fin-test", detail)
    for i, (et, _) in enumerate(events):
        payload = json.loads(caplog.records[-(len(events) - i)].message)
        assert payload["event_type"] == et
        assert payload["task_id"] == "fin-test"
