"""Unit tests for content-aware membership scoring."""

from __future__ import annotations

import math

import pytest

from shared.membership_scoring import (
    MembershipScore,
    combine_membership_parts,
    score_article_against_signals,
)


def test_combine_rejects_no_canonical_low_semantic(monkeypatch):
    class _P:
        relevance_weight = 0.40
        semantic_weight = 0.15
        keyword_weight = 0.10
        quality_weight = 0.10
        temporal_weight = 0.10
        canonical_entity_weight = 0.15
        vault_boost_cap = 0.03
        semantic_alone_floor = 0.55

    class _C:
        link_score_profile = _P()

    monkeypatch.setattr(
        "services.domain_synthesis_config.get_domain_synthesis_config",
        lambda _dk: _C(),
    )
    ms = combine_membership_parts(
        domain_key="politics",
        canonical=0.0,
        relevance=0.2,
        semantic=0.2,
        keyword=0.1,
        quality=0.8,
        temporal=0.7,
    )
    assert ms.rejected
    assert ms.combined == 0.0
    assert "no_canonical" in ms.reject_reason


def test_combine_accepts_canonical_overlap(monkeypatch):
    class _P:
        relevance_weight = 0.40
        semantic_weight = 0.15
        keyword_weight = 0.10
        quality_weight = 0.10
        temporal_weight = 0.10
        canonical_entity_weight = 0.15
        vault_boost_cap = 0.03
        semantic_alone_floor = 0.55

    class _C:
        link_score_profile = _P()

    monkeypatch.setattr(
        "services.domain_synthesis_config.get_domain_synthesis_config",
        lambda _dk: _C(),
    )
    ms = combine_membership_parts(
        domain_key="politics",
        canonical=0.5,
        relevance=0.4,
        semantic=0.3,
        keyword=0.2,
        quality=0.7,
        temporal=0.8,
    )
    assert not ms.rejected
    assert 0.3 < ms.combined < 0.8
    assert "overall" in ms.parts


def test_kitchen_sink_michigan_vs_settlers(monkeypatch):
    """11110-style: Michigan schools should score below MidEast settler article."""

    class _P:
        relevance_weight = 0.40
        semantic_weight = 0.15
        keyword_weight = 0.10
        quality_weight = 0.10
        temporal_weight = 0.10
        canonical_entity_weight = 0.15
        vault_boost_cap = 0.03
        semantic_alone_floor = 0.55
        temporal_half_life_days = 14.0

    class _C:
        link_score_profile = _P()

    monkeypatch.setattr(
        "services.domain_synthesis_config.get_domain_synthesis_config",
        lambda _dk: _C(),
    )

    # Unit vectors: MidEast story centroid near (1,0,0); Michigan near (0,1,0)
    mid_east_centroid = [1.0, 0.0, 0.0]
    mid_east_emb = [0.95, 0.05, 0.0]
    michigan_emb = [0.05, 0.95, 0.0]
    # Normalize
    def _n(v):
        n = math.sqrt(sum(x * x for x in v))
        return [x / n for x in v]

    story_cids = {101, 102}  # netanyahu, israel
    settler = score_article_against_signals(
        domain_key="politics",
        article_canonical_ids={101, 102},
        article_entity_names={"benjamin netanyahu", "israel", "settlers"},
        article_title="Israel has done little to rein in settler violence",
        article_embedding=_n(mid_east_emb),
        article_quality=0.8,
        article_published_at=None,
        story_canonical_ids=story_cids,
        story_core_entities={"benjamin netanyahu", "israel", "west bank"},
        story_title="Netanyahu's Settler Problem Escalates as Iran Tensions Rise",
        story_keywords={"settler", "netanyahu", "iran"},
        story_centroid=_n(mid_east_centroid),
        story_ref_time=None,
    )
    michigan = score_article_against_signals(
        domain_key="politics",
        article_canonical_ids={999},  # unrelated
        article_entity_names={"michigan", "schools"},
        article_title="A renewed push to ban seclusion in Michigan schools",
        article_embedding=_n(michigan_emb),
        article_quality=0.8,
        article_published_at=None,
        story_canonical_ids=story_cids,
        story_core_entities={"benjamin netanyahu", "israel", "west bank"},
        story_title="Netanyahu's Settler Problem Escalates as Iran Tensions Rise",
        story_keywords={"settler", "netanyahu", "iran"},
        story_centroid=_n(mid_east_centroid),
        story_ref_time=None,
    )
    assert settler.combined > michigan.combined
    assert settler.combined >= 0.35
    # Michigan: no shared canonical + weak keyword/entity → rejected
    assert michigan.rejected
    assert michigan.combined == 0.0


def test_membership_score_metadata():
    ms = MembershipScore(combined=0.72, parts={"canonical": 0.5}, rejected=False)
    meta = ms.as_metadata()
    assert meta["combined"] == 0.72
    assert meta["scorer"] == "membership_scoring_v1"
    assert meta["score_parts"]["canonical"] == 0.5


def test_link_score_profile_loaded():
    from services.domain_synthesis_config import get_domain_synthesis_config, reload_config

    reload_config()
    cfg = get_domain_synthesis_config("politics")
    assert cfg.link_score_profile.auto_approve_combined == pytest.approx(0.80)
    assert cfg.link_score_profile.discovery_seed_floor == pytest.approx(0.75)
    assert cfg.link_score_profile.aggressive_membership is False
    assert cfg.link_score_profile.max_member_articles == 32
    assert cfg.link_score_profile.max_storylines_per_article == 3
    assert not cfg.is_chemistry_kind()
    med = get_domain_synthesis_config("medicine")
    assert med.is_chemistry_kind()
