"""Persist and list human judgments on context ↔ grouping (topic/storyline/pattern)."""

import logging
from typing import Any, Dict, List, Optional

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

GROUPING_TYPES = frozenset({"topic", "storyline", "pattern", "other"})
JUDGMENTS = frozenset({"belongs", "does_not_belong", "unsure"})


def submit_context_grouping_feedback(
    context_id: int,
    grouping_type: str,
    judgment: str,
    grouping_id: Optional[int] = None,
    grouping_label: Optional[str] = None,
    notes: Optional[str] = None,
    judged_by: Optional[str] = None,
) -> Dict[str, Any]:
    if grouping_type not in GROUPING_TYPES:
        return {"success": False, "error": f"grouping_type must be one of {sorted(GROUPING_TYPES)}"}
    if judgment not in JUDGMENTS:
        return {"success": False, "error": f"judgment must be one of {sorted(JUDGMENTS)}"}
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed"}
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM intelligence.contexts WHERE id = %s",
                (context_id,),
            )
            if not cur.fetchone():
                return {"success": False, "error": "Context not found"}
            cur.execute(
                """
                INSERT INTO intelligence.context_grouping_feedback
                    (context_id, grouping_type, grouping_id, grouping_label, judgment, notes, judged_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, judged_at
                """,
                (
                    context_id,
                    grouping_type,
                    grouping_id,
                    (grouping_label or "").strip() or None,
                    judgment,
                    (notes or "").strip() or None,
                    (judged_by or "").strip() or None,
                ),
            )
            row = cur.fetchone()
        conn.commit()
        return {
            "success": True,
            "id": row[0],
            "judged_at": row[1].isoformat() if row[1] else None,
        }
    except Exception as e:
        logger.warning("submit_context_grouping_feedback: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return {"success": False, "error": str(e)}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def list_context_grouping_feedback(
    context_id: int,
    limit: int = 50,
) -> Dict[str, Any]:
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed", "items": []}
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, context_id, grouping_type, grouping_id, grouping_label,
                       judgment, notes, judged_by, judged_at
                FROM intelligence.context_grouping_feedback
                WHERE context_id = %s
                ORDER BY judged_at DESC
                LIMIT %s
                """,
                (context_id, min(max(limit, 1), 200)),
            )
            rows = cur.fetchall()
        items: List[Dict[str, Any]] = []
        for r in rows:
            items.append(
                {
                    "id": r[0],
                    "context_id": r[1],
                    "grouping_type": r[2],
                    "grouping_id": r[3],
                    "grouping_label": r[4],
                    "judgment": r[5],
                    "notes": r[6],
                    "judged_by": r[7],
                    "judged_at": r[8].isoformat() if r[8] else None,
                }
            )
        return {"success": True, "items": items}
    except Exception as e:
        logger.warning("list_context_grouping_feedback: %s", e)
        return {"success": False, "error": str(e), "items": []}
    finally:
        try:
            conn.close()
        except Exception:
            pass
