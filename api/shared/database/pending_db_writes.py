"""
Local spill file for DB writes that fail during outages (automation_run_history first).

Writes JSON lines under DB_PENDING_WRITES_DIR (default: <project>/.local/db_pending_writes).
The `pending_db_flush` automation phase replays and removes successful rows.

This does **not** buffer arbitrary application writes — extend with new record `type` values carefully.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_lock = threading.Lock()


def _project_root() -> Path:
    # api/shared/database -> api -> project
    return Path(__file__).resolve().parents[3]


def _queue_dir() -> Path:
    raw = os.getenv("DB_PENDING_WRITES_DIR")
    if raw:
        return Path(raw)
    return _project_root() / ".local" / "db_pending_writes"


def _queue_file() -> Path:
    d = _queue_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "pending.jsonl"


def enqueue_automation_run_history(
    phase_name: str,
    started_at: str,
    finished_at: str,
    success: bool,
    error_message: Optional[str],
) -> None:
    """Append one automation_run_history-equivalent row for later flush."""
    rec = {
        "type": "automation_run_history",
        "phase_name": phase_name,
        "started_at": started_at,
        "finished_at": finished_at,
        "success": success,
        "error_message": error_message,
        "enqueued_at": datetime.utcnow().isoformat() + "Z",
    }
    _append_record(rec)


def _append_record(rec: Dict[str, Any]) -> None:
    line = json.dumps(rec, default=str) + "\n"
    path = _queue_file()
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
    logger.info("Queued pending DB write: %s", rec.get("type"))


def pending_line_count() -> int:
    path = _queue_file()
    if not path.is_file():
        return 0
    try:
        with open(path, encoding="utf-8") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def flush_pending_writes() -> Dict[str, Any]:
    """
    Replay queued records. Returns stats dict.
    """
    path = _queue_file()
    if not path.is_file():
        return {"flushed": 0, "failed": 0, "skipped": 0}

    with _lock:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as e:
            logger.warning("pending_db_writes: cannot read %s: %s", path, e)
            return {"flushed": 0, "failed": 0, "skipped": 0, "error": str(e)}

        if not lines:
            return {"flushed": 0, "failed": 0, "skipped": 0}

        remaining: List[str] = []
        flushed = failed = skipped = 0

        try:
            from shared.database.connection import get_db_connection
        except Exception as e:
            logger.warning("pending_db_writes: no DB module: %s", e)
            return {"flushed": 0, "failed": 0, "skipped": len(lines), "error": str(e)}

        conn = None
        try:
            conn = get_db_connection()
        except Exception as e:
            logger.warning("pending_db_writes: DB still down: %s", e)
            return {"flushed": 0, "failed": 0, "skipped": len(lines)}

        try:
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    skipped += 1
                    remaining.append(line)
                    continue
                rtype = rec.get("type")
                if rtype == "automation_run_history":
                    try:
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                INSERT INTO automation_run_history (phase_name, started_at, finished_at, success, error_message)
                                VALUES (%s, %s, %s, %s, %s)
                                """,
                                (
                                    rec.get("phase_name"),
                                    rec.get("started_at"),
                                    rec.get("finished_at"),
                                    rec.get("success"),
                                    rec.get("error_message"),
                                ),
                            )
                        conn.commit()
                        flushed += 1
                    except Exception as ex:
                        conn.rollback()
                        logger.warning("pending_db_writes: flush one row failed: %s", ex)
                        failed += 1
                        remaining.append(line)
                else:
                    skipped += 1
                    remaining.append(line)
        finally:
            try:
                conn.close()
            except Exception:
                pass

        try:
            if remaining:
                path.write_text("\n".join(remaining) + ("\n" if remaining else ""), encoding="utf-8")
            else:
                path.unlink(missing_ok=True)
        except OSError as e:
            logger.error("pending_db_writes: could not rewrite queue file: %s", e)

        try:
            from shared.database.db_availability import invalidate_db_health_cache

            if flushed:
                invalidate_db_health_cache()
        except Exception:
            pass

        return {"flushed": flushed, "failed": failed, "skipped": skipped}
