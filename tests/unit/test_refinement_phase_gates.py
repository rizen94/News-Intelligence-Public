"""Unit tests for refinement-phase gates under ordered spine."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import patch

from shared.pipeline_resource_policy import refinement_phase_allowed


def _schedule_service_module():
    name = "services.pipeline_schedule_service"
    if name in sys.modules:
        return sys.modules[name]
    if "services" not in sys.modules:
        sys.modules["services"] = types.ModuleType("services")
    path = (
        Path(__file__).resolve().parents[2]
        / "api"
        / "services"
        / "pipeline_schedule_service.py"
    )
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_refinement_phase_allowed_entity_profile_build_ordered_spine():
    pending = {"unified_intake_extraction": 50000, "entity_extraction": 10000}
    with patch(
        "shared.spine_phase_order.spine_pipeline_ordered_active",
        return_value=True,
    ):
        assert refinement_phase_allowed("entity_profile_build", pending=pending)


def test_refinement_phase_allowed_entity_profile_build_blocked_without_spine():
    pending = {"unified_intake_extraction": 50000, "entity_extraction": 10000}
    schedule = _schedule_service_module()
    with patch(
        "shared.spine_phase_order.spine_pipeline_ordered_active",
        return_value=False,
    ), patch.object(schedule, "in_nightly_heavy_window", return_value=False):
        assert not refinement_phase_allowed("entity_profile_build", pending=pending)
