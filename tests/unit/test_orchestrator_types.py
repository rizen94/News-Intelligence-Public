"""Unit tests for orchestrator data structures."""

from datetime import datetime, timezone, date

import pytest

from domains.finance.orchestrator_types import (
    Task,
    TaskContext,
    TaskType,
    TaskStatus,
    TaskPriority,
    TaskResult,
    ResultStatus,
    QualityCriteria,
    EvidenceIndexEntry,
)


def test_task_has_unique_id():
    """Task auto-generates a unique task_id via submit_task; manually created tasks get assigned ids."""
    now = datetime.now(timezone.utc)
    t1 = Task(
        task_id="fin-abc123",
        task_type=TaskType.refresh,
        priority=TaskPriority.high,
        parameters={},
        iteration_budget=3,
        current_iteration=0,
        context=TaskContext(),
        status=TaskStatus.queued,
        created_at=now,
        updated_at=now,
    )
    t2 = Task(
        task_id="fin-def456",
        task_type=TaskType.refresh,
        priority=TaskPriority.high,
        parameters={},
        iteration_budget=3,
        current_iteration=0,
        context=TaskContext(),
        status=TaskStatus.queued,
        created_at=now,
        updated_at=now,
    )
    assert t1.task_id != t2.task_id


def test_task_update_status_changes_status_and_updated_at():
    """Task.update_status changes both status and updated_at."""
    now = datetime.now(timezone.utc)
    t = Task(
        task_id="fin-test",
        task_type=TaskType.refresh,
        priority=TaskPriority.high,
        parameters={},
        iteration_budget=3,
        current_iteration=0,
        context=TaskContext(),
        status=TaskStatus.queued,
        created_at=now,
        updated_at=now,
    )
    t.update_status(TaskStatus.executing)
    assert t.status == TaskStatus.executing
    assert t.updated_at >= now


def test_task_context_initializes_with_empty_collections():
    """TaskContext initializes with all empty collections."""
    ctx = TaskContext()
    assert ctx.fetched_data == {}
    assert ctx.evidence_index == []
    assert ctx.evidence_chunks == []
    assert ctx.revision_notes == []
    assert ctx.errors == []


def test_task_priority_sorts_correctly():
    """TaskPriority sorts correctly — high < medium < low by integer value."""
    assert TaskPriority.high.sort_value < TaskPriority.medium.sort_value
    assert TaskPriority.medium.sort_value < TaskPriority.low.sort_value
    assert TaskPriority.high.sort_value == 1
    assert TaskPriority.medium.sort_value == 5
    assert TaskPriority.low.sort_value == 10


def test_evidence_index_entry_all_field_types():
    """EvidenceIndexEntry can be created with float value, str value."""
    e1 = EvidenceIndexEntry(
        ref_id="REF-001",
        source="fred",
        identifier="IQ12260",
        date=date.today(),
        value=2650.5,
        unit="USD/oz",
    )
    e2 = EvidenceIndexEntry(
        ref_id="REF-002",
        source="edgar",
        identifier="10-K",
        date=date.today(),
        value="text summary",
        unit="text",
        context="mining disclosure",
    )
    assert e1.value == 2650.5
    assert e2.value == "text summary"
    assert e2.context == "mining disclosure"


def test_quality_criteria_sensible_defaults():
    """QualityCriteria has sensible defaults."""
    qc = QualityCriteria()
    assert qc.min_sources == 1
    assert qc.require_all_sources is False
    assert qc.max_source_failures >= 0
    assert qc.min_data_points == 0


def test_task_result_to_dict():
    """TaskResult can be serialized to dict for JSON response."""
    now = datetime.now(timezone.utc)
    tr = TaskResult(
        task_id="fin-123",
        status=ResultStatus.success,
        output={"sources": {}},
        confidence=0.9,
        iterations_used=1,
        provenance=[],
        verification_summary=None,
        warnings=[],
        duration_ms=100,
        sources_consulted=["gold"],
        sources_succeeded=["gold"],
        sources_failed=[],
        created_at=now,
    )
    d = tr.to_dict()
    assert d["task_id"] == "fin-123"
    assert d["status"] == "success"
    assert d["sources_consulted"] == ["gold"]
    assert d["sources_succeeded"] == ["gold"]
    assert d["sources_failed"] == []
    assert "created_at" in d


def test_task_context_isolated_between_tasks():
    """Task context is isolated — mutable defaults don't share state."""
    ctx1 = TaskContext()
    ctx2 = TaskContext()
    ctx1.fetched_data["gold"] = [1, 2, 3]
    ctx1.errors.append({"source": "gold", "msg": "test"})
    assert "gold" not in ctx2.fetched_data
    assert len(ctx2.errors) == 0
