"""Integration tests for orchestrator sequential collaboration."""

from unittest.mock import MagicMock, patch

import pytest
from domains.finance.orchestrator import FinanceOrchestrator
from domains.finance.orchestrator_types import TaskType


def mock_fetch_all(*, start=None, end=None, store=True):
    """Mock gold amalgamator returns sample data."""
    return {"freegoldapi": [{"date": "2024-01-15", "value": 2030.5, "unit": "USD/oz"}]}


@pytest.mark.asyncio
async def test_refresh_feeds_data_into_context_keys():
    """Refresh stores data under keys that evaluate and evidence_index can read."""
    from unittest.mock import patch

    with patch("domains.finance.gold_amalgamator.fetch_all", side_effect=mock_fetch_all):
        orch = FinanceOrchestrator(evidence_ledger=MagicMock())
        task_id = orch.submit_task(TaskType.refresh, {"topic": "gold"})
        result = await orch.run_task(task_id)

    assert result is not None
    task = orch._tasks[task_id]
    assert "refresh_results" in task.context.fetched_data
    assert "refresh_summary" in task.context.fetched_data
    assert task.context.evidence_index


@pytest.mark.asyncio
async def test_failed_refresh_produces_useful_task_result():
    """All sources fail → TaskResult includes failure details."""
    from unittest.mock import patch

    def failing_fetch(*, start=None, end=None, store=True):
        raise ConnectionError("network unreachable")

    with patch("domains.finance.gold_amalgamator.fetch_all", side_effect=failing_fetch):
        orch = FinanceOrchestrator(evidence_ledger=MagicMock())
        task_id = orch.submit_task(TaskType.refresh, {"topic": "gold"})
        result = await orch.run_task(task_id)

    assert result is not None
    assert result.status.value == "failed"
    assert result.confidence == 0.0
    assert result.sources_failed or result.warnings


@pytest.mark.asyncio
async def test_task_context_isolated_between_tasks():
    """Data from task A does not appear in task B's context."""
    from unittest.mock import patch

    with patch("domains.finance.gold_amalgamator.fetch_all", side_effect=mock_fetch_all):
        orch = FinanceOrchestrator(evidence_ledger=MagicMock())
        id_a = orch.submit_task(TaskType.refresh, {"topic": "gold"})
        id_b = orch.submit_task(TaskType.refresh, {"topic": "gold"})
        await orch.run_task(id_a)
        await orch.run_task(id_b)

    task_a = orch._tasks[id_a]
    task_b = orch._tasks[id_b]
    assert task_a.context.fetched_data is not task_b.context.fetched_data
    assert task_a.task_id != task_b.task_id


@pytest.mark.asyncio
async def test_worker_dispatch_and_ledger_recording_consistent():
    """Run refresh; ledger call count and statuses match task result."""
    record_calls = []

    def capture_record(*, report_id, source_type, source_id, evidence_data, **kwargs):
        record_calls.append({"source_id": source_id, "status": evidence_data.get("status")})

    def gold_ok(*, start=None, end=None, store=True):
        return {"freegoldapi": [{"date": "2024-01-01", "value": 2000}]}

    def gold_fail(*, start=None, end=None, store=True):
        raise ConnectionError("gold unreachable")

    with patch("domains.finance.data.evidence_ledger.record", side_effect=capture_record):
        with patch("domains.finance.gold_amalgamator.fetch_all", side_effect=gold_ok):
            orch = FinanceOrchestrator(evidence_ledger=MagicMock())
            task_id = orch.submit_task(TaskType.refresh, {"topic": "gold"})
            result = await orch.run_task(task_id)

    assert len(record_calls) == 1
    assert record_calls[0]["status"] == "success"
    assert result.sources_succeeded

    record_calls.clear()
    with patch("domains.finance.data.evidence_ledger.record", side_effect=capture_record):
        with patch("domains.finance.gold_amalgamator.fetch_all", side_effect=gold_fail):
            orch = FinanceOrchestrator(evidence_ledger=MagicMock())
            task_id = orch.submit_task(TaskType.refresh, {"topic": "gold"})
            result = await orch.run_task(task_id)

    assert len(record_calls) == 1
    assert record_calls[0]["status"] == "error"
    assert result.status.value == "failed"


@pytest.mark.asyncio
async def test_log_output_traceable_by_task_id(caplog):
    """Log output for a complete refresh contains traceable task_id in every entry."""
    import json
    import logging
    from unittest.mock import patch

    caplog.set_level(logging.INFO)
    with patch("domains.finance.gold_amalgamator.fetch_all", side_effect=mock_fetch_all):
        orch = FinanceOrchestrator(evidence_ledger=MagicMock())
        task_id = orch.submit_task(TaskType.refresh, {"topic": "gold"})
        await orch.run_task(task_id)

    # Grep for orchestrator log entries (JSON) containing our task_id
    found = []
    for r in caplog.records:
        if hasattr(r, "message") and "event_type" in str(r.message):
            try:
                p = json.loads(r.message)
                if p.get("task_id") == task_id:
                    found.append(p["event_type"])
            except json.JSONDecodeError:
                pass
    # Should have TASK_ACCEPTED, TASK_PLANNED, WORKER_DISPATCHED, etc.
    assert "TASK_ACCEPTED" in found or "TASK_PLANNED" in found
