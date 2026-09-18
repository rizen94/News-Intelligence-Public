"""Unit tests for discovery lead ranking and attach domain resolution."""

from services.discovery_finding_quality import (
    bridge_sort_key,
    discovery_finalize_action,
    finding_skip_reason,
    is_bridgeable,
    package_default_domain,
    should_split_incoherent_package,
)


def test_skip_global_temporal_pattern():
    finding = {
        "finding_type": "pattern",
        "domain_keys": [],
        "confidence": 0.9,
        "evidence": {
            "pattern_type": "temporal",
            "context_ids": list(range(20)),
            "entity_profile_ids": [],
            "data": {"date": "2026-08-13", "context_count": 551},
        },
    }
    assert finding_skip_reason(finding) == "global_temporal_pattern"
    assert not is_bridgeable(finding)


def test_keep_network_pattern_with_entities():
    finding = {
        "finding_type": "pattern",
        "domain_keys": ["finance"],
        "confidence": 0.75,
        "evidence": {
            "pattern_type": "network",
            "context_ids": [1],
            "entity_profile_ids": [10, 20],
            "data": {"relation": "co_mentioned", "context_count": 1},
        },
    }
    assert finding_skip_reason(finding) is None
    assert is_bridgeable(finding)


def test_skip_thin_network():
    finding = {
        "finding_type": "pattern",
        "domain_keys": ["finance"],
        "evidence": {
            "pattern_type": "network",
            "entity_profile_ids": [10],
        },
    }
    assert finding_skip_reason(finding) == "thin_network"


def test_skip_graph_without_endpoints():
    finding = {
        "finding_type": "graph_proposal",
        "domain_keys": ["politics"],
        "evidence": {"endpoints": {"proposal_kind": "same_as"}},
    }
    assert finding_skip_reason(finding) == "graph_no_endpoints"


def test_keep_same_day_temporal_events():
    finding = {
        "finding_type": "temporal",
        "domain_keys": ["politics"],
        "left_id": 1,
        "right_id": 2,
        "confidence": 0.65,
        "evidence": {},
    }
    assert is_bridgeable(finding)


def test_cross_domain_ranks_ahead_of_pattern():
    xdom = {
        "finding_type": "cross_domain",
        "domain_keys": ["artificial-intelligence", "finance"],
        "confidence": 0.7,
        "evidence": {"entity_profile_ids": [1], "event_ids": [2]},
    }
    pattern = {
        "finding_type": "pattern",
        "domain_keys": ["finance"],
        "confidence": 0.95,
        "evidence": {
            "pattern_type": "network",
            "entity_profile_ids": [1, 2],
        },
    }
    ranked = sorted([pattern, xdom], key=bridge_sort_key)
    assert ranked[0] is xdom


def test_research_entity_ranks_ahead_of_finance_graph():
    entity = {
        "finding_type": "research_entity",
        "domain_keys": ["artificial-intelligence"],
        "confidence": 0.5,
        "evidence": {"canonical_entity_ids": [1], "entity_profile_ids": [2]},
    }
    graph = {
        "finding_type": "graph_proposal",
        "domain_keys": ["finance"],
        "confidence": 0.9,
        "evidence": {"endpoints": {"storyline_ids": [99]}},
    }
    ranked = sorted([graph, entity], key=bridge_sort_key)
    assert ranked[0] is entity


def test_package_default_domain_from_members():
    pkg = {
        "domain_keys": [],
        "members": [
            {"status": "active", "domain_key": "politics"},
        ],
    }
    assert package_default_domain(pkg) == "politics"


def test_finalize_defers_when_llm_unavailable():
    status, decision = discovery_finalize_action(
        {"gaps": ["llm_unavailable"], "attach": [], "rejected": []},
        changed=0,
        pass_name="narrative",
    )
    assert status == "queued_research"
    assert decision == "deferred_llm_unavailable"


def test_finalize_links_when_members_changed():
    status, decision = discovery_finalize_action(
        {"gaps": [], "attach": [], "rejected": []},
        changed=5,
        pass_name="narrative",
    )
    assert status == "linked"
    assert decision == "narrative_attached"


def test_keep_same_day_temporal_for_research_domain():
    finding = {
        "finding_type": "temporal",
        "domain_keys": ["artificial-intelligence"],
        "left_id": 1,
        "right_id": 2,
        "confidence": 0.65,
        "evidence": {},
    }
    # Bridge truncates to a single CE for research modal.
    assert finding_skip_reason(finding) is None
    assert is_bridgeable(finding)


def test_split_when_llm_says_no_link():
    pkg = {
        "metadata": {"discovery_source": "temporal"},
        "members": [
            {"status": "active", "member_type": "chronological_event", "member_id": 10},
            {"status": "active", "member_type": "chronological_event", "member_id": 20},
        ],
    }
    validated = {
        "insufficient_evidence": True,
        "gaps": ["No logical bridge between TDP-43 toxicology and brain-language alignment."],
    }
    assert should_split_incoherent_package(pkg, validated, used_fallback=False)
    assert not should_split_incoherent_package(pkg, validated, used_fallback=True)


def test_no_split_single_event():
    pkg = {
        "metadata": {"discovery_source": "temporal"},
        "members": [
            {"status": "active", "member_type": "chronological_event", "member_id": 10},
        ],
    }
    validated = {"gaps": ["No logical bridge."], "insufficient_evidence": True}
    assert not should_split_incoherent_package(pkg, validated)
