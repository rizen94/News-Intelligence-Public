"""Unit tests for collision sampling helpers (stage + config flags + guided priors)."""

from __future__ import annotations

import importlib.util
import random
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


def _load_embedding_link():
    import sys
    from unittest.mock import MagicMock

    sys.modules.setdefault("shared.database.connection", MagicMock())
    sys.modules.setdefault(
        "shared.domain_registry",
        MagicMock(
            get_pipeline_active_domain_keys=lambda: ["politics"],
            resolve_domain_schema=lambda k: k.replace("-", "_"),
        ),
    )
    _rt = MagicMock()
    _rt.env_str = lambda k, d="": d
    _rt.env_int = lambda k, d=0: int(d)
    _rt.env_float = lambda k, d=0.0: float(d)
    sys.modules["config.runtime"] = _rt
    path = (
        Path(__file__).resolve().parents[2]
        / "api"
        / "services"
        / "embedding_link_candidate_service.py"
    )
    name = "emb_collision_test"
    if name in sys.modules:
        del sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
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


def test_collision_prior_prefers_high_overlap():
    emb = _load_embedding_link()
    high = emb._collision_pair_prior(
        centroid_cos=0.9, entity_jaccard=0.8, temporal_proximity=1.0
    )
    low = emb._collision_pair_prior(
        centroid_cos=0.1, entity_jaccard=0.0, temporal_proximity=0.2
    )
    assert high > low


def test_guided_weighted_sample_prefers_high_prior():
    """With fixed RNG seed, weighted choices prefer the high-overlap pair."""
    random.seed(42)
    pool = [
        (0.05, 1, 2, {}),
        (0.90, 3, 4, {}),
        (0.05, 5, 6, {}),
    ]
    picks = []
    for _ in range(40):
        weights = [w[0] for w in pool]
        idx = random.choices(range(len(pool)), weights=weights, k=1)[0]
        picks.append(pool[idx][1:3])
    # Majority should be the high-prior pair (3,4)
    assert picks.count((3, 4)) > picks.count((1, 2))
    assert picks.count((3, 4)) > picks.count((5, 6))
