"""
Narrative thread detection and synthesis — T3.3.
Build/update intelligence.narrative_threads from storylines.
Synthesize threads into coherent narratives using LLM with full intelligence context
(articles, entities, claims, entity positions, processed documents).
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


async def _llm_synthesize(prompt: str) -> Optional[str]:
    """Call LLM for narrative synthesis; returns text or None."""
    try:
        from shared.services.llm_service import llm_service, TaskType
        result = await llm_service.generate_summary(prompt[:4000], task_type=TaskType.QUICK_SUMMARY)
        if result.get("success"):
            return (result.get("summary") or "").strip() or None
    except Exception as e:
        logger.debug("LLM narrative synthesis failed: %s", e)
    return None


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
    T3.3: Multi-source narrative synthesis. Gathers thread summaries and uses
    content_synthesis_service to build full context, then produces an LLM-synthesized
    narrative that weaves storylines together with entity positions, claims, and documents.
    """
    import asyncio

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

        if not threads:
            return {"success": True, "synthesis": "(No narrative threads yet; run narrative thread build first.)", "thread_count": 0, "threads": []}

        # Build rich context from content_synthesis_service for each domain represented
        from services.content_synthesis_service import synthesize_domain_context, render_synthesis_for_llm
        domains_represented = list({t["domain_key"] for t in threads if t.get("domain_key")})
        context_parts = []
        for dk in domains_represented[:3]:
            synthesis_ctx = synthesize_domain_context(dk, hours=48, max_articles=15, max_storylines=8, max_events=5, max_entities=15)
            if synthesis_ctx.get("success"):
                rendered = render_synthesis_for_llm(synthesis_ctx, max_chars=2500)
                context_parts.append(f"### Domain: {dk}\n{rendered}")

        thread_summaries = "\n".join(
            f"- {t.get('summary_snippet', '(no summary)')}" for t in threads if t.get("summary_snippet")
        )

        prompt = (
            "You are an intelligence analyst synthesizing multiple narrative threads into a coherent briefing.\n\n"
            f"Narrative threads:\n{thread_summaries}\n\n"
        )
        if context_parts:
            prompt += "Supporting intelligence:\n" + "\n\n".join(context_parts) + "\n\n"
        prompt += (
            "Write a unified narrative synthesis (300-500 words) that:\n"
            "1. Identifies the overarching story across these threads\n"
            "2. Highlights where entity positions or stances create tension or alignment\n"
            "3. Notes any government/research document findings that support or contradict the narrative\n"
            "4. Identifies cross-domain connections if present\n"
            "5. Concludes with what to watch next\n"
            "Write in a professional journalistic tone suitable for an intelligence briefing."
        )

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    synthesis_text = pool.submit(lambda: asyncio.run(_llm_synthesize(prompt))).result(timeout=60)
            else:
                synthesis_text = loop.run_until_complete(_llm_synthesize(prompt))
        except Exception:
            synthesis_text = None

        if not synthesis_text:
            # Fallback: structured summary without LLM
            parts = [t["summary_snippet"] for t in threads if t["summary_snippet"]]
            synthesis_text = "\n\n".join(parts)[:4000] if parts else "(Synthesis unavailable; thread summaries collected.)"

        return {
            "success": True,
            "synthesis": synthesis_text,
            "thread_count": len(threads),
            "threads": threads,
            "domains": domains_represented,
        }
    except Exception as e:
        logger.exception("synthesize_threads: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "synthesis": None, "error": str(e)}
