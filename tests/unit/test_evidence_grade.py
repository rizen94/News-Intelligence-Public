"""Unit tests for shared.evidence_grade compose rules, refusal contract, MeSH mapping."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "api"))

from shared.evidence_grade import (
    EVIDENCE_GRADES,
    PAPER_SUPPORTS,
    REPLICATION_STATUSES,
    STUDY_DESIGNS,
    assert_valid_appraisal_payload,
    compose_evidence_grade,
    mesh_publication_type_to_study_design,
    normalize_paper_support,
    normalize_replication_status,
)


def test_vocab_sets_nonempty():
    assert "rct" in STUDY_DESIGNS
    assert "peer_reviewed" not in STUDY_DESIGNS
    assert "supported_by_own_evidence" in PAPER_SUPPORTS
    assert "needs_follow_up" in REPLICATION_STATUSES
    assert "strong" in EVIDENCE_GRADES


def test_mesh_publication_type_mapping():
    assert mesh_publication_type_to_study_design("Randomized Controlled Trial") == "rct"
    assert mesh_publication_type_to_study_design("Meta-Analysis") == "meta_analysis"
    assert mesh_publication_type_to_study_design("Systematic Review") == "systematic_review"
    assert mesh_publication_type_to_study_design("Cohort Studies") == "cohort"
    assert mesh_publication_type_to_study_design("Case-Control Studies") == "case_control"
    assert mesh_publication_type_to_study_design("Cross-Sectional Studies") == "cross_sectional"
    assert mesh_publication_type_to_study_design("Case Reports") == "case_report"
    assert mesh_publication_type_to_study_design("Editorial") == "opinion"
    assert mesh_publication_type_to_study_design("") == "unknown"
    assert mesh_publication_type_to_study_design("Something Obscure") == "unknown"


def test_compose_abstract_only_never_strong():
    grade = compose_evidence_grade(
        "meta_analysis",
        "peer_reviewed",
        "supported_by_own_evidence",
        "replicated_independent",
        abstract_only=True,
    )
    assert grade != "strong"
    assert grade in EVIDENCE_GRADES


def test_compose_full_text_can_be_strong():
    grade = compose_evidence_grade(
        "meta_analysis",
        "peer_reviewed",
        "supported_by_own_evidence",
        "replicated_independent",
        abstract_only=False,
    )
    assert grade == "strong"


def test_compose_not_supported_unsubstantiated():
    assert (
        compose_evidence_grade(
            "rct",
            "peer_reviewed",
            "not_supported_by_own_evidence",
            "single_study",
            abstract_only=False,
        )
        == "unsubstantiated"
    )


def test_compose_insufficient_reporting_preliminary():
    assert (
        compose_evidence_grade(
            "rct",
            "peer_reviewed",
            "insufficient_reporting",
            "single_study",
            abstract_only=False,
        )
        == "preliminary"
    )


def test_compose_needs_follow_up_not_contradicted():
    # needs_follow_up must not collapse to contradicted/unsubstantiated-as-false
    grade = compose_evidence_grade(
        "rct",
        "peer_reviewed",
        "supported_by_own_evidence",
        "needs_follow_up",
        abstract_only=False,
    )
    assert grade in ("limited", "preliminary")
    assert grade != "unsubstantiated"
    assert normalize_replication_status("false") == "needs_follow_up"


def test_compose_contradicted_unsubstantiated():
    assert (
        compose_evidence_grade(
            "cohort",
            "peer_reviewed",
            "supported_by_own_evidence",
            "contradicted",
            abstract_only=False,
        )
        == "unsubstantiated"
    )


def test_refusal_contract_missing_quotes():
    out = assert_valid_appraisal_payload(
        {
            "study_design": "rct",
            "peer_review_status": "peer_reviewed",
            "paper_support": "supported_by_own_evidence",
            "replication_status": "single_study",
            "evidence_quotes": [],
            "abstract_only": False,
        }
    )
    assert out["paper_support"] == "insufficient_reporting"
    assert out["evidence_grade"] == "preliminary"
    assert out["evidence_quotes"] == []


def test_refusal_contract_keeps_quotes_when_present():
    out = assert_valid_appraisal_payload(
        {
            "study_design": "rct",
            "peer_review_status": "peer_reviewed",
            "paper_support": "supported_by_own_evidence",
            "replication_status": "single_study",
            "evidence_quotes": [{"quote": "Participants improved on the primary endpoint."}],
            "abstract_only": True,
        }
    )
    assert out["paper_support"] == "supported_by_own_evidence"
    assert len(out["evidence_quotes"]) == 1
    assert out["evidence_grade"] != "strong"  # abstract_only


def test_normalize_paper_support_aliases():
    assert normalize_paper_support("not_supported") == "not_supported_by_own_evidence"
    assert normalize_paper_support("no_quotes") == "insufficient_reporting"
