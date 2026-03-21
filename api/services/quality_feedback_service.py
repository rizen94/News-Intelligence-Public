"""
Quality feedback service — persist and read claim/event validations and source reliability.
Feeds extraction_metrics and source_rankings; supports Collection Governor prioritization.
See docs/DATA_PIPELINE_ENHANCEMENTS_ROADMAP.md.
"""

import logging
from typing import Any

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)


def get_latest_claim_validations(
    claim_ids: list[int],
    conn: Any | None = None,
) -> dict[int, str]:
    """Return latest validation_status per claim_id (for use when listing claims). Ids with no validation are omitted."""
    if not claim_ids:
        return {}
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = conn is not None
    if not conn:
        return {}
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT ON (claim_id) claim_id, validation_status
                FROM intelligence.claim_validations
                WHERE claim_id = ANY(%s)
                ORDER BY claim_id, validated_at DESC
                """,
                (claim_ids,),
            )
            return {r[0]: r[1] for r in cur.fetchall()}
    except Exception as e:
        logger.debug("get_latest_claim_validations: %s", e)
        return {}
    finally:
        if close_conn and conn:
            conn.close()


def get_latest_event_validations(
    event_ids: list[int],
    conn: Any | None = None,
) -> dict[int, str]:
    """Return latest validation_status per event_id (for use when listing events). Ids with no validation are omitted."""
    if not event_ids:
        return {}
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = conn is not None
    if not conn:
        return {}
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT ON (event_id) event_id, validation_status
                FROM intelligence.event_validations
                WHERE event_id = ANY(%s)
                ORDER BY event_id, validated_at DESC
                """,
                (event_ids,),
            )
            return {r[0]: r[1] for r in cur.fetchall()}
    except Exception as e:
        logger.debug("get_latest_event_validations: %s", e)
        return {}
    finally:
        if close_conn and conn:
            conn.close()


def submit_claim_feedback(
    claim_id: int,
    validation_status: str,
    accuracy_score: float | None = None,
    corrected_text: str | None = None,
    validated_by: str | None = None,
) -> dict[str, Any]:
    """Persist claim validation feedback. Returns { success, validation_id?, error? }."""
    if validation_status not in ("accurate", "corrected", "rejected"):
        return {
            "success": False,
            "error": "validation_status must be accurate, corrected, or rejected",
        }
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed"}
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.claim_validations
                (claim_id, validation_status, accuracy_score, corrected_text, validated_by)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (claim_id, validation_status, accuracy_score, corrected_text, validated_by),
            )
            row = cur.fetchone()
        conn.commit()
        return {"success": True, "validation_id": row[0] if row else None}
    except Exception as e:
        logger.warning("submit_claim_feedback: %s", e)
        if conn:
            conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        if conn:
            conn.close()


def submit_event_validation(
    event_id: int,
    validation_status: str,
    corrections: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist event validation feedback. Returns { success, validation_id?, error? }."""
    if validation_status not in ("accurate", "corrected", "rejected"):
        return {
            "success": False,
            "error": "validation_status must be accurate, corrected, or rejected",
        }
    import json

    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed"}
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.event_validations (event_id, validation_status, corrections)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (event_id, validation_status, json.dumps(corrections or {})),
            )
            row = cur.fetchone()
        conn.commit()
        return {"success": True, "validation_id": row[0] if row else None}
    except Exception as e:
        logger.warning("submit_event_validation: %s", e)
        if conn:
            conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        if conn:
            conn.close()


def submit_source_feedback(
    source_name: str,
    metric: str,
    value: float,
) -> dict[str, Any]:
    """Update source_reliability with a single metric (accuracy, exclusive, correction). Returns { success, error? }."""
    if metric not in ("accuracy", "exclusive", "correction"):
        return {"success": False, "error": "metric must be accuracy, exclusive, or correction"}
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed"}
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.source_reliability (source_name, accuracy_score, exclusive_stories_count, correction_rate, last_updated)
                VALUES (%s, 0.5, 0, 0, NOW())
                ON CONFLICT (source_name) DO UPDATE SET last_updated = NOW()
                """,
                (source_name,),
            )
            if metric == "accuracy":
                cur.execute(
                    """
                    UPDATE intelligence.source_reliability
                    SET accuracy_score = %s, last_updated = NOW()
                    WHERE source_name = %s
                    """,
                    (max(0, min(1, value)), source_name),
                )
            elif metric == "exclusive":
                cur.execute(
                    """
                    UPDATE intelligence.source_reliability
                    SET exclusive_stories_count = exclusive_stories_count + GREATEST(0, %s::INTEGER), last_updated = NOW()
                    WHERE source_name = %s
                    """,
                    (int(value), source_name),
                )
            else:  # correction
                cur.execute(
                    """
                    UPDATE intelligence.source_reliability
                    SET correction_rate = %s, last_updated = NOW()
                    WHERE source_name = %s
                    """,
                    (max(0, min(1, value)), source_name),
                )
        conn.commit()
        return {"success": True}
    except Exception as e:
        logger.warning("submit_source_feedback: %s", e)
        if conn:
            conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        if conn:
            conn.close()


def get_source_rankings(
    domain: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Return sources ranked by reliability (accuracy_score, then exclusive_stories_count)."""
    conn = get_db_connection()
    if not conn:
        return {"success": False, "rankings": [], "error": "Database connection failed"}
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT source_name, accuracy_score, exclusive_stories_count, correction_rate, last_updated
                FROM intelligence.source_reliability
                WHERE (%s IS NULL OR source_name LIKE %s)
                ORDER BY COALESCE(accuracy_score, 0) DESC, exclusive_stories_count DESC
                LIMIT %s
                """,
                (domain, f"%{domain}%" if domain else None, limit),
            )
            rows = cur.fetchall()
        rankings = [
            {
                "source_name": r[0],
                "accuracy_score": r[1],
                "exclusive_stories_count": r[2],
                "correction_rate": r[3],
                "last_updated": r[4].isoformat() if r[4] else None,
            }
            for r in rows
        ]
        return {"success": True, "rankings": rankings}
    except Exception as e:
        logger.warning("get_source_rankings: %s", e)
        return {"success": False, "rankings": [], "error": str(e)}
    finally:
        if conn:
            conn.close()


def get_extraction_metrics(
    source: str | None = None,
    phase: str | None = None,
    since_days: int | None = None,
) -> dict[str, Any]:
    """Per-source and per-phase quality scores from claim_validations (and optionally event_validations)."""
    conn = get_db_connection()
    if not conn:
        return {"success": False, "metrics": [], "error": "Database connection failed"}
    try:
        since_clause = ""
        args: list[Any] = []
        if since_days is not None:
            since_clause = "AND cv.validated_at >= NOW() - INTERVAL '1 day' * %s"
            args.append(since_days)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) AS sample_size,
                    COUNT(*) FILTER (WHERE cv.validation_status = 'accurate') AS accurate_count,
                    COUNT(*) FILTER (WHERE cv.validation_status = 'corrected') AS corrected_count,
                    COUNT(*) FILTER (WHERE cv.validation_status = 'rejected') AS rejected_count,
                    AVG(cv.accuracy_score) FILTER (WHERE cv.accuracy_score IS NOT NULL) AS avg_accuracy
                FROM intelligence.claim_validations cv
                WHERE 1=1
                """
                + since_clause,
                tuple(args),
            )
            row = cur.fetchone()
        sample_size = row[0] or 0
        accurate = row[1] or 0
        corrected = row[2] or 0
        rejected = row[3] or 0
        avg_accuracy = float(row[4]) if row[4] is not None else None
        metrics = [
            {
                "phase": "claim_extraction",
                "sample_size": sample_size,
                "accurate_count": accurate,
                "corrected_count": corrected,
                "rejected_count": rejected,
                "avg_accuracy_score": avg_accuracy,
            }
        ]
        return {"success": True, "metrics": metrics, "source": source, "since_days": since_days}
    except Exception as e:
        logger.warning("get_extraction_metrics: %s", e)
        return {"success": False, "metrics": [], "error": str(e)}
    finally:
        if conn:
            conn.close()
