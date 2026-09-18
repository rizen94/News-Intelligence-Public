"""Review parked resolution queue entries."""

from __future__ import annotations

from typing import Any

from config.investigation_tables import T_PARKED_RESOLUTION
from nri_core.evidence import ni_reader


def review_parked(
    parked_id: int,
    *,
    review_status: str,
    candidate_ftm_id: str | None = None,
) -> dict[str, Any]:
    with ni_reader.news_intel_connection() as conn:
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

    if not row:
        return {"error": "not_found"}
    return {
        "id": row[0],
        "context_id": row[1],
        "mention_text": row[2],
        "candidate_ftm_id": row[3],
        "review_status": row[4],
    }
