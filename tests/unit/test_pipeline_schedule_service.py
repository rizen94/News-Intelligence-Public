"""Unit tests for pipeline_schedule_service three-window schedule."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from services.pipeline_schedule_service import (
    active_pipeline_window,
    automation_phase_allowed,
    db_adjacent_sync_allowed,
    in_nightly_heavy_window,
    in_pipeline_quiet_window,
    in_weekday_daytime_window,
    pipeline_schedule_info,
    popos_gpu_work_allowed,
    popos_gpu_work_allowed_detail,
    rss_collection_allowed,
)

ET = ZoneInfo("America/New_York")


def _et(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=ET)


class TestPipelineWindows:
    def test_nightly_heavy_midnight_to_seven(self, monkeypatch):
        monkeypatch.setenv("PIPELINE_NIGHTLY_START_HOUR", "0")
        monkeypatch.setenv("PIPELINE_NIGHTLY_END_HOUR", "7")
        monkeypatch.setenv("PIPELINE_DAYTIME_START_HOUR", "7")
        monkeypatch.setenv("PIPELINE_DAYTIME_END_HOUR", "16")
        assert in_nightly_heavy_window(_et(2026, 5, 18, 3))
        assert not in_nightly_heavy_window(_et(2026, 5, 18, 7))
        assert not in_nightly_heavy_window(_et(2026, 5, 18, 12))

    def test_nightly_end_hour_24_means_end_of_day(self, monkeypatch):
        """Catch-up configs use END_HOUR=24; must not raise ValueError on replace(hour=24)."""
        monkeypatch.setenv("PIPELINE_NIGHTLY_START_HOUR", "0")
        monkeypatch.setenv("PIPELINE_NIGHTLY_END_HOUR", "24")
        assert in_nightly_heavy_window(_et(2026, 5, 18, 0))
        assert in_nightly_heavy_window(_et(2026, 5, 18, 12))
        assert in_nightly_heavy_window(_et(2026, 5, 18, 23, 59))
        info = pipeline_schedule_info(now_local=_et(2026, 5, 18, 15))
        assert info["in_nightly_heavy"] is True
        assert rss_collection_allowed(now_local=_et(2026, 5, 18, 15)) is True

    def test_weekday_daytime_monday_noon(self, monkeypatch):
        monkeypatch.setenv("PIPELINE_DAYTIME_START_HOUR", "7")
        monkeypatch.setenv("PIPELINE_DAYTIME_END_HOUR", "16")
        # Monday 2026-05-18
        assert in_weekday_daytime_window(_et(2026, 5, 18, 10))
        assert not in_weekday_daytime_window(_et(2026, 5, 18, 6))
        assert not in_weekday_daytime_window(_et(2026, 5, 18, 17))

    def test_weekend_daytime_is_quiet_not_active(self, monkeypatch):
        monkeypatch.setenv("PIPELINE_DAYTIME_START_HOUR", "7")
        monkeypatch.setenv("PIPELINE_DAYTIME_END_HOUR", "16")
        # Saturday 2026-05-16
        assert not in_weekday_daytime_window(_et(2026, 5, 16, 10))
        assert in_pipeline_quiet_window(_et(2026, 5, 16, 10))
        assert active_pipeline_window(_et(2026, 5, 16, 10)) == "quiet"

    def test_evening_quiet_weekday(self, monkeypatch):
        monkeypatch.setenv("PIPELINE_DAYTIME_END_HOUR", "16")
        assert in_pipeline_quiet_window(_et(2026, 5, 18, 18))
        assert active_pipeline_window(_et(2026, 5, 18, 18)) == "quiet"

    def test_automation_phase_allowed_in_quiet(self, monkeypatch):
        monkeypatch.setenv("PIPELINE_QUIET_ALLOWED_PHASES", "health_check,pending_db_flush")
        quiet = _et(2026, 5, 18, 20)
        assert automation_phase_allowed("health_check", now_local=quiet)
        assert automation_phase_allowed("pending_db_flush", now_local=quiet)
        assert not automation_phase_allowed("claim_extraction", now_local=quiet)
        assert not automation_phase_allowed("collection_cycle", now_local=quiet)

    def test_automation_phase_allowed_weekday_daytime(self, monkeypatch):
        daytime = _et(2026, 5, 18, 11)
        assert automation_phase_allowed("claim_extraction", now_local=daytime)
        assert automation_phase_allowed("collection_cycle", now_local=daytime)

    def test_rss_allowed_daytime_and_nightly_not_quiet(self, monkeypatch):
        assert rss_collection_allowed(now_local=_et(2026, 5, 18, 11))
        assert rss_collection_allowed(now_local=_et(2026, 5, 18, 2))
        assert not rss_collection_allowed(now_local=_et(2026, 5, 18, 20))
        assert not rss_collection_allowed(now_local=_et(2026, 5, 16, 10))

    def test_db_adjacent_sync_blocked_in_quiet(self, monkeypatch):
        assert db_adjacent_sync_allowed(now_local=_et(2026, 5, 18, 20)) is False
        assert db_adjacent_sync_allowed(now_local=_et(2026, 5, 18, 11)) is True

    def test_pipeline_schedule_info_keys(self, monkeypatch):
        info = pipeline_schedule_info(now_local=_et(2026, 5, 18, 11))
        assert info["active_window"] == "weekday_daytime"
        assert "rss_collection_allowed" in info
        assert info["rss_collection_allowed"] is True

    def test_popos_gpu_deferred_in_quiet(self, monkeypatch):
        monkeypatch.delenv("PIPELINE_QUIET_HOURS_DISABLED", raising=False)
        monkeypatch.setenv("POPOS_GPU_COTENANT_DEFER", "false")
        quiet = _et(2026, 5, 16, 15)  # Saturday afternoon
        assert popos_gpu_work_allowed(now_local=quiet) is False
        detail = popos_gpu_work_allowed_detail(now_local=quiet)
        assert detail["allowed"] is False
        assert detail["active_window"] == "quiet"

    def test_popos_gpu_allowed_weekday_daytime_without_cotenant(self, monkeypatch):
        monkeypatch.delenv("PIPELINE_QUIET_HOURS_DISABLED", raising=False)
        monkeypatch.setenv("POPOS_GPU_COTENANT_DEFER", "false")
        monkeypatch.setenv("POPOS_GPU_GAME_DEFER", "false")
        monkeypatch.delenv("WORKER_EXECUTION_HOST", raising=False)
        daytime = _et(2026, 5, 18, 11)
        assert popos_gpu_work_allowed(now_local=daytime) is True

    def test_popos_gpu_deferred_when_game_running(self, monkeypatch):
        monkeypatch.setenv("WORKER_EXECUTION_HOST", "popos")
        monkeypatch.setenv("PIPELINE_QUIET_HOURS_DISABLED", "true")
        monkeypatch.setenv("POPOS_GPU_COTENANT_DEFER", "false")
        monkeypatch.setenv("POPOS_GPU_GAME_DEFER", "true")
        monkeypatch.setattr(
            "services.pipeline_schedule_service.detect_popos_game_processes",
            lambda: {
                "active": True,
                "processes": [{"pid": "1", "comm": "bg3", "cmdline": "/bin/bg3"}],
            },
        )
        daytime = _et(2026, 5, 18, 11)
        detail = popos_gpu_work_allowed_detail(now_local=daytime)
        assert detail["allowed"] is False
        assert detail["reason"] == "game_running"
