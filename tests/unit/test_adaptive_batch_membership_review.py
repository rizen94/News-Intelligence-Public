"""Adaptive batch registration for storyline_membership_review."""

from shared.adaptive_batch_policy import (
    ensure_phase_bounds,
    is_adaptive_batch_phase,
    is_per_domain_adaptive_batch,
)


def test_membership_review_is_adaptive_and_per_domain():
    assert is_adaptive_batch_phase("storyline_membership_review")
    assert is_per_domain_adaptive_batch("storyline_membership_review")
    bounds = ensure_phase_bounds("storyline_membership_review", 100)
    assert bounds["min"] >= 100
    assert bounds.get("max") is None
    assert int(bounds["step"]) >= 50
