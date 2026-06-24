"""In-process parked resolution review (replaces NRI API proxy)."""

from __future__ import annotations

from typing import Any

from config.investigation_tables import T_PARKED_RESOLUTION
from shared.database.connection import get_db_connection


def review_parked_in_process(
    parked_id: int,
    *,
    review_status: str,
    candidate_ftm_id: str | None = None,
) -> dict[str, Any]:
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed"}
    try:
        with conn.cursor() as cur:
            if candidate_ftm_id:
                cur.execute(
                    f"""
                    UPDATE {T_PARKED_RESOLUTION}
                    SET review_status = %s,
                        candidate_ftm_id = %s,
                        reviewed_at = NOW()
                    WHERE id = %s
                    RETURNING id, context_id, mention_text, candidate_ftm_id, review_status
                    """,
                    (review_status, candidate_ftm_id, parked_id),
                )
            else:
                cur.execute(
                    f"""
                    UPDATE {T_PARKED_RESOLUTION}
                    SET review_status = %s,
                        reviewed_at = NOW()
                    WHERE id = %s
                    RETURNING id, context_id, mention_text, candidate_ftm_id, review_status
                    """,
                    (review_status, parked_id),
                )
            row = cur.fetchone()
        conn.commit()
        conn.close()
        if not row:
            return {"success": False, "error": "not_found"}
        return {
            "success": True,
            "id": row[0],
            "context_id": row[1],
            "mention_text": row[2],
            "candidate_ftm_id": row[3],
            "review_status": row[4],
        }
    except Exception as e:
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)}
