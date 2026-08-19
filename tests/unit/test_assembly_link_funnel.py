"""Unit tests for assembly link funnel + event essence (Mode A/B seatbelts)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

from shared.assembly_link_funnel import (
    allow_storyline_membership_attach,
    filter_durable_canonical_ids,
    is_durable_entity_type,
    membership_metadata,
    shared_durable_canonical_count,
)
from shared.assembly_link_modes import (
    DENY_SOLO_ENTITY_TYPES,
    LINK_MODE_SEQUENCE,
)
from shared.event_essence import event_essence_text
from shared.story_entity_index import resolve_entity_role_for_sei

_ROOT = Path(__file__).resolve().parents[2]
_API = _ROOT / "api"


def _load_domain_synthesis_config():
    path = _API / "services" / "domain_synthesis_config.py"
    spec = importlib.util.spec_from_file_location("domain_synthesis_config_test", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._normalise_domain_key = lambda k: (k or "").strip().lower().replace("_", "-")
    return mod


def test_event_essence_includes_who_what_when_where():
    text = event_essence_text(
        {
            "title": "Patients sue Abbott over data breach",
            "event_type": "legal_action",
            "location": "Illinois",
            "actual_event_date": "2026-07-16",
            "key_actors": [
                {"name": "Abbott Laboratories", "role": "defendant"},
                {"name": "Exact Sciences", "role": "defendant"},
            ],
            "outcome": "Class action filed",
        }
    )
    assert "Abbott" in text
    assert "Illinois" in text
    assert "2026-07-16" in text
    assert "Class action" in text


def test_subject_canonical_excluded_from_durable_filter():
    # data breach subject must not count; Abbott org must
    ids = filter_durable_canonical_ids(
        [
            (10012, "subject"),
            (34188, "organization"),
            (999, "other"),
            (None, "person"),
        ]
    )
    assert ids == [34188]


def test_hub_names_excluded_from_durable_filter():
    ids = filter_durable_canonical_ids(
        [
            (1, "organization"),
            (2, "organization"),
            (3, "person"),
        ],
        exclude_hub_names=frozenset({"supreme court", "scotus"}),
        name_by_cid={
            1: "Supreme Court",
            2: "Abbott Laboratories",
            3: "John Roberts",
        },
    )
    assert 1 not in ids
    assert 2 in ids
    assert 3 in ids


def test_is_durable_entity_type():
    assert is_durable_entity_type("organization")
    assert is_durable_entity_type("person")
    assert not is_durable_entity_type("subject")
    assert not is_durable_entity_type("other")
    for t in DENY_SOLO_ENTITY_TYPES:
        assert not is_durable_entity_type(t)


def test_shared_durable_overlap():
    assert shared_durable_canonical_count([1, 2, 3], [3, 9]) == 1
    assert shared_durable_canonical_count([1], [2]) == 0
    assert shared_durable_canonical_count([], [1]) == 0


def test_membership_metadata_sequence():
    meta = membership_metadata(LINK_MODE_SEQUENCE, source="storyline_automation")
    assert meta["link_mode"] == "sequence"
    assert meta["source"] == "storyline_automation"


def test_resolve_entity_role_hub_and_party():
    role, hub_key = resolve_entity_role_for_sei(
        domain_key="legal",
        entity_name="Supreme Court",
        entity_type="organization",
    )
    assert role in ("who", "what", "where")
    assert hub_key == "scotus"

    role2, hub2 = resolve_entity_role_for_sei(
        domain_key="legal",
        entity_name="Abbott Laboratories",
        entity_type="organization",
    )
    assert role2 == "party"
    assert hub2 is None

    role3, _ = resolve_entity_role_for_sei(
        domain_key="legal",
        entity_name="1:22-cv-00123",
        entity_type="case_number",
    )
    assert role3 == "matter"


def test_allow_storyline_membership_attach_rejects_low_blend():
    conn = MagicMock()
    with patch(
        "shared.assembly_link_funnel.allow_auto_membership_sequence",
        return_value=(True, "durable_overlap_1"),
    ), patch(
        "shared.storyline_attach_caps.storyline_at_or_over_attach_cap",
        return_value=False,
    ):
        ok, reason = allow_storyline_membership_attach(
            conn,
            domain_key="legal",
            schema="legal",
            storyline_id=1,
            article_id=2,
            blend_score=0.1,
            link_mode=LINK_MODE_SEQUENCE,
            article_count=5,
        )
    assert ok is False
    assert "blend_" in reason


def test_allow_storyline_membership_attach_rejects_bad_link_mode():
    conn = MagicMock()
    ok, reason = allow_storyline_membership_attach(
        conn,
        domain_key="legal",
        schema="legal",
        storyline_id=1,
        article_id=2,
        blend_score=0.99,
        link_mode="cosine_peer",
        article_count=1,
    )
    assert ok is False
    assert "link_mode_not_auto" in reason


def test_allow_storyline_membership_attach_ok_path():
    conn = MagicMock()
    with patch(
        "shared.assembly_link_funnel.allow_auto_membership_sequence",
        return_value=(True, "durable_overlap_2"),
    ), patch(
        "shared.storyline_attach_caps.storyline_at_or_over_attach_cap",
        return_value=False,
    ):
        ok, reason = allow_storyline_membership_attach(
            conn,
            domain_key="politics",
            schema="politics",
            storyline_id=10,
            article_id=20,
            blend_score=0.95,
            link_mode=LINK_MODE_SEQUENCE,
            article_count=3,
        )
    assert ok is True
    assert reason.startswith("ok:")


def test_major_attach_callers_reference_shared_gate():
    """Regression: silent attach paths must reference the SSOT gate."""
    files = [
        _API / "services" / "story_continuation_service.py",
        _API / "services" / "storyline_automation_service.py",
        _API / "services" / "narrative_first_linking_service.py",
        _API / "services" / "ai_storyline_discovery.py",
    ]
    for path in files:
        src = path.read_text(encoding="utf-8")
        assert "allow_storyline_membership_attach" in src, path.name


def test_hub_facets_config_loaded_for_pipeline_domains():
    dsc = _load_domain_synthesis_config()
    for dk in ("legal", "politics", "finance", "medicine", "artificial-intelligence"):
        facets = dsc.get_domain_hub_facets(dk)
        assert facets, f"expected hub_facets for {dk}"
        assert all(f.key and f.role in ("who", "what", "where") for f in facets)
    legal = dsc.get_domain_synthesis_config("legal")
    assert legal.match_hub_facet("SCOTUS") is not None
    assert legal.match_hub_facet("Abbott Laboratories") is None
    politics = dsc.get_domain_synthesis_config("politics")
    assert politics.match_hub_facet("White House") is not None
    finance = dsc.get_domain_synthesis_config("finance")
    assert finance.match_hub_facet("Federal Reserve") is not None or finance.match_hub_facet(
        "Fed"
    )
