"""
Standardized activity logging — single format, consolidated storage.

All activity (API requests, RSS pulls, orchestrator decisions) uses this schema:
  timestamp, component, event_type, status, status_code?, message?, detail?

Outputs:
  - logs/activity.log — human-readable
  - logs/activity.jsonl — JSON Lines for parsing/analysis

When LOG_DIR is unavailable or file write fails, logging is no-op (failure swallowed).
"""

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Lazy init to avoid circular import with config
_LOG_DIR: Path | None = None
_LOCK = threading.Lock()
_FILE_HANDLER: logging.FileHandler | None = None
_JSONL_HANDLER: logging.FileHandler | None = None
_INITIALIZED = False


def _ensure_init() -> None:
    global _LOG_DIR, _FILE_HANDLER, _JSONL_HANDLER, _INITIALIZED
    if _INITIALIZED:
        return
    with _LOCK:
        if _INITIALIZED:
            return
        try:
            from config.paths import LOG_DIR
            _LOG_DIR = Path(LOG_DIR)
        except Exception:
            _LOG_DIR = Path(__file__).resolve().parents[3] / "logs"
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        _INITIALIZED = True


def _write_entry(component: str, event_type: str, status: str, **fields: Any) -> None:
    """Write standardized entry to activity.log and activity.jsonl."""
    _ensure_init()
    ts = datetime.now(timezone.utc).isoformat()
    entry = {
        "timestamp": ts,
        "component": component,
        "event_type": event_type,
        "status": status,
        **{k: v for k, v in fields.items() if v is not None},
    }
    line = json.dumps(entry, default=str)
    human = f"{ts} | {component} | {event_type} | {status}"
    if fields.get("message"):
        human += f" | {fields['message']}"
    if fields.get("detail"):
        human += f" | {json.dumps(fields['detail'], default=str)}"

    log_dir = _LOG_DIR or Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    try:
        with open(log_dir / "activity.log", "a") as f:
            f.write(human + "\n")
    except Exception:
        pass
    try:
        with open(log_dir / "activity.jsonl", "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def log_api_request(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float | None = None,
    request_id: str | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
    **extra: Any,
) -> None:
    """Log an API request. Call from middleware after response."""
    status = "success" if 200 <= status_code < 400 else "error"
    level = "error" if status_code >= 500 else ("warn" if status_code >= 400 else "info")
    _write_entry(
        component="api",
        event_type="request",
        status=status,
        level=level,
        status_code=status_code,
        method=method,
        path=path,
        duration_ms=round(duration_ms, 2) if duration_ms is not None else None,
        request_id=request_id,
        user_id=user_id,
        session_id=session_id,
        message=f"{method} {path} {status_code}",
        detail=extra or None,
    )


def log_rss_pull(
    feed_id: int | str,
    feed_name: str,
    status: str,
    articles_fetched: int = 0,
    articles_saved: int = 0,
    duration_ms: float | None = None,
    error: str | None = None,
    **extra: Any,
) -> None:
    """
    Log an RSS feed pull. status: success | partial | error | no_entries
    """
    detail = {"articles_fetched": articles_fetched, "articles_saved": articles_saved, **(extra or {})}
    if error:
        detail["error"] = error
    _write_entry(
        component="rss",
        event_type="feed_pull",
        status=status,
        feed_id=str(feed_id),
        feed_name=feed_name,
        message=f"RSS {feed_name}: {status} ({articles_fetched} fetched, {articles_saved} saved)",
        duration_ms=round(duration_ms, 2) if duration_ms is not None else None,
        detail=detail,
    )


def log_orchestrator_decision(
    orchestrator_id: str,
    activity: str,
    reason: str,
    task_id: str | None = None,
    priority: str | None = None,
    **extra: Any,
) -> None:
    """
    Log orchestrator decision: what activity is being queued and why.
    activity: e.g. "refresh_gold", "analysis", "scheduled_refresh"
    reason: short human-readable rationale
    """
    _write_entry(
        component="orchestrator",
        event_type="queue_decision",
        status="queued",
        orchestrator_id=orchestrator_id,
        activity=activity,
        reason=reason,
        task_id=task_id,
        priority=priority,
        message=f"Queued {activity}: {reason}",
        detail=extra or None,
    )


def log_external_call(
    url: str,
    status: str,
    duration_ms: float | None = None,
    error: str | None = None,
    source: str | None = None,
    **extra: Any,
) -> None:
    """Log outbound HTTP call (FRED, EDGAR, FreeGoldAPI, etc.)."""
    _write_entry(
        component="external",
        event_type="api_call",
        status=status,
        url=url,
        duration_ms=round(duration_ms, 2) if duration_ms is not None else None,
        error=error,
        source=source,
        message=f"External call {source or url}: {status}",
        detail=extra or None,
    )


def log_activity(
    component: str,
    event_type: str,
    status: str,
    message: str | None = None,
    **detail: Any,
) -> None:
    """Generic activity log for other components."""
    _write_entry(
        component=component,
        event_type=event_type,
        status=status,
        message=message,
        detail=detail if detail else None,
    )
