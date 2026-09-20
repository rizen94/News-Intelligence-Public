"""Unit tests for editorial package Narrative modality helpers + cycle escape."""

from __future__ import annotations

from services.editorial_package_narrative_service import (
    resolve_narrative_route,
    resolve_reduction_route_after_pass,
    validate_narrative_payload,
)


def _base_payload(**overrides):
    payload = {
        "members": [
            {
                "member_row_id": 10,
                "member_type": "chronological_event",
                "member_id": 100,
                "role": "supporting",
                "candidate_key": "chronological_event:100",
            }
        ],
        "candidates": [
            {
                "candidate_key": "chronological_event:200",
                "member_type": "chronological_event",
                "member_id": 200,
                "domain_key": None,
                "source": "coreference",
            },
            {
                "candidate_key": "entity:politics:9",
                "member_type": "entity",
                "member_id": 9,
                "domain_key": "politics",
                "source": "search",
            },
        ],
        "coreference_clusters": [{"root_event_id": 100, "event_ids": [100, 200]}],
        "causal_edges": [
            {
                "edge_id": 77,
                "cause_kind": "chronological_event",
                "cause_id": 100,
                "effect_kind": "chronological_event",
                "effect_id": 200,
            }
        ],
        "uncoupled_history": [
            {
                "candidate_key": "entity:politics:9",
                "member_type": "entity",
                "member_id": 9,
                "status": "removed",
            }
        ],
    }
    payload.update(overrides)
    return payload


def test_validate_drops_unknown_candidate():
    validated = validate_narrative_payload(
        {
            "attach": [
                {"candidate_key": "chronological_event:200", "role": "anchor_event"},
                {"candidate_key": "chronological_event:999", "role": "supporting"},
            ],
            "links": [],
            "role_updates": [],
        },
        payload=_base_payload(),
    )
    keys = {a["candidate_key"] for a in validated["attach"]}
    assert keys == {"chronological_event:200"}
    assert any("attach_unknown" in r for r in validated["rejected"])


def test_validate_blocks_reattach_without_evidence():
    validated = validate_narrative_payload(
        {
            "attach": [
                {
                    "candidate_key": "entity:politics:9",
                    "role": "actor",
                    "confidence": 0.5,
                }
            ],
            "links": [],
        },
        payload=_base_payload(),
    )
    assert validated["attach"] == []
    assert any("reattach_blocked" in r for r in validated["rejected"])


def test_validate_allows_high_conf_coreference_reattach():
    payload = _base_payload()
    # Mark chronological_event:200 as previously uncoupled but coreference-sourced
    payload["uncoupled_history"] = [
        {
            "candidate_key": "chronological_event:200",
            "member_type": "chronological_event",
            "member_id": 200,
            "status": "removed",
        }
    ]
    validated = validate_narrative_payload(
        {
            "attach": [
                {
                    "candidate_key": "chronological_event:200",
                    "role": "supporting",
                    "confidence": 0.9,
                }
            ],
            "links": [],
        },
        payload=payload,
    )
    assert len(validated["attach"]) == 1


def test_validate_same_event_requires_cluster():
    validated = validate_narrative_payload(
        {
            "attach": [
                {"candidate_key": "chronological_event:200", "role": "supporting"}
            ],
            "links": [
                {
                    "from_ref": "member:10",
                    "to_ref": "candidate:chronological_event:200",
                    "link_type": "same_event",
                    "inference_stage": "established",
                }
            ],
        },
        payload=_base_payload(),
    )
    assert len(validated["links"]) == 1
    assert validated["links"][0]["link_type"] == "same_event"

    # Event not in any shared cluster with the package member → reject
    validated2 = validate_narrative_payload(
        {
            "attach": [
                {
                    "candidate_key": "chronological_event:999",
                    "role": "supporting",
                    "confidence": 0.8,
                }
            ],
            "links": [
                {
                    "from_ref": "member:10",
                    "to_ref": "candidate:chronological_event:999",
                    "link_type": "same_event",
                }
            ],
        },
        payload=_base_payload(
            candidates=[
                {
                    "candidate_key": "chronological_event:999",
                    "member_type": "chronological_event",
                    "member_id": 999,
                    "source": "search",
                }
            ],
            coreference_clusters=[{"root_event_id": 100, "event_ids": [100]}],
        ),
    )
    assert validated2["links"] == []
    assert any("same_event_rejected" in r for r in validated2["rejected"])


def test_validate_caused_by_requires_edge_else_downgrade():
    validated = validate_narrative_payload(
        {
            "attach": [
                {"candidate_key": "chronological_event:200", "role": "supporting"}
            ],
            "links": [
                {
                    "from_ref": "member:10",
                    "to_ref": "candidate:chronological_event:200",
                    "link_type": "caused_by",
                    "edge_id": 77,
                    "inference_stage": "candidate",
                },
                {
                    "from_ref": "member:10",
                    "to_ref": "candidate:chronological_event:200",
                    "link_type": "caused_by",
                    "edge_id": 999,
                    "inference_stage": "candidate",
                },
            ],
        },
        payload=_base_payload(),
    )
    types = [ln["link_type"] for ln in validated["links"]]
    assert "caused_by" in types
    assert "near_in_time" in types  # downgraded bogus edge
    assert any("caused_by_downgraded" in r for r in validated["rejected"])


def test_validate_role_updates_and_clamps():
    validated = validate_narrative_payload(
        {
            "role_updates": [
                {"member_row_id": 10, "role": "anchor_event", "confidence": 1.5},
                {"member_row_id": 999, "role": "anchor_event"},
                {"member_row_id": 10, "role": "not_a_role"},
            ],
            "attach": [],
            "links": [],
        },
        payload=_base_payload(),
    )
    assert len(validated["role_updates"]) == 1
    assert validated["role_updates"][0]["confidence"] == 1.0


def test_resolve_narrative_route_cycle_escape():
    # Changes → reduction
    assert (
        resolve_narrative_route(
            changed=2, meta={"reduction_rounds": 0}, round_n=1, max_r=3
        )
        == "reduction"
    )
    # Zero + no prior reduction → reduction once
    assert (
        resolve_narrative_route(
            changed=0, meta={"reduction_rounds": 0}, round_n=1, max_r=3
        )
        == "reduction"
    )
    # Zero + reduction also zero → editor
    assert (
        resolve_narrative_route(
            changed=0,
            meta={"reduction_rounds": 1, "last_reduction_removed_count": 0},
            round_n=2,
            max_r=3,
        )
        == "editor"
    )
    # Max rounds → editor
    assert (
        resolve_narrative_route(
            changed=5, meta={}, round_n=3, max_r=3
        )
        == "editor"
    )


def test_resolve_reduction_route_cycle_escape():
    assert (
        resolve_reduction_route_after_pass(
            changed=3,
            meta={},
            round_n=1,
            max_r=3,
            default_return_modal="narrative",
        )
        == "narrative"
    )
    assert (
        resolve_reduction_route_after_pass(
            changed=0,
            meta={"narrative_rounds": 0},
            round_n=1,
            max_r=3,
            default_return_modal="narrative",
        )
        == "narrative"
    )
    assert (
        resolve_reduction_route_after_pass(
            changed=0,
            meta={"narrative_rounds": 1, "last_narrative_change_count": 0},
            round_n=1,
            max_r=3,
            default_return_modal="narrative",
        )
        == "editor"
    )
    assert (
        resolve_reduction_route_after_pass(
            changed=1,
            meta={},
            round_n=3,
            max_r=3,
            default_return_modal="narrative",
        )
        == "editor"
    )


def test_no_infinite_loop_possible():
    """Simulate alternating zero-change settles to editor within 2 confirmation passes."""
    meta: dict = {"narrative_rounds": 0, "reduction_rounds": 0}
    # Narrative adds
    r1 = resolve_narrative_route(changed=2, meta=meta, round_n=1, max_r=3)
    assert r1 == "reduction"
    meta["narrative_rounds"] = 1
    meta["last_narrative_change_count"] = 2
    # Reduction prunes
    r2 = resolve_reduction_route_after_pass(
        changed=1, meta=meta, round_n=1, max_r=3, default_return_modal="narrative"
    )
    assert r2 == "narrative"
    meta["reduction_rounds"] = 1
    meta["last_reduction_removed_count"] = 1
    # Narrative confirms 0
    r3 = resolve_narrative_route(changed=0, meta=meta, round_n=2, max_r=3)
    assert r3 == "reduction"  # reduction last was not 0
    meta["narrative_rounds"] = 2
    meta["last_narrative_change_count"] = 0
    # Reduction confirms 0 → editor
    r4 = resolve_reduction_route_after_pass(
        changed=0, meta=meta, round_n=2, max_r=3, default_return_modal="narrative"
    )
    assert r4 == "editor"
