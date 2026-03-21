"""
Structured logging for Finance Orchestrator.
Every orchestrator action produces a traceable log entry with task_id and event type.
Also writes to shared activity log for consolidated storage.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

try:
    from config.logging_config import get_component_logger

    LOG = get_component_logger("finance")
except Exception:
    LOG = logging.getLogger("finance.orchestrator")

# Event types — every log must include one
TASK_ACCEPTED = "TASK_ACCEPTED"
TASK_PLANNED = "TASK_PLANNED"
WORKER_DISPATCHED = "WORKER_DISPATCHED"
WORKER_COMPLETED = "WORKER_COMPLETED"
WORKER_FAILED = "WORKER_FAILED"
EVAL_PASSED = "EVAL_PASSED"
EVAL_FAILED = "EVAL_FAILED"
TASK_COMPLETED = "TASK_COMPLETED"
TASK_FAILED = "TASK_FAILED"
SOURCE_SKIPPED = "SOURCE_SKIPPED"
QUEUE_STATUS = "QUEUE_STATUS"


def log_event(
    event_type: str,
    task_id: str,
    detail: dict[str, Any] | None = None,
    level: str = "info",
) -> None:
    """
    Log a structured orchestrator event. All entries include task_id for traceability.
    detail carries event-specific data: source name, error, duration_ms, counts, etc.
    """
    payload = {
        "event_type": event_type,
        "task_id": task_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "detail": detail or {},
    }
    msg = json.dumps(payload, default=str)
    log_fn = getattr(LOG, level.lower(), LOG.info)
    log_fn(msg)


def log_queue_decision(
    activity: str, reason: str, task_id: str, priority: str, **extra: Any
) -> None:
    """
    Log what activity is being queued and why. Writes to shared activity logger
    for consolidated storage (logs/activity.log, logs/activity.jsonl).
    """
    try:
        from shared.logging.activity_logger import log_orchestrator_decision

        log_orchestrator_decision(
            orchestrator_id="finance",
            activity=activity,
            reason=reason,
            task_id=task_id,
            priority=priority,
            **extra,
        )
    except Exception:
        pass
