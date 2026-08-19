"""Unit tests for editorial package Research modality helpers + cycle escape."""

from __future__ import annotations

from services.editorial_package_research_service import (
    resolve_research_route,
    validate_research_payload,
)
from services.editorial_package_narrative_service import (
    resolve_reduction_route_after_pass,
)


def _base_payload(**overrides):
    payload = {
        "members": [
            {
                "member_row_id": 10,
                "member_type": "extracted_claim",
                "member_id": 100,
                "role": "supporting",
                "candidate_key": "extracted_claim:100",
            }
        ],
        "candidates": [
            {
                "candidate_key": "versioned_fact:200",
                "member_type": "versioned_fact",
                "member_id": 200,
                "domain_key": None,
                "source": "spine",
                "provenance": {"quote": "Drug X reduced symptoms in trial Y"},
            },
            {
                "candidate_key": "claim_evidence_appraisal:9",
                "member_type": "claim_evidence_appraisal",
                "member_id": 9,
                "domain_key": "medicine",
                "source": "search",
                "provenance": {"source_url": "https://example.org/paper"},
            },
            {
                "candidate_key": "extracted_claim:50",
                "member_type": "extracted_claim",
                "member_id": 50,
                "domain_key": None,
                "source": "search",
                "provenance": {},  # not citeable
            },
        ],
        "uncoupled_history": [
            {
                "candidate_key": "claim_evidence_appraisal:9",
                "member_type": "claim_evidence_appraisal",
                "member_id": 9,
                "status": "removed",
            }
        ],
        "gaps": [],
    }
    payload.update(overrides)
    return payload


def test_validate_drops_unknown_candidate():
    validated = validate_research_payload(
        {
            "attach": [
                {"candidate_key": "versioned_fact:200", "role": "core_claim"},
                {"candidate_key": "versioned_fact:999", "role": "supporting"},
            ],
            "links": [],
            "role_updates": [],
        },
        payload=_base_payload(),
    )
    keys = {a["candidate_key"] for a in validated["attach"]}
    assert keys == {"versioned_fact:200"}
    assert any("attach_unknown" in r for r in validated["rejected"])


def test_validate_rejects_non_citeable():
    validated = validate_research_payload(
        {
            "attach": [
                {
                    "candidate_key": "extracted_claim:50",
                    "role": "supporting",
                    "confidence": 0.9,
                }
            ],
            "links": [],
        },
        payload=_base_payload(),
    )
    assert validated["attach"] == []
    assert any("not_citeable" in r for r in validated["rejected"])


def test_validate_blocks_uncoupled_reattach_without_high_conf():
    validated = validate_research_payload(
        {
            "attach": [
                {
                    "candidate_key": "claim_evidence_appraisal:9",
                    "role": "supporting",
                    "confidence": 0.5,
                }
            ],
            "links": [],
        },
        payload=_base_payload(),
    )
    assert validated["attach"] == []
    assert any("reattach_blocked" in r for r in validated["rejected"])


def test_validate_allows_high_conf_citeable_reattach():
    validated = validate_research_payload(
        {
            "attach": [
                {
                    "candidate_key": "claim_evidence_appraisal:9",
                    "role": "supporting",
                    "confidence": 0.9,
                }
            ],
            "links": [],
        },
        payload=_base_payload(),
    )
    assert len(validated["attach"]) == 1


def test_validate_research_links_and_roles():
    validated = validate_research_payload(
        {
            "attach": [
                {"candidate_key": "versioned_fact:200", "role": "core_claim"},
            ],
            "role_updates": [
                {"member_row_id": 10, "role": "hypothesis", "confidence": 1.5},
                {"member_row_id": 999, "role": "core_claim"},
                {"member_row_id": 10, "role": "anchor_event"},
            ],
            "links": [
                {
                    "from_ref": "member:10",
                    "to_ref": "candidate:versioned_fact:200",
                    "link_type": "supports",
                    "inference_stage": "candidate",
                },
                {
                    "from_ref": "member:10",
                    "to_ref": "candidate:versioned_fact:200",
                    "link_type": "same_event",
                },
            ],
        },
        payload=_base_payload(),
    )
    assert len(validated["role_updates"]) == 1
    assert validated["role_updates"][0]["confidence"] == 1.0
    assert len(validated["links"]) == 1
    assert validated["links"][0]["link_type"] == "supports"
    assert any("link_type_invalid" in r for r in validated["rejected"])
    assert any("role_invalid" in r for r in validated["rejected"])


def test_resolve_research_route_cycle_escape():
    assert (
        resolve_research_route(
            changed=2, meta={"reduction_rounds": 0}, round_n=1, max_r=3
        )
        == "reduction"
    )
    assert (
        resolve_research_route(
            changed=0, meta={"reduction_rounds": 0}, round_n=1, max_r=3
        )
        == "reduction"
    )
    assert (
        resolve_research_route(
            changed=0,
            meta={"reduction_rounds": 1, "last_reduction_removed_count": 0},
            round_n=2,
            max_r=3,
        )
        == "editor"
    )
    assert (
        resolve_research_route(changed=5, meta={}, round_n=3, max_r=3) == "editor"
    )


def test_reduction_partner_escape_uses_research_counters():
    # research_brief partner: Research zero + Reduction zero → editor
    assert (
        resolve_reduction_route_after_pass(
            changed=0,
            meta={"research_rounds": 1, "last_research_change_count": 0},
            round_n=1,
            max_r=3,
            default_return_modal="research",
        )
        == "editor"
    )
    # research partner not yet zero → return to research
    assert (
        resolve_reduction_route_after_pass(
            changed=0,
            meta={"research_rounds": 0},
            round_n=1,
            max_r=3,
            default_return_modal="research",
        )
        == "research"
    )
    # narrative counters must not falsely escape research packages
    assert (
        resolve_reduction_route_after_pass(
            changed=0,
            meta={"narrative_rounds": 1, "last_narrative_change_count": 0},
            round_n=1,
            max_r=3,
            default_return_modal="research",
        )
        == "research"
    )
