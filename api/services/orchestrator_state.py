"""
Orchestrator coordination — persistent state (SQLite).
Tables: controller_state, source_profiles, decision_history, performance_metrics,
resource_usage, learned_patterns. Used by OrchestratorCoordinator and governors.
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config.logging_config import get_component_logger

    logger = get_component_logger("orchestrator")
except Exception:
    logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


def _get_db_path() -> Path:
    from config.paths import ORCHESTRATOR_STATE_DB

    return Path(ORCHESTRATOR_STATE_DB)


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS _schema_meta (key TEXT PRIMARY KEY, value TEXT)")
    cur = conn.execute("SELECT value FROM _schema_meta WHERE key = 'schema_version'")
    if cur.fetchone() is None:
        conn.execute(
            "INSERT INTO _schema_meta (key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )

    # Single row state snapshot (current cycle, last_collection_times, etc.)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orchestrator_controller_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            state_json TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS orchestrator_source_profiles (
            source_id TEXT PRIMARY KEY,
            historical_update_times TEXT,
            average_interval_seconds REAL,
            reliability_score REAL,
            content_value_score REAL,
            last_empty_fetch_count INTEGER DEFAULT 0,
            predicted_next_update TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS orchestrator_decision_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            decision TEXT NOT NULL,
            factors TEXT,
            weights TEXT,
            outcome TEXT,
            learning_notes TEXT
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_decision_history_timestamp ON orchestrator_decision_history(timestamp)"
    )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS orchestrator_performance_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name TEXT NOT NULL,
            value REAL NOT NULL,
            recorded_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_performance_metrics_recorded ON orchestrator_performance_metrics(recorded_at)"
    )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS orchestrator_resource_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_type TEXT NOT NULL,
            usage REAL NOT NULL,
            limit_value REAL,
            recorded_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_resource_usage_recorded ON orchestrator_resource_usage(recorded_at)"
    )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS orchestrator_learned_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_type TEXT NOT NULL,
            pattern_data TEXT,
            confidence REAL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()


def get_controller_state() -> dict[str, Any]:
    """Load current controller state. Returns dict with current_cycle, last_collection_times, etc."""
    try:
        conn = sqlite3.connect(str(_get_db_path()))
        _init_schema(conn)
        cur = conn.execute("SELECT state_json FROM orchestrator_controller_state WHERE id = 1")
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            return json.loads(row[0])
        return {
            "current_cycle": 0,
            "last_collection_times": {},
            "last_finance_interest_analysis": {},
            "processing_queue": [],
            "active_investigations": [],
            "resource_usage": {},
            "performance_metrics": {},
            "config_overrides": {},
            "updated_at": None,
        }
    except Exception as e:
        logger.warning("Orchestrator get_controller_state failed: %s", e)
        return {
            "current_cycle": 0,
            "last_collection_times": {},
            "last_finance_interest_analysis": {},
            "processing_queue": [],
            "active_investigations": [],
            "resource_usage": {},
            "performance_metrics": {},
            "config_overrides": {},
            "updated_at": None,
        }


def save_controller_state(state: dict[str, Any]) -> bool:
    """Persist controller state. state must be JSON-serializable."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        state["updated_at"] = now
        conn = sqlite3.connect(str(_get_db_path()))
        _init_schema(conn)
        conn.execute(
            """INSERT OR REPLACE INTO orchestrator_controller_state (id, state_json, updated_at)
               VALUES (1, ?, ?)""",
            (json.dumps(state, default=str), now),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.warning("Orchestrator save_controller_state failed: %s", e)
        return False


def get_source_profile(source_id: str) -> dict[str, Any] | None:
    """Get profile for a source. Returns None if not found."""
    try:
        conn = sqlite3.connect(str(_get_db_path()))
        conn.row_factory = sqlite3.Row
        _init_schema(conn)
        cur = conn.execute(
            "SELECT * FROM orchestrator_source_profiles WHERE source_id = ?",
            (source_id,),
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return {
            "source_id": row["source_id"],
            "historical_update_times": json.loads(row["historical_update_times"] or "[]"),
            "average_interval_seconds": row["average_interval_seconds"],
            "reliability_score": row["reliability_score"],
            "content_value_score": row["content_value_score"],
            "last_empty_fetch_count": row["last_empty_fetch_count"] or 0,
            "predicted_next_update": row["predicted_next_update"],
            "updated_at": row["updated_at"],
        }
    except Exception as e:
        logger.warning("Orchestrator get_source_profile failed: %s", e)
        return None


def update_source_profile(
    source_id: str,
    *,
    historical_update_times: list[str] | None = None,
    average_interval_seconds: float | None = None,
    reliability_score: float | None = None,
    content_value_score: float | None = None,
    last_empty_fetch_count: int | None = None,
    predicted_next_update: str | None = None,
) -> bool:
    """Upsert source profile. Only provided fields are updated."""
    try:
        conn = sqlite3.connect(str(_get_db_path()))
        _init_schema(conn)
        now = datetime.now(timezone.utc).isoformat()
        existing = get_source_profile(source_id)
        if existing:
            ht = (
                historical_update_times
                if historical_update_times is not None
                else existing["historical_update_times"]
            )
            avg = (
                average_interval_seconds
                if average_interval_seconds is not None
                else existing["average_interval_seconds"]
            )
            rel = (
                reliability_score
                if reliability_score is not None
                else existing["reliability_score"]
            )
            cv = (
                content_value_score
                if content_value_score is not None
                else existing["content_value_score"]
            )
            empty = (
                last_empty_fetch_count
                if last_empty_fetch_count is not None
                else existing["last_empty_fetch_count"]
            )
            pred = (
                predicted_next_update
                if predicted_next_update is not None
                else existing["predicted_next_update"]
            )
        else:
            ht = historical_update_times or []
            avg = average_interval_seconds
            rel = reliability_score
            cv = content_value_score
            empty = last_empty_fetch_count if last_empty_fetch_count is not None else 0
            pred = predicted_next_update

        conn.execute(
            """INSERT OR REPLACE INTO orchestrator_source_profiles
               (source_id, historical_update_times, average_interval_seconds, reliability_score,
                content_value_score, last_empty_fetch_count, predicted_next_update, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                source_id,
                json.dumps(ht) if isinstance(ht, list) else ht,
                avg,
                rel,
                cv,
                empty,
                pred,
                now,
            ),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.warning("Orchestrator update_source_profile failed: %s", e)
        return False


def append_decision_log(
    decision: str,
    *,
    factors: dict | list | None = None,
    weights: dict | list | None = None,
    outcome: str | None = None,
    learning_notes: str | None = None,
) -> int:
    """Append a decision to history. Returns row id or 0 on failure."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(str(_get_db_path()))
        _init_schema(conn)
        cur = conn.execute(
            """INSERT INTO orchestrator_decision_history
               (timestamp, decision, factors, weights, outcome, learning_notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                now,
                decision,
                json.dumps(factors) if factors is not None else None,
                json.dumps(weights) if weights is not None else None,
                outcome,
                learning_notes,
            ),
        )
        rowid = cur.lastrowid
        conn.commit()
        conn.close()
        return rowid or 0
    except Exception as e:
        logger.warning("Orchestrator append_decision_log failed: %s", e)
        return 0


def get_decision_log(
    limit: int = 50,
    offset: int = 0,
    since: str | None = None,
) -> dict[str, Any]:
    """Paginated decision history. since = ISO timestamp to filter from."""
    try:
        conn = sqlite3.connect(str(_get_db_path()))
        conn.row_factory = sqlite3.Row
        _init_schema(conn)
        params: list[Any] = []
        where = "1=1"
        if since:
            where = "timestamp >= ?"
            params.append(since)
        cur = conn.execute(
            f"SELECT COUNT(*) FROM orchestrator_decision_history WHERE {where}",
            params,
        )
        total = cur.fetchone()[0]
        cur = conn.execute(
            f"""SELECT id, timestamp, decision, factors, weights, outcome, learning_notes
                FROM orchestrator_decision_history WHERE {where}
                ORDER BY timestamp DESC LIMIT ? OFFSET ?""",
            params + [limit, offset],
        )
        rows = cur.fetchall()
        conn.close()
        entries = [
            {
                "id": r["id"],
                "timestamp": r["timestamp"],
                "decision": r["decision"],
                "factors": json.loads(r["factors"]) if r["factors"] else None,
                "weights": json.loads(r["weights"]) if r["weights"] else None,
                "outcome": r["outcome"],
                "learning_notes": r["learning_notes"],
            }
            for r in rows
        ]
        return {"entries": entries, "total": total, "limit": limit, "offset": offset}
    except Exception as e:
        logger.warning("Orchestrator get_decision_log failed: %s", e)
        return {"entries": [], "total": 0, "limit": limit, "offset": offset}


def record_performance_metric(metric_name: str, value: float) -> bool:
    """Record a performance metric snapshot."""
    try:
        conn = sqlite3.connect(str(_get_db_path()))
        _init_schema(conn)
        conn.execute(
            "INSERT INTO orchestrator_performance_metrics (metric_name, value) VALUES (?, ?)",
            (metric_name, value),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.warning("Orchestrator record_performance_metric failed: %s", e)
        return False


def record_resource_usage(
    resource_type: str,
    usage: float,
    limit_value: float | None = None,
) -> bool:
    """Record resource usage snapshot."""
    try:
        conn = sqlite3.connect(str(_get_db_path()))
        _init_schema(conn)
        conn.execute(
            """INSERT INTO orchestrator_resource_usage (resource_type, usage, limit_value)
               VALUES (?, ?, ?)""",
            (resource_type, usage, limit_value),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.warning("Orchestrator record_resource_usage failed: %s", e)
        return False


def get_recent_metrics(metric_name: str | None = None, limit: int = 100) -> list[dict]:
    """Recent performance_metrics rows, optionally filtered by metric_name."""
    try:
        conn = sqlite3.connect(str(_get_db_path()))
        conn.row_factory = sqlite3.Row
        _init_schema(conn)
        if metric_name:
            cur = conn.execute(
                """SELECT id, metric_name, value, recorded_at
                   FROM orchestrator_performance_metrics WHERE metric_name = ?
                   ORDER BY recorded_at DESC LIMIT ?""",
                (metric_name, limit),
            )
        else:
            cur = conn.execute(
                """SELECT id, metric_name, value, recorded_at
                   FROM orchestrator_performance_metrics
                   ORDER BY recorded_at DESC LIMIT ?""",
                (limit,),
            )
        rows = cur.fetchall()
        conn.close()
        return [
            {
                "id": r["id"],
                "metric_name": r["metric_name"],
                "value": r["value"],
                "recorded_at": r["recorded_at"],
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning("Orchestrator get_recent_metrics failed: %s", e)
        return []


def get_recent_resource_usage(resource_type: str | None = None, limit: int = 100) -> list[dict]:
    """Recent resource_usage rows, optionally filtered by resource_type."""
    try:
        conn = sqlite3.connect(str(_get_db_path()))
        conn.row_factory = sqlite3.Row
        _init_schema(conn)
        if resource_type:
            cur = conn.execute(
                """SELECT id, resource_type, usage, limit_value, recorded_at
                   FROM orchestrator_resource_usage WHERE resource_type = ?
                   ORDER BY recorded_at DESC LIMIT ?""",
                (resource_type, limit),
            )
        else:
            cur = conn.execute(
                """SELECT id, resource_type, usage, limit_value, recorded_at
                   FROM orchestrator_resource_usage ORDER BY recorded_at DESC LIMIT ?""",
                (limit,),
            )
        rows = cur.fetchall()
        conn.close()
        return [
            {
                "id": r["id"],
                "resource_type": r["resource_type"],
                "usage": r["usage"],
                "limit_value": r["limit_value"],
                "recorded_at": r["recorded_at"],
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning("Orchestrator get_recent_resource_usage failed: %s", e)
        return []


def save_learned_pattern(
    pattern_type: str,
    pattern_data: dict | list | None = None,
    confidence: float | None = None,
) -> int:
    """Insert a learned pattern. Returns row id or 0."""
    try:
        conn = sqlite3.connect(str(_get_db_path()))
        _init_schema(conn)
        now = datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            """INSERT INTO orchestrator_learned_patterns (pattern_type, pattern_data, confidence, updated_at)
               VALUES (?, ?, ?, ?)""",
            (
                pattern_type,
                json.dumps(pattern_data) if pattern_data is not None else None,
                confidence,
                now,
            ),
        )
        rowid = cur.lastrowid
        conn.commit()
        conn.close()
        return rowid or 0
    except Exception as e:
        logger.warning("Orchestrator save_learned_pattern failed: %s", e)
        return 0


def get_learned_patterns(
    pattern_type: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """List learned patterns, optionally filtered by pattern_type. Most recent first."""
    try:
        conn = sqlite3.connect(str(_get_db_path()))
        conn.row_factory = sqlite3.Row
        _init_schema(conn)
        if pattern_type:
            cur = conn.execute(
                """SELECT id, pattern_type, pattern_data, confidence, updated_at
                   FROM orchestrator_learned_patterns WHERE pattern_type = ?
                   ORDER BY updated_at DESC LIMIT ?""",
                (pattern_type, limit),
            )
        else:
            cur = conn.execute(
                """SELECT id, pattern_type, pattern_data, confidence, updated_at
                   FROM orchestrator_learned_patterns ORDER BY updated_at DESC LIMIT ?""",
                (limit,),
            )
        rows = cur.fetchall()
        conn.close()
        return [
            {
                "id": r["id"],
                "pattern_type": r["pattern_type"],
                "pattern_data": json.loads(r["pattern_data"]) if r["pattern_data"] else None,
                "confidence": r["confidence"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning("Orchestrator get_learned_patterns failed: %s", e)
        return []


def get_resource_usage_sum(resource_type: str, since_iso: str) -> float:
    """Sum of usage for resource_type where recorded_at >= since_iso (for daily/hourly budgets)."""
    try:
        conn = sqlite3.connect(str(_get_db_path()))
        _init_schema(conn)
        cur = conn.execute(
            """SELECT COALESCE(SUM(usage), 0) FROM orchestrator_resource_usage
               WHERE resource_type = ? AND recorded_at >= ?""",
            (resource_type, since_iso),
        )
        row = cur.fetchone()
        conn.close()
        return float(row[0] or 0)
    except Exception as e:
        logger.warning("Orchestrator get_resource_usage_sum failed: %s", e)
        return 0.0


def get_learned_pattern_counts_by_type() -> dict[str, int]:
    """Return counts of learned patterns per pattern_type for learning_stats."""
    try:
        conn = sqlite3.connect(str(_get_db_path()))
        _init_schema(conn)
        cur = conn.execute(
            "SELECT pattern_type, COUNT(*) FROM orchestrator_learned_patterns GROUP BY pattern_type"
        )
        rows = cur.fetchall()
        conn.close()
        return {row[0]: row[1] for row in rows}
    except Exception as e:
        logger.warning("Orchestrator get_learned_pattern_counts_by_type failed: %s", e)
        return {}
