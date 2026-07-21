"""Adaptive batch registration for storyline_membership_review."""

from shared.adaptive_batch_policy import (
    is_adaptive_batch_phase,
    is_per_domain_adaptive_batch,
    resolve_adaptive_batch,
)


def test_membership_review_is_adaptive_and_per_domain(monkeypatch):
    monkeypatch.setenv("AUTOMATION_ADAPTIVE_BATCH_ENABLED", "true")
    assert is_adaptive_batch_phase("storyline_membership_review")
    assert is_per_domain_adaptive_batch("storyline_membership_review")
    tuned, meta = resolve_adaptive_batch("storyline_membership_review", 8)
    assert 8 <= int(tuned) <= 48
    assert isinstance(meta, dict)
