"""Neurodiversity topic_filter.include_keywords allowlist (ingest gate).

Loads domain_synthesis_config by path so services/__init__.py does not pull DB.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_API = Path(__file__).resolve().parents[2] / "api"
_MOD_PATH = _API / "services" / "domain_synthesis_config.py"


def _load_mod():
    spec = importlib.util.spec_from_file_location(
        "domain_synthesis_config_under_test", _MOD_PATH
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_neurodiversity_config_has_include_keywords():
    mod = _load_mod()
    mod.reload_config()
    cfg = mod.get_domain_synthesis_config("neurodiversity")
    assert cfg.topic_filter.include_keywords
    assert any("autism" in k for k in cfg.topic_filter.include_keywords)
    assert any("adhd" in k for k in cfg.topic_filter.include_keywords)
    # Broad neuro* / developmental terms are not opt-in keys
    assert not any(k.startswith("neurodiverg") for k in cfg.topic_filter.include_keywords)
    assert not any("developmental" in k for k in cfg.topic_filter.include_keywords)
    assert cfg.passes_include_topic_gate("ADHD medication response in adults")
    assert cfg.passes_include_topic_gate("Autism spectrum cohort study")
    assert cfg.passes_include_topic_gate("AuDHD traits in adults")
    assert cfg.passes_include_topic_gate("ASD comorbidity in clinic samples")
    assert not cfg.passes_include_topic_gate("Neurodiversity workplace survey")
    assert "asd" in cfg.topic_filter.include_keywords
    assert not cfg.passes_include_topic_gate(
        "Theta oscillations in hippocampal CA1 during spatial navigation"
    )
    assert not cfg.passes_include_topic_gate(
        "Major depressive disorder GWAS meta-analysis"
    )


def test_topic_gate_text_omits_empty_and_supports_surfaces():
    mod = _load_mod()
    assert "ADHD" in mod.topic_gate_text("ADHD study", "body text")
    assert "abstract" in mod.topic_gate_text(None, None, abstract="abstract only")
    # feed_name must not be mixed in by the helper — callers pass it separately for excludes
    assert "PubMed" not in mod.topic_gate_text("title", "body", extra=None)


def test_empty_include_keywords_passes_everything():
    mod = _load_mod()
    cfg = mod.DomainSynthesisConfig(
        domain_key="demo",
        topic_filter=mod.TopicFilter(include_keywords=[]),
    )
    assert cfg.passes_include_topic_gate("anything at all")


def test_politics_has_no_include_allowlist():
    mod = _load_mod()
    mod.reload_config()
    cfg = mod.get_domain_synthesis_config("politics")
    assert not cfg.topic_filter.include_keywords
    assert cfg.passes_include_topic_gate("unrelated neuroscience preprint title")


def test_pulse_style_opt_in_filter_for_neurodiversity_cards():
    """Mirror pulse _filter_pulse_items: domain filter uses neurodiversity allowlist."""
    mod = _load_mod()
    mod.reload_config()
    cfg = mod.get_domain_synthesis_config("neurodiversity")

    def keep(title: str) -> bool:
        return cfg.passes_include_topic_gate(title)

    assert keep("ADHD comorbidity study")
    assert keep("AuDHD traits in clinic samples")
    assert not keep("Neurodiversity workplace survey")
    assert not keep("General psychiatry preprint dump")
