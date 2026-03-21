"""
Orchestrator Decision Logger — structured decision records at branching points.
Captures available_options, chosen_option, rationale, decision_inputs; outcome backfill.
Writes to logs/orchestrator_decisions.jsonl and activity.jsonl.
When file write or activity_logger forward fails, the write is no-op (failure swallowed).
"""

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOG_DIR: Path | None = None
_INITIALIZED = False
_LOCK = threading.Lock()
_PENDING: dict[str, dict] = {}


def _ensure_init() -> Path:
    global _LOG_DIR, _INITIALIZED
    if _INITIALIZED and _LOG_DIR:
        return _LOG_DIR
    with _LOCK:
        if _INITIALIZED and _LOG_DIR:
            return _LOG_DIR
        try:
            from config.paths import LOG_DIR

            _LOG_DIR = Path(LOG_DIR)
        except Exception:
            _LOG_DIR = Path(__file__).resolve().parents[3] / "logs"
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        _INITIALIZED = True
    return _LOG_DIR


def log_decision(
    task_id: str,
    decision_point: str,
    current_phase: str,
    chosen_option: str,
    rationale: str,
    available_options: list[str] | None = None,
    elapsed_ms: float | None = None,
    iterations_so_far: int | None = None,
    **decision_inputs: Any,
) -> str:
    """
    Log an orchestrator decision at a branching point. Returns decision_id.
    """
    decision_id = f"dec-{uuid.uuid4().hex[:12]}"
    ts = datetime.now(timezone.utc).isoformat()

    record = {
        "decision_id": decision_id,
        "task_id": task_id,
        "decision_point": decision_point,
        "current_phase": current_phase,
        "chosen_option": chosen_option,
        "rationale": rationale,
        "available_options": available_options or [],
        "elapsed_ms": elapsed_ms,
        "iterations_so_far": iterations_so_far,
        "decision_inputs": decision_inputs,
        "timestamp": ts,
    }
    _PENDING[decision_id] = record

    log_dir = _ensure_init()
    try:
        with open(log_dir / "orchestrator_decisions.jsonl", "a") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception:
        pass

    try:
        from shared.logging.activity_logger import log_activity

        log_activity(
            component="orchestrator",
            event_type="orchestrator_decision",
            status="decided",
            message=f"{decision_point}: {chosen_option} — {rationale}",
            decision_id=decision_id,
            task_id=task_id,
            decision_point=decision_point,
            chosen_option=chosen_option,
            rationale=rationale,
        )
    except Exception:
        pass

    return decision_id


def log_decision_outcome(
    decision_id: str,
    outcome_status: str,
    outcome_duration_ms: float | None = None,
) -> None:
    """
    Backfill outcome for a previously logged decision.
    """
    if decision_id not in _PENDING:
        return
    record = _PENDING.pop(decision_id)
    record["outcome_status"] = outcome_status
    record["outcome_duration_ms"] = outcome_duration_ms
    record["outcome_timestamp"] = datetime.now(timezone.utc).isoformat()

    log_dir = _ensure_init()
    try:
        with open(log_dir / "orchestrator_decisions_outcomes.jsonl", "a") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception:
        pass
