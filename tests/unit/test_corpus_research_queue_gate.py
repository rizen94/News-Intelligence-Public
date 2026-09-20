"""Corpus domain must report zero depth contribution on research phases (static SSOT)."""

from __future__ import annotations

import pytest

from shared import domain_processing_mode as dpm
from shared.domain_processing_mode import (
    RESEARCH_PHASES,
    clear_processing_mode_caches,
    domain_runs_phase,
    filter_domains_for_phase,
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
        "medicine": "research",
        "politics": "research",
    }

    def _modes() -> dict[str, str]:
        return dict(mapping)

    monkeypatch.setattr(dpm, "get_domain_processing_modes", _modes)
    return mapping


def test_corpus_domain_skips_all_research_phases(modes):
    for phase in sorted(RESEARCH_PHASES):
        assert domain_runs_phase("neurodiversity", phase) is False, phase
        assert domain_runs_phase("politics", phase) is True, phase


def test_filter_domains_excludes_corpus_from_storyline_assembly(modes):
    out = filter_domains_for_phase(
        ["neurodiversity", "medicine", "politics"],
        "storyline_assembly",
    )
    assert "neurodiversity" not in out
    assert set(out) == {"medicine", "politics"}
