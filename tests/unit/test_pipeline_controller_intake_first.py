"""Intake-first catchup ordering for PipelineController."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_API = Path(__file__).resolve().parents[2] / "api" / "services" / "pipeline_controller.py"
_spec = importlib.util.spec_from_file_location("pipeline_controller_intake_first", _API)
assert _spec and _spec.loader
pc = importlib.util.module_from_spec(_spec)
sys.modules["pipeline_controller_intake_first"] = pc
_spec.loader.exec_module(pc)


def _eligible_true(*_a, **_k) -> bool:
    return True


def test_intake_preprocess_pending_sums_core_only():
    from shared.pipeline_resource_policy import intake_preprocess_pending

    pending = {
        "content_enrichment": 40,
        "unified_intake_extraction": 30,
        "document_processing": 5,
        "mention_resolution": 38000,
        "context_sync": 999,
    }
    assert intake_preprocess_pending(pending) == 75


def test_intake_preprocess_hot_respects_threshold():
    from shared.pipeline_resource_policy import intake_preprocess_hot

    with patch(
        "shared.pipeline_resource_policy.intake_preprocess_clear_threshold",
        return_value=50,
    ):
        assert intake_preprocess_hot(
            {"content_enrichment": 20, "unified_intake_extraction": 20}
        ) is False
        assert intake_preprocess_hot(
            {"content_enrichment": 20, "unified_intake_extraction": 31}
        ) is True


def test_catchup_phases_intake_hot_co_schedules_structure_and_mr():
    pending = {
        "content_enrichment": 100,
        "unified_intake_extraction": 80,
        "mention_resolution": 38000,
        "entity_profile_build": 7000,
        "storyline_assembly": 2000,
        "topic_clustering": 500,
    }
    automation = MagicMock()
    with (
        patch.object(pc, "catchup_phases", return_value=frozenset(pending.keys())),
        patch.object(pc, "_phase_eligible", side_effect=_eligible_true),
        patch.object(pc, "_popos_gpu_phases", return_value=frozenset({"storyline_assembly"})),
        patch.object(pc, "popos_available_for_overflow", return_value=True),
        patch.object(pc, "widow_memory_pressure", return_value=False),
        patch(
            "shared.pipeline_resource_policy.intake_preprocess_clear_threshold",
            return_value=50,
        ),
    ):
        phases, intake_first = pc._catchup_phases_by_backlog(
            pending,
            automation,
            stall_holds={},
            skip=frozenset({"collection_cycle"}),
            resources=object(),
        )
    assert intake_first is True
    assert "content_enrichment" in phases
    assert "unified_intake_extraction" in phases
    # Soft intake-first: structure + MR still appended
    assert "mention_resolution" in phases
    assert "entity_profile_build" in phases
    assert "storyline_assembly" in phases
    # Non-structure post-band (e.g. topic_clustering) stays omitted under intake-first
    assert "topic_clustering" not in phases
    # Spine order: enrichment before unified intake; intake before co-scheduled post
    assert phases.index("content_enrichment") < phases.index("unified_intake_extraction")
    assert phases.index("content_enrichment") < phases.index("mention_resolution")


def test_catchup_phases_intake_clear_includes_post_sorted_by_backlog():
    pending = {
        "content_enrichment": 0,
        "unified_intake_extraction": 0,
        "document_processing": 0,
        "claim_extraction": 0,
        "context_sync": 0,
        "mention_resolution": 38000,
        "entity_profile_build": 7000,
        "storyline_assembly": 2000,
    }
    automation = MagicMock()
    with (
        patch.object(
            pc,
            "catchup_phases",
            return_value=frozenset(
                {
                    "mention_resolution",
                    "entity_profile_build",
                    "storyline_assembly",
                }
            ),
        ),
        patch.object(pc, "_phase_eligible", side_effect=_eligible_true),
        patch.object(pc, "_popos_gpu_phases", return_value=frozenset({"storyline_assembly"})),
        patch.object(pc, "popos_available_for_overflow", return_value=True),
        patch.object(pc, "widow_memory_pressure", return_value=False),
        patch(
            "shared.pipeline_resource_policy.intake_preprocess_clear_threshold",
            return_value=50,
        ),
        patch(
            "shared.pipeline_resource_policy.preprocess_stable_threshold",
            return_value=5,
        ),
    ):
        phases, intake_first = pc._catchup_phases_by_backlog(
            pending,
            automation,
            stall_holds={},
            skip=frozenset({"collection_cycle"}),
            resources=object(),
        )
    assert intake_first is False
    # preprocess stable + structure backlog → widow_first (MR/EPB before PopOS assembly)
    assert phases[0] == "mention_resolution"
    assert phases.index("mention_resolution") < phases.index("entity_profile_build")
    assert phases.index("entity_profile_build") < phases.index("storyline_assembly")


def test_preprocess_stable_and_post_process_preferred():
    from shared.pipeline_resource_policy import (
        post_process_preferred,
        preprocess_stable,
        preprocess_stable_pending,
    )

    clear = {
        "content_enrichment": 0,
        "unified_intake_extraction": 0,
        "document_processing": 0,
        "claim_extraction": 2,
        "context_sync": 1,
        "mention_resolution": 30000,
    }
    with patch(
        "shared.pipeline_resource_policy.preprocess_stable_threshold",
        return_value=5,
    ):
        assert preprocess_stable_pending(clear) == 3
        assert preprocess_stable(clear) is True
        assert post_process_preferred(clear) is True

    hot = {**clear, "unified_intake_extraction": 80, "mention_resolution": 0}
    with patch(
        "shared.pipeline_resource_policy.preprocess_stable_threshold",
        return_value=5,
    ):
        assert preprocess_stable(hot) is False
        assert post_process_preferred(hot) is False


def test_pick_next_phases_post_process_preferred_branch():
    automation = MagicMock()
    automation.schedules = {
        "collection_cycle": {
            "enabled": True,
            "interval": 7200,
            "last_run": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ),
        },
        "mention_resolution": {"enabled": True},
        "entity_profile_build": {"enabled": True},
        "graph_connection_distillation": {"enabled": True},
        "event_tracking": {"enabled": True},
    }
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
        patch("shared.pipeline_admission.flat_scheduler_enabled", return_value=False),
        patch.object(pc, "_widow_resources_ok", return_value=True),
        patch.object(pc, "widow_memory_critical", return_value=False),
        patch.object(pc, "widow_oom_popos_overflow_active", return_value=False),
        patch.object(pc, "widow_memory_pressure", return_value=False),
        patch.object(pc, "popos_available_for_overflow", return_value=True),
        patch.object(pc, "_phase_eligible", side_effect=_eligible_true),
        patch.object(pc, "_collection_allowed", return_value=False),
        patch.object(
            pc,
            "catchup_phases",
            return_value=frozenset(pending.keys()),
        ),
        patch.object(
            pc,
            "_popos_gpu_phases",
            return_value=frozenset({"storyline_assembly", "unified_intake_extraction"}),
        ),
        patch(
            "shared.pipeline_resource_policy.intake_preprocess_clear_threshold",
            return_value=50,
        ),
        patch(
            "shared.pipeline_resource_policy.preprocess_stable_threshold",
            return_value=5,
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
    assert branch == "post_process_preferred"
    assert "mention_resolution" in desired
    assert "entity_profile_build" in desired
    assert "graph_connection_distillation" in desired
    assert "event_tracking" in desired
    # Widow structure before remote-owned assembly; collection deferred mid-interval
    assert desired.index("mention_resolution") < desired.index("storyline_assembly")
    assert "collection_cycle" not in desired


def test_catchup_order_policy_widow_first_when_post_process_preferred():
    pending = {
        "content_enrichment": 0,
        "unified_intake_extraction": 0,
        "document_processing": 0,
        "claim_extraction": 0,
        "context_sync": 0,
        "mention_resolution": 1000,
    }
    with patch(
        "shared.pipeline_resource_policy.preprocess_stable_threshold",
        return_value=5,
    ):
        assert (
            pc._catchup_order_policy(popos_ok=True, mem_pressure=False, pending=pending)
            == "widow_first"
        )
        # Without structure backlog, normal popos_first resumes
        assert (
            pc._catchup_order_policy(
                popos_ok=True,
                mem_pressure=False,
                pending={**pending, "mention_resolution": 0},
            )
            == "popos_first"
        )


def test_structure_hot_keeps_mention_resolution():
    post = [
        ("mention_resolution", 38000),
        ("entity_profile_build", 7000),
        ("content_refinement_queue", 100),
    ]
    pending = {
        "entity_profile_build": 7000,
        "storyline_assembly": 2000,
        "storyline_automation": 0,
        "mention_resolution": 38000,
    }
    with (
        patch.object(pc, "_popos_gpu_phases", return_value=frozenset()),
        patch.object(pc, "popos_available_for_overflow", return_value=False),
        patch.object(pc, "widow_memory_pressure", return_value=False),
        patch(
            "shared.pipeline_resource_policy.structure_catchup_refinement_defer_threshold",
            return_value=200,
        ),
    ):
        ordered = pc._sort_post_phases_by_host(post, resources=object(), pending=pending)
    assert "mention_resolution" in ordered
    assert "entity_profile_build" in ordered
    assert "content_refinement_queue" not in ordered


def test_bulk_extract_defers_post_when_preprocess_hot():
    from shared.pipeline_resource_policy import bulk_extract_compete_defer_phase

    pending = {
        "content_enrichment": 100,
        "unified_intake_extraction": 50,
        "mention_resolution": 1000,
        "entity_profile_build": 500,
    }
    with patch(
        "shared.spine_phase_order.spine_pipeline_ordered_active",
        return_value=True,
    ), patch(
        "shared.pipeline_resource_policy.intake_preprocess_clear_threshold",
        return_value=50,
    ):
        # MR / EPB exempt from intake-preprocess hard defer
        assert bulk_extract_compete_defer_phase("mention_resolution", pending) is False
        assert bulk_extract_compete_defer_phase("entity_profile_build", pending) is False
        assert bulk_extract_compete_defer_phase("topic_clustering", pending) is True
        assert bulk_extract_compete_defer_phase("content_enrichment", pending) is False
        assert bulk_extract_compete_defer_phase("unified_intake_extraction", pending) is False


def test_residual_entity_profile_build_in_maintenance():
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


def test_residual_assembly_widow_fallback_when_popos_stale():
    automation = MagicMock()
    automation.schedules = {"storyline_assembly": {"enabled": False}}
    pending = {"storyline_assembly": 500, "unified_intake_extraction": 0}
    with (
        patch("shared.pipeline_admission.flat_scheduler_enabled", return_value=False),
        patch.object(pc, "_widow_resources_ok", return_value=True),
        patch.object(pc, "widow_memory_critical", return_value=False),
        patch.object(pc, "widow_oom_popos_overflow_active", return_value=False),
        patch.object(pc, "widow_memory_pressure", return_value=False),
        patch.object(pc, "_collection_allowed", return_value=False),
        patch.object(pc, "residual_assembly_pending_threshold", return_value=100),
        patch.object(pc, "unified_intake_defer_threshold", return_value=50),
        patch.object(pc, "_phase_eligible", return_value=False),
        patch.object(pc, "_widow_residual_assembly_fallback_allowed", return_value=True),
    ):
        desired, branch = pc.pick_next_phases(
            pending,
            resources=object(),
            phase_health={},
            automation=automation,
            stall_holds={},
            catchup=False,
        )
    assert branch == "residual_assembly_widow_fallback"
    assert "storyline_assembly" in desired
