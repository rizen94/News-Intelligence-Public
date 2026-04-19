"""
Article batch ordering for automation (FIFO vs LIFO) and optional backfill collection pause.

Env:
- ``PIPELINE_ARTICLE_SELECTION_ORDER`` — ``fifo`` (default, oldest first) or ``lifo`` / ``newest_first``
  (restore previous newest-first behavior).
- ``PIPELINE_BACKFILL_MODE`` — ``true`` enables backlog catch-up semantics alongside optional
  external-ingest pause (see below).
- ``PIPELINE_BACKFILL_COLLECTION_RESUME_AT`` — ISO-8601 UTC instant; while ``now`` is before this
  time and backfill mode is on, RSS + document discovery are skipped in ``collection_cycle`` and
  nightly kickoff RSS is skipped. Overrides the file-based default window.
- ``PIPELINE_BACKFILL_PAUSE_HOURS`` — when ``RESUME_AT`` is not set, first activation writes
  ``.local/pipeline_backfill_pause_until`` with ``now + hours`` (default 48).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_LOCAL_STATE_NAME = "pipeline_backfill_pause_until"


def _workspace_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _pause_state_path() -> Path:
    return _workspace_root() / ".local" / _LOCAL_STATE_NAME


def article_selection_newest_first() -> bool:
    """True = LIFO (newest batches first); False = FIFO (oldest first). Default FIFO."""
    raw = os.environ.get("PIPELINE_ARTICLE_SELECTION_ORDER", "fifo").strip().lower()
    if raw in ("lifo", "newest_first", "newest", "desc"):
        return True
    return False


def pipeline_article_selection_mode_report() -> dict[str, str]:
    """Resolved mode for logs, Monitor, or health payloads (env string may be empty)."""
    raw = (os.environ.get("PIPELINE_ARTICLE_SELECTION_ORDER") or "fifo").strip()
    if article_selection_newest_first():
        return {
            "order_env": raw or "lifo",
            "mode": "lifo",
            "label": "newest_first_legacy_v8",
            "sql_created_at": "DESC",
        }
    return {
        "order_env": raw or "fifo",
        "mode": "fifo",
        "label": "oldest_first_backlog_drain",
        "sql_created_at": "ASC",
    }


def sql_order_created_at(_column: str = "created_at") -> str:
    """Direction for ``ORDER BY ... created_at`` (column name is for documentation only)."""
    return "DESC" if article_selection_newest_first() else "ASC"


def sql_order_id(_column: str = "id") -> str:
    """Direction for ``ORDER BY ... id`` when ids correlate with ingestion time."""
    return "DESC" if article_selection_newest_first() else "ASC"


def sql_order_coalesce_pub_created(alias: str = "a") -> str:
    """``ORDER BY`` fragment using published_at with created_at fallback."""
    direction = "DESC" if article_selection_newest_first() else "ASC"
    return f"COALESCE({alias}.published_at, {alias}.created_at) {direction} NULLS LAST"


def _parse_iso_utc(s: str) -> datetime | None:
    s = (s or "").strip().replace("Z", "+00:00")
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def pipeline_backfill_mode_enabled() -> bool:
    return os.environ.get("PIPELINE_BACKFILL_MODE", "").lower() in ("1", "true", "yes")


def _ensure_pause_until_from_file() -> datetime | None:
    """Persist ``now + PIPELINE_BACKFILL_PAUSE_HOURS`` on first use when resume env is unset."""
    path = _pause_state_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.debug("backfill pause dir: %s", e)
        return None

    raw_hours = os.environ.get("PIPELINE_BACKFILL_PAUSE_HOURS", "48").strip()
    try:
        hours = float(raw_hours)
    except ValueError:
        hours = 48.0
    hours = max(1.0, min(8760.0, hours))

    if path.is_file():
        try:
            text = path.read_text(encoding="utf-8").strip()
            dt = _parse_iso_utc(text)
            if dt:
                return dt
        except OSError:
            pass

    end = datetime.now(timezone.utc) + timedelta(hours=hours)
    try:
        path.write_text(end.isoformat(), encoding="utf-8")
        logger.warning(
            "PIPELINE_BACKFILL_MODE: external collection paused until %s (state %s; set PIPELINE_BACKFILL_COLLECTION_RESUME_AT to fix the end time)",
            end.isoformat(),
            path,
        )
    except OSError as e:
        logger.warning("Could not write backfill pause file %s: %s — using in-memory end time", path, e)
        return end
    return end


def pipeline_backfill_collection_should_pause() -> bool:
    """
    When True, skip ingesting new data from RSS and document discovery (not processing of existing rows).
    """
    if not pipeline_backfill_mode_enabled():
        return False
    ex = os.environ.get("PIPELINE_BACKFILL_COLLECTION_RESUME_AT", "").strip()
    if ex:
        end = _parse_iso_utc(ex)
        if end is None:
            logger.warning(
                "PIPELINE_BACKFILL_COLLECTION_RESUME_AT invalid — not pausing collection (fix env or unset)"
            )
            return False
        return datetime.now(timezone.utc) < end
    end = _ensure_pause_until_from_file()
    if end is None:
        return False
    return datetime.now(timezone.utc) < end


def pipeline_backfill_status_line() -> str:
    if not pipeline_backfill_mode_enabled():
        return ""
    if pipeline_backfill_collection_should_pause():
        ex = os.environ.get("PIPELINE_BACKFILL_COLLECTION_RESUME_AT", "").strip()
        end: datetime | None = _parse_iso_utc(ex) if ex else None
        if end is None:
            p = _pause_state_path()
            if p.is_file():
                try:
                    end = _parse_iso_utc(p.read_text(encoding="utf-8").strip())
                except OSError:
                    end = None
        tail = end.isoformat() if end else "unknown"
        return (
            f"backfill: external collection paused until {tail} "
            f"(FIFO selection unless PIPELINE_ARTICLE_SELECTION_ORDER=lifo)"
        )
    return "backfill: collection pause ended — RSS/document discovery allowed again"


def log_terminal_skip_stub_candidate(schema: str, article_id: int, phase_name: str) -> None:
    """Opt-in log when a phase hits terminal skip (possible stub row). No deletion."""
    if os.environ.get("PIPELINE_LOG_STUB_PURGE_CANDIDATES", "").lower() not in ("1", "true", "yes"):
        return
    logger.warning(
        "Terminal pipeline skip — stub review candidate: schema=%s article_id=%s phase=%s "
        "(automatic deletion not enabled; audit before any manual delete)",
        schema,
        article_id,
        phase_name,
    )
