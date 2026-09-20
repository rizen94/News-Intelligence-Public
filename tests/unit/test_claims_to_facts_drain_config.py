"""Config helpers for claims_to_facts drain and nightly batch alignment."""

import importlib.util
from pathlib import Path

_PCS = Path(__file__).resolve().parents[2] / "api" / "services" / "pipeline_conductor_service.py"
_spec = importlib.util.spec_from_file_location("pipeline_conductor_service", _PCS)
assert _spec and _spec.loader
_pcs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_pcs)
_FALLBACK_PIPELINE_PHASES = _pcs._FALLBACK_PIPELINE_PHASES


def test_get_nightly_claims_to_facts_batch_limit_matches_daytime_when_unset(monkeypatch):
    from services import claim_extraction_service as ces

    monkeypatch.delenv("NIGHTLY_CLAIMS_TO_FACTS_BATCH_LIMIT", raising=False)
    monkeypatch.setenv("CLAIMS_TO_FACTS_BATCH_LIMIT", "12345")
    assert ces.get_nightly_claims_to_facts_batch_limit() == 12345


def test_get_nightly_claims_to_facts_batch_limit_explicit_override(monkeypatch):
    from services import claim_extraction_service as ces

    monkeypatch.setenv("NIGHTLY_CLAIMS_TO_FACTS_BATCH_LIMIT", "800")
    assert ces.get_nightly_claims_to_facts_batch_limit() == 800


def test_claims_to_facts_drain_enabled_default(monkeypatch):
    from services import claim_extraction_service as ces

    monkeypatch.delenv("CLAIMS_TO_FACTS_DRAIN", raising=False)
    assert ces.claims_to_facts_drain_enabled() is True
    monkeypatch.setenv("CLAIMS_TO_FACTS_DRAIN", "false")
    assert ces.claims_to_facts_drain_enabled() is False


def test_claims_to_facts_in_effective_processing_phases():
    assert "claims_to_facts" in _FALLBACK_PIPELINE_PHASES


def test_claims_to_facts_backlog_suffix_promotable_hint_default(monkeypatch):
    from services import claim_extraction_service as ces

    monkeypatch.delenv("CLAIMS_TO_FACTS_BACKLOG_COUNT_MODE", raising=False)
    s = ces.build_claims_to_facts_backlog_where_suffix()
    assert "context_entity_mentions" in s
    assert "entity_profiles" in s
    assert "NOT IN" in s


def test_claims_to_facts_backlog_suffix_batch_candidate_mode(monkeypatch):
    from services import claim_extraction_service as ces

    monkeypatch.setenv("CLAIMS_TO_FACTS_BACKLOG_COUNT_MODE", "batch_candidate")
    s = ces.build_claims_to_facts_backlog_where_suffix()
    assert "context_entity_mentions" not in s
    assert "NOT IN" in s
