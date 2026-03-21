"""
Content refinement queue — durable jobs for storyline LLM work (not ad-hoc on HTTP GET).

Job types:
  - comprehensive_rag: same pipeline as legacy POST .../analyze (process_storyline_rag_analysis)
  - narrative_finisher: ~70B canonical narrative pass + persist
  - timeline_narrative_chronological | timeline_narrative_briefing: 8B narrative from timeline, stored on storylines

Processed by automation task `content_refinement_queue` (see automation_manager).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

ALLOWED_DOMAIN_KEYS = frozenset({"politics", "finance", "science-tech"})

JOB_COMPREHENSIVE_RAG = "comprehensive_rag"
JOB_NARRATIVE_FINISHER = "narrative_finisher"
JOB_TIMELINE_CHRONO = "timeline_narrative_chronological"
JOB_TIMELINE_BRIEFING = "timeline_narrative_briefing"

VALID_JOB_TYPES = frozenset(
    {
        JOB_COMPREHENSIVE_RAG,
        JOB_NARRATIVE_FINISHER,
        JOB_TIMELINE_CHRONO,
        JOB_TIMELINE_BRIEFING,
    }
)

_MAX_FINISHER_PER_CYCLE = int(os.environ.get("CONTENT_REFINEMENT_MAX_FINISHER_JOBS_PER_CYCLE", "1"))
_MAX_JOBS_PER_CYCLE = int(os.environ.get("CONTENT_REFINEMENT_MAX_JOBS_PER_CYCLE", "4"))


def enqueue_content_refinement(
    domain_key: str,
    storyline_id: int,
    job_type: str,
    *,
    priority: str = "medium",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Insert a pending job if none exists for (domain, storyline, job_type).
    Returns { success, queue_id?, already_queued?, error? }.
    """
    if domain_key not in ALLOWED_DOMAIN_KEYS:
        return {"success": False, "error": "invalid_domain"}
    if job_type not in VALID_JOB_TYPES:
        return {"success": False, "error": "invalid_job_type"}
    if priority not in ("high", "medium", "low"):
        return {"success": False, "error": "invalid_priority"}

    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "no_db_connection"}

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM intelligence.content_refinement_queue
                WHERE domain_key = %s AND storyline_id = %s AND job_type = %s
                  AND status = 'pending'
                LIMIT 1
                """,
                (domain_key, storyline_id, job_type),
            )
            row = cur.fetchone()
            if row:
                return {
                    "success": True,
                    "queue_id": row[0],
                    "already_queued": True,
                    "message": "Job already pending for this storyline",
                }

            meta_json = json.dumps(metadata or {})
            cur.execute(
                """
                INSERT INTO intelligence.content_refinement_queue
                    (domain_key, storyline_id, job_type, priority, status, metadata)
                VALUES (%s, %s, %s, %s, 'pending', %s::jsonb)
                RETURNING id
                """,
                (domain_key, storyline_id, job_type, priority, meta_json),
            )
            qid = cur.fetchone()[0]
        conn.commit()
        return {
            "success": True,
            "queue_id": qid,
            "already_queued": False,
            "message": "Queued for background processing",
        }
    except Exception as e:
        conn.rollback()
        logger.exception("enqueue_content_refinement: %s", e)
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def list_pending_job_types(domain_key: str, storyline_id: int) -> List[str]:
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT job_type FROM intelligence.content_refinement_queue
                WHERE domain_key = %s AND storyline_id = %s AND status = 'pending'
                ORDER BY created_at ASC
                """,
                (domain_key, storyline_id),
            )
            return [r[0] for r in cur.fetchall()]
    except Exception as e:
        logger.warning("list_pending_job_types: %s", e)
        return []
    finally:
        conn.close()


def _claim_pending_batch(conn, limit: int) -> List[Tuple[Any, ...]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH cte AS (
                SELECT id
                FROM intelligence.content_refinement_queue
                WHERE status = 'pending'
                ORDER BY
                    CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                    created_at ASC
                LIMIT %s
                FOR UPDATE SKIP LOCKED
            )
            UPDATE intelligence.content_refinement_queue q
            SET status = 'processing',
                started_at = NOW()
            FROM cte
            WHERE q.id = cte.id
            RETURNING q.id, q.domain_key, q.storyline_id, q.job_type, q.priority, q.metadata
            """,
            (limit,),
        )
        return list(cur.fetchall())


def _complete_job(job_id: int, ok: bool, err: Optional[str] = None) -> None:
    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            if ok:
                cur.execute(
                    """
                    UPDATE intelligence.content_refinement_queue
                    SET status = 'completed', completed_at = NOW(), error_message = NULL
                    WHERE id = %s
                    """,
                    (job_id,),
                )
            else:
                cur.execute(
                    """
                    UPDATE intelligence.content_refinement_queue
                    SET status = 'failed', completed_at = NOW(), error_message = %s
                    WHERE id = %s
                    """,
                    ((err or "unknown")[:8000], job_id),
                )
        conn.commit()
    finally:
        conn.close()


async def _run_comprehensive_rag(domain_key: str, storyline_id: int) -> None:
    from domains.storyline_management.routes.storyline_management import (
        load_rag_analysis_inputs_for_queue,
        process_storyline_rag_analysis,
    )

    loaded = load_rag_analysis_inputs_for_queue(domain_key, storyline_id)
    if not loaded:
        raise RuntimeError("storyline_not_found_or_no_articles")
    storyline_tuple, articles = loaded
    await process_storyline_rag_analysis(domain_key, storyline_id, storyline_tuple, articles)


async def _run_narrative_finisher(domain_key: str, storyline_id: int) -> None:
    from services.storyline_narrative_finisher_service import (
        run_narrative_finish_from_db,
        persist_narrative_finish_to_db,
    )

    result = await run_narrative_finish_from_db(domain_key, storyline_id, parse_json=True)
    if not result.get("success"):
        raise RuntimeError(result.get("error", "finisher_failed"))
    persist_narrative_finish_to_db(domain_key, storyline_id, result)


async def _run_timeline_narrative(domain_key: str, storyline_id: int, mode: str) -> None:
    schema = domain_key.replace("-", "_")
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("no_db_connection")
    try:
        from services.timeline_builder_service import TimelineBuilderService
        from services.narrative_synthesis_service import NarrativeSynthesisService

        tb = TimelineBuilderService(conn, schema_name=schema)
        timeline = tb.build_timeline(storyline_id)
        if not timeline.get("events"):
            raise RuntimeError("no_timeline_events")

        ns = NarrativeSynthesisService()
        try:
            if mode == "briefing":
                result = await ns.generate_briefing(timeline)
                col_text = "timeline_narrative_briefing"
                col_at = "timeline_narrative_briefing_at"
            else:
                result = await ns.generate_chronological_narrative(timeline)
                col_text = "timeline_narrative_chronological"
                col_at = "timeline_narrative_chronological_at"
        finally:
            await ns.close()

        if not result.get("success"):
            raise RuntimeError(result.get("error", "narrative_generation_failed"))

        text = (result.get("narrative") or result.get("briefing") or "").strip()
        now = datetime.now(timezone.utc)
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {schema}.storylines
                SET {col_text} = %s,
                    {col_at} = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                (text, now, now, storyline_id),
            )
        conn.commit()
    finally:
        conn.close()


async def process_content_refinement_queue_batch() -> Dict[str, Any]:
    """
    Claim and run up to CONTENT_REFINEMENT_MAX_JOBS_PER_CYCLE jobs.
    Caps narrative_finisher jobs per cycle for GPU friendliness.
    """
    conn = get_db_connection()
    if not conn:
        return {"processed": 0, "error": "no_db_connection"}

    stats = {"processed": 0, "failed": 0, "by_type": {}}
    finisher_run = 0
    to_process: List[Tuple[Any, ...]] = []

    try:
        rows = _claim_pending_batch(conn, _MAX_JOBS_PER_CYCLE * 2)
        if not rows:
            conn.commit()
            return stats

        # Re-order: defer extra finisher jobs beyond cap (put back to pending)
        to_process = []
        deferred_ids: List[int] = []
        for row in rows:
            _id, dkey, sid, jtype, _prio, _meta = row
            if jtype == JOB_NARRATIVE_FINISHER:
                if finisher_run >= _MAX_FINISHER_PER_CYCLE:
                    deferred_ids.append(_id)
                    continue
                finisher_run += 1
            to_process.append(row)

        if deferred_ids:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE intelligence.content_refinement_queue
                    SET status = 'pending', started_at = NULL
                    WHERE id = ANY(%s)
                    """,
                    (deferred_ids,),
                )

        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.exception("process_content_refinement_queue_batch claim: %s", e)
        stats["error"] = str(e)
        return stats
    finally:
        try:
            conn.close()
        except Exception:
            pass

    for row in to_process[:_MAX_JOBS_PER_CYCLE]:
        job_id, domain_key, storyline_id, job_type, _priority, _metadata = row
        try:
            if job_type == JOB_COMPREHENSIVE_RAG:
                await _run_comprehensive_rag(domain_key, storyline_id)
            elif job_type == JOB_NARRATIVE_FINISHER:
                await _run_narrative_finisher(domain_key, storyline_id)
            elif job_type == JOB_TIMELINE_CHRONO:
                await _run_timeline_narrative(domain_key, storyline_id, "chronological")
            elif job_type == JOB_TIMELINE_BRIEFING:
                await _run_timeline_narrative(domain_key, storyline_id, "briefing")
            else:
                raise RuntimeError(f"unknown_job_type:{job_type}")

            _complete_job(job_id, True)
            stats["processed"] += 1
            stats["by_type"][job_type] = stats["by_type"].get(job_type, 0) + 1
        except Exception as e:
            logger.exception("content_refinement job %s failed: %s", job_id, e)
            _complete_job(job_id, False, str(e))
            stats["failed"] += 1

    return stats
