"""
Content refinement queue — durable jobs for storyline LLM work (not ad-hoc on HTTP GET).

Job types:
  - comprehensive_rag: same pipeline as legacy POST .../analyze (process_storyline_rag_analysis)
  - narrative_finisher: ~70B canonical narrative pass + persist
  - headline_refiner: ~70B editorial headline + optional description (from article evidence)
  - timeline_narrative_chronological | timeline_narrative_briefing: 8B narrative from timeline, stored on storylines

Processed by automation task `content_refinement_queue` (see automation_manager).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

ALLOWED_DOMAIN_KEYS = frozenset({"politics", "finance", "science-tech"})

JOB_COMPREHENSIVE_RAG = "comprehensive_rag"
JOB_NARRATIVE_FINISHER = "narrative_finisher"
JOB_HEADLINE_REFINER = "headline_refiner"
JOB_TIMELINE_CHRONO = "timeline_narrative_chronological"
JOB_TIMELINE_BRIEFING = "timeline_narrative_briefing"

VALID_JOB_TYPES = frozenset(
    {
        JOB_COMPREHENSIVE_RAG,
        JOB_NARRATIVE_FINISHER,
        JOB_HEADLINE_REFINER,
        JOB_TIMELINE_CHRONO,
        JOB_TIMELINE_BRIEFING,
    }
)

# ~70B narrative finisher + headline refiner share one GPU-friendly cap per batch
_HEAVY_70B_JOB_TYPES = frozenset({JOB_NARRATIVE_FINISHER, JOB_HEADLINE_REFINER})
_MAX_FINISHER_PER_CYCLE = int(os.environ.get("CONTENT_REFINEMENT_MAX_FINISHER_JOBS_PER_CYCLE", "1"))
_MAX_JOBS_PER_CYCLE = int(os.environ.get("CONTENT_REFINEMENT_MAX_JOBS_PER_CYCLE", "4"))


def enqueue_content_refinement(
    domain_key: str,
    storyline_id: int,
    job_type: str,
    *,
    priority: str = "medium",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
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


def list_pending_job_types(domain_key: str, storyline_id: int) -> list[str]:
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


def _claim_pending_batch(conn, limit: int) -> list[tuple[Any, ...]]:
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


def _complete_job(job_id: int, ok: bool, err: str | None = None) -> None:
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
        persist_narrative_finish_to_db,
        run_narrative_finish_from_db,
    )

    result = await run_narrative_finish_from_db(domain_key, storyline_id, parse_json=True)
    if not result.get("success"):
        raise RuntimeError(result.get("error", "finisher_failed"))
    persist_narrative_finish_to_db(domain_key, storyline_id, result)


async def _run_headline_refiner(domain_key: str, storyline_id: int) -> None:
    """~70B headline/description pass using linked articles as evidence."""
    from services.storyline_narrative_finisher_service import refine_storyline_headline_with_70b

    schema = domain_key.replace("-", "_")
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("no_db_connection")
    draft_title = ""
    draft_desc = ""
    evidence_lines: list[str] = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT title, COALESCE(description, '')
                FROM {schema}.storylines
                WHERE id = %s
                """,
                (storyline_id,),
            )
            row = cur.fetchone()
            if not row:
                raise RuntimeError("storyline_not_found")
            draft_title = row[0] or ""
            draft_desc = row[1] or ""
            cur.execute(
                f"""
                SELECT a.title, COALESCE(a.summary, '') AS summary
                FROM {schema}.articles a
                JOIN {schema}.storyline_articles sa ON sa.article_id = a.id
                WHERE sa.storyline_id = %s
                  AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                ORDER BY a.published_at DESC NULLS LAST
                LIMIT 20
                """,
                (storyline_id,),
            )
            for r in cur.fetchall() or []:
                bt = (r[0] or "").strip()
                sm = (r[1] or "").strip()
                line = f"{bt[:400]} — {sm[:400]}".strip(" —")
                if line:
                    evidence_lines.append(line)
    finally:
        conn.close()

    if not evidence_lines:
        raise RuntimeError("no_articles_for_headline_evidence")

    refined = await refine_storyline_headline_with_70b(
        domain_key,
        draft_title,
        draft_desc[:2000],
        evidence_lines,
    )
    if not refined.get("success") or not (refined.get("title") or "").strip():
        raise RuntimeError(
            refined.get("parse_error") or "headline_refine_failed_or_empty_title"
        )

    new_t = refined["title"][:500]
    new_d = (refined.get("description") or "").strip()[:5000]

    conn = get_db_connection()
    if not conn:
        raise RuntimeError("no_db_connection")
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {schema}.storylines
                SET title = %s,
                    description = COALESCE(NULLIF(%s, ''), description),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (new_t, new_d, storyline_id),
            )
        conn.commit()
    finally:
        conn.close()


async def _run_timeline_narrative(domain_key: str, storyline_id: int, mode: str) -> None:
    schema = domain_key.replace("-", "_")
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("no_db_connection")
    try:
        from services.narrative_synthesis_service import NarrativeSynthesisService
        from services.timeline_builder_service import TimelineBuilderService

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


async def process_content_refinement_queue_batch() -> dict[str, Any]:
    """
    Claim and run up to CONTENT_REFINEMENT_MAX_JOBS_PER_CYCLE jobs.
    Caps ~70B jobs (narrative_finisher + headline_refiner) per cycle for GPU friendliness.
    """
    conn = get_db_connection()
    if not conn:
        return {"processed": 0, "error": "no_db_connection"}

    stats = {"processed": 0, "failed": 0, "by_type": {}}
    finisher_run = 0
    to_process: list[tuple[Any, ...]] = []

    try:
        rows = _claim_pending_batch(conn, _MAX_JOBS_PER_CYCLE * 2)
        if not rows:
            conn.commit()
            return stats

        # Re-order: defer extra finisher jobs beyond cap (put back to pending)
        to_process = []
        deferred_ids: list[int] = []
        for row in rows:
            _id, dkey, sid, jtype, _prio, _meta = row
            if jtype in _HEAVY_70B_JOB_TYPES:
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
            elif job_type == JOB_HEADLINE_REFINER:
                await _run_headline_refiner(domain_key, storyline_id)
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
