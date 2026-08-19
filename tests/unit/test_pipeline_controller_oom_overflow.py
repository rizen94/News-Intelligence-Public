"""Overflow under Widow RAM pressure must not enqueue PopOS-preferring work locally."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _clear_remote(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REMOTE_PHASE_WORKER_OWNED_PHASES", raising=False)
    monkeypatch.delenv("REMOTE_PHASE_WORKER_ENABLED", raising=False)
    monkeypatch.delenv("AUTOMATION_BLOCK_PHASES", raising=False)
    monkeypatch.delenv("AUTOMATION_RSS_PAUSE_MB", raising=False)


def test_oom_overflow_skips_popos_gpu_phases(monkeypatch: pytest.MonkeyPatch) -> None:
    from services import pipeline_controller as pc

    monkeypatch.setattr(pc, "_popos_gpu_phases", lambda: frozenset({"storyline_assembly", "claim_extraction"}))
    monkeypatch.setattr(pc, "_phase_eligible", lambda *a, **k: True)
    monkeypatch.setattr(pc, "_spine_sql_tail_should_run", lambda pending: False)

    automation = SimpleNamespace(
        schedules={
            "health_check": {"enabled": True},
            "rss_feed_health": {"enabled": False},
            "mention_resolution": {"enabled": True},
            "storyline_assembly": {"enabled": True},
        }
    )
    pending = {
        "storyline_assembly": 100,
        "claim_extraction": 50,
        "mention_resolution": 10,
        "health_check": 0,
    }
    desired, branch = pc._pick_widow_oom_popos_overflow(
        pending,
        resources=None,
        phase_health={},
        automation=automation,
        stall_holds={},
        catchup=False,
    )
    assert branch == "widow_oom_popos_overflow"
    assert "storyline_assembly" not in desired
    assert "claim_extraction" not in desired
    assert "mention_resolution" in desired
