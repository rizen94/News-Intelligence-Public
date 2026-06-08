"""Per-domain storyline_development config resolution."""

from services.domain_synthesis_config import (
    get_domain_synthesis_config,
    get_storyline_development_config,
    reload_config,
)


def setup_function() -> None:
    reload_config()


def test_politics_discovery_stricter_than_medicine():
    politics = get_storyline_development_config("politics")
    medicine = get_storyline_development_config("medicine")
    assert politics.discovery.clustering_similarity_threshold > medicine.discovery.clustering_similarity_threshold
    assert politics.discovery.min_cluster_size >= medicine.discovery.min_cluster_size


def test_medicine_outbreak_promote_enabled():
    med = get_storyline_development_config("medicine")
    assert med.narrative.allow_promote_pair_on_outbreak is True
    assert "hantavirus" in med.narrative.outbreak_keywords
    assert med.proactive.min_articles <= 2


def test_legacy_top_level_clustering_keys_merged():
    legal = get_domain_synthesis_config("legal")
    assert legal.clustering_similarity_threshold == 0.58
    assert legal.storyline_min_cluster_size == 2


def test_narrative_prompt_context_includes_patterns():
    med = get_domain_synthesis_config("medicine")
    ctx = med.narrative_prompt_context()
    assert "outbreak" in ctx.lower() or "trial" in ctx.lower()


def test_politics_finance_storyline_config_present():
    reload_config()
    pol = get_storyline_development_config("politics")
    fin = get_storyline_development_config("finance")
    assert pol.discovery.clustering_similarity_threshold > 0
    assert fin.consolidation.merge_similarity_threshold > 0
