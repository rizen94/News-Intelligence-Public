"""Unit tests for PopOS phase idle gate / exponential backoff."""

from __future__ import annotations

import time

from shared.phase_idle_gate import (
    PhaseIdleBackoff,
    decide_phase_action,
    drain_result_had_work,
)


def test_backoff_escalates_and_resets() -> None:
    b = PhaseIdleBackoff(base_seconds=10, max_seconds=80, factor=2)
    assert b.mark_idle("topic_clustering") == 10
    assert b.streak("topic_clustering") == 1
    assert b.mark_idle("topic_clustering") == 20
    assert b.mark_idle("topic_clustering") == 40
    assert b.mark_idle("topic_clustering") == 80  # capped
    b.mark_work("topic_clustering")
    assert b.streak("topic_clustering") == 0
    assert b.mark_idle("topic_clustering") == 10


def test_should_skip_respects_until() -> None:
    b = PhaseIdleBackoff(base_seconds=5, max_seconds=60, factor=2)
    now = time.monotonic()
    b.mark_idle("claim_extraction", now=now)
    skip, rem = b.should_skip("claim_extraction", now=now + 1)
    assert skip is True
    assert rem > 3
    skip2, _ = b.should_skip("claim_extraction", now=now + 6)
    assert skip2 is False


def test_decide_phase_action_skip_backoff(monkeypatch) -> None:
    b = PhaseIdleBackoff(base_seconds=30, max_seconds=300, factor=2)
    b.mark_idle("unified_intake_extraction")
    decision = decide_phase_action(
        "unified_intake_extraction", b, enabled=True
    )
    assert decision["action"] == "skip_backoff"
    assert float(decision["delay_sec"]) > 0


def test_decide_phase_action_skip_idle(monkeypatch) -> None:
    b = PhaseIdleBackoff(base_seconds=30, max_seconds=300, factor=2)

    monkeypatch.setattr(
        "shared.phase_idle_gate.phase_has_work",
        lambda phase: False,
    )
    decision = decide_phase_action("claim_extraction", b, enabled=True)
    assert decision["action"] == "skip_idle"
    assert b.streak("claim_extraction") == 1


def test_drain_result_had_work() -> None:
    assert drain_result_had_work({"processed": 0}) is False
    assert drain_result_had_work({"claims_inserted": 0, "batches": 3}) is False
    assert drain_result_had_work({"processed": 2}) is True
    assert drain_result_had_work({"llm_processed": 1}) is True
    assert drain_result_had_work({"skipped": "idle"}) is False
    assert drain_result_had_work({"error": "boom"}) is False
    assert drain_result_had_work({"frequency_skip_only": True, "articles_linked": 0}) is False
    assert drain_result_had_work(
        {"domains": {"medicine": {"articles_linked": 0}}, "articles_linked": 0}
    ) is False
    assert drain_result_had_work(
        {"domains": {"medicine": {"articles_linked": 2}}, "articles_linked": 2}
    ) is True


def test_mark_idle_honors_delay_hint() -> None:
    b = PhaseIdleBackoff(base_seconds=30, max_seconds=300, factor=2)
    delay = b.mark_idle("storyline_assembly", delay_seconds=3600)
    assert delay == 3600
    skip, rem = b.should_skip("storyline_assembly")
    assert skip is True
    assert rem > 3000
