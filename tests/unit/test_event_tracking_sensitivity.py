"""Event tracking sensitivity gates."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import patch


def test_min_articles_default_raised():
    from config.settings import event_tracking_min_articles_per_event

    with patch.dict("os.environ", {}, clear=False):
        os.environ.pop("EVENT_TRACKING_MIN_ARTICLES_PER_EVENT", None)
        assert event_tracking_min_articles_per_event() == 4


def test_min_articles_env_override():
    from config.settings import event_tracking_min_articles_per_event

    with patch.dict("os.environ", {"EVENT_TRACKING_MIN_ARTICLES_PER_EVENT": "6"}):
        assert event_tracking_min_articles_per_event() == 6


def test_storyline_overlap_default():
    from config.settings import event_tracking_storyline_min_entity_overlap

    os.environ.pop("EVENT_TRACKING_STORYLINE_MIN_ENTITY_OVERLAP", None)
    assert event_tracking_storyline_min_entity_overlap() == 3


def test_prompt_requires_min_articles_placeholder():
    path = (
        Path(__file__).resolve().parents[2]
        / "api"
        / "services"
        / "event_tracking_service.py"
    )
    text = path.read_text(encoding="utf-8")
    assert "{min_articles}" in text
    assert "Fed rate decision March 2026" in text
    assert "Do not invent names" in text or "never invent" in text.lower()


def test_chronicle_relevance_rejects_unrelated_politics_title():
    import importlib.util
    import sys
    import types
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[2]
        / "api"
        / "services"
        / "event_tracking_service.py"
    )
    sys.modules.setdefault(
        "shared.services.llm_service",
        types.SimpleNamespace(LLMService=object, ModelType=object),
    )
    sys.modules.setdefault(
        "services.commodity_event_bridge",
        types.SimpleNamespace(maybe_append_finance_domain_key=lambda *a, **k: None),
    )
    sys.modules.setdefault(
        "config.runtime",
        types.SimpleNamespace(
            env_bool=lambda *a, **k: False,
            env_float=lambda *a, **k: 0.0,
            env_int=lambda *a, **k: 0,
            env_pop=lambda *a, **k: None,
            env_set=lambda *a, **k: None,
            env_setdefault=lambda *a, **k: None,
            env_str=lambda *a, **k: a[1] if len(a) > 1 else "",
        ),
    )
    spec = importlib.util.spec_from_file_location("event_tracking_service_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    name = "Research Breakthroughs in Large Language Models"
    assert any("language models" in p.lower() for p in mod.significant_event_phrases(name))
    assert not mod.development_title_matches_event(
        name,
        "Burnham must shift UK mood on racism, chair of Operation Black Vote says",
    )
    assert not mod.development_title_matches_event(
        name,
        "A Durability and Cross-Language Transfer Benchmark for a Validated Teaching-Feedback Classification Protocol",
    )
    assert mod.development_title_matches_event(
        name, "OpenAI announces breakthroughs in large language models"
    )
    assert mod.development_title_matches_event(
        name, "New language models beat benchmarks on reasoning"
    )