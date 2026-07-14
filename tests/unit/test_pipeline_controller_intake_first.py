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


def test_catchup_phases_intake_hot_excludes_post_band():
    pending = {
        "content_enrichment": 100,
        "unified_intake_extraction": 80,
        "mention_resolution": 38000,
        "entity_profile_build": 7000,
        "storyline_assembly": 2000,
    }
    automation = MagicMock()
    with (
        patch.object(pc, "catchup_phases", return_value=frozenset(pending.keys())),
        patch.object(pc, "_phase_eligible", side_effect=_eligible_true),
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
            resources=None,
        )
    assert intake_first is True
    assert "content_enrichment" in phases
    assert "unified_intake_extraction" in phases
    assert "mention_resolution" not in phases
    assert "entity_profile_build" not in phases
    assert "storyline_assembly" not in phases
    # Spine order: enrichment before unified intake
    assert phases.index("content_enrichment") < phases.index("unified_intake_extraction")


def test_catchup_phases_intake_clear_includes_post_sorted_by_backlog():
    pending = {
        "content_enrichment": 0,
        "unified_intake_extraction": 0,
        "document_processing": 0,
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
    ):
        phases, intake_first = pc._catchup_phases_by_backlog(
            pending,
            automation,
            stall_holds={},
            skip=frozenset({"collection_cycle"}),
            resources=object(),
        )
    assert intake_first is False
    assert phases[0] == "storyline_assembly"  # popos_first + only gpu phase
    # Widow-local post: largest backlog first
    assert phases.index("mention_resolution") < phases.index("entity_profile_build")


def test_bulk_extract_defers_post_when_preprocess_hot():
    from shared.pipeline_resource_policy import bulk_extract_compete_defer_phase

    pending = {
        "content_enrichment": 100,
        "unified_intake_extraction": 50,
        "mention_resolution": 1000,
    }
    with patch(
        "shared.spine_phase_order.spine_pipeline_ordered_active",
        return_value=True,
    ), patch(
        "shared.pipeline_resource_policy.intake_preprocess_clear_threshold",
        return_value=50,
    ):
        assert bulk_extract_compete_defer_phase("mention_resolution", pending) is True
        assert bulk_extract_compete_defer_phase("entity_profile_build", pending) is True
        assert bulk_extract_compete_defer_phase("topic_clustering", pending) is True
        assert bulk_extract_compete_defer_phase("content_enrichment", pending) is False
        assert bulk_extract_compete_defer_phase("unified_intake_extraction", pending) is False
