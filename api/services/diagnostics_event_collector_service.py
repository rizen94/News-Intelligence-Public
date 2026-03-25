"""
Aggregate diagnostic events from stored history: automation failures, pipeline traces,
checkpoints, pending DB spill, structured activity logs, and optional plain-log tail scans.

Used by GET /api/system_monitoring/diagnostics/events and scripts/run_diagnostics_collect.py.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DiagnosticEvent:
    """Normalized event for review (JSON-serializable)."""

    event_type: str
    severity: str  # critical | high | medium | low | info
    source: str
    occurred_at: str | None
    summary: str
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "severity": self.severity,
            "source": self.source,
            "occurred_at": self.occurred_at,
            "summary": self.summary,
            "detail": self.detail,
        }


def _iso(dt: Any) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    return str(dt)


def _collect_automation_failures(
    conn: Any, since: datetime, limit: int
) -> list[DiagnosticEvent]:
    out: list[DiagnosticEvent] = []
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '15s'")
            cur.execute(
                """
                SELECT phase_name, started_at, finished_at, success, error_message
                FROM automation_run_history
                WHERE finished_at >= %s
                  AND (success = false OR (error_message IS NOT NULL AND btrim(error_message) <> ''))
                ORDER BY finished_at DESC
                LIMIT %s
                """,
                (since, limit),
            )
            for row in cur.fetchall() or []:
                phase, started, finished, success, err = row[0], row[1], row[2], row[3], row[4]
                # success=false is common (phase error); reserve critical for likely infra/DB loss.
                err_l = (err or "").lower()
                sev = "high"
                if success is False and (
                    "connection" in err_l
                    or "timeout" in err_l
                    or "pool" in err_l
                    or "operationalerror" in err_l
                    or "could not connect" in err_l
                    or "ssl" in err_l
                    or "authentication failed" in err_l
                    or "too many connections" in err_l
                ):
                    sev = "critical"
                elif success is True and err and err_l.strip():
                    sev = "medium"
                out.append(
                    DiagnosticEvent(
                        event_type="automation_phase_failure",
                        severity=sev,
                        source="automation_run_history",
                        occurred_at=_iso(finished),
                        summary=f"Automation phase {phase!r} reported failure or error message",
                        detail={
                            "phase_name": phase,
                            "started_at": _iso(started),
                            "finished_at": _iso(finished),
                            "success": success,
                            "error_message": (err or "")[:4000],
                        },
                    )
                )
    except Exception as e:
        logger.debug("diagnostics automation_run_history: %s", e)
    return out


def _collect_pipeline_trace_failures(
    conn: Any, since: datetime, limit: int
) -> list[DiagnosticEvent]:
    out: list[DiagnosticEvent] = []
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '15s'")
            cur.execute(
                """
                SELECT trace_id, start_time, end_time, success, error_stage, rss_feed_id
                FROM pipeline_traces
                WHERE start_time >= %s
                  AND (success = false OR error_stage IS NOT NULL)
                ORDER BY start_time DESC
                LIMIT %s
                """,
                (since, limit),
            )
            for row in cur.fetchall() or []:
                tid, st, et, ok, err_stage, feed_id = (
                    row[0],
                    row[1],
                    row[2],
                    row[3],
                    row[4],
                    row[5],
                )
                out.append(
                    DiagnosticEvent(
                        event_type="pipeline_trace_failed",
                        severity="high",
                        source="pipeline_traces",
                        occurred_at=_iso(st),
                        summary=f"Pipeline trace {tid!r} failed or recorded error_stage",
                        detail={
                            "trace_id": tid,
                            "start_time": _iso(st),
                            "end_time": _iso(et),
                            "success": ok,
                            "error_stage": err_stage,
                            "rss_feed_id": feed_id,
                        },
                    )
                )
    except Exception as e:
        logger.debug("diagnostics pipeline_traces: %s", e)
    return out


def _collect_checkpoint_failures(
    conn: Any, since: datetime, limit: int
) -> list[DiagnosticEvent]:
    out: list[DiagnosticEvent] = []
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '15s'")
            cur.execute(
                """
                SELECT checkpoint_id, trace_id, stage, status, timestamp, error_message
                FROM pipeline_checkpoints
                WHERE timestamp >= %s
                  AND (
                    lower(coalesce(status, '')) IN ('failed', 'error')
                    OR (error_message IS NOT NULL AND btrim(error_message) <> '')
                  )
                ORDER BY timestamp DESC
                LIMIT %s
                """,
                (since, limit),
            )
            for row in cur.fetchall() or []:
                cpid, tid, stage, status, ts, err = row[0], row[1], row[2], row[3], row[4], row[5]
                out.append(
                    DiagnosticEvent(
                        event_type="pipeline_checkpoint_error",
                        severity="high",
                        source="pipeline_checkpoints",
                        occurred_at=_iso(ts),
                        summary=f"Pipeline checkpoint {stage!r} on trace {tid!r}: {status}",
                        detail={
                            "checkpoint_id": cpid,
                            "trace_id": tid,
                            "stage": stage,
                            "status": status,
                            "error_message": (err or "")[:4000],
                        },
                    )
                )
    except Exception as e:
        logger.debug("diagnostics pipeline_checkpoints: %s", e)
    return out


def _collect_pending_db_spill() -> list[DiagnosticEvent]:
    out: list[DiagnosticEvent] = []
    try:
        from shared.database.pending_db_writes import pending_line_count

        n = pending_line_count()
        if n <= 0:
            return out
        sev = "critical" if n >= 500 else ("high" if n >= 100 else "medium")
        out.append(
            DiagnosticEvent(
                event_type="pending_db_spill",
                severity=sev,
                source="pending_db_writes",
                occurred_at=datetime.now(timezone.utc).isoformat(),
                summary=f"{n} deferred automation_run_history row(s) in local spill file (DB was down)",
                detail={"pending_lines": n, "hint": "Run pending_db_flush automation or flush_pending_writes()"},
            )
        )
    except Exception as e:
        logger.debug("diagnostics pending_db_writes: %s", e)
    return out


def _tail_lines_from_file(path: Path, max_bytes: int = 512_000, max_lines: int = 800) -> list[str]:
    if not path.is_file():
        return []
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            start = max(0, size - max_bytes)
            f.seek(start)
            raw = f.read().decode("utf-8", errors="replace")
        lines = raw.splitlines()
        return lines[-max_lines:] if len(lines) > max_lines else lines
    except OSError as e:
        logger.debug("diagnostics tail %s: %s", path, e)
        return []


def _collect_activity_jsonl_events(
    log_dir: Path, since: datetime, limit: int
) -> list[DiagnosticEvent]:
    out: list[DiagnosticEvent] = []
    path = log_dir / "activity.jsonl"
    lines = _tail_lines_from_file(path, max_bytes=768_000, max_lines=2000)
    since_ts = since.timestamp()

    for line in reversed(lines):
        if len(out) >= limit:
            break
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = rec.get("timestamp")
        if ts:
            try:
                t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if t.timestamp() < since_ts:
                    continue
            except (ValueError, TypeError):
                pass

        status = (rec.get("status") or "").lower()
        status_code = rec.get("status_code")
        level = (rec.get("level") or "").lower()
        component = rec.get("component") or ""
        event_type = rec.get("event_type") or ""

        bad = False
        sev: str = "medium"
        if status_code is not None and int(status_code) >= 500:
            bad = True
            sev = "high"
        elif status_code is not None and int(status_code) >= 400:
            bad = True
            sev = "low"
        elif status in ("error", "failed"):
            bad = True
            sev = "high" if component in ("rss", "orchestrator") else "medium"
        elif level == "error":
            bad = True
            sev = "medium"

        if not bad:
            continue

        msg = rec.get("message") or f"{component} {event_type}"
        detail = {
            "component": component,
            "event_type": event_type,
            "status": status,
            "status_code": status_code,
            "path": rec.get("path"),
            "method": rec.get("method"),
            "feed_name": rec.get("feed_name"),
        }
        d_extra = rec.get("detail")
        if isinstance(d_extra, dict) and d_extra.get("error"):
            detail["detail_error"] = str(d_extra.get("error"))[:2000]
        out.append(
            DiagnosticEvent(
                event_type="activity_log_signal",
                severity=sev,
                source="activity.jsonl",
                occurred_at=ts if isinstance(ts, str) else None,
                summary=msg[:500],
                detail=detail,
            )
        )

    return out[:limit]


_ERROR_LINE = re.compile(r"\b(ERROR|CRITICAL|FATAL)\b", re.IGNORECASE)


def _collect_plain_log_hits(
    log_dir: Path, since: datetime, limit: int, filenames: tuple[str, ...]
) -> list[DiagnosticEvent]:
    """Heuristic: last chunk of pipeline.log / api.log lines mentioning ERROR/CRITICAL/FATAL."""
    out: list[DiagnosticEvent] = []
    since_iso = since.isoformat()
    for name in filenames:
        path = log_dir / name
        if not path.is_file():
            continue
        lines = _tail_lines_from_file(path, max_bytes=384_000, max_lines=1200)
        for line in lines:
            if len(out) >= limit:
                return out
            if not _ERROR_LINE.search(line):
                continue
            out.append(
                DiagnosticEvent(
                    event_type="log_line_error_keyword",
                    severity="medium",
                    source=name,
                    occurred_at=None,
                    summary=line.strip()[:500],
                    detail={"log_file": name, "note": "Heuristic match; verify timestamp in full logs."},
                )
            )
    return out


def collect_diagnostic_events(
    *,
    since_hours: float = 24.0,
    max_per_source: int = 200,
    include_activity_jsonl: bool = True,
    include_plain_logs: bool = True,
    log_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Pull normalized events from DB + local files. Safe to call on a schedule.

    Returns dict with keys: generated_at_utc, since_hours, events, counts_by_severity, counts_by_source.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=since_hours)

    if log_dir is None:
        try:
            from config.paths import LOG_DIR

            log_dir = Path(LOG_DIR)
        except Exception:
            log_dir = Path(__file__).resolve().parents[2] / "logs"

    events: list[DiagnosticEvent] = []

    try:
        from shared.database.connection import get_ui_db_connection

        conn = get_ui_db_connection()
        if conn:
            try:
                events.extend(_collect_automation_failures(conn, since, max_per_source))
                events.extend(_collect_pipeline_trace_failures(conn, since, max_per_source))
                events.extend(_collect_checkpoint_failures(conn, since, max_per_source))
            finally:
                conn.close()
    except Exception as e:
        logger.warning("diagnostics DB collection: %s", e)

    events.extend(_collect_pending_db_spill())

    if include_activity_jsonl:
        events.extend(_collect_activity_jsonl_events(log_dir, since, max_per_source))

    if include_plain_logs:
        events.extend(
            _collect_plain_log_hits(
                log_dir, since, min(80, max_per_source), ("pipeline.log", "api.log", "news_intel.log")
            )
        )

    # Dedupe: automation + activity might overlap conceptually; keep all for now (different sources)

    by_sev: dict[str, int] = {}
    by_src: dict[str, int] = {}
    for ev in events:
        by_sev[ev.severity] = by_sev.get(ev.severity, 0) + 1
        by_src[ev.source] = by_src.get(ev.source, 0) + 1

    events.sort(
        key=lambda e: (e.occurred_at or "") or "",
        reverse=True,
    )

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "since_hours": since_hours,
        "since_utc": since.isoformat(),
        "events": [e.as_dict() for e in events],
        "counts_by_severity": by_sev,
        "counts_by_source": by_src,
        "total": len(events),
    }
