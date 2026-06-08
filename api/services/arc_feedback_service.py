"""
Arc report feedback — operator ratings on weekly brief sections (Phase 6).

High-rated sections boost priority in the next slow_report generation pass.
"""

from __future__ import annotations

import logging
from typing import Any

from shared.database.connection import get_db_connection_context, get_ui_db_connection_context

logger = logging.getLogger(__name__)

SECTION_KEYS = (
    "overall",
    "what_changed",
    "where_this_fits",
    "the_numbers",
    "prior_analogues",
    "open_questions",
)


def submit_arc_report_feedback(
    arc_id: str,
    *,
    report_id: int | None = None,
    section_key: str = "overall",
    rating: int | None = None,
    useful: bool | None = None,
    notes: str | None = None,
    curator: str = "operator",
) -> dict[str, Any]:
    if section_key not in SECTION_KEYS:
        return {"success": False, "error": f"invalid section_key; use one of {SECTION_KEYS}"}
    if rating is not None and (rating < 1 or rating > 5):
        return {"success": False, "error": "rating must be 1-5"}
    if rating is None and useful is None and not notes:
        return {"success": False, "error": "provide rating, useful, and/or notes"}

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.arc_report_feedback (
                    arc_id, report_id, section_key, rating, useful, notes, curator
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (arc_id, report_id, section_key, rating, useful, notes, curator),
            )
            fid = cur.fetchone()[0]
        conn.commit()
    return {"success": True, "feedback_id": fid}


def get_arc_feedback_summary(arc_id: str, *, limit: int = 50) -> dict[str, Any]:
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT section_key,
                       COUNT(*) AS n,
                       AVG(rating)::numeric(4,2) AS avg_rating,
                       SUM(CASE WHEN useful THEN 1 ELSE 0 END) AS useful_count
                FROM intelligence.arc_report_feedback
                WHERE arc_id = %s AND created_at > NOW() - INTERVAL '90 days'
                GROUP BY section_key
                ORDER BY avg_rating DESC NULLS LAST
                """,
                (arc_id,),
            )
            by_section = []
            for row in cur.fetchall():
                by_section.append(
                    {
                        "section_key": row[0],
                        "count": int(row[1]),
                        "avg_rating": float(row[2]) if row[2] is not None else None,
                        "useful_count": int(row[3] or 0),
                    }
                )
            cur.execute(
                """
                SELECT id, report_id, section_key, rating, useful, notes, curator, created_at
                FROM intelligence.arc_report_feedback
                WHERE arc_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (arc_id, limit),
            )
            cols = [d[0] for d in cur.description]
            recent = []
            for row in cur.fetchall():
                d = dict(zip(cols, row))
                if d.get("created_at"):
                    d["created_at"] = d["created_at"].isoformat()
                recent.append(d)
    return {"arc_id": arc_id, "by_section": by_section, "recent": recent}


def get_feedback_prompt_boost(arc_id: str) -> str:
    """Text block for slow_report prompt — sections operators rated highly."""
    summary = get_arc_feedback_summary(arc_id)
    boosts = [
        s
        for s in summary.get("by_section") or []
        if (s.get("avg_rating") or 0) >= 4 or (s.get("useful_count") or 0) >= 2
    ]
    if not boosts:
        return ""
    lines = ["Operator feedback (prioritize these sections in depth):"]
    for s in boosts:
        lines.append(
            f"- {s['section_key']}: avg rating {s.get('avg_rating')}, useful marks {s.get('useful_count')}"
        )
    return "\n".join(lines)
