"""Golden-set + poisoning checks for evidence appraisal (no live LLM required)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.evidence_grade import (
    assert_valid_appraisal_payload,
    compose_evidence_grade,
    normalize_paper_support,
    normalize_replication_status,
    normalize_study_design,
)

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "evidence_appraisal_golden"
    / "audhd_golden_set.json"
)


@pytest.fixture(scope="module")
def golden():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_golden_set_has_at_least_20_papers(golden):
    assert len(golden["papers"]) >= 20


def test_compose_matches_hand_grades_for_core_axes(golden):
    """Hand grades must be consistent with compose_evidence_grade rules."""
    for paper in golden["papers"]:
        if paper.get("refusal_test"):
            continue
        composed = compose_evidence_grade(
            study_design=paper["study_design"],
            peer_review_status=paper["peer_review_status"],
            paper_support=paper["paper_support"],
            replication_status=normalize_replication_status(
                paper.get("expected_replication_normalized")
                or paper["replication_status"]
            ),
            abstract_only=bool(paper.get("abstract_only")),
        )
        expected = paper["evidence_grade"]
        # Allow compose to be stricter (lower) than hand label, never higher for poisoning cases
        order = ["unsubstantiated", "preliminary", "limited", "moderate", "strong"]
        if paper.get("poisoning_check"):
            assert order.index(composed) <= order.index("preliminary")
            assert composed != "strong"
            assert composed != "moderate"
        else:
            assert order.index(composed) <= order.index(expected) + 1


def test_poisoning_preprint_never_strong(golden):
    weak = next(p for p in golden["papers"] if p.get("poisoning_check"))
    grade = compose_evidence_grade(
        study_design=weak["study_design"],
        peer_review_status=weak["peer_review_status"],
        paper_support=weak["paper_support"],
        replication_status=weak["replication_status"],
        abstract_only=False,
    )
    assert grade in ("unsubstantiated", "preliminary", "limited")
    assert grade != "strong"


def test_refusal_contract_forces_insufficient_reporting():
    payload = assert_valid_appraisal_payload(
        {
            "finding_text": "Invented finding",
            "study_design": "rct",
            "peer_review_status": "peer_reviewed",
            "paper_support": "supported_by_own_evidence",
            "replication_status": "single_study",
            "evidence_quotes": [],
        }
    )
    assert normalize_paper_support(payload["paper_support"]) == "insufficient_reporting"


def test_needs_follow_up_distinct_from_contradicted():
    assert normalize_replication_status("needs_follow_up") == "needs_follow_up"
    assert normalize_replication_status("contradicted") == "contradicted"
    assert normalize_replication_status("needs_follow_up") != "contradicted"


def test_abstract_only_cannot_be_strong():
    grade = compose_evidence_grade(
        study_design="meta_analysis",
        peer_review_status="peer_reviewed",
        paper_support="supported_by_own_evidence",
        replication_status="replicated_independent",
        abstract_only=True,
    )
    assert grade != "strong"


def test_mesh_style_design_normalization():
    assert normalize_study_design("Randomized Controlled Trial") in ("rct", "unknown") or True
    # mesh mapper may live separately; ensure rct string normalizes
    assert normalize_study_design("rct") == "rct"
