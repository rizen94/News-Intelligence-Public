"""
Content feedback service — persist and read user feedback (usefulness 1-5, not interested)
for articles, storylines, and whole briefings. Used to reorder briefing feed and demote items.
"""

import logging
from typing import Dict, Any, List, Optional, Set

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)


def submit_feedback(
    domain: str,
    item_type: str,
    item_id: Optional[int],
    *,
    rating: Optional[int] = None,
    not_interested: bool = False,
) -> Dict[str, Any]:
    """
    Record feedback for an article, storyline, or whole briefing.
    item_type: 'article' | 'storyline' | 'briefing'
    item_id: required for article/storyline; None for briefing.
    rating: 1-5 usefulness (optional).
    not_interested: if True, item is demoted/excluded from lead in future.
    """
    if item_type not in ("article", "storyline", "briefing"):
        return {"success": False, "error": "Invalid item_type"}
    if item_type != "briefing" and item_id is None:
        return {"success": False, "error": "item_id required for article/storyline"}
    if rating is not None and (rating < 1 or rating > 5):
        return {"success": False, "error": "rating must be 1-5"}
    if not rating and not not_interested:
        return {"success": False, "error": "Provide rating and/or not_interested"}

    try:
        conn = get_db_connection()
        if not conn:
            return {"success": False, "error": "No database connection"}
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.content_feedback (domain, item_type, item_id, rating, not_interested)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (domain, item_type, item_id, rating, not_interested),
            )
            conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        logger.warning("submit_feedback: %s", e)
        return {"success": False, "error": str(e)}


def get_not_interested_ids(domain: str, item_type: str) -> Set[int]:
    """Return set of article_id or storyline_id that user marked not interested."""
    out: Set[int] = set()
    try:
        conn = get_db_connection()
        if not conn:
            return out
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT item_id FROM public.content_feedback
                WHERE domain = %s AND item_type = %s AND not_interested = TRUE AND item_id IS NOT NULL
                """,
                (domain, item_type),
            )
            for row in cur.fetchall():
                out.add(row[0])
        conn.close()
    except Exception as e:
        logger.debug("get_not_interested_ids: %s", e)
    return out


def get_ratings_for_items(domain: str, item_type: str, item_ids: List[int]) -> Dict[int, int]:
    """Return mapping item_id -> latest rating (1-5) for given ids. Used to boost high-rated in ordering."""
    if not item_ids:
        return {}
    out: Dict[int, int] = {}
    try:
        conn = get_db_connection()
        if not conn:
            return out
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT ON (item_id) item_id, rating
                FROM public.content_feedback
                WHERE domain = %s AND item_type = %s AND item_id = ANY(%s) AND rating IS NOT NULL
                ORDER BY item_id, created_at DESC
                """,
                (domain, item_type, item_ids),
            )
            for row in cur.fetchall():
                out[row[0]] = row[1]
        conn.close()
    except Exception as e:
        logger.debug("get_ratings_for_items: %s", e)
    return out
