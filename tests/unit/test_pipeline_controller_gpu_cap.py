"""Unit tests for PipelineController PopOS GPU drain cap defaults."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

_API = Path(__file__).resolve().parents[2] / "api" / "services" / "pipeline_controller.py"
_spec = importlib.util.spec_from_file_location("pipeline_controller", _API)
assert _spec and _spec.loader
pc = importlib.util.module_from_spec(_spec)
sys.modules["pipeline_controller"] = pc
_spec.loader.exec_module(pc)

_default_max_concurrent_widow_gpu_drains = pc._default_max_concurrent_widow_gpu_drains
max_concurrent_widow_gpu_drains = pc.max_concurrent_widow_gpu_drains


def test_default_max_concurrent_widow_gpu_drains_when_workers_ge_4(monkeypatch):
    monkeypatch.delenv("AUTOMATION_MAX_CONCURRENT_TASKS", raising=False)
    assert _default_max_concurrent_widow_gpu_drains() == 2


def test_default_max_concurrent_widow_gpu_drains_when_workers_lt_4(monkeypatch):
    monkeypatch.setenv("AUTOMATION_MAX_CONCURRENT_TASKS", "2")
    assert _default_max_concurrent_widow_gpu_drains() == 1


def test_max_concurrent_widow_gpu_drains_yaml_override():
    with patch.object(
        pc,
        "_controller_config",
        return_value={"max_concurrent_widow_gpu_drains": 3},
    ):
        assert max_concurrent_widow_gpu_drains() == 3


def test_max_concurrent_widow_gpu_drains_falls_back_when_yaml_unset(monkeypatch):
    monkeypatch.delenv("AUTOMATION_MAX_CONCURRENT_TASKS", raising=False)
    with patch.object(pc, "_controller_config", return_value={}):
        assert max_concurrent_widow_gpu_drains() == 2
