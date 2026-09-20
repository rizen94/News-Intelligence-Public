"""
Finance domain — evidence ledger for report provenance.
Tracks which data sources, observations, and chunks supported each report/section.
"""

import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

try:
    from config.logging_config import get_component_logger
    logger = get_component_logger("finance")
except Exception:
    logger = logging.getLogger(__name__)

from config.settings import FINANCE_DATA_DIR
from domains.finance.data.schema_version import ensure_schema_version, SCHEMA_VERSION

LEDGER_DB = FINANCE_DATA_DIR / "evidence_ledger.db"


def _init_schema(conn: sqlite3.Connection) -> None:
    ensure_schema_version(conn, str(LEDGER_DB), SCHEMA_VERSION)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS evidence_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id TEXT NOT NULL,
            section_id TEXT,
            source_type TEXT NOT NULL,
            source_id TEXT,
            evidence_data TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_report ON evidence_entries(report_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_source ON evidence_entries(source_type)")
    conn.commit()


def record(
    report_id: str,
    source_type: str,
    source_id: str | None = None,
    evidence_data: dict | None = None,
    section_id: str | None = None,
) -> int:
    """Record an evidence entry. Returns row id."""
    try:
        conn = sqlite3.connect(str(LEDGER_DB))
        _init_schema(conn)
        cur = conn.execute(
            """INSERT INTO evidence_entries (report_id, section_id, source_type, source_id, evidence_data)
               VALUES (?, ?, ?, ?, ?)""",
            (report_id, section_id, source_type, source_id, json.dumps(evidence_data or {}, default=str))
        )
        rowid = cur.lastrowid
        conn.commit()
        conn.close()
        return rowid or 0
    except Exception as e:
        logger.warning("Evidence ledger record failed: %s", e)
        return 0


def list_entries(
    source_id: str | None = None,
    source_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """
    List evidence entries with optional filters. Returns paginated results.
    Sorted by created_at descending (most recent first).
    """
    try:
        conn = sqlite3.connect(str(LEDGER_DB))
        conn.row_factory = sqlite3.Row
        conditions = []
        params = []
        if source_id:
            conditions.append("source_id = ?")
            params.append(source_id)
        if source_type:
            conditions.append("source_type = ?")
            params.append(source_type)
        where = (" AND ".join(conditions)) if conditions else "1=1"

        cur = conn.execute(
            f"SELECT COUNT(*) FROM evidence_entries WHERE {where}", params
        )
        total = cur.fetchone()[0]

        cur = conn.execute(
            f"""SELECT id, report_id, section_id, source_type, source_id, evidence_data, created_at
                FROM evidence_entries WHERE {where}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?""",
            params + [limit, offset],
        )
        rows = cur.fetchall()
        conn.close()
        entries = [
            {
                "id": r["id"],
                "report_id": r["report_id"],
                "section_id": r["section_id"],
                "source_type": r["source_type"],
                "source_id": r["source_id"],
                "evidence_data": json.loads(r["evidence_data"] or "{}"),
                "created_at": r["created_at"],
            }
            for r in rows
        ]
        return {"entries": entries, "total": total, "limit": limit, "offset": offset}
    except Exception as e:
        logger.warning("Evidence ledger list_entries failed: %s", e)
        return {"entries": [], "total": 0, "limit": limit, "offset": offset}


def get_recent_by_source(limit_per_source: int = 5) -> dict[str, list[dict]]:
    """
    Get most recent ledger entries per source_id (orchestrator_refresh only).
    Returns {source_id: [entries]}. Used for source health status.
    """
    try:
        conn = sqlite3.connect(str(LEDGER_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            """SELECT id, report_id, source_type, source_id, evidence_data, created_at
               FROM evidence_entries
               WHERE source_type = 'orchestrator_refresh' AND source_id IS NOT NULL
               ORDER BY created_at DESC""",
        )
        rows = cur.fetchall()
        conn.close()
        by_source: dict[str, list[dict]] = {}
        for r in rows:
            sid = r["source_id"] or "unknown"
            if sid not in by_source:
                by_source[sid] = []
            if len(by_source[sid]) < limit_per_source:
                by_source[sid].append({
                    "status": json.loads(r["evidence_data"] or "{}").get("status"),
                    "created_at": r["created_at"],
                    "error": json.loads(r["evidence_data"] or "{}").get("error"),
                })
        return by_source
    except Exception as e:
        logger.warning("Evidence ledger get_recent_by_source failed: %s", e)
        return {}


def get_by_report(report_id: str) -> list[dict]:
    """Get all evidence entries for a report."""
    try:
        conn = sqlite3.connect(str(LEDGER_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT id, report_id, section_id, source_type, source_id, evidence_data, created_at FROM evidence_entries WHERE report_id = ? ORDER BY id",
            (report_id,)
        )
        rows = cur.fetchall()
        conn.close()
        return [
            {
                "id": r["id"],
                "report_id": r["report_id"],
                "section_id": r["section_id"],
                "source_type": r["source_type"],
                "source_id": r["source_id"],
                "evidence_data": json.loads(r["evidence_data"] or "{}"),
                "created_at": r["created_at"],
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning("Evidence ledger get_by_report failed: %s", e)
        return []
