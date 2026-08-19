"""Flat scheduler mode → priority → admit_phase contract tests."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_API = Path(__file__).resolve().parents[2] / "api" / "services" / "pipeline_controller.py"
_spec = importlib.util.spec_from_file_location("pipeline_controller_flat", _API)
assert _spec and _spec.loader
pc = importlib.util.module_from_spec(_spec)
sys.modules["pipeline_controller_flat"] = pc
_spec.loader.exec_module(pc)


def _eligible_true(*_a, **_k) -> bool:
    return True


def test_compute_mode_preprocess_when_intake_hot():
    from shared.pipeline_admission import compute_mode

    pending = {
        "content_enrichment": 40,
        "unified_intake_extraction": 40,
        "document_processing": 0,
        "mention_resolution": 1000,
    }
    with patch("shared.pipeline_admission.mode_intake_clear", return_value=50):
        assert compute_mode(pending, pressure=False) == "preprocess"


def test_compute_mode_postprocess_when_preprocess_stable():
    from shared.pipeline_admission import compute_mode

    pending = {
        "content_enrichment": 0,
        "unified_intake_extraction": 0,
        "document_processing": 0,
        "claim_extraction": 0,
        "context_sync": 0,
        "mention_resolution": 30000,
    }
    with (
        patch("shared.pipeline_admission.mode_intake_clear", return_value=50),
        patch("shared.pipeline_admission.mode_preprocess_stable", return_value=5),
        patch(
            "shared.pipeline_resource_policy.post_process_preferred_enabled",
            return_value=True,
        ),
    ):
        assert compute_mode(pending, pressure=False) == "postprocess"


def test_compute_mode_pressure_on_flag():
    from shared.pipeline_admission import compute_mode

    assert compute_mode({}, pressure=True) == "pressure"


def test_pick_flat_postprocess_orders_structure_first():
    automation = MagicMock()
    automation.schedules = {
        name: {"enabled": True, "priority": 2, "phase": 4, "interval": 300}
        for name in (
            "mention_resolution",
            "entity_profile_build",
            "event_tracking",
            "graph_connection_distillation",
            "storyline_assembly",
            "collection_cycle",
        )
    }
    automation._pending_collection_queue = []
    pending = {
        "content_enrichment": 0,
        "unified_intake_extraction": 0,
        "document_processing": 0,
        "claim_extraction": 0,
        "context_sync": 0,
        "mention_resolution": 30716,
        "entity_profile_build": 5891,
        "graph_connection_distillation": 1972,
        "event_tracking": 584,
        "storyline_assembly": 425,
    }
    with (
        patch("shared.pipeline_admission.flat_scheduler_enabled", return_value=True),
        patch.object(pc, "_widow_resources_ok", return_value=True),
        patch.object(pc, "widow_memory_critical", return_value=False),
        patch.object(pc, "widow_oom_popos_overflow_active", return_value=False),
        patch.object(pc, "widow_memory_pressure", return_value=False),
        patch.object(pc, "popos_available_for_overflow", return_value=True),
        patch.object(pc, "_popos_gpu_phases", return_value=frozenset({"storyline_assembly"})),
        patch.object(pc, "catchup_phases", return_value=frozenset(pending.keys())),
        patch.object(pc, "_widow_residual_assembly_fallback_allowed", return_value=False),
        patch("shared.pipeline_admission.admit_phase", return_value=None),
        patch("shared.pipeline_admission._collection_allowed_flat", return_value=False),
        patch("shared.pipeline_admission.mode_intake_clear", return_value=50),
        patch("shared.pipeline_admission.mode_preprocess_stable", return_value=5),
        patch(
            "shared.pipeline_resource_policy.post_process_preferred_enabled",
            return_value=True,
        ),
    ):
        desired, branch = pc.pick_next_phases(
            pending,
            resources=object(),
            phase_health={},
            automation=automation,
            stall_holds={},
            catchup=True,
        )
    assert branch == "mode_postprocess"
    assert "mention_resolution" in desired
    assert "entity_profile_build" in desired
    assert desired.index("mention_resolution") < desired.index("storyline_assembly")
    assert "collection_cycle" not in desired


def test_pick_flat_pressure_excludes_popos_gpu():
    automation = MagicMock()
    automation.schedules = {
        "mention_resolution": {"enabled": True},
        "context_sync": {"enabled": True},
        "storyline_assembly": {"enabled": True},
        "pending_db_flush": {"enabled": True},
        "entity_profile_sync": {"enabled": True},
        "spine_sql_tail": {"enabled": True},
        "claims_to_facts": {"enabled": True},
        "event_tracking": {"enabled": True},
    }
    pending = {
        "mention_resolution": 100,
        "context_sync": 10,
        "storyline_assembly": 50,
        "event_tracking": 5,
    }
    with (
        patch("shared.pipeline_admission.flat_scheduler_enabled", return_value=True),
        patch.object(pc, "widow_memory_critical", return_value=False),
        patch.object(pc, "widow_oom_popos_overflow_active", return_value=True),
        patch.object(pc, "popos_available_for_overflow", return_value=True),
        patch.object(pc, "_widow_resources_ok", return_value=True),
        patch.object(pc, "_popos_gpu_phases", return_value=frozenset({"storyline_assembly"})),
        patch.object(pc, "catchup_phases", return_value=frozenset(pending.keys())),
        patch.object(pc, "_widow_residual_assembly_fallback_allowed", return_value=False),
        patch(
            "shared.pipeline_admission.admit_phase",
            side_effect=lambda phase, **k: (
                "pressure_no_gpu" if phase == "storyline_assembly" else None
            ),
        ),
    ):
        desired, branch = pc.pick_next_phases(
            pending,
            resources=object(),
            phase_health={},
            automation=automation,
            stall_holds={},
            catchup=True,
        )
    assert branch == "mode_pressure"
    assert "storyline_assembly" not in desired
    assert "mention_resolution" in desired or "context_sync" in desired


def test_admit_denies_remote_owned():
    from shared.pipeline_admission import admit_phase

    automation = MagicMock()
    automation.schedules = {"storyline_assembly": {"enabled": True}}
    with patch(
        "shared.remote_phase_worker.phase_owned_by_remote_worker",
        return_value=True,
    ):
        assert (
            admit_phase(
                "storyline_assembly",
                pending={"storyline_assembly": 10},
                mode="postprocess",
                automation=automation,
                stall_holds={},
            )
            == "remote_owned"
        )


def test_admit_denies_empty_backlog():
    from shared.pipeline_admission import admit_phase

    automation = MagicMock()
    automation.schedules = {"mention_resolution": {"enabled": True}}
    with patch(
        "shared.remote_phase_worker.phase_owned_by_remote_worker",
        return_value=False,
    ):
        deny = admit_phase(
            "mention_resolution",
            pending={"mention_resolution": 0},
            mode="postprocess",
            automation=automation,
            stall_holds={},
        )
    assert deny == "empty_backlog"


def test_legacy_pick_still_available_when_flag_off():
    automation = MagicMock()
    automation.schedules = {
        "entity_profile_build": {"enabled": True},
        "context_sync": {"enabled": True},
    }
    pending = {"entity_profile_build": 500, "unified_intake_extraction": 0}
    with (
        patch("shared.pipeline_admission.flat_scheduler_enabled", return_value=False),
        patch.object(pc, "_widow_resources_ok", return_value=True),
        patch.object(pc, "widow_memory_critical", return_value=False),
        patch.object(pc, "widow_oom_popos_overflow_active", return_value=False),
        patch.object(pc, "widow_memory_pressure", return_value=False),
        patch.object(pc, "_collection_allowed", return_value=False),
        patch.object(pc, "_phase_eligible", side_effect=_eligible_true),
        patch.object(pc, "residual_entity_profile_build_pending_threshold", return_value=100),
        patch.object(pc, "residual_assembly_pending_threshold", return_value=100),
        patch.object(pc, "residual_topic_clustering_pending_threshold", return_value=100),
        patch.object(pc, "residual_mention_resolution_pending_threshold", return_value=100),
        patch.object(pc, "unified_intake_defer_threshold", return_value=50),
    ):
        desired, branch = pc.pick_next_phases(
            pending,
            resources=object(),
            phase_health={},
            automation=automation,
            stall_holds={},
            catchup=False,
        )
    assert branch == "residual_entity_profile_build"
    assert "entity_profile_build" in desired
