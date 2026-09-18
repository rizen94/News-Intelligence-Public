"""Medicine bioRxiv URL-scoped include gate + curated subjects."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_API = Path(__file__).resolve().parents[2] / "api"
_MOD_PATH = _API / "services" / "domain_synthesis_config.py"


def _load_mod():
    spec = importlib.util.spec_from_file_location(
        "domain_synthesis_config_under_test_med", _MOD_PATH
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_medicine_feed_url_include_gate_blocks_ecology_on_subject_all():
    mod = _load_mod()
    mod.reload_config()
    cfg = mod.get_domain_synthesis_config("medicine")
    rules = cfg.topic_filter.include_keywords_for_feed_url_substrings
    assert "biorxiv_xml.php?subject=all" in rules
    feed = "https://connect.biorxiv.org/biorxiv_xml.php?subject=all"
    assert not cfg.passes_feed_url_include_gate(
        "Arabidopsis thaliana drought response in plant ecology", feed
    )
    assert cfg.passes_feed_url_include_gate(
        "Randomized clinical trial of immunotherapy in cancer patients", feed
    )
    # Curated subject feeds are not gated by the subject=all rule
    curated = "https://connect.biorxiv.org/biorxiv_xml.php?subject=immunology"
    assert cfg.passes_feed_url_include_gate(
        "Arabidopsis thaliana drought response in plant ecology", curated
    )


def test_medicine_yaml_has_no_subject_all():
    yaml_path = _API / "config" / "domains" / "medicine.yaml"
    text = yaml_path.read_text(encoding="utf-8")
    assert "subject=all" not in text
    assert "subject=pathology" in text
    assert "subject=neuroscience" not in text


def test_medicine_spec_has_curated_biorxiv_subjects():
    import json

    spec = json.loads(
        (_API / "config" / "domains" / "specs" / "medicine.domain.json").read_text()
    )
    urls = [f.get("feed_url", "") for f in (spec.get("rss") or {}).get("feeds") or []]
    assert not any("subject=all" in u for u in urls)
    for subj in (
        "pathology",
        "immunology",
        "microbiology",
        "pharmacology_and_toxicology",
        "genetics",
        "genomics",
        "cancer_biology",
        "epidemiology",
        "clinical_trials",
        "physiology",
    ):
        assert any(f"subject={subj}" in u for u in urls), subj
