"""
Finance orchestrator — data structures for tasks, context, and results.
Dataclasses only; no ORM.
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from enum import Enum
from typing import Any


class TaskType(str, Enum):
    refresh = "refresh"
    ingest = "ingest"
    analysis = "analysis"
    report = "report"
    scheduled_refresh = "scheduled_refresh"


class TaskPriority(str, Enum):
    """Priorities are sortable: high(1) < medium(5) < low(10)."""

    high = "high"
    medium = "medium"
    low = "low"

    @property
    def sort_value(self) -> int:
        return {"high": 1, "medium": 5, "low": 10}.get(self.value, 5)


class TaskStatus(str, Enum):
    queued = "queued"
    planning = "planning"
    executing = "executing"
    evaluating = "evaluating"
    revising = "revising"
    complete = "complete"
    failed = "failed"


class ResultStatus(str, Enum):
    success = "success"
    partial = "partial"
    failed = "failed"


class ClaimVerdict(str, Enum):
    verified = "verified"
    unsupported = "unsupported"
    fabricated = "fabricated"


@dataclass
class EvidenceIndexEntry:
    """Single verifiable fact for prompt and verification."""

    ref_id: str
    source: str
    identifier: str
    date: date | datetime
    value: str | float
    unit: str
    context: str = ""


@dataclass
class ClaimCheck:
    """Result of verifying one concrete claim against evidence."""

    claim_text: str
    ref_id: str | None  # Expected evidence ref or None if unsupported
    verdict: ClaimVerdict


@dataclass
class VerificationResult:
    """Aggregate fact-check result for LLM output."""

    total_claims: int
    verified: int
    unsupported: int
    fabricated: int
    details: list[ClaimCheck] = field(default_factory=list)


@dataclass
class QualityCriteria:
    """Quality thresholds for evaluation."""

    min_sources: int = 1
    min_evidence_chunks: int = 0
    require_stat_validation: bool = False
    max_unsupported_claims: int = 5
    max_fabricated_claims: int = 0
    require_all_sources: bool = False
    max_source_failures: int = 999
    min_data_points: int = 0


@dataclass
class TaskContext:
    """Mutable accumulator for execution state."""

    fetched_data: dict[str, Any] = field(default_factory=dict)  # source -> DataResult
    evidence_index: list[EvidenceIndexEntry] = field(default_factory=list)
    evidence_chunks: list[Any] = field(default_factory=list)  # EvidenceChunk
    stats_results: dict[str, Any] = field(default_factory=dict)
    llm_prompt: str | None = None
    llm_response: str | None = None
    verification_result: VerificationResult | None = None
    revision_notes: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class TaskResult:
    """Final deliverable from a completed task."""

    task_id: str
    status: ResultStatus
    output: str | dict | list | None
    confidence: float
    iterations_used: int
    provenance: list[EvidenceIndexEntry]
    verification_summary: VerificationResult | None
    warnings: list[str]
    duration_ms: int
    sources_consulted: list[str] = field(default_factory=list)
    sources_succeeded: list[str] = field(default_factory=list)
    sources_failed: list[str] = field(default_factory=list)
    created_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON response."""
        return {
            "task_id": self.task_id,
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "output": self.output,
            "confidence": self.confidence,
            "iterations_used": self.iterations_used,
            "sources_consulted": self.sources_consulted,
            "sources_succeeded": self.sources_succeeded,
            "sources_failed": self.sources_failed,
            "warnings": self.warnings,
            "duration_ms": self.duration_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class RefreshSummary:
    """Output for completed refresh tasks."""

    sources: dict[str, dict[str, Any]]  # source_id -> {success, count, error?, error_type?}
    total_observations: int
    chunks_embedded: int = 0  # For EDGAR ingest
    chunk_ids: list[str] = field(default_factory=list)


@dataclass
class Task:
    """Orchestrator task — plan, execute, evaluate, decide."""

    task_id: str
    task_type: TaskType
    priority: TaskPriority
    parameters: dict[str, Any]
    iteration_budget: int
    current_iteration: int
    context: TaskContext
    status: TaskStatus
    created_at: datetime
    updated_at: datetime

    def update_status(self, status: TaskStatus) -> None:
        """Update task status (and updated_at)."""
        self.status = status
        self.updated_at = datetime.now(timezone.utc)
