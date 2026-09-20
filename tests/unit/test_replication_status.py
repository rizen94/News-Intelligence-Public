"""Replication status classification from similar findings."""

from __future__ import annotations

from services.claim_similarity_service import classify_replication_status


def test_no_matches_is_single_study():
    assert classify_replication_status(matching_findings=[]) == "single_study"


def test_independent_authors():
    status = classify_replication_status(
        matching_findings=[{"authors": ["Alice Smith", "Bob Jones"]}],
        seed_authors=["Carol Lee"],
    )
    assert status == "replicated_independent"


def test_same_group_authors():
    status = classify_replication_status(
        matching_findings=[{"authors": ["Alice Smith"]}],
        seed_authors=["Alice Smith", "Dana"],
    )
    assert status == "replicated_same_group"


def test_contradicted_wins():
    status = classify_replication_status(
        matching_findings=[{"authors": ["X"], "contradicts": True}],
        seed_authors=["Y"],
    )
    assert status == "contradicted"
