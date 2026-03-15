"""
Narrative thread detection and synthesis — T3.3.
Build/update intelligence.narrative_threads from storylines (summary, linked_article_ids).
Stub for causal-chain detection and synthesis engine; quality checks placeholder.
See docs/V6_QUALITY_FIRST_UPGRADE_PLAN.md, V6_QUALITY_FIRST_TODO.md Tier 3.
"""

import logging
from typing import Any, Dict, List, Optional

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

DOMAIN_TO_SCHEMA = {
    "politics": "politics",
    "finance": "finance",
    "science-tech": "science_tech",
}


def ensure_narrative_thread(domain_key: str, storyline_id: int) -> Dict[str, Any]:
    """
    Ensure a narrative_thread exists for (domain_key, storyline_id). If the storyline exists,
    populate linked_article_ids from storyline_articles and optional summary from storyline title/analysis_summary.
    Returns { success, thread_id, created: bool }.
    """
    schema = DOMAIN_TO_SCHEMA.get(domain_key)
    if not schema:
        return {"success": False, "error": f"Unknown domain_key: {domain_key}"}

    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database unavailable"}

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM intelligence.narrative_threads WHERE domain_key = %s AND storyline_id = %s",
                (domain_key, storyline_id),
            )
            existing = cur.fetchone()
            if existing:
                thread_id = existing[0]
                # Optionally refresh linked_article_ids and summary from storyline
                cur.execute(
                    f'SELECT title, analysis_summary FROM "{schema}".storylines WHERE id = %s',
                    (storyline_id,),
                )
                srow = cur.fetchone()
                summary = None
                if srow:
                    title, analysis = srow
                    summary = (analysis or title or "")[:2000] if (analysis or title) else None
                cur.execute(
                    f'SELECT article_id FROM "{schema}".storyline_articles WHERE storyline_id = %s ORDER BY added_at NULLS LAST, article_id',
                    (storyline_id,),
                )
                article_ids = [r[0] for r in cur.fetchall()]
                cur.execute(
                    "UPDATE intelligence.narrative_threads SET summary = %s, linked_article_ids = %s WHERE id = %s",
                    (summary, article_ids, thread_id),
                )
                conn.commit()
                return {"success": True, "thread_id": thread_id, "created": False}
            # Create new thread
            cur.execute(
                f'SELECT title, analysis_summary FROM "{schema}".storylines WHERE id = %s',
                (storyline_id,),
            )
            srow = cur.fetchone()
            if not srow:
                return {"success": False, "error": f"Storyline {storyline_id} not found in domain {domain_key}"}
            title, analysis = srow
            summary = (analysis or title or "")[:2000] if (analysis or title) else None
            cur.execute(
                f'SELECT article_id FROM "{schema}".storyline_articles WHERE storyline_id = %s ORDER BY added_at NULLS LAST, article_id',
                (storyline_id,),
            )
            article_ids = [r[0] for r in cur.fetchall()]
            cur.execute(
                """
                INSERT INTO intelligence.narrative_threads (domain_key, storyline_id, summary, linked_article_ids)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (domain_key, storyline_id, summary, article_ids),
            )
            thread_id = cur.fetchone()[0]
        conn.commit()
        return {"success": True, "thread_id": thread_id, "created": True}
    except Exception as e:
        logger.exception("ensure_narrative_thread: %s", e)
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


def build_threads_for_domain(domain_key: str, limit: int = 50) -> Dict[str, Any]:
    """
    Create or update narrative_threads for recent storylines in the domain.
    Returns { success, built: int, errors: [] }.
    """
    schema = DOMAIN_TO_SCHEMA.get(domain_key)
    if not schema:
        return {"success": False, "built": 0, "errors": [f"Unknown domain_key: {domain_key}"]}

    conn = get_db_connection()
    if not conn:
        return {"success": False, "built": 0, "errors": ["Database unavailable"]}

    built = 0
    errors: List[str] = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                f'SELECT id FROM "{schema}".storylines ORDER BY updated_at DESC NULLS LAST LIMIT %s',
                (limit,),
            )
            storyline_ids = [r[0] for r in cur.fetchall()]
        conn.close()
        for sid in storyline_ids:
            result = ensure_narrative_thread(domain_key, sid)
            if result.get("success"):
                built += 1
            else:
                errors.append(f"storyline {sid}: {result.get('error', 'unknown')}")
        return {"success": len(errors) == 0, "built": built, "errors": errors}
    except Exception as e:
        logger.exception("build_threads_for_domain: %s", e)
        return {"success": False, "built": built, "errors": [str(e)]}


def synthesize_threads(domain_key: Optional[str] = None, thread_ids: Optional[List[int]] = None) -> Dict[str, Any]:
    """
    T3.3 stub: Multi-source synthesis. Returns placeholder synthesis text and thread refs.
    Full implementation: conflict resolution, uncertainty quantification later.
    """
    conn = get_db_connection()
    if not conn:
        return {"success": False, "synthesis": None, "error": "Database unavailable"}

    try:
        with conn.cursor() as cur:
            if thread_ids:
                placeholders = ",".join(["%s"] * len(thread_ids))
                cur.execute(
                    f"""
                    SELECT id, domain_key, storyline_id, summary FROM intelligence.narrative_threads
                    WHERE id IN ({placeholders})
                    ORDER BY id
                    """,
                    tuple(thread_ids),
                )
            elif domain_key:
                cur.execute(
                    """
                    SELECT id, domain_key, storyline_id, summary FROM intelligence.narrative_threads
                    WHERE domain_key = %s
                    ORDER BY id DESC
                    LIMIT 20
                    """,
                    (domain_key,),
                )
            else:
                cur.execute(
                    """
                    SELECT id, domain_key, storyline_id, summary FROM intelligence.narrative_threads
                    ORDER BY id DESC
                    LIMIT 20
                    """
                )
            rows = cur.fetchall()
        conn.close()
        threads = [
            {"id": r[0], "domain_key": r[1], "storyline_id": r[2], "summary_snippet": (r[3] or "")[:300] if r[3] else None}
            for r in rows
        ]
        # Placeholder synthesis: concatenate snippet of summaries
        parts = [t["summary_snippet"] for t in threads if t["summary_snippet"]]
        synthesis = "\n\n".join(parts)[:4000] if parts else "(No thread summaries yet; run narrative thread build first.)"
        return {
            "success": True,
            "synthesis": synthesis,
            "thread_count": len(threads),
            "threads": threads,
        }
    except Exception as e:
        logger.exception("synthesize_threads: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "synthesis": None, "error": str(e)}
