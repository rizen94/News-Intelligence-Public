"""Unit tests for domain story_kind + link_score_profile (chemistry model)."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_domain_synthesis_config():
    path = (
        Path(__file__).resolve().parents[2]
        / "api"
        / "services"
        / "domain_synthesis_config.py"
    )
    spec = importlib.util.spec_from_file_location("domain_synthesis_config", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._normalise_domain_key = lambda k: (k or "").strip().lower().replace("_", "-")
    return mod


def setup_function():
    _load_domain_synthesis_config().reload_config()


def test_story_kinds_per_domain():
    dsc = _load_domain_synthesis_config()
    assert dsc.get_domain_synthesis_config("politics").story_kind == "event_narrative"
    assert dsc.get_domain_synthesis_config("finance").story_kind == "market_regulatory_arc"
    assert dsc.get_domain_synthesis_config("legal").story_kind == "matter_docket"
    assert dsc.get_domain_synthesis_config("medicine").story_kind == "evidence_thread"
    assert (
        dsc.get_domain_synthesis_config("artificial-intelligence").story_kind
        == "research_topic"
    )


def test_chemistry_kinds_flag():
    dsc = _load_domain_synthesis_config()
    assert not dsc.get_domain_synthesis_config("politics").is_chemistry_kind()
    assert dsc.get_domain_synthesis_config("artificial-intelligence").is_chemistry_kind()
    assert dsc.get_domain_synthesis_config("legal").is_chemistry_kind()


def test_attach_score_differs_by_domain():
    """Same signals: AI weights semantic/keyword higher than politics."""
    dsc = _load_domain_synthesis_config()
    kwargs = dict(relevance=0.4, semantic=0.9, keyword=0.8, quality=0.5)
    pol = dsc.combined_attach_score("politics", **kwargs)
    ai = dsc.combined_attach_score("artificial-intelligence", **kwargs)
    assert ai > pol


def test_ai_disallows_aggressive_merge():
    dsc = _load_domain_synthesis_config()
    ai = dsc.get_domain_synthesis_config("artificial-intelligence")
    assert ai.link_score_profile.allow_storyline_merge is False
    assert ai.link_score_profile.aggressive_membership is False
    pol = dsc.get_domain_synthesis_config("politics")
    assert pol.link_score_profile.allow_storyline_merge is True
