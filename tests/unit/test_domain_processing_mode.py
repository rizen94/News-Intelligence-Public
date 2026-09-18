"""Unit tests for corpus vs research processing-mode gate."""

from __future__ import annotations

import pytest

from shared import domain_processing_mode as dpm
from shared.domain_processing_mode import (
    CORPUS_PHASES,
    RESEARCH_PHASES,
    clear_processing_mode_caches,
    domain_runs_phase,
    filter_domains_for_phase,
    get_domain_processing_mode,
    is_corpus_domain,
    phase_band,
)


@pytest.fixture(autouse=True)
def _clear_caches():
    clear_processing_mode_caches()
    yield
    clear_processing_mode_caches()


@pytest.fixture
def modes(monkeypatch):
    monkeypatch.setenv("PROCESSING_MODE_ENFORCE", "true")
    mapping = {
        "neurodiversity": "corpus",
        "politics": "research",
        "medicine": "research",
    }

    def _modes() -> dict[str, str]:
        return dict(mapping)

    # Replace the cached loader without breaking cache_clear on teardown.
    monkeypatch.setattr(dpm, "get_domain_processing_modes", _modes)
    return mapping


def test_corpus_domain_refuses_research_phases(modes):
    assert is_corpus_domain("neurodiversity")
    assert get_domain_processing_mode("neurodiversity") == "corpus"
    for phase in (
        "storyline_assembly",
        "storyline_automation",
        "collision_sampling",
        "embedding_link_candidates",
        "protein_harden",
        "stimulus_rag",
        "editorial_room_loop",
        "entity_profile_build",
        "event_tracking",
        "story_continuation",
        "storyline_membership_review",
        "graph_connection_distillation",
    ):
        assert phase in RESEARCH_PHASES
        assert domain_runs_phase("neurodiversity", phase) is False


def test_corpus_domain_allows_corpus_phases(modes):
    for phase in ("content_enrichment", "unified_intake_extraction", "topic_clustering"):
        assert phase in CORPUS_PHASES
        assert domain_runs_phase("neurodiversity", phase) is True


def test_research_domain_allows_both_bands(modes):
    assert domain_runs_phase("politics", "storyline_assembly") is True
    assert domain_runs_phase("politics", "content_enrichment") is True
    assert domain_runs_phase("medicine", "entity_profile_build") is True


def test_unknown_phase_fail_open(modes):
    assert phase_band("totally_unknown_phase_xyz") is None
    assert domain_runs_phase("neurodiversity", "totally_unknown_phase_xyz") is True
    assert domain_runs_phase("politics", "totally_unknown_phase_xyz") is True


def test_filter_domains_for_phase(modes):
    domains = ["neurodiversity", "politics", "medicine"]
    research_only = filter_domains_for_phase(domains, "storyline_assembly")
    assert research_only == ["politics", "medicine"]
    corpus_ok = filter_domains_for_phase(domains, "content_enrichment")
    assert corpus_ok == domains
    unknown = filter_domains_for_phase(domains, "custom_ops_phase")
    assert unknown == domains


def test_enforce_off_disables_gate(monkeypatch, modes):
    monkeypatch.setenv("PROCESSING_MODE_ENFORCE", "0")
    assert domain_runs_phase("neurodiversity", "storyline_assembly") is True
