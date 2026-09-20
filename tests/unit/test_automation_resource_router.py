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
    assert mgr._phase_default_lane("claim_extraction") == "cpu"
    assert mgr._phase_default_lane("entity_extraction") == "cpu"
    assert mgr._phase_default_lane("event_tracking") == "gpu"
    assert mgr._phase_default_lane("context_sync") == "cpu"


def test_resolve_effective_lane_uses_phase_policy():
    mgr = AutomationManager(get_db_config())
    lane, reason = mgr._resolve_effective_lane("claim_extraction", "cpu_light")
    assert lane == "cpu"
    assert reason == "phase_policy"


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


def test_skip_redundant_claim_extraction_when_drain_pipeline_saturated(monkeypatch):
    monkeypatch.setenv("CLAIM_EXTRACTION_DRAIN", "true")
    monkeypatch.delenv("AUTOMATION_PER_PHASE_CONCURRENT_CAP_OVERRIDES", raising=False)
    monkeypatch.setattr(am, "AUTOMATION_PER_PHASE_CONCURRENT_CAP", 2)
    mgr = AutomationManager(get_db_config())
    mgr._running_tasks_by_phase["claim_extraction"] = 2
    mgr._scheduled_queue_depth_by_phase["claim_extraction"] = 0
    mgr._requested_queue_depth_by_phase["claim_extraction"] = 0
    assert mgr._should_skip_redundant_phase_request("claim_extraction") is True
    assert (
        mgr._should_skip_redundant_phase_request(
            "claim_extraction", allow_operator_bypass=True
        )
        is False
    )
    mgr._running_tasks_by_phase["claim_extraction"] = 1
    mgr._scheduled_queue_depth_by_phase["claim_extraction"] = 0
    mgr._requested_queue_depth_by_phase["claim_extraction"] = 0
    assert mgr._should_skip_redundant_phase_request("claim_extraction") is False


def test_skip_redundant_claim_extraction_off_when_drain_disabled(monkeypatch):
    monkeypatch.setenv("CLAIM_EXTRACTION_DRAIN", "false")
    monkeypatch.setattr(am, "AUTOMATION_PER_PHASE_CONCURRENT_CAP", 2)
    mgr = AutomationManager(get_db_config())
    mgr._running_tasks_by_phase["claim_extraction"] = 5
    assert mgr._should_skip_redundant_phase_request("claim_extraction") is False


def test_discard_redundant_claim_extraction_at_cap(monkeypatch):
    monkeypatch.setenv("CLAIM_EXTRACTION_DRAIN", "true")
    monkeypatch.setattr(am, "AUTOMATION_PER_PHASE_CONCURRENT_CAP", 2)
    mgr = AutomationManager(get_db_config())
    now = datetime.now(timezone.utc)
    t = Task(
        id="ce1",
        name="claim_extraction",
        priority=TaskPriority.NORMAL,
        status=TaskStatus.PENDING,
        created_at=now,
        metadata={"scheduled": True, "phase": 2, "estimated_duration": 60},
    )
    mgr._running_tasks_by_phase["claim_extraction"] = 2
    assert mgr._discard_redundant_claim_extraction_when_at_cap(t, 2) is True
    mgr._running_tasks_by_phase["claim_extraction"] = 1
    assert mgr._discard_redundant_claim_extraction_when_at_cap(t, 2) is False
    t2 = Task(
        id="ce2",
        name="claim_extraction",
        priority=TaskPriority.NORMAL,
        status=TaskStatus.PENDING,
        created_at=now,
        metadata={"requested_activity_id": "mon_1"},
    )
    mgr._running_tasks_by_phase["claim_extraction"] = 2
    assert mgr._discard_redundant_claim_extraction_when_at_cap(t2, 2) is False


def test_collection_cycle_concurrent_cap_defaults_to_one(monkeypatch):
    monkeypatch.delenv("AUTOMATION_PER_PHASE_CONCURRENT_CAP_OVERRIDES", raising=False)
    monkeypatch.setattr(am, "AUTOMATION_PER_PHASE_CONCURRENT_CAP", 8)
    mgr = AutomationManager(get_db_config())
    now = datetime.now(timezone.utc)
    t = Task(
        id="cc1",
        name="collection_cycle",
        priority=TaskPriority.NORMAL,
        status=TaskStatus.PENDING,
        created_at=now,
        metadata={"scheduled": True},
    )
    assert mgr._per_phase_execute_concurrent_cap(t) == 1
    mgr._running_tasks_by_phase["collection_cycle"] = 1
    assert mgr._discard_redundant_drain_when_at_cap(t, 1) is True
    assert mgr._should_skip_redundant_phase_request("collection_cycle") is True
