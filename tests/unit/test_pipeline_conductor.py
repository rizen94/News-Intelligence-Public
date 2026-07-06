"""Unit tests for pipeline conductor — orchestrator ↔ automation connectivity."""

import importlib.util
from pathlib import Path
from unittest.mock import patch

_API = Path(__file__).resolve().parents[2] / "api" / "services" / "pipeline_conductor_service.py"
_spec = importlib.util.spec_from_file_location("pipeline_conductor_service", _API)
assert _spec and _spec.loader
pcs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pcs)

_FALLBACK_PIPELINE_PHASES = pcs._FALLBACK_PIPELINE_PHASES
get_effective_processing_phases = pcs.get_effective_processing_phases
get_post_collection_kickoff_phases = pcs.get_post_collection_kickoff_phases
should_orchestrator_request_phase = pcs.should_orchestrator_request_phase


def test_effective_processing_phases_includes_full_pipeline():
    with patch.object(
        pcs,
        "_automation_pipeline_phases",
        return_value=_FALLBACK_PIPELINE_PHASES,
    ):
        phases = get_effective_processing_phases()
    assert "claim_extraction" in phases
    assert "mention_resolution" in phases
    assert "claims_to_facts" in phases
    assert "collection_cycle" not in phases
    assert phases["topic_clustering"]["scope"] == "domain"
    assert phases["storyline_automation"]["scope"] == "storyline"
    assert phases["context_sync"]["interval_seconds"] == 900


def test_post_collection_kickoff_defaults():
    with patch("shared.spine_phase_order.spine_pipeline_ordered_active", return_value=False):
        phases = get_post_collection_kickoff_phases()
    assert "content_enrichment" in phases
    assert "context_sync" in phases


def test_should_orchestrator_request_phase_retired():
    """PipelineController owns enqueue; orchestrator nudge path is retired."""
    ok = should_orchestrator_request_phase(
        "entity_extraction",
        {
            "pending_counts": {"entity_extraction": 50},
            "active_tasks_by_phase": {},
            "queued_tasks_by_phase": {},
        },
    )
    assert ok is False
