"""TRACK_BUILD (entity_profile_build) must size from Widow local headroom."""

from __future__ import annotations

from shared.catchup_host_metrics import (
    TRACK_BUILD,
    TRACK_GPU,
    ResourceSnapshot,
    headroom_for_track,
    tune_batch_track,
)


def _snap(**kwargs) -> ResourceSnapshot:
    base = dict(
        local_cpu_percent=20.0,
        local_memory_percent=40.0,
        db_worker_util=0.1,
        gpu_host="192.168.93.99",
        gpu_util_percent=None,
        gpu_temp_c=None,
        gpu_vram_percent=None,
        gpu_probe_source="unavailable",
        cpu_llm_cpu_percent=None,
        local_cpu_headroom=0.8,
        local_memory_headroom=0.7,
        db_headroom=0.9,
        gpu_llm_headroom=0.1,
        cpu_llm_headroom=0.5,
    )
    base.update(kwargs)
    return ResourceSnapshot(**base)


def test_track_build_headroom_uses_local_not_popos_gpu():
    snap = _snap(gpu_llm_headroom=0.05, local_memory_headroom=0.75, local_cpu_headroom=0.8)
    h = headroom_for_track(TRACK_BUILD, snap)
    assert h == min(0.8, 0.75, 0.9)
    assert h != snap.gpu_llm_headroom


def test_track_build_can_increase_without_gpu_probe():
    snap = _snap(
        gpu_llm_headroom=0.05,
        local_memory_headroom=0.8,
        local_cpu_headroom=0.8,
        local_memory_percent=40.0,
        gpu_probe_source="unavailable",
    )
    cfg = {
        "batch_min": 25,
        "batch_max": 150,
        "batch_step": 10,
        "build_batch_max": 150,
        "enrich_batch_max": 120,
        "dossier_fast_batch_min": 20,
        "increase_headroom": 0.50,
        "decrease_headroom": 0.25,
        "memory_pressure_pct": 88,
        "memory_critical_pct": 94,
        "gpu_temp_decrease_c": 82,
        "gpu_temp_increase_max_c": 78,
    }
    new_batch, action, meta = tune_batch_track(
        TRACK_BUILD, 100, snap, auto_tune=True, tuning_config=cfg
    )
    assert action == "increase"
    assert new_batch == 110
    assert meta["track"] == TRACK_BUILD


def test_track_gpu_still_blocks_on_unavailable_probe():
    snap = _snap(gpu_llm_headroom=0.9, gpu_probe_source="unavailable")
    cfg = {
        "batch_min": 40,
        "batch_max": 120,
        "batch_step": 10,
        "build_batch_max": 150,
        "enrich_batch_max": 120,
        "dossier_fast_batch_min": 20,
        "increase_headroom": 0.50,
        "decrease_headroom": 0.25,
        "memory_pressure_pct": 88,
        "memory_critical_pct": 94,
        "gpu_temp_decrease_c": 82,
        "gpu_temp_increase_max_c": 78,
    }
    _new, action, meta = tune_batch_track(
        TRACK_GPU, 80, snap, auto_tune=True, tuning_config=cfg
    )
    assert action == "hold"
    assert "gpu_metrics_unavailable" in (meta.get("reason") or "")
