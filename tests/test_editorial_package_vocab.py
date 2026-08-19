"""Unit tests for editorial package vocab and citation marker parsing."""

from __future__ import annotations

from shared.editorial_package_vocab import (
    DEFERRED_MEMBER_TYPES,
    NARRATIVE_MEMBER_TYPES,
    compute_readiness,
    family_for_member_type,
    provenance_has_citeable_source,
)
from shared.post_processing_modals import (
    allowed_domains_for_modal,
    domain_in_modal,
    list_modals,
    normalize_domain_filter,
)


def test_family_for_member_type():
    assert family_for_member_type("extracted_claim") == "research"
    assert family_for_member_type("chronological_event") == "narrative"
    assert family_for_member_type("article") is None  # ambiguous


def test_deferred_member_types_not_in_hot_path():
    assert "time_span" in DEFERRED_MEMBER_TYPES
    assert "movement_edge" in DEFERRED_MEMBER_TYPES
    assert "time_span" not in NARRATIVE_MEMBER_TYPES
    assert "movement_edge" not in NARRATIVE_MEMBER_TYPES


def test_provenance_has_citeable_source():
    assert provenance_has_citeable_source({"quote": "x"}) is True
    assert provenance_has_citeable_source({"source_url": "https://a"}) is True
    assert provenance_has_citeable_source({"url": "https://a"}) is True
    assert provenance_has_citeable_source({"article_id": 1}) is False
    assert provenance_has_citeable_source({"document_id": 9}) is False
    assert provenance_has_citeable_source({}) is False


def test_provenance_rejects_title_as_quote_for_publish():
    soft = {"label": "Same Title", "quote": "Same Title"}
    assert provenance_has_citeable_source(soft) is True  # attach/search still ok
    assert provenance_has_citeable_source(soft, for_publish=True) is False
    assert (
        provenance_has_citeable_source(
            {"label": "T", "quote": "T", "quote_is_title": True},
            for_publish=True,
        )
        is False
    )
    assert (
        provenance_has_citeable_source(
            {"label": "T", "quote": "T", "source_url": "https://x"},
            for_publish=True,
        )
        is True
    )


def test_compute_readiness_hybrid():
    members = [
        {
            "status": "active",
            "member_family": "research",
            "member_type": "extracted_claim",
            "role": "core_claim",
            "provenance": {"quote": "q"},
        },
        {
            "status": "active",
            "member_family": "narrative",
            "member_type": "chronological_event",
            "role": "anchor_event",
            "provenance": {"source_url": "https://x"},
        },
        {
            "status": "quarantined",
            "member_family": "research",
            "member_type": "hypothesis",
            "role": "hypothesis",
        },
    ]
    readiness = compute_readiness(
        members,
        [{"status": "active"}],
        package_status="ready_for_editor",
        reduction_cleared=True,
    )
    assert readiness["research_brief_ready"] is True
    assert readiness["event_narrative_ready"] is True
    assert readiness["hybrid_ready"] is True
    assert readiness["active_member_count"] == 2
    assert readiness["research_member_count"] == 1
    assert readiness["citeable_member_count"] == 2
    assert readiness["citation_coverage"] == 1.0
    assert readiness["contested_or_quarantined_count"] == 1
    assert readiness["reduction_cleared"] is True


def test_reduction_cleared_not_implied_by_in_editing():
    members = [
        {
            "status": "active",
            "member_family": "research",
            "member_type": "extracted_claim",
            "role": "core_claim",
            "provenance": {"quote": "q"},
        }
    ]
    r = compute_readiness(
        members, [], package_status="in_editing", reduction_cleared=False
    )
    assert r["reduction_cleared"] is False
    r2 = compute_readiness(
        members, [], package_status="ready_for_editor", reduction_cleared=False
    )
    assert r2["reduction_cleared"] is True


def test_research_brief_requires_citeable():
    members = [
        {
            "status": "active",
            "member_family": "research",
            "member_type": "extracted_claim",
            "role": "core_claim",
            "provenance": {"article_id": 1},  # not citeable for publish
        }
    ]
    r = compute_readiness(members, [], package_status="draft")
    assert r["has_research_core"] is True
    assert r["research_brief_ready"] is False
    assert r["citeable_member_count"] == 0


def test_modal_allowlists():
    mods = list_modals()
    assert [m["key"] for m in mods] == [
        "research",
        "narrative",
        "reduction",
        "editor",
    ]
    assert "medicine" in allowed_domains_for_modal("research")
    assert "politics" in allowed_domains_for_modal("narrative")
    assert domain_in_modal("medicine", "research")
    assert not domain_in_modal("politics", "research")
    assert normalize_domain_filter("research", ["medicine", "politics"]) == ["medicine"]
    assert set(normalize_domain_filter("research", None)) >= {"medicine"}
