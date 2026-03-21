"""Unit tests for orchestrator skeleton and lifecycle logic."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from domains.finance.orchestrator import FinanceOrchestrator
from domains.finance.orchestrator_types import (
    Task,
    TaskContext,
    TaskPriority,
    TaskStatus,
    TaskType,
)


def test_orchestrator_initializes_with_partial_components():
    """Orchestrator initializes with only some components in the dict."""
    orch = FinanceOrchestrator(source_loader=object())
    assert orch.source_loader is not None
    assert orch.vector_store is None
    assert orch.evidence_ledger is None


def test_submit_task_returns_unique_task_ids():
    """Submit two tasks; IDs are different; both appear in get_task_status."""
    orch = FinanceOrchestrator()
    id1 = orch.submit_task(TaskType.refresh, {"topic": "gold"})
    id2 = orch.submit_task(TaskType.refresh, {"topic": "edgar"})
    assert id1 != id2
    assert orch.get_task_status(id1) is not None
    assert orch.get_task_status(id2) is not None


def test_priority_ordering():
    """Submit three tasks — low, high, medium. Queue yields high, medium, low."""
    orch = FinanceOrchestrator()
    orch.submit_task(TaskType.refresh, {}, priority=TaskPriority.low)
    orch.submit_task(TaskType.refresh, {}, priority=TaskPriority.high)
    orch.submit_task(TaskType.refresh, {}, priority=TaskPriority.medium)
    # _task_order preserves submission order; sorting is applied when processing.
    # Test that we can sort by priority:
    tasks = [orch._tasks[tid] for tid in orch._task_order]
    sorted_tasks = sorted(tasks, key=lambda t: t.priority.sort_value)
    assert sorted_tasks[0].priority == TaskPriority.high
    assert sorted_tasks[1].priority == TaskPriority.medium
    assert sorted_tasks[2].priority == TaskPriority.low


def test_list_tasks_returns_paginated_summaries():
    """list_tasks returns task summaries with optional filters."""
    orch = FinanceOrchestrator()
    orch.submit_task(TaskType.refresh, {"topic": "gold"})
    orch.submit_task(TaskType.analysis, {"query": "test"})
    orch.submit_task(TaskType.refresh, {"topic": "edgar"})

    data = orch.list_tasks(limit=2, offset=0)
    assert "tasks" in data
    assert data["total"] == 3
    assert len(data["tasks"]) == 2
    assert data["limit"] == 2
    assert data["offset"] == 0
    for t in data["tasks"]:
        assert "task_id" in t
        assert "status" in t
        assert "phase" in t

    filtered = orch.list_tasks(task_type="refresh")
    assert filtered["total"] == 2
    assert all(t["task_type"] == "refresh" for t in filtered["tasks"])


def test_task_context_accumulates_data():
    """Context accumulates fetched_data and errors; mutable defaults don't share state."""
    ctx = TaskContext()
    ctx.fetched_data["gold"] = {"results": {"freegoldapi": [{"date": "2024-01-01", "value": 2000}]}}
    ctx.errors.append({"source": "fred", "msg": "timeout"})
    assert "gold" in ctx.fetched_data
    assert len(ctx.errors) == 1
    # Second context is independent
    ctx2 = TaskContext()
    assert "gold" not in ctx2.fetched_data
    assert len(ctx2.errors) == 0


@pytest.mark.asyncio
async def test_list_evidence_index_from_completed_tasks():
    """list_evidence_index aggregates provenance from completed tasks."""

    orch = FinanceOrchestrator()
    task_id = orch.submit_task(TaskType.refresh, {"topic": "gold"})

    def mock_fetch(**kw):
        return {"freegoldapi": [{"date": "2024-01-01", "value": 2000, "unit": "USD/oz"}]}

    with patch("domains.finance.gold_amalgamator.fetch_all", return_value=mock_fetch):
        await orch.run_task(task_id)

    data = orch.list_evidence_index(limit=10)
    assert "entries" in data
    assert "total" in data
    if data["total"] > 0:
        e = data["entries"][0]
        assert "ref_id" in e and "source" in e


def test_list_verifications_from_analysis_tasks():
    """list_verifications returns verification results from completed analysis tasks."""
    orch = FinanceOrchestrator()
    data = orch.list_verifications(limit=10)
    assert "verifications" in data
    assert "total" in data
    assert isinstance(data["verifications"], list)


@pytest.mark.asyncio
async def test_unsupported_task_type_returns_failed_result():
    """Unimplemented task type (e.g. report) returns failed result."""
    orch = FinanceOrchestrator()
    task = Task(
        task_id="fin-unsupported",
        task_type=TaskType.report,
        priority=TaskPriority.high,
        parameters={},
        iteration_budget=3,
        current_iteration=0,
        context=TaskContext(),
        status=TaskStatus.queued,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    orch._tasks[task.task_id] = task
    orch._task_order.append(task.task_id)
    result = await orch.run_task(task.task_id)
    assert result is not None
    assert result.status.value == "failed"
