"""Adaptive batch: no DB-pool floor on local tracks; no artificial ceilings."""

from __future__ import annotations

from dataclasses import replace

from shared.adaptive_batch_policy import _PHASE_BOUNDS, synthesize_phase_bounds
from shared.catchup_host_metrics import (
    TRACK_BUILD,
    TRACK_CHEMISTRY_LOCAL,
    TRACK_DOSSIER_FAST,
    TRACK_ENRICH,
    TRACK_LOCAL,
    ResourceSnapshot,
    headroom_for_track,
    tune_batch_track,
)
from shared.phase_spec import HIGH_CHURN_PHASE_SPECS


def _snap(**kwargs) -> ResourceSnapshot:
    base = ResourceSnapshot(
        local_cpu_percent=20.0,
        local_memory_percent=45.0,
        db_worker_util=1.0,
        gpu_host="test",
        gpu_util_percent=None,
        gpu_temp_c=None,
        gpu_vram_percent=None,
        gpu_probe_source="test",
        cpu_llm_cpu_percent=None,
        local_cpu_headroom=0.80,
        local_memory_headroom=0.55,
        db_headroom=0.0,
        gpu_llm_headroom=0.7,
        cpu_llm_headroom=1.0,
    )
    return replace(base, **kwargs)


def test_local_enrich_build_ignore_saturated_db_pool():
    sat = _snap()
    for track in (TRACK_LOCAL, TRACK_ENRICH, TRACK_BUILD, TRACK_CHEMISTRY_LOCAL):
        assert headroom_for_track(track, sat) == 0.55
    assert headroom_for_track(TRACK_DOSSIER_FAST, sat) == 0.80


def test_local_tune_increases_when_db_saturated():
    sat = _snap()
    cfg = {
        "batch_min": 10,
        "batch_max": None,
        "batch_step": 10,
        "decrease_headroom": 0.25,
        "increase_headroom": 0.50,
        "memory_pressure_pct": 88.0,
        "memory_critical_pct": 94.0,
        "gpu_temp_decrease_c": 82,
        "gpu_temp_increase_max_c": 78,
    }
    new_b, action, _meta = tune_batch_track(
        TRACK_LOCAL, 10, sat, auto_tune=True, tuning_config=cfg
    )
    assert action == "increase"
    assert new_b == 20


def test_all_high_churn_specs_uncapped():
    for spec in HIGH_CHURN_PHASE_SPECS:
        assert spec.adaptive_max is None, spec.name


def test_phase_bounds_uncapped():
    capped = [k for k, b in _PHASE_BOUNDS.items() if b.get("max") is not None]
    assert capped == [], capped


def test_synthesize_bounds_uncapped():
    b = synthesize_phase_bounds("brand_new_drain_phase", 50)
    assert b["max"] is None
    assert b["min"] >= 1


def test_catchup_floors_are_high_enough_for_drain():
    """Regression: tiny mins make backlog ETA impossible."""
    specs = {s.name: s for s in HIGH_CHURN_PHASE_SPECS}
    assert specs["claims_to_facts"].adaptive_min >= 500
    assert specs["collision_sampling"].adaptive_min >= 64
    assert _PHASE_BOUNDS["topic_clustering"]["min"] >= 80
    assert _PHASE_BOUNDS["claims_to_facts"]["min"] >= 500
    assert _PHASE_BOUNDS["collision_sampling"]["min"] >= 64


def test_catchup_boost_jumps_on_severe_backlog(monkeypatch):
    from shared import adaptive_batch_policy as ab

    monkeypatch.setattr(ab, "_pending_for_phase", lambda _p: 50_000)
    bounds = {"min": 64, "max": None, "step": 32, "track": ab.TRACK_CHEMISTRY_LOCAL}
    new_b, action, meta = ab._apply_catchup_boost(
        "collision_sampling",
        bounds,
        current=64,
        new_batch=64,
        action="increase",
        meta={"reason": "headroom_ok", "headroom": 0.6},
    )
    assert action == "increase_catchup"
    assert new_b > 64
    assert meta.get("catchup_boost") is True


def test_phase_headroom_ignores_db_pool():
    sat = _snap(db_headroom=0.0, db_worker_util=1.0)
    # Non-GPU phase: CPU+RAM only
    assert sat.phase_headroom("claims_to_facts") == 0.55
    assert sat.phase_headroom("collision_sampling") == 0.55


def test_resolve_meta_never_decreases_for_db_pool_alone():
    from shared.adaptive_batch_policy import resolve_adaptive_batch

    sat = _snap(db_headroom=0.0, db_worker_util=1.0)
    _size, meta = resolve_adaptive_batch("protein_harden", 40, resources=sat)
    reason = str(meta.get("reason") or "")
    assert "db" not in reason.lower()
    assert meta.get("action") in ("increase", "hold", "hold_floor", "decrease")
    # With healthy CPU/RAM, saturated pool must not floor
    assert meta.get("action") == "increase" or float(meta.get("headroom") or 0) >= 0.25
