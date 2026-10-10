"""Unit tests for disk IO pressure advisory helpers (no live disk required)."""

from __future__ import annotations

import json
from pathlib import Path

import shared.database.disk_io_pressure_advisory as dio


def test_defer_from_history_hot_util_single_sample(tmp_path, monkeypatch):
    """One sample above util threshold is enough for hot_util / defer_heavy."""
    monkeypatch.setattr(dio, "_RUN_DIR", tmp_path)
    monkeypatch.setattr(dio, "_STATE_JSON", tmp_path / "state.json")
    monkeypatch.setattr(dio, "_util_threshold", lambda: 85.0)
    monkeypatch.setattr(dio, "_write_kb_s_threshold", lambda: 8192.0)
    monkeypatch.setattr(dio, "_automation_write_floor_kb_s", lambda: 2048.0)
    monkeypatch.setattr(dio, "_saturation_util_threshold", lambda: 95.0)
    monkeypatch.setattr(dio, "_hot_window_sec", lambda: 45.0)
    now = 1_000_000.0
    # High util but low write, below saturation — apt defers, automation does not
    hist = [{"t": now, "util_pct": 90.0, "write_kb_s": 110.0}]
    sample = {"sampled_at": now, "util_pct": 90.0, "write_kb_s": 110.0}
    defer_heavy, defer_new, detail = dio._defer_from_history(sample, hist)
    assert defer_heavy is True
    assert defer_new is False
    assert detail["hot_util"] is True
    assert detail["saturated"] is False
    assert detail["samples_in_window"] == 1


def test_defer_from_history_hot_util(tmp_path, monkeypatch):
    monkeypatch.setattr(dio, "_RUN_DIR", tmp_path)
    monkeypatch.setattr(dio, "_STATE_JSON", tmp_path / "state.json")
    monkeypatch.setattr(dio, "_util_threshold", lambda: 85.0)
    monkeypatch.setattr(dio, "_write_kb_s_threshold", lambda: 8192.0)
    monkeypatch.setattr(dio, "_automation_write_floor_kb_s", lambda: 2048.0)
    monkeypatch.setattr(dio, "_saturation_util_threshold", lambda: 95.0)
    monkeypatch.setattr(dio, "_hot_window_sec", lambda: 45.0)
    now = 1_000_000.0
    # High util but low write — apt defers, automation does not
    hist = [
        {"t": now - 10, "util_pct": 90.0, "write_kb_s": 100.0},
        {"t": now - 5, "util_pct": 92.0, "write_kb_s": 120.0},
        {"t": now, "util_pct": 88.0, "write_kb_s": 110.0},
    ]
    sample = {"sampled_at": now, "util_pct": 88.0, "write_kb_s": 110.0}
    defer_heavy, defer_new, detail = dio._defer_from_history(sample, hist)
    assert defer_heavy is True
    assert defer_new is False
    assert detail["hot_util"] is True


def test_defer_from_history_saturation_defers_automation(tmp_path, monkeypatch):
    """USB pegged at ≥95% util defers automation even with low write throughput."""
    monkeypatch.setattr(dio, "_util_threshold", lambda: 85.0)
    monkeypatch.setattr(dio, "_write_kb_s_threshold", lambda: 8192.0)
    monkeypatch.setattr(dio, "_automation_write_floor_kb_s", lambda: 2048.0)
    monkeypatch.setattr(dio, "_saturation_util_threshold", lambda: 95.0)
    monkeypatch.setattr(dio, "_hot_window_sec", lambda: 45.0)
    now = 1_000_000.0
    hist = [
        {"t": now - 20, "util_pct": 97.0, "write_kb_s": 400.0},
        {"t": now - 10, "util_pct": 98.0, "write_kb_s": 450.0},
        {"t": now, "util_pct": 96.0, "write_kb_s": 500.0},
    ]
    sample = {"sampled_at": now, "util_pct": 96.0, "write_kb_s": 500.0}
    defer_heavy, defer_new, detail = dio._defer_from_history(sample, hist)
    assert defer_heavy is True
    assert defer_new is True
    assert detail["saturated"] is True
    assert detail["hot_write"] is False


def test_defer_from_history_hot_write(tmp_path, monkeypatch):
    monkeypatch.setattr(dio, "_util_threshold", lambda: 85.0)
    monkeypatch.setattr(dio, "_write_kb_s_threshold", lambda: 8192.0)
    monkeypatch.setattr(dio, "_automation_write_floor_kb_s", lambda: 2048.0)
    monkeypatch.setattr(dio, "_saturation_util_threshold", lambda: 95.0)
    monkeypatch.setattr(dio, "_hot_window_sec", lambda: 45.0)
    now = 1_000_000.0
    hist = [{"t": now, "util_pct": 10.0, "write_kb_s": 9000.0}]
    sample = {"sampled_at": now, "util_pct": 10.0, "write_kb_s": 9000.0}
    defer_heavy, defer_new, detail = dio._defer_from_history(sample, hist)
    assert defer_heavy is True
    assert defer_new is True
    assert detail["hot_write"] is True


def test_defer_automation_util_plus_write_floor(tmp_path, monkeypatch):
    monkeypatch.setattr(dio, "_util_threshold", lambda: 85.0)
    monkeypatch.setattr(dio, "_write_kb_s_threshold", lambda: 8192.0)
    monkeypatch.setattr(dio, "_automation_write_floor_kb_s", lambda: 2048.0)
    monkeypatch.setattr(dio, "_saturation_util_threshold", lambda: 95.0)
    monkeypatch.setattr(dio, "_hot_window_sec", lambda: 45.0)
    now = 1_000_000.0
    hist = [
        {"t": now - 5, "util_pct": 90.0, "write_kb_s": 2500.0},
        {"t": now, "util_pct": 91.0, "write_kb_s": 2600.0},
    ]
    sample = {"sampled_at": now, "util_pct": 91.0, "write_kb_s": 2600.0}
    defer_heavy, defer_new, _ = dio._defer_from_history(sample, hist)
    assert defer_heavy is True
    assert defer_new is True


def test_disk_io_should_defer_phase_uses_defer_new_only(tmp_path, monkeypatch):
    """Automation gate ignores heavy-only (apt) signals."""
    monkeypatch.setattr(dio, "_RUN_DIR", tmp_path)
    monkeypatch.setattr(dio, "_RUN_JSON", tmp_path / "disk_io_pressure.json")
    monkeypatch.setattr(dio, "_disk_gate_enabled", lambda: True)
    monkeypatch.setattr(dio, "_disk_gate_exempt_phases", lambda: {"health_check"})
    monkeypatch.setattr(dio, "_stale_sec", lambda: 120.0)
    signal = {
        "source": "test",
        "device": "sdc",
        "util_pct": 90.0,
        "write_kb_s": 100.0,
        "defer_heavy_writes": True,
        "defer_new_work": False,
        "updated_at": "2099-01-01T00:00:00+00:00",
        "detail": {},
    }
    dio.write_run_file(signal)
    # Fresh written_at from write_run_file
    defer, _ = dio.disk_io_should_defer_phase("rss_collection")
    assert defer is False

    signal["defer_new_work"] = True
    dio.write_run_file(signal)
    defer, _ = dio.disk_io_should_defer_phase("rss_collection")
    assert defer is True

    defer_exempt, meta = dio.disk_io_should_defer_phase("health_check")
    assert defer_exempt is False
    assert meta.get("exempt") is True


def test_write_and_read_run_file_fail_open_stale(tmp_path, monkeypatch):
    monkeypatch.setattr(dio, "_RUN_DIR", tmp_path)
    monkeypatch.setattr(dio, "_RUN_JSON", tmp_path / "disk_io_pressure.json")
    monkeypatch.setattr(dio, "_stale_sec", lambda: 1.0)
    signal = {
        "source": "test",
        "device": "sdc",
        "util_pct": 99.0,
        "write_kb_s": 100.0,
        "defer_heavy_writes": True,
        "defer_new_work": True,
        "updated_at": "2000-01-01T00:00:00+00:00",
        "detail": {},
    }
    dio.write_run_file(signal)
    # Overwrite written_at to ancient
    path = tmp_path / "disk_io_pressure.json"
    data = json.loads(path.read_text())
    data["written_at"] = "2000-01-01T00:00:00+00:00"
    path.write_text(json.dumps(data))
    out = dio.read_run_file(max_age_sec=1.0)
    assert out["available"] is True
    assert out["stale"] is True
    assert out["defer_new_work"] is False  # fail-open
