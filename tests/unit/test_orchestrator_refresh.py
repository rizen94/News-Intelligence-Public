"""Unit tests for refresh workflow with mocked sources."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from domains.finance.orchestrator import FinanceOrchestrator
from domains.finance.orchestrator_types import (
    Task,
    TaskContext,
    TaskPriority,
    TaskStatus,
    TaskType,
)


@pytest.fixture
def orch():
    """Orchestrator with mocked evidence ledger."""
    return FinanceOrchestrator(evidence_ledger=MagicMock())


def test_plan_refresh_gold_topic(orch):
    """plan_refresh for topic=gold returns actions including gold."""
    task = Task(
        task_id="fin-plan",
        task_type=TaskType.refresh,
        priority=TaskPriority.high,
        parameters={"topic": "gold"},
        iteration_budget=3,
        current_iteration=0,
        context=TaskContext(),
        status=TaskStatus.queued,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    plan = orch._plan_refresh(task)
    assert "gold" in plan["actions"]


def test_evaluate_refresh_passes_with_enough_sources(orch):
    """evaluate_refresh passes when min_sources met."""
    task = Task(
        task_id="fin-eval",
        task_type=TaskType.refresh,
        priority=TaskPriority.high,
        parameters={},
        iteration_budget=3,
        current_iteration=0,
        context=TaskContext(),
        status=TaskStatus.queued,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    task.context.fetched_data["refresh_results"] = {
        "gold": {"results": {"freegoldapi": [{"date": "2024-01-01", "value": 2000}]}},
        "fred": {"observations": [{"date": "2024-01-01", "value": 100}], "success": True},
    }
    met = orch._evaluate_refresh(task)
    assert met is True


def test_evaluate_refresh_fails_with_no_sources(orch):
    """evaluate_refresh fails when 0 successful sources."""
    task = Task(
        task_id="fin-eval-fail",
        task_type=TaskType.refresh,
        priority=TaskPriority.high,
        parameters={},
        iteration_budget=3,
        current_iteration=0,
        context=TaskContext(),
        status=TaskStatus.queued,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    task.context.fetched_data["refresh_results"] = {
        "gold": {"results": {}},
        "fred": {"observations": [], "success": False},
    }
    met = orch._evaluate_refresh(task)
    assert met is False


@pytest.mark.asyncio
async def test_full_refresh_mocked_gold():
    """Full refresh with mocked gold returns TaskResult with sources_consulted, etc."""

    def mock_fetch_all(*, start=None, end=None, store=True):
        return {"freegoldapi": [{"date": "2024-01-15", "value": 2030.5, "unit": "USD/oz"}]}

    with patch("domains.finance.gold_amalgamator.fetch_all", side_effect=mock_fetch_all):
        orch = FinanceOrchestrator(evidence_ledger=MagicMock())
        task_id = orch.submit_task(TaskType.refresh, {"topic": "gold"}, priority=TaskPriority.high)
        result = await orch.run_task(task_id)

    assert result is not None
    assert result.sources_consulted
    assert result.sources_succeeded
    assert result.duration_ms >= 0
    assert result.created_at is not None
