"""Unit tests for editorial package Reduction modality helpers."""

from __future__ import annotations

from services.editorial_package_reduction_service import (
    resolve_return_modal,
    validate_reduction_payload,
)


def test_validate_drops_unknown_ids():
    validated = validate_reduction_payload(
        {
            "summary": "t",
            "actions": [
                {"target": "member", "id": 1, "action": "remove", "flags": ["unrelated"]},
                {"target": "member", "id": 999, "action": "remove", "flags": ["unrelated"]},
                {"target": "link", "id": 5, "action": "remove", "flags": ["weak_link"]},
                {"target": "link", "id": 88, "action": "remove", "flags": ["weak_link"]},
            ],
        },
        known_member_ids={1, 2},
        known_link_ids={5},
    )
    ids = {(a["target"], a["id"]) for a in validated["actions"]}
    assert ids == {("member", 1), ("link", 5)}


def test_validate_clamps_actions_and_forces_geo_entity_remove():
    validated = validate_reduction_payload(
        {
            "summary": "geo",
            "actions": [
                {
                    "target": "member",
                    "id": 1,
                    "action": "quarantine",
                    "flags": ["geo_mismatch"],
                    "confidence": 0.9,
                },
                {
                    "target": "member",
                    "id": 2,
                    "action": "keep",
                    "flags": ["entity_mismatch"],
                },
                {
                    "target": "member",
                    "id": 3,
                    "action": "explode",  # invalid → keep
                    "flags": [],
                },
                {
                    "target": "link",
                    "id": 9,
                    "action": "quarantine",  # links → remove
                    "flags": ["weak_link"],
                },
            ],
        },
        known_member_ids={1, 2, 3},
        known_link_ids={9},
    )
    by_id = {a["id"]: a for a in validated["actions"] if a["target"] == "member"}
    assert by_id[1]["action"] == "remove"
    assert by_id[2]["action"] == "remove"
    assert by_id[3]["action"] == "keep"
    link = next(a for a in validated["actions"] if a["target"] == "link")
    assert link["action"] == "remove"


def test_validate_dedupes_and_ignores_bad_targets():
    validated = validate_reduction_payload(
        {
            "actions": [
                {"target": "member", "id": 1, "action": "remove", "flags": ["unrelated"]},
                {"target": "member", "id": 1, "action": "quarantine", "flags": []},
                {"target": "widget", "id": 1, "action": "remove"},
                {"target": "member", "id": "x", "action": "remove"},
            ]
        },
        known_member_ids={1},
        known_link_ids=set(),
    )
    assert len(validated["actions"]) == 1
    assert validated["actions"][0]["action"] == "remove"


def test_resolve_return_modal_by_presentation_kind():
    assert (
        resolve_return_modal({"presentation_kind": "research_brief", "metadata": {}})
        == "research"
    )
    assert (
        resolve_return_modal({"presentation_kind": "event_narrative", "metadata": {}})
        == "narrative"
    )
    assert resolve_return_modal({"presentation_kind": "hybrid", "metadata": {}}) == "narrative"
    assert resolve_return_modal({"presentation_kind": "unset", "metadata": {}}) == "narrative"


def test_resolve_return_modal_metadata_override():
    assert (
        resolve_return_modal(
            {
                "presentation_kind": "event_narrative",
                "metadata": {"reduction_return_modal": "research"},
            }
        )
        == "research"
    )
    assert (
        resolve_return_modal(
            {
                "presentation_kind": "research_brief",
                "metadata": {"reduction_return_modal": "narrative"},
            }
        )
        == "narrative"
    )


def test_convergence_logic_helpers():
    """Cycle escape: use shared Reduction route helper (0+narrative0 or max → editor)."""
    from services.editorial_package_narrative_service import (
        resolve_reduction_route_after_pass,
    )

    assert (
        resolve_reduction_route_after_pass(
            changed=2, meta={}, round_n=1, max_r=3, default_return_modal="narrative"
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
            changed=5, meta={}, round_n=3, max_r=3, default_return_modal="narrative"
        )
        == "editor"
    )


def test_convergence_uses_research_partner_counters():
    from services.editorial_package_narrative_service import (
        resolve_reduction_route_after_pass,
    )

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
