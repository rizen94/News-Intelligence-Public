import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "api"))

import pytest

import services.automation_manager as am
from config.database import get_db_config
from services.automation_manager import (
    AutomationManager,
    Task,
    TaskPriority,
    TaskStatus,
)


def test_phase_default_lane_policy():
    mgr = AutomationManager(get_db_config())
    assert mgr._phase_default_lane("content_refinement_queue") == "gpu"
    assert mgr._phase_default_lane("claim_extraction") == "gpu"
    assert mgr._phase_default_lane("context_sync") == "cpu"


def test_dynamic_lane_resolution_prefers_gpu_when_cpu_hot(monkeypatch):
    monkeypatch.setattr(am, "AUTOMATION_DYNAMIC_RESOURCE_ROUTING_ENABLED", True)
    mgr = AutomationManager(get_db_config())
    mgr._resource_headroom = {"cpu_headroom": 0.1, "gpu_headroom": 0.8, "db_headroom": 0.5}
    # Use a default-CPU-lane phase (not in OLLAMA_AUTOMATION_PHASES) with cpu_light class.
    lane, reason = mgr._resolve_effective_lane("metadata_enrichment", "cpu_light")
    assert lane == "gpu"
    assert reason == "dynamic_cpu_hot_gpu_available"


def test_db_heavy_cooldown_expands_under_pool_pressure(monkeypatch):
    monkeypatch.setattr(am, "AUTOMATION_DYNAMIC_RESOURCE_ROUTING_ENABLED", True)
    mgr = AutomationManager(get_db_config())
    mgr._resource_headroom = {"cpu_headroom": 0.6, "gpu_headroom": 0.6, "db_headroom": 0.1}
    mult, reason = mgr._dynamic_cooldown_multiplier("db_heavy")
    assert mult > 1.0
    assert reason == "db_pool_pressure"


@pytest.mark.asyncio
async def test_scheduled_depth_cap_blocks_second_enqueue(monkeypatch):
    monkeypatch.setattr(am, "AUTOMATION_MAX_SCHEDULED_DEPTH_PER_PHASE", 1)
    mgr = AutomationManager(get_db_config())
    now = datetime.now(timezone.utc)
    meta = {"scheduled": True, "phase": 99, "estimated_duration": 1}
    a = Task(
        id="cap_a",
        name="cache_cleanup",
        priority=TaskPriority.NORMAL,
        status=TaskStatus.PENDING,
        created_at=now,
        metadata=dict(meta),
    )
    b = Task(
        id="cap_b",
        name="cache_cleanup",
        priority=TaskPriority.NORMAL,
        status=TaskStatus.PENDING,
        created_at=now,
        metadata=dict(meta),
    )
    assert await mgr._enqueue_scheduled_task(a) is True
    assert await mgr._enqueue_scheduled_task(b) is False
    assert mgr._scheduled_queue_depth_by_phase["cache_cleanup"] == 1


@pytest.mark.asyncio
async def test_bypass_schedule_depth_cap_allows_second_enqueue(monkeypatch):
    monkeypatch.setattr(am, "AUTOMATION_MAX_SCHEDULED_DEPTH_PER_PHASE", 1)
    mgr = AutomationManager(get_db_config())
    now = datetime.now(timezone.utc)
    meta = {"scheduled": True, "phase": 99, "estimated_duration": 1}

    async def _one(i: int) -> bool:
        return await mgr._enqueue_scheduled_task(
            Task(
                id=f"by_{i}",
                name="data_cleanup",
                priority=TaskPriority.NORMAL,
                status=TaskStatus.PENDING,
                created_at=now,
                metadata=dict(meta),
            ),
            bypass_schedule_depth_cap=(i == 2),
        )

    assert await _one(1) is True
    assert await _one(2) is True
    assert mgr._scheduled_queue_depth_by_phase["data_cleanup"] == 2


def test_per_phase_scheduler_cap_blocks_when_at_capacity(monkeypatch):
    monkeypatch.setattr(am, "AUTOMATION_PER_PHASE_CONCURRENT_CAP", 2)
    mgr = AutomationManager(get_db_config())
    mgr._running_tasks_by_phase["claim_extraction"] = 2
    sched = mgr.schedules.get("claim_extraction") or {}
    ok = mgr._should_run_task(
        "claim_extraction",
        {
            "enabled": True,
            "depends_on": [],
            "last_run": None,
            "phase": 5,
            "priority": am.TaskPriority.NORMAL,
            "interval": 60,
        },
        datetime.now(timezone.utc),
        {"claim_extraction": 100},
    )
    assert ok is False


def test_per_phase_execute_cap_zero_for_nightly_sequential(monkeypatch):
    monkeypatch.setattr(am, "AUTOMATION_PER_PHASE_CONCURRENT_CAP", 2)
    mgr = AutomationManager(get_db_config())
    now = datetime.now(timezone.utc)
    t = Task(
        id="n1",
        name="claim_extraction",
        priority=TaskPriority.NORMAL,
        status=TaskStatus.PENDING,
        created_at=now,
        metadata={"nightly_sequential_drain": True},
    )
    assert mgr._per_phase_execute_concurrent_cap(t) == 0
