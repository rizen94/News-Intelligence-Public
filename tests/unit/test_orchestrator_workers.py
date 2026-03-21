"""Unit tests for orchestrator worker dispatch and normalization layer."""

from unittest.mock import MagicMock, patch

import pytest
from domains.finance.orchestrator import FinanceOrchestrator
from domains.finance.orchestrator_types import TaskType


@pytest.mark.asyncio
async def test_refresh_exception_stores_normalized_error_in_context():
    """When a worker raises, context.errors gets normalized error with error_type."""

    def failing_fetch(*, start=None, end=None, store=True):
        raise ConnectionError("network unreachable")

    with patch("domains.finance.gold_amalgamator.fetch_all", side_effect=failing_fetch):
        orch = FinanceOrchestrator(evidence_ledger=MagicMock())
        task_id = orch.submit_task(TaskType.refresh, {"topic": "gold"})
        result = await orch.run_task(task_id)

    assert result is not None
    task = orch._tasks[task_id]
    assert len(task.context.errors) >= 1
    err = task.context.errors[0]
    assert "error" in err
    assert "source" in err
    assert err["source"] == "gold"
    assert "network" in err["error"].lower() or "unreachable" in err["error"].lower()


@pytest.mark.asyncio
async def test_ledger_called_for_each_refresh_worker():
    """Ledger record is called for each worker (success or failure)."""
    record_calls = []

    def capture_record(*, report_id, source_type, source_id, evidence_data, **kwargs):
        record_calls.append({"source_id": source_id, "evidence_data": evidence_data})

    with patch("domains.finance.data.evidence_ledger.record", side_effect=capture_record):
        with patch(
            "domains.finance.gold_amalgamator.fetch_all",
            return_value={"freegoldapi": [{"date": "2024-01-01", "value": 2000}]},
        ):
            orch = FinanceOrchestrator(evidence_ledger=MagicMock())
            task_id = orch.submit_task(TaskType.refresh, {"topic": "gold"})
            await orch.run_task(task_id)

    assert len(record_calls) >= 1
    last = record_calls[-1]
    assert last["evidence_data"].get("status") in ("success", "error")
    assert last["source_id"] == "gold"


@pytest.mark.asyncio
async def test_ledger_records_failure_when_worker_raises():
    """When a worker raises, ledger records status=error."""
    record_calls = []

    def capture_record(*, report_id, source_type, source_id, evidence_data, **kwargs):
        record_calls.append({"source_id": source_id, "status": evidence_data.get("status")})

    with patch("domains.finance.data.evidence_ledger.record", side_effect=capture_record):
        with patch(
            "domains.finance.gold_amalgamator.fetch_all", side_effect=ValueError("rate limit")
        ):
            orch = FinanceOrchestrator(evidence_ledger=MagicMock())
            task_id = orch.submit_task(TaskType.refresh, {"topic": "gold"})
            await orch.run_task(task_id)

    assert any(c["status"] == "error" for c in record_calls)


@pytest.mark.asyncio
async def test_ingest_records_ledger_on_success_and_failure():
    """Ingest worker records ledger on both success and failure."""
    record_calls = []

    def capture_record(*, report_id, source_type, source_id, evidence_data, **kwargs):
        record_calls.append({"source_id": source_id, "status": evidence_data.get("status")})

    with patch("domains.finance.data.evidence_ledger.record", side_effect=capture_record):
        with patch(
            "domains.finance.data_sources.edgar.ingest_edgar_10ks",
            return_value=(5, ["chunk1", "chunk2"]),
        ):
            orch = FinanceOrchestrator(evidence_ledger=MagicMock())
            task_id = orch.submit_task(TaskType.ingest, {"filings_per_company": 1})
            await orch.run_task(task_id)

    assert any(c["source_id"] == "edgar" and c["status"] == "success" for c in record_calls)

    record_calls.clear()
    with patch("domains.finance.data.evidence_ledger.record", side_effect=capture_record):
        with patch(
            "domains.finance.data_sources.edgar.ingest_edgar_10ks",
            side_effect=RuntimeError("EDGAR down"),
        ):
            orch = FinanceOrchestrator(evidence_ledger=MagicMock())
            task_id = orch.submit_task(TaskType.ingest, {})
            result = await orch.run_task(task_id)

    assert any(c["source_id"] == "edgar" and c["status"] == "error" for c in record_calls)
    assert result.status.value == "failed"
