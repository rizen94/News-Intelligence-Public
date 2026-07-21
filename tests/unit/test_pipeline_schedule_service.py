"""Unit tests for pipeline_schedule_service desk three-band schedule."""

from __future__ import annotations

import importlib.util
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

_API = Path(__file__).resolve().parents[2] / "api" / "services" / "pipeline_schedule_service.py"
_spec = importlib.util.spec_from_file_location("pipeline_schedule_service", _API)
assert _spec and _spec.loader
pss = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pss)

active_pipeline_window = pss.active_pipeline_window
automation_phase_allowed = pss.automation_phase_allowed
db_adjacent_sync_allowed = pss.db_adjacent_sync_allowed
in_desk_light_window = pss.in_desk_light_window
in_heavy_window = pss.in_heavy_window
in_morning_ingest_window = pss.in_morning_ingest_window
in_nightly_heavy_window = pss.in_nightly_heavy_window
in_pipeline_quiet_window = pss.in_pipeline_quiet_window
pipeline_schedule_info = pss.pipeline_schedule_info
popos_gpu_work_allowed = pss.popos_gpu_work_allowed
rss_collection_allowed = pss.rss_collection_allowed

ET = ZoneInfo("America/New_York")


def _et(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=ET)


def _default_hours(monkeypatch):
    monkeypatch.setenv("PIPELINE_HEAVY_START_HOUR", "1")
    monkeypatch.setenv("PIPELINE_HEAVY_END_HOUR", "6")
    monkeypatch.setenv("PIPELINE_MORNING_START_HOUR", "6")
    monkeypatch.setenv("PIPELINE_MORNING_END_HOUR", "10")
    monkeypatch.setenv("PIPELINE_DESK_START_HOUR", "10")
    monkeypatch.setenv("PIPELINE_DESK_END_HOUR", "1")
    monkeypatch.delenv("PIPELINE_QUIET_HOURS_DISABLED", raising=False)
    monkeypatch.setenv("DESK_PRESENCE_DISABLED", "true")


class TestDeskThreeBand:
    def test_heavy_window(self, monkeypatch):
        _default_hours(monkeypatch)
        assert in_heavy_window(_et(2026, 5, 18, 3))
        assert in_nightly_heavy_window(_et(2026, 5, 18, 3))
        assert not in_heavy_window(_et(2026, 5, 18, 6))
        assert not in_heavy_window(_et(2026, 5, 18, 12))
        assert active_pipeline_window(_et(2026, 5, 18, 3)) == "heavy"

    def test_morning_ingest(self, monkeypatch):
        _default_hours(monkeypatch)
        assert in_morning_ingest_window(_et(2026, 5, 18, 8))
        assert active_pipeline_window(_et(2026, 5, 18, 8)) == "morning_ingest"
        assert popos_gpu_work_allowed(now_local=_et(2026, 5, 18, 8))

    def test_desk_light_weekday_and_weekend(self, monkeypatch):
        _default_hours(monkeypatch)
        # Monday afternoon desk
        assert in_desk_light_window(_et(2026, 5, 18, 14))
        assert in_pipeline_quiet_window(_et(2026, 5, 18, 14))
        assert active_pipeline_window(_et(2026, 5, 18, 14)) == "desk_light"
        assert not popos_gpu_work_allowed(now_local=_et(2026, 5, 18, 14))
        # Saturday afternoon also desk (no weekend special case)
        assert active_pipeline_window(_et(2026, 5, 16, 14)) == "desk_light"

    def test_desk_wraps_midnight(self, monkeypatch):
        _default_hours(monkeypatch)
        assert in_desk_light_window(_et(2026, 5, 18, 23))
        assert in_desk_light_window(_et(2026, 5, 19, 0))
        assert not in_desk_light_window(_et(2026, 5, 19, 1))  # heavy starts
        assert in_heavy_window(_et(2026, 5, 19, 1))

    def test_widow_rss_and_sync_always(self, monkeypatch):
        _default_hours(monkeypatch)
        desk = _et(2026, 5, 18, 15)
        assert rss_collection_allowed(now_local=desk)
        assert db_adjacent_sync_allowed(now_local=desk)
        assert automation_phase_allowed("collection_cycle", now_local=desk)
        assert automation_phase_allowed("content_enrichment", now_local=desk)
        assert automation_phase_allowed("context_sync", now_local=desk)

    def test_gpu_blocked_in_desk(self, monkeypatch):
        _default_hours(monkeypatch)
        desk = _et(2026, 5, 18, 15)
        assert not automation_phase_allowed("unified_intake_extraction", now_local=desk)
        assert not automation_phase_allowed("claim_extraction", now_local=desk)
        assert not automation_phase_allowed("storyline_assembly", now_local=desk)

    def test_widow_safe_phases_allowed_in_desk(self, monkeypatch):
        """DB/CPU/fetch phases must not be misclassified as GPU-heavy."""
        _default_hours(monkeypatch)
        desk = _et(2026, 5, 18, 15)
        assert automation_phase_allowed("event_tracking", now_local=desk)
        assert automation_phase_allowed("mention_resolution", now_local=desk)
        assert automation_phase_allowed("entity_profile_build", now_local=desk)
        assert automation_phase_allowed("rag_enhancement", now_local=desk)

    def test_gpu_allowed_in_heavy_and_morning(self, monkeypatch):
        _default_hours(monkeypatch)
        assert automation_phase_allowed(
            "unified_intake_extraction", now_local=_et(2026, 5, 18, 2)
        )
        assert automation_phase_allowed(
            "claim_extraction", now_local=_et(2026, 5, 18, 7)
        )

    def test_severe_escape_in_desk(self, monkeypatch):
        _default_hours(monkeypatch)
        monkeypatch.setenv("AUTOMATION_BACKLOG_SEVERE_THRESHOLD", "10000")
        desk = _et(2026, 5, 18, 15)
        assert automation_phase_allowed(
            "topic_clustering", now_local=desk, pending_count=20000
        )
        assert not automation_phase_allowed(
            "topic_clustering", now_local=desk, pending_count=100
        )

    def test_moderate_escape_allowlist(self, monkeypatch):
        _default_hours(monkeypatch)
        monkeypatch.setenv("AUTOMATION_BACKLOG_MODERATE_THRESHOLD", "2500")
        monkeypatch.setenv(
            "PIPELINE_DESK_GPU_ESCAPE_PHASES",
            "unified_intake_extraction",
        )
        desk = _et(2026, 5, 18, 15)
        assert automation_phase_allowed(
            "unified_intake_extraction", now_local=desk, pending_count=3000
        )
        assert not automation_phase_allowed(
            "storyline_assembly", now_local=desk, pending_count=3000
        )

    def test_quiet_hours_disabled(self, monkeypatch):
        _default_hours(monkeypatch)
        monkeypatch.setenv("PIPELINE_QUIET_HOURS_DISABLED", "true")
        desk_hour = _et(2026, 5, 18, 15)
        assert not in_desk_light_window(desk_hour)
        assert popos_gpu_work_allowed(now_local=desk_hour)
        assert automation_phase_allowed("claim_extraction", now_local=desk_hour)

    def test_pipeline_schedule_info_keys(self, monkeypatch):
        _default_hours(monkeypatch)
        info = pipeline_schedule_info(now_local=_et(2026, 5, 18, 8))
        assert info["active_window"] == "morning_ingest"
        assert info["popos_gpu_work_allowed"] is True
        assert info["widow_work_allowed"] is True
        assert info["rss_collection_allowed"] is True
        assert info["schedule_model"] == "desk_three_band_v1"
        assert info["presence_model"] == "desk_presence_v1"
        assert info["popos_gpu_work_reason"] in (
            "wall_clock",
            "wall_clock_no_presence",
            "quiet_hours_disabled",
        )


class TestDeskPresenceGate:
    def test_locked_allows_gpu_in_desk(self, monkeypatch):
        _default_hours(monkeypatch)
        monkeypatch.delenv("DESK_PRESENCE_DISABLED", raising=False)
        desk = _et(2026, 5, 18, 15)
        presence = {
            "ts": "2026-05-18T19:00:00+00:00",
            "session_locked": True,
            "interactive_ollama": False,
        }
        detail = pss.popos_gpu_work_allowed_detail(now_local=desk, presence=presence)
        assert detail["allowed"] is True
        assert detail["reason"] == "session_locked"

    def test_interactive_defers_even_in_heavy(self, monkeypatch):
        _default_hours(monkeypatch)
        monkeypatch.delenv("DESK_PRESENCE_DISABLED", raising=False)
        heavy = _et(2026, 5, 18, 3)
        presence = {
            "ts": "2026-05-18T07:00:00+00:00",
            "session_locked": False,
            "interactive_ollama": True,
        }
        detail = pss.popos_gpu_work_allowed_detail(now_local=heavy, presence=presence)
        assert detail["allowed"] is False
        assert detail["reason"] == "interactive_ollama"

    def test_unlocked_idle_uses_wall_clock(self, monkeypatch):
        _default_hours(monkeypatch)
        monkeypatch.delenv("DESK_PRESENCE_DISABLED", raising=False)
        desk = _et(2026, 5, 18, 15)
        morning = _et(2026, 5, 18, 8)
        presence = {
            "ts": "2026-05-18T19:00:00+00:00",
            "session_locked": False,
            "interactive_ollama": False,
        }
        assert pss.popos_gpu_work_allowed_detail(now_local=desk, presence=presence)[
            "allowed"
        ] is False
        assert pss.popos_gpu_work_allowed_detail(now_local=morning, presence=presence)[
            "allowed"
        ] is True
