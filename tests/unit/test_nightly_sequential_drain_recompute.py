"""Nightly sequential drain must recompute the backlog once per loop, not twice."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from services import nightly_ingest_window_service as nws


class _Automation:
    def __init__(self, runs_before_empty: int):
        self.runs_before_empty = runs_before_empty
        self.run_nightly_sequential_phase = AsyncMock(side_effect=self._run)
        self.runs = 0

    async def _run(self, _phase_name):
        self.runs += 1
        return {"skipped": False}


def _drain(monkeypatch, *, runs_before_empty: int, loop_cap: int = 10):
    checks = {"n": 0}
    automation = _Automation(runs_before_empty)

    def _pending(_phase_name):
        checks["n"] += 1
        return automation.runs < runs_before_empty

    monkeypatch.setattr(nws, "_phase_loop_cap", lambda _p, _m: loop_cap)
    monkeypatch.setitem(
        __import__("sys").modules,
        "services.nightly_phase_idle",
        type(
            "_stub",
            (),
            {
                "is_single_pass_phase": staticmethod(lambda _p: False),
                "phase_has_pending_work": staticmethod(_pending),
            },
        ),
    )

    stats: dict = {}
    asyncio.run(
        nws._drain_sequential_phase(
            automation,
            "unified_intake_extraction",
            lambda: True,
            loop_cap,
            stats,
        )
    )
    return automation, checks, stats


def test_one_backlog_check_per_run_plus_the_final_empty_check(monkeypatch):
    automation, checks, stats = _drain(monkeypatch, runs_before_empty=3)

    assert automation.runs == 3
    assert stats["sequential_phase_runs"] == 3
    # 3 checks that found work + 1 that found none. The old shape checked twice per iteration,
    # and each check invalidates the backlog caches and re-runs every raw pending COUNT.
    assert checks["n"] == 4


def test_no_backlog_means_one_check_and_no_runs(monkeypatch):
    automation, checks, stats = _drain(monkeypatch, runs_before_empty=0)

    assert automation.runs == 0
    assert checks["n"] == 1
    assert stats == {}


def test_loop_cap_bounds_the_checks(monkeypatch):
    automation, checks, _stats = _drain(monkeypatch, runs_before_empty=99, loop_cap=4)

    assert automation.runs == 4
    assert checks["n"] == 4
