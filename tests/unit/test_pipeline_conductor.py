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
orchestrator_processing_nudge_enabled = pcs.orchestrator_processing_nudge_enabled
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
    assert "entity_extraction" in phases
    assert "collection_cycle" not in phases
    assert phases["topic_clustering"]["scope"] == "domain"
    assert phases["storyline_automation"]["scope"] == "storyline"
    assert phases["context_sync"]["interval_seconds"] == 900


def test_post_collection_kickoff_defaults():
    phases = get_post_collection_kickoff_phases()
    assert "content_enrichment" in phases
    assert "context_sync" in phases


def test_should_orchestrator_request_phase_skips_when_automation_is_draining():
    with patch.object(
        pcs, "orchestrator_processing_nudge_enabled", return_value=True
    ), patch.object(
        pcs, "workload_driven_scheduling_enabled", return_value=True
    ):
        ok = should_orchestrator_request_phase(
            "entity_extraction",
            {
                "pending_counts": {"entity_extraction": 50},
                "active_tasks_by_phase": {"entity_extraction": 1},
                "queued_tasks_by_phase": {},
            },
        )
    assert ok is False


def test_should_orchestrator_request_phase_nudges_stuck_backlog():
    with patch.object(
        pcs, "orchestrator_processing_nudge_enabled", return_value=True
    ), patch.object(
        pcs, "workload_driven_scheduling_enabled", return_value=True
    ):
        ok = should_orchestrator_request_phase(
            "entity_extraction",
            {
                "pending_counts": {"entity_extraction": 50},
                "active_tasks_by_phase": {},
                "queued_tasks_by_phase": {},
                "schedules": {},
            },
        )
    assert ok is True


def test_should_orchestrator_request_phase_allows_idle_phase():
    with patch.object(
        pcs, "orchestrator_processing_nudge_enabled", return_value=True
    ), patch.object(
        pcs, "workload_driven_scheduling_enabled", return_value=True
    ):
        ok = should_orchestrator_request_phase(
            "claim_extraction",
            {
                "pending_counts": {"claim_extraction": 0},
                "active_tasks_by_phase": {},
                "queued_tasks_by_phase": {},
                "schedules": {},
            },
        )
    assert ok is True


def test_nudge_enabled_from_yaml_default():
    with patch.object(
        pcs,
        "get_conductor_config",
        return_value={
            "automation_primary": True,
            "orchestrator_processing_nudge_enabled": True,
        },
    ):
        assert orchestrator_processing_nudge_enabled() is True
