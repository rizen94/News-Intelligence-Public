"""
Task Execution Trace Logger — span-based task traces (OpenTelemetry-style).
Writes to logs/task_traces.jsonl. Use SpanContext as context manager.
"""

import json
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

_LOG_DIR: Path | None = None
_INITIALIZED = False
_LOCK = threading.Lock()


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


def _write_span(span: dict) -> None:
    log_dir = _ensure_init()
    try:
        with open(log_dir / "task_traces.jsonl", "a") as f:
            f.write(json.dumps(span, default=str) + "\n")
    except Exception:
        pass

    try:
        from shared.logging.activity_logger import log_activity
        log_activity(
            component="trace",
            event_type="task_span",
            status=span.get("status", "success"),
            message=f"{span.get('span_type')} {span.get('name')} {span.get('duration_ms', 0):.0f}ms",
            **{k: v for k, v in span.items() if k != "attributes" and isinstance(v, (str, int, float, bool, type(None)))},
        )
    except Exception:
        pass


@contextmanager
def span_context(
    task_id: str,
    name: str,
    span_type: str = "phase",
    parent_span_id: Optional[str] = None,
    **attributes: Any,
):
    """
    Context manager for a span. Logs on exit with duration.
    """
    span_id = f"span-{uuid.uuid4().hex[:12]}"
    start = datetime.now(timezone.utc)
    status = "success"
    try:
        yield span_id
    except Exception as e:
        status = "failure"
        attributes["error"] = str(e)
        raise
    finally:
        end = datetime.now(timezone.utc)
        duration_ms = (end - start).total_seconds() * 1000
        span = {
            "span_id": span_id,
            "parent_span_id": parent_span_id,
            "task_id": task_id,
            "span_type": span_type,
            "name": name,
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "duration_ms": round(duration_ms, 2),
            "status": status,
            "attributes": attributes,
        }
        _write_span(span)


def get_traces_for_task(task_id: str) -> list:
    """
    Reconstruct spans for a task_id from task_traces.jsonl.
    Returns list of span dicts.
    """
    log_dir = _ensure_init()
    path = log_dir / "task_traces.jsonl"
    if not path.exists():
        return []
    spans = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                s = json.loads(line)
                if s.get("task_id") == task_id:
                    spans.append(s)
            except json.JSONDecodeError:
                continue
    spans.sort(key=lambda x: x.get("start_time", ""))
    return spans
