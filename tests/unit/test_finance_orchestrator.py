"""
Unit tests for Finance Orchestrator.
Uses real data where possible (gold fetch, plan logic). No mocked/fake values.
"""

import pytest
from domains.finance.orchestrator import FinanceOrchestrator
from domains.finance.orchestrator_types import (
    Task,
    TaskContext,
    TaskPriority,
    TaskStatus,
    TaskType,
)


def test_orchestrator_initializes_with_minimal_config():
    """Orchestrator initializes with no component references."""
    orch = FinanceOrchestrator()
    assert orch.source_loader is None
    assert orch._tasks == {}
    assert orch.cpu_concurrency == 4


def test_orchestrator_initializes_with_components():
    """Orchestrator accepts component references."""
    loader = object()
    orch = FinanceOrchestrator(source_loader=loader)
    assert orch.source_loader is loader


def test_submit_task_returns_task_id():
    """submit_task creates task, returns unique task_id."""
    orch = FinanceOrchestrator()
    task_id = orch.submit_task(
        task_type=TaskType.refresh,
        parameters={"topic": "gold"},
        priority=TaskPriority.high,
    )
    assert task_id is not None
    assert task_id.startswith("fin-")
    assert len(task_id) > 10


def test_submit_task_stores_queued_task():
    """Submitted task is stored with queued status."""
    orch = FinanceOrchestrator()
    task_id = orch.submit_task(
        task_type=TaskType.analysis,
        parameters={"query": "gold price trend"},
        priority=TaskPriority.high,
    )
    status = orch.get_task_status(task_id)
    assert status is not None
    assert status["task_id"] == task_id
    assert status["status"] == TaskStatus.queued.value
    assert status["task_type"] == TaskType.analysis.value
    assert status["priority"] == TaskPriority.high.value
    assert status["current_iteration"] == 0
    assert status["iteration_budget"] == 3


def test_get_task_status_unknown_returns_none():
    """Unknown task_id returns None."""
    orch = FinanceOrchestrator()
    assert orch.get_task_status("fin-nonexistent") is None


def test_get_task_result_incomplete_returns_none():
    """get_task_result returns None for queued (non-complete) task."""
    orch = FinanceOrchestrator()
    task_id = orch.submit_task(task_type=TaskType.refresh, parameters={})
    result = orch.get_task_result(task_id)
    # Phase 1: tasks never complete, so result is None
    assert result is None


def test_multiple_tasks_stored_independently():
    """Multiple submitted tasks are stored and retrievable."""
    orch = FinanceOrchestrator()
    id1 = orch.submit_task(TaskType.refresh, {"topic": "gold"})
    id2 = orch.submit_task(TaskType.ingest, {"source": "edgar"})
    assert id1 != id2
    s1 = orch.get_task_status(id1)
    s2 = orch.get_task_status(id2)
    assert s1["task_type"] == TaskType.refresh.value
    assert s2["task_type"] == TaskType.ingest.value


def test_submit_task_with_custom_budget():
    """submit_task accepts custom iteration_budget."""
    orch = FinanceOrchestrator()
    task_id = orch.submit_task(
        TaskType.analysis,
        {"query": "test"},
        iteration_budget=5,
    )
    status = orch.get_task_status(task_id)
    assert status["iteration_budget"] == 5


# Phase 2 — Plan logic and real-data refresh
@pytest.mark.asyncio
async def test_plan_refresh_determines_actions():
    """plan_refresh returns correct actions for each topic."""
    from datetime import datetime, timezone

    orch = FinanceOrchestrator()
    task = Task(
        task_id="test",
        task_type=TaskType.refresh,
        priority=TaskPriority.high,
        parameters={"topic": "gold", "start_date": "2024-01-01"},
        iteration_budget=3,
        current_iteration=0,
        context=TaskContext(),
        status=TaskStatus.queued,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    plan = orch._plan_refresh(task)
    assert "gold" in plan["actions"]
    assert plan.get("start") == "2024-01-01"

    task.parameters["topic"] = "edgar"
    plan2 = orch._plan_refresh(task)
    assert "edgar" in plan2["actions"]

    task.parameters["topic"] = "all"
    plan3 = orch._plan_refresh(task)
    assert "gold" in plan3["actions"]
    assert "edgar" in plan3["actions"]


@pytest.mark.asyncio
async def test_run_task_refresh_gold_real():
    """Gold refresh fetches real data from FreeGoldAPI. Requires network."""
    orch = FinanceOrchestrator()
    task_id = orch.submit_task(TaskType.refresh, {"topic": "gold"}, priority=TaskPriority.high)
    result = await orch.run_task(task_id)
    assert result is not None
    assert result.output is not None
    assert "sources" in result.output
    sources = result.output["sources"]
    assert len(sources) >= 1
    total = result.output.get("total_observations", 0)
    assert total >= 0


@pytest.mark.asyncio
async def test_evidence_index_built_from_gold_refresh():
    """Gold refresh builds evidence index (provenance) from real observations."""
    orch = FinanceOrchestrator()
    task_id = orch.submit_task(TaskType.refresh, {"topic": "gold"}, priority=TaskPriority.high)
    result = await orch.run_task(task_id)
    assert result is not None
    assert result.provenance is not None
    assert len(result.provenance) >= 1
    entry = result.provenance[0]
    assert entry.ref_id.startswith("REF-")
    assert entry.source == "gold"
    assert entry.value is not None


@pytest.mark.asyncio
async def test_run_task_analysis_gold_real():
    """Analysis task: fetches gold, builds evidence index, verification, runs through LLM."""
    orch = FinanceOrchestrator()
    task_id = orch.submit_task(
        TaskType.analysis,
        {"query": "What is the recent gold price trend?", "topic": "gold"},
        priority=TaskPriority.high,
    )
    result = await orch.run_task(task_id)
    assert result is not None
    assert result.output is not None
    assert "response" in result.output
    assert result.provenance is not None
    assert len(result.provenance) >= 1
    assert result.verification_summary is not None


@pytest.mark.asyncio
async def test_schedule_status():
    """Schedule status returns config structure."""
    orch = FinanceOrchestrator()
    status = orch.get_schedule_status()
    assert "tasks" in status
