"""Unit tests for collision sampling helpers (stage + config flags)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from shared.connection_inference import (
    INFERENCE_HYPOTHESIZED,
    stage_for_embedding_source,
)


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
    # Avoid domain_registry DB at import/normalize time
    mod._normalise_domain_key = lambda k: (k or "").strip().lower().replace("_", "-")
    return mod


def test_exploratory_stage_is_hypothesized():
    assert stage_for_embedding_source(exploratory=True) == INFERENCE_HYPOTHESIZED


def test_ai_domain_is_chemistry_research_topic():
    dsc = _load_domain_synthesis_config()
    dsc.reload_config()
    cfg = dsc.get_domain_synthesis_config("artificial-intelligence")
    assert cfg.story_kind == "research_topic"
    assert cfg.is_chemistry_kind()
    assert not cfg.link_score_profile.allow_storyline_merge
    assert not cfg.link_score_profile.aggressive_membership


def test_politics_allows_merge_and_membership():
    dsc = _load_domain_synthesis_config()
    dsc.reload_config()
    cfg = dsc.get_domain_synthesis_config("politics")
    assert cfg.story_kind == "event_narrative"
    assert cfg.link_score_profile.allow_storyline_merge
    assert cfg.link_score_profile.aggressive_membership
