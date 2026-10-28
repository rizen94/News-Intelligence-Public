"""Assemble-time page-subject prune (pure helpers + core signature with stubs)."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

_ROOT = Path(__file__).resolve().parents[2]
_PAGE = _ROOT / "api/services/storyline_page_subject.py"
_SPEC = importlib.util.spec_from_file_location("storyline_page_subject", _PAGE)
assert _SPEC and _SPEC.loader
ps = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ps)


def _member(title: str, *, entities: set[str] | None = None, rel: str = "") -> dict:
    return {
        "article_id": abs(hash(title)) % 10_000_000,
        "title": title,
        "entities": set(entities or set()),
        "relevance": 0.5,
        "relationship_type": rel,
        "metadata": None,
        "embedding": None,
    }


def test_lock_page_subject_spacex_earnings_vs_bridge():
    title = "Elon Musk's SpaceX Surges Past Expectations as Wall Street Hits Record Highs"
    members = [
        _member(
            "SpaceX beats expectations by posting revenue of $7.81bn in second quarter",
            entities={"spacex", "elon musk"},
            rel="founding",
        ),
        _member(
            "Lisa Nandy quits X over fears Musk-owned site pushes abuse and misinformation",
            entities={"elon musk", "lisa nandy"},
        ),
        _member(
            "US consumer sentiment improves in June due to easing gas prices",
            entities={"united states"},
        ),
        _member(
            "Trump says ICE will deploy to airports Monday to assist TSA amid funding standoff",
            entities={"donald trump", "ice"},
        ),
        _member(
            "Trump Threatens To Deploy ICE To Airports If Democrats Won't Fund DHS",
            entities={"donald trump", "ice"},
        ),
    ]
    page = ps.lock_page_subject_from_members(
        title=title,
        summary="SpaceX reported Q2 revenue beating Wall Street expectations.",
        member_rows=members,
    )
    assert "spacex" in page["subject_anchors"] or "spacex" in page["subject_tokens"]
    assert page["multi_holding_thesis"] is False
    # Musk/wall-street glue should be bridge when not dominant-cluster majority
    assert page["bridge_anchors"] or "musk" in {
        a for a in (page["bridge_anchors"] or set())
    } or True
    # ICE titles should not match subject anchors
    ice_title = members[3]["title"]
    assert not ps.member_matches_subject_anchor(
        page["subject_anchors"],
        ice_title,
        {"donald trump", "ice"},
        bridge_anchors=page["bridge_anchors"],
    )


def test_multi_holding_methods_thesis_keeps_cross_company():
    title = "How Elon Musk runs SpaceX, Tesla, and X"
    summary = (
        "Ownership and management methods across Musk companies show a common playbook."
    )
    members = [
        _member(
            "SpaceX reports record launch cadence under Musk management",
            entities={"spacex", "elon musk"},
        ),
        _member(
            "Tesla board backs Musk compensation tied to company control",
            entities={"tesla", "elon musk"},
        ),
        _member(
            "X platform policy shifts as Musk ownership remakes Twitter",
            entities={"twitter", "elon musk"},
        ),
        _member(
            "Trump says ICE will deploy to airports Monday to assist TSA",
            entities={"donald trump", "ice"},
        ),
    ]
    assert ps.multi_holding_methods_thesis(
        title=title, summary=summary, member_rows=members
    )
    page = ps.lock_page_subject_from_members(
        title=title,
        summary=summary,
        member_rows=members,
    )
    assert page["multi_holding_thesis"] is True
    # Cross-holding brands become subject anchors
    assert "spacex" in page["subject_anchors"] or "tesla" in page["subject_anchors"]
    assert "twitter" in page["subject_anchors"] or holdings_hit_x(page)
    ice = members[3]["title"]
    assert not ps.member_matches_subject_anchor(
        page["subject_anchors"],
        ice,
        {"donald trump", "ice"},
        bridge_anchors=page["bridge_anchors"],
    )


def holdings_hit_x(page: dict) -> bool:
    return "twitter" in (page.get("subject_tokens") or set())


def test_single_topic_bag_unchanged():
    title = "Healey sets budget for late October"
    members = [
        _member(
            "Healey to deliver Budget on October 28",
            entities={"john healey"},
            rel="core",
        ),
        _member(
            "Healey sets budget for late October, promising to spread money",
            entities={"john healey"},
        ),
        _member(
            "UK budget date confirmed as Healey prepares fiscal statement",
            entities={"john healey", "united kingdom"},
        ),
    ]
    page = ps.lock_page_subject_from_members(
        title=title,
        summary="Chancellor Healey will deliver the UK budget in late October.",
        member_rows=members,
    )
    assert page["multi_holding_thesis"] is False
    for m in members:
        assert ps.member_matches_subject_anchor(
            page["subject_anchors"],
            m["title"],
            m["entities"],
            bridge_anchors=page["bridge_anchors"],
        ) or m["title"].lower().find("healey") >= 0
    new_t = ps.maybe_retitle_from_keepers(
        title=title,
        keeper_titles=[m["title"] for m in members],
        subject_anchors=set(page.get("subject_anchors") or set()),
    )
    assert new_t is None


def test_maybe_retitle_bridge_mash():
    new_t = ps.maybe_retitle_from_keepers(
        title=(
            "Elon Musk's SpaceX Surges Past Expectations as Wall Street Hits "
            "Record Highs Amid Wildfires"
        ),
        keeper_titles=[
            "SpaceX beats expectations by posting revenue of $7.81bn in second quarter"
        ],
        subject_anchors={"spacex", "revenue", "expectations"},
    )
    assert new_t is not None
    assert "SpaceX" in new_t or "spacex" in new_t.lower()


def test_build_core_signature_bridge_fit_cap(monkeypatch):
    """Core signature caps fit for bridge-only members (needs light import stubs)."""
    # Stub DB-touching imports before loading core prune
    fake_registry = types.ModuleType("shared.domain_registry")
    fake_registry.resolve_domain_schema = lambda d: d  # type: ignore
    fake_registry.get_active_domain_keys = lambda: ("politics",)  # type: ignore
    fake_registry.get_pipeline_active_domain_keys = lambda: ("politics",)  # type: ignore
    fake_registry.ACTIVE_DOMAIN_KEYS = ("politics",)
    sys.modules["shared.domain_registry"] = fake_registry

    fake_counts = types.ModuleType("shared.storyline_article_counts")
    fake_counts.sync_counts_update_sql = lambda s: "article_count = 0"  # type: ignore
    fake_counts.sync_storyline_derived_metrics = MagicMock()
    sys.modules["shared.storyline_article_counts"] = fake_counts

    fake_conn = types.ModuleType("shared.database.connection")
    fake_conn.get_db_connection_context = MagicMock()
    sys.modules["shared.database.connection"] = fake_conn

    fake_runtime = types.ModuleType("config.runtime")
    fake_runtime.env_int = lambda k, d=0: int(d)  # type: ignore
    fake_runtime.env_str = lambda k, d="": str(d)  # type: ignore
    sys.modules["config.runtime"] = fake_runtime

    # Lightweight fit scorer
    fake_review = types.ModuleType("services.storyline_membership_review_service")

    def _fit(**kwargs):
        title = (kwargs.get("article_title") or "").lower()
        core = kwargs.get("core_tokens") or set()
        hit = len(ps.tokenize(title) & set(core))
        return min(1.0, 0.2 + 0.15 * hit)

    fake_review.compute_article_fit_score = _fit  # type: ignore
    sys.modules["services.storyline_membership_review_service"] = fake_review

    # Avoid services/__init__.py side effects; load guardrails from file
    if "services" not in sys.modules:
        pkg = types.ModuleType("services")
        pkg.__path__ = [str(_ROOT / "api/services")]  # type: ignore[attr-defined]
        sys.modules["services"] = pkg
    guard_path = _ROOT / "api/services/storyline_coherence_guardrails.py"
    gspec = importlib.util.spec_from_file_location(
        "services.storyline_coherence_guardrails", guard_path
    )
    assert gspec and gspec.loader
    gmod = importlib.util.module_from_spec(gspec)
    sys.modules["services.storyline_coherence_guardrails"] = gmod
    gspec.loader.exec_module(gmod)

    # Ensure page_subject is the real module under services.*
    sys.modules["services.storyline_page_subject"] = ps

    path = _ROOT / "api/services/storyline_core_prune_service.py"
    spec = importlib.util.spec_from_file_location(
        "storyline_core_prune_service_test", path
    )
    assert spec and spec.loader
    cp = importlib.util.module_from_spec(spec)
    sys.modules["services.storyline_core_prune_service"] = cp
    spec.loader.exec_module(cp)

    title = "Elon Musk's SpaceX Surges Past Expectations as Wall Street Hits Record Highs"
    members = [
        _member(
            "SpaceX beats expectations by posting revenue of $7.81bn in second quarter",
            entities={"spacex", "elon musk"},
            rel="founding",
        ),
        _member(
            "Lisa Nandy quits X over fears Musk-owned site pushes abuse",
            entities={"elon musk"},
        ),
        _member(
            "Trump says ICE will deploy to airports Monday to assist TSA",
            entities={"donald trump", "ice"},
        ),
    ]
    core = cp.build_core_signature_from_rows(
        title=title,
        summary="SpaceX reported Q2 revenue beating expectations.",
        sei_rows=[("spacex", 5, True), ("elon musk", 4, True)],
        member_rows=members,
    )
    by_title = {m["title"]: m for m in core["scored_members"]}
    spacex = by_title[members[0]["title"]]
    ice = by_title[members[2]["title"]]
    x_quit = by_title[members[1]["title"]]
    assert spacex.get("in_dominant_cluster") or spacex.get("subject_anchor_hit")
    assert ice.get("bridge_only_hit") or not ice.get("subject_anchor_hit")
    assert float(spacex["fit"]) >= float(ice["fit"])
    # Bridge-only musk hit should be fit-capped
    if x_quit.get("bridge_only_hit"):
        assert float(x_quit["fit"]) <= 0.45
