"""Unit tests for PipelineController phase health / stall-yield."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_API = Path(__file__).resolve().parents[2] / "api" / "services" / "pipeline_controller.py"
_spec = importlib.util.spec_from_file_location("pipeline_controller", _API)
assert _spec and _spec.loader
pc = importlib.util.module_from_spec(_spec)
sys.modules["pipeline_controller"] = pc
_spec.loader.exec_module(pc)

assess_phase_health = pc.assess_phase_health


def test_assess_phase_health_in_flight_activity_avoids_stall():
    pending = {"unified_intake_extraction": 9000}
    hist = {"unified_intake_extraction": [9000, 9000, 9000]}
    activity = {
        "task_name": "unified_intake_extraction",
        "loops_processed": 0,
        "started_at": "2026-07-05T22:00:00+00:00",
    }
    health = assess_phase_health(
        "unified_intake_extraction",
        pending,
        hist,
        run_history_rows=[],
        activity_progress=activity,
    )
    assert health.status == "slow"
    assert health.detail == "drain in-flight"


def test_assess_phase_health_empty_history_stalls_without_activity():
    pending = {"entity_profile_build": 12000}
    hist = {"entity_profile_build": [12000, 12000, 12000]}
    health = assess_phase_health(
        "entity_profile_build",
        pending,
        hist,
        run_history_rows=[],
        activity_progress=None,
    )
    assert health.status == "stalled"


def test_assess_phase_health_batch_round_counts_as_moving():
    pending = {"unified_intake_extraction": 9000}
    hist = {"unified_intake_extraction": [9000, 9000, 9000]}
    health = assess_phase_health(
        "unified_intake_extraction",
        pending,
        hist,
        run_history_rows=[{"articles_processed": 4, "success": True}],
        activity_progress=None,
    )
    assert health.status == "moving"


def test_assess_phase_health_activity_loops_slow():
    pending = {"entity_profile_build": 12000}
    hist = {"entity_profile_build": [12000, 12000]}
    activity = {
        "task_name": "entity_profile_build",
        "loops_processed": 3,
        "total_processed": 3,
    }
    health = assess_phase_health(
        "entity_profile_build",
        pending,
        hist,
        run_history_rows=[],
        activity_progress=activity,
    )
    assert health.status == "moving"
    assert "total_processed=3" in health.detail
