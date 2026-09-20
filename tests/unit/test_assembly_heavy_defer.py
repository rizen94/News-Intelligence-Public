"""Unit tests for assembly heavy-defer pick logic."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


_API = Path(__file__).resolve().parents[2] / "api" / "services" / "assembly_conductor_service.py"
_spec = importlib.util.spec_from_file_location("assembly_conductor_service", _API)
assert _spec and _spec.loader
acs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(acs)

_pick_assembly_phase = acs._pick_assembly_phase


def _stub_services_modules(monkeypatch):
    """Avoid importing services.__init__ (pulls automation_manager + DB)."""
    pkg = types.ModuleType("services")
    pkg.__path__ = []  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "services", pkg)

    bm = types.ModuleType("services.backlog_metrics")
    bm.get_per_run_batch_size_for_phase = lambda phase: 25
    monkeypatch.setitem(sys.modules, "services.backlog_metrics", bm)

    pwq = types.ModuleType("services.phase_work_queue_metrics")

    def _wq(phase, pending_total=0):
        if phase == "entity_profile_build":
            return {"first_pass": pending_total, "retry_pending": 0}
        return {"first_pass": 0, "retry_pending": 0}

    pwq.get_phase_work_queue = _wq
    monkeypatch.setitem(sys.modules, "services.phase_work_queue_metrics", pwq)


class TestAssemblyHeavyDefer:
    def test_defers_narrative_when_intake_heavy(self, monkeypatch):
        _stub_services_modules(monkeypatch)
        monkeypatch.setenv("ASSEMBLY_DEFER_INTAKE_BACKLOG", "1000")
        monkeypatch.setenv("ASSEMBLY_DEFER_PROFILE_BACKLOG", "8000")
        backlog = {
            "unified_intake_extraction": 5000,
            "entity_profile_build": 100,
            "storyline_assembly": 9000,
            "editorial_room_loop": 2000,
            "entity_organizer": 50,
        }
        picked, meta = _pick_assembly_phase(backlog)
        assert meta["heavy_defer"] is True
        assert "storyline_assembly" in meta["deferred_phases"]
        assert "editorial_room_loop" in meta["deferred_phases"]
        assert picked == "entity_profile_build"

    def test_picks_narrative_when_not_heavy(self, monkeypatch):
        _stub_services_modules(monkeypatch)
        monkeypatch.setenv("ASSEMBLY_DEFER_INTAKE_BACKLOG", "10000")
        monkeypatch.setenv("ASSEMBLY_DEFER_PROFILE_BACKLOG", "20000")
        backlog = {
            "unified_intake_extraction": 100,
            "entity_profile_build": 50,
            "storyline_assembly": 5000,
            "entity_organizer": 10,
        }
        picked, meta = _pick_assembly_phase(backlog)
        assert meta["heavy_defer"] is False
        assert picked == "storyline_assembly"

    def test_idle_when_only_deferred_have_work(self, monkeypatch):
        _stub_services_modules(monkeypatch)
        monkeypatch.setenv("ASSEMBLY_DEFER_INTAKE_BACKLOG", "500")
        monkeypatch.setenv("ASSEMBLY_DEFER_PROFILE_BACKLOG", "8000")
        backlog = {
            "unified_intake_extraction": 4000,
            "storyline_assembly": 2000,
            "editorial_room_loop": 1000,
        }
        picked, meta = _pick_assembly_phase(backlog)
        assert meta["heavy_defer"] is True
        assert picked is None
        assert set(meta["deferred_phases"]) >= {"storyline_assembly", "editorial_room_loop"}
