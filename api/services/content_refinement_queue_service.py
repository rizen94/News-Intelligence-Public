"""
Content refinement queue — durable jobs for storyline LLM work (not ad-hoc on HTTP GET).

Job types:
  - comprehensive_rag: same pipeline as legacy POST .../analyze (process_storyline_rag_analysis)
  - narrative_finisher: ~70B canonical narrative pass + persist
  - headline_refiner: ~70B editorial headline + optional description (from article evidence)
  - timeline_narrative_chronological | timeline_narrative_briefing: 8B narrative from timeline, stored on storylines

Processed by automation task `content_refinement_queue` (see automation_manager).
Before each drain batch, automation calls `auto_enqueue_comprehensive_rag_for_automation()` so
deep analysis (`comprehensive_rag`) is queued without using the UI (disable via
`AUTO_ENQUEUE_COMPREHENSIVE_RAG=0`). The scheduler also calls
`maybe_auto_enqueue_comprehensive_rag_from_scheduler()` every ~30s so the DB queue gains work even
when the refinement phase is starved (`AUTO_ENQUEUE_RAG_SCHEDULER_SECONDS`).

Nightly pipeline (America/New_York by default): automation phase `nightly_enrichment_context` runs
02:00–05:00 (`NIGHTLY_PIPELINE_*`), draining enrichment, then context_sync, then this queue with
higher per-batch caps. GPU refinement starts as soon as enrichment and context_sync are idle (no
wait for 03:00). When all three are idle, the phase exits and normal automation resumes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from collections.abc import Callable
from typing import Any

from shared.database.connection import get_db_connection
from shared.domain_registry import get_active_domain_keys

logger = logging.getLogger(__name__)

# Throttle scheduler-driven enqueue so we fill the DB queue even if the refinement phase is starved.
_last_scheduler_auto_enqueue_monotonic: float = 0.0

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
# Claim enough pending rows to sort by "initial master narrative" vs refresh before applying caps
_CLAIM_BATCH = int(os.environ.get("CONTENT_REFINEMENT_CLAIM_BATCH", "32"))

# Nightly window (local TZ): higher throughput for ~70B finisher catch-up
_NIGHTLY_MAX_FINISHER = int(
    os.environ.get(
        "CONTENT_REFINEMENT_NIGHTLY_MAX_FINISHER_JOBS_PER_CYCLE",
        str(max(_MAX_FINISHER_PER_CYCLE, 2)),
    )
)
_NIGHTLY_MAX_JOBS = int(
    os.environ.get(
        "CONTENT_REFINEMENT_NIGHTLY_MAX_JOBS_PER_CYCLE",
        str(max(_MAX_JOBS_PER_CYCLE, 6)),
    )
)
_NIGHTLY_CLAIM_BATCH = int(
    os.environ.get(
        "CONTENT_REFINEMENT_NIGHTLY_CLAIM_BATCH",
        str(max(_CLAIM_BATCH, 48)),
    )
)
_NIGHTLY_MAX_BATCH_LOOPS = int(os.environ.get("NIGHTLY_GPU_REFINEMENT_MAX_BATCH_LOOPS", "500"))

_nightly_drain_lock = asyncio.Lock()


def in_nightly_gpu_refinement_window_est() -> bool:
    """
    True during the unified nightly pipeline window (default 02:00–05:00 local).
    Kept for backward compatibility; delegates to nightly_ingest_window_service.in_nightly_pipeline_window_est.
    """
    try:
        from services.nightly_ingest_window_service import in_nightly_pipeline_window_est

        return in_nightly_pipeline_window_est()
    except Exception:
        return False


def _default_nightly_pipeline_window_active() -> bool:
    return in_nightly_gpu_refinement_window_est()


def nightly_gpu_refinement_exclusive_gpu_enabled() -> bool:
    """When True, automation defers other Ollama phases during the nightly refinement window."""
    return os.environ.get("NIGHTLY_GPU_REFINEMENT_EXCLUSIVE_GPU", "0").lower() in (
        "1",
        "true",
        "yes",
    )


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
    if domain_key not in get_active_domain_keys():
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


def storyline_needs_initial_master_narrative(domain_key: str, storyline_id: int) -> bool:
    """True if ~70B canonical narrative has never been stored (first finisher pass)."""
    if domain_key not in get_active_domain_keys():
        return True
    schema = domain_key.replace("-", "_")
    conn = get_db_connection()
    if not conn:
        return True
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT (canonical_narrative IS NULL OR btrim(canonical_narrative) = '')
                FROM {schema}.storylines
                WHERE id = %s
                """,
                (storyline_id,),
            )
            row = cur.fetchone()
            if not row:
                return True
            return bool(row[0])
    except Exception as e:
        logger.warning("storyline_needs_initial_master_narrative: %s", e)
        return True
    finally:
        conn.close()


def enqueue_initial_narrative_finisher(
    domain_key: str, storyline_id: int, *, source: str
) -> dict[str, Any]:
    """Queue ~70B master narrative at high priority (deduped per storyline/job_type)."""
    if os.getenv("STORYLINE_AUTO_ENQUEUE_NARRATIVE_FINISHER", "1") == "0":
        return {"success": True, "skipped": True, "reason": "disabled_by_env"}
    return enqueue_content_refinement(
        domain_key,
        storyline_id,
        JOB_NARRATIVE_FINISHER,
        priority="high",
        metadata={"finisher_pass": "initial", "source": source},
    )


def auto_enqueue_comprehensive_rag_for_automation() -> dict[str, Any]:
    """
    Enqueue comprehensive_rag (deep storyline analysis) for storylines that should not depend
    on the UI "Queue deep analysis" button. Called by automation `content_refinement_queue` and
    nightly GPU refinement drain.

    Candidates:
      - ml_processing_status in (pending, processing) — e.g. topic→storyline promotion
      - Else if document_status is present: never rag_analyzed (NULL or other values)

    Disabled with AUTO_ENQUEUE_COMPREHENSIVE_RAG=0. Per-domain scan cap:
    AUTO_ENQUEUE_COMPREHENSIVE_RAG_PER_DOMAIN (default 8).
    """
    if os.getenv("AUTO_ENQUEUE_COMPREHENSIVE_RAG", "1").lower() not in (
        "1",
        "true",
        "yes",
    ):
        return {"skipped": True, "reason": "disabled_by_env", "enqueued": 0, "already_queued": 0}

    limit = max(1, int(os.environ.get("AUTO_ENQUEUE_COMPREHENSIVE_RAG_PER_DOMAIN", "8")))
    stats: dict[str, Any] = {"enqueued": 0, "already_queued": 0, "errors": 0, "by_domain": {}}

    for domain_key in sorted(get_active_domain_keys()):
        schema = domain_key.replace("-", "_")
        d_stats = {"enqueued": 0, "already_queued": 0}
        conn = get_db_connection()
        if not conn:
            stats["errors"] += 1
            continue
        rows: list[tuple[int, str]] = []
        try:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        f"""
                        SELECT s.id,
                          CASE
                            WHEN s.ml_processing_status IN ('pending', 'processing')
                            THEN 'high' ELSE 'medium'
                          END AS prio
                        FROM {schema}.storylines s
                        WHERE s.status = 'active'
                          AND EXISTS (
                              SELECT 1 FROM {schema}.storyline_articles sa
                              WHERE sa.storyline_id = s.id
                          )
                          AND NOT EXISTS (
                              SELECT 1 FROM intelligence.content_refinement_queue q
                              WHERE q.domain_key = %s
                                AND q.storyline_id = s.id
                                AND q.job_type = %s
                                AND q.status IN ('pending', 'processing')
                          )
                          AND (
                            s.ml_processing_status IN ('pending', 'processing')
                            OR (
                              s.document_status IS NULL
                              OR s.document_status <> 'rag_analyzed'
                            )
                          )
                        ORDER BY
                          CASE
                            WHEN s.ml_processing_status IN ('pending', 'processing') THEN 0
                            ELSE 1
                          END,
                          s.updated_at DESC NULLS LAST
                        LIMIT %s
                        """,
                        (domain_key, JOB_COMPREHENSIVE_RAG, limit),
                    )
                    rows = [(int(r[0]), str(r[1])) for r in cur.fetchall()]
                except Exception as e:
                    err = str(e).lower()
                    if "document_status" not in err and "undefinedcolumn" not in err:
                        raise
                    cur.execute(
                        f"""
                        SELECT s.id, 'high'::text AS prio
                        FROM {schema}.storylines s
                        WHERE s.status = 'active'
                          AND EXISTS (
                              SELECT 1 FROM {schema}.storyline_articles sa
                              WHERE sa.storyline_id = s.id
                          )
                          AND NOT EXISTS (
                              SELECT 1 FROM intelligence.content_refinement_queue q
                              WHERE q.domain_key = %s
                                AND q.storyline_id = s.id
                                AND q.job_type = %s
                                AND q.status IN ('pending', 'processing')
                          )
                          AND s.ml_processing_status IN ('pending', 'processing')
                        ORDER BY s.updated_at DESC NULLS LAST
                        LIMIT %s
                        """,
                        (domain_key, JOB_COMPREHENSIVE_RAG, limit),
                    )
                    rows = [(int(r[0]), str(r[1])) for r in cur.fetchall()]
        except Exception as e:
            logger.warning("auto_enqueue_comprehensive_rag domain=%s: %s", domain_key, e)
            stats["errors"] += 1
        finally:
            conn.close()

        for sid, prio in rows:
            res = enqueue_content_refinement(
                domain_key,
                sid,
                JOB_COMPREHENSIVE_RAG,
                priority=prio if prio in ("high", "medium", "low") else "medium",
                metadata={"source": "automation_auto_enqueue"},
            )
            if not res.get("success"):
                stats["errors"] += 1
                continue
            if res.get("already_queued"):
                d_stats["already_queued"] += 1
            else:
                d_stats["enqueued"] += 1
                stats["enqueued"] += 1

        stats["already_queued"] += d_stats["already_queued"]
        if d_stats["enqueued"] or d_stats["already_queued"]:
            stats["by_domain"][domain_key] = d_stats

    if stats["enqueued"] or stats.get("errors"):
        logger.info(
            "auto_enqueue comprehensive_rag: enqueued=%s already_queued=%s errors=%s by_domain=%s",
            stats["enqueued"],
            stats["already_queued"],
            stats.get("errors", 0),
            stats.get("by_domain", {}),
        )
    return stats


def maybe_auto_enqueue_comprehensive_rag_from_scheduler() -> None:
    """
    Run auto_enqueue on an interval from AutomationManager._scheduler (not only when the
    content_refinement_queue task runs). Otherwise pending=0 skips visible work and the phase
    can starve behind higher-backlog tasks, so storylines never get comprehensive_rag rows.

    Skipped during the unified nightly pipeline window (nightly_enrichment_context owns drain +
    enqueue at drain start). Interval: AUTO_ENQUEUE_RAG_SCHEDULER_SECONDS (default 30).
    """
    global _last_scheduler_auto_enqueue_monotonic
    if os.getenv("AUTO_ENQUEUE_COMPREHENSIVE_RAG", "1").lower() not in (
        "1",
        "true",
        "yes",
    ):
        return
    try:
        from services.nightly_ingest_window_service import in_nightly_pipeline_window_est

        if in_nightly_pipeline_window_est():
            return
    except Exception:
        pass
    interval = float(os.environ.get("AUTO_ENQUEUE_RAG_SCHEDULER_SECONDS", "30"))
    if interval <= 0:
        return
    now = time.monotonic()
    if now - _last_scheduler_auto_enqueue_monotonic < interval:
        return
    _last_scheduler_auto_enqueue_monotonic = now
    auto_enqueue_comprehensive_rag_for_automation()


def _need_initial_narrative_map_for_batch(
    conn, rows: list[tuple[Any, ...]]
) -> dict[tuple[str, int], bool]:
    """Map (domain_key, storyline_id) -> empty canonical narrative, for narrative_finisher rows only."""
    from collections import defaultdict

    by_dkey: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        if len(row) < 4:
            continue
        dkey, sid, jtype = row[1], int(row[2]), row[3]
        if jtype != JOB_NARRATIVE_FINISHER or dkey not in get_active_domain_keys():
            continue
        by_dkey[str(dkey)].append(sid)

    out: dict[tuple[str, int], bool] = {}
    for dkey, ids in by_dkey.items():
        uniq = list(dict.fromkeys(ids))
        schema = dkey.replace("-", "_")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id,
                      (canonical_narrative IS NULL OR btrim(canonical_narrative) = '')
                    FROM {schema}.storylines
                    WHERE id = ANY(%s::int[])
                    """,
                    (uniq,),
                )
                for rid, empty in cur.fetchall() or []:
                    out[(dkey, int(rid))] = bool(empty)
        except Exception as e:
            logger.warning("need_initial_narrative_map %s: %s", schema, e)
        for sid in uniq:
            if (dkey, sid) not in out:
                out[(dkey, sid)] = True
    return out


def _refinement_queue_sort_key(
    row: tuple[Any, ...], initial_nf: dict[tuple[str, int], bool]
) -> tuple[Any, ...]:
    """Order: priority high→low; then initial narrative_finisher; then refresh finisher; headline; other."""
    if len(row) < 7:
        return (9, 9, "", row[0])
    job_id, dkey, sid, jtype, prio, _meta, created_at = row[0], row[1], int(row[2]), row[3], row[4], row[5], row[6]
    pr = 0 if prio == "high" else 1 if prio == "medium" else 2
    if jtype == JOB_NARRATIVE_FINISHER:
        tier = 0 if initial_nf.get((str(dkey), sid), True) else 1
    elif jtype == JOB_HEADLINE_REFINER:
        tier = 2
    else:
        tier = 3
    ts = created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at)
    return (pr, tier, ts, job_id)


def count_content_refinement_pending() -> int:
    """Rows waiting in the DB queue (``status = pending``)."""
    conn = get_db_connection()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.content_refinement_queue
                WHERE status = 'pending'
                """
            )
            return int(cur.fetchone()[0] or 0)
    except Exception as e:
        logger.debug("count_content_refinement_pending: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


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
            RETURNING q.id, q.domain_key, q.storyline_id, q.job_type, q.priority, q.metadata, q.created_at
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


async def process_content_refinement_queue_batch(
    *,
    max_finisher_per_cycle: int | None = None,
    max_jobs_per_cycle: int | None = None,
    claim_batch: int | None = None,
) -> dict[str, Any]:
    """
    Claim and run up to CONTENT_REFINEMENT_MAX_JOBS_PER_CYCLE jobs.
    Caps ~70B jobs (narrative_finisher + headline_refiner) per cycle for GPU friendliness.
    Prefers: high priority, then first-time ~70B master narrative (empty canonical_narrative),
    then refresh finisher, headline refiner, then other job types.
    """
    cap_fin = (
        max_finisher_per_cycle
        if max_finisher_per_cycle is not None
        else _MAX_FINISHER_PER_CYCLE
    )
    cap_jobs = max_jobs_per_cycle if max_jobs_per_cycle is not None else _MAX_JOBS_PER_CYCLE
    cap_claim = claim_batch if claim_batch is not None else _CLAIM_BATCH

    conn = get_db_connection()
    if not conn:
        return {"processed": 0, "error": "no_db_connection"}

    stats: dict[str, Any] = {
        "processed": 0,
        "failed": 0,
        "by_type": {},
        "pending_before": 0,
        "pending_after": 0,
    }
    finisher_run = 0
    to_process: list[tuple[Any, ...]] = []

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.content_refinement_queue
                WHERE status = 'pending'
                """
            )
            stats["pending_before"] = int(cur.fetchone()[0] or 0)

        rows = _claim_pending_batch(conn, max(cap_claim, cap_jobs * 2))
        if not rows:
            conn.commit()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM intelligence.content_refinement_queue
                    WHERE status = 'pending'
                    """
                )
                stats["pending_after"] = int(cur.fetchone()[0] or 0)
            return stats

        initial_nf = _need_initial_narrative_map_for_batch(conn, rows)
        rows_sorted = sorted(rows, key=lambda r: _refinement_queue_sort_key(r, initial_nf))

        to_process = []
        deferred_ids: list[int] = []
        for row in rows_sorted:
            _id, dkey, sid, jtype, _prio, _meta, _ca = (
                row[0],
                row[1],
                row[2],
                row[3],
                row[4],
                row[5],
                row[6] if len(row) > 6 else None,
            )
            if jtype in _HEAVY_70B_JOB_TYPES:
                if finisher_run >= cap_fin:
                    deferred_ids.append(_id)
                    continue
                finisher_run += 1
            if len(to_process) >= cap_jobs:
                deferred_ids.append(_id)
                continue
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
        stats["pending_after"] = stats.get("pending_before", 0)
        return stats
    finally:
        try:
            conn.close()
        except Exception:
            pass

    for row in to_process:
        job_id, domain_key, storyline_id, job_type, _priority, _metadata = row[:6]
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

    try:
        tail = get_db_connection()
        if tail:
            try:
                with tail.cursor() as cur:
                    cur.execute(
                        """
                        SELECT COUNT(*) FROM intelligence.content_refinement_queue
                        WHERE status = 'pending'
                        """
                    )
                    stats["pending_after"] = int(cur.fetchone()[0] or 0)
            finally:
                tail.close()
    except Exception as e:
        logger.debug("pending_after count: %s", e)

    return stats


async def _nightly_gpu_refinement_drain_inner(
    window_active: Callable[[], bool],
) -> dict[str, Any]:
    aggregate: dict[str, Any] = {
        "batches": 0,
        "processed": 0,
        "failed": 0,
        "by_type": {},
        "stopped_reason": None,
    }
    auto_enqueue_comprehensive_rag_for_automation()
    while aggregate["batches"] < _NIGHTLY_MAX_BATCH_LOOPS:
        if not window_active():
            aggregate["stopped_reason"] = "window_ended"
            break

        batch = await process_content_refinement_queue_batch(
            max_finisher_per_cycle=_NIGHTLY_MAX_FINISHER,
            max_jobs_per_cycle=_NIGHTLY_MAX_JOBS,
            claim_batch=_NIGHTLY_CLAIM_BATCH,
        )
        aggregate["batches"] += 1
        aggregate["processed"] += int(batch.get("processed") or 0)
        aggregate["failed"] += int(batch.get("failed") or 0)
        for k, v in (batch.get("by_type") or {}).items():
            aggregate["by_type"][k] = aggregate["by_type"].get(k, 0) + int(v)

        if batch.get("error"):
            aggregate["error"] = batch["error"]
            aggregate["stopped_reason"] = "batch_error"
            break
        if int(batch.get("processed") or 0) == 0 and int(batch.get("failed") or 0) == 0:
            aggregate["stopped_reason"] = "queue_idle"
            break

    if aggregate["batches"] >= _NIGHTLY_MAX_BATCH_LOOPS and aggregate.get("stopped_reason") is None:
        aggregate["stopped_reason"] = "max_loops"

    return aggregate


async def process_nightly_gpu_refinement_drain(
    *,
    window_active: Callable[[], bool] | None = None,
    use_drain_lock: bool = True,
) -> dict[str, Any]:
    """
    Nightly caps refinement batches until idle, window ends, or max loops.
    use_drain_lock=False when nightly unified pipeline already holds _nightly_ingest_lock.
    """
    win = window_active or _default_nightly_pipeline_window_active
    aggregate: dict[str, Any] = {
        "batches": 0,
        "processed": 0,
        "failed": 0,
        "by_type": {},
        "stopped_reason": None,
    }
    if not win():
        aggregate["stopped_reason"] = "outside_window"
        return aggregate

    if use_drain_lock:
        async with _nightly_drain_lock:
            if not win():
                aggregate["stopped_reason"] = "outside_window_after_lock"
                return aggregate
            inner = await _nightly_gpu_refinement_drain_inner(win)
            aggregate.update(inner)
    else:
        inner = await _nightly_gpu_refinement_drain_inner(win)
        aggregate.update(inner)

    return aggregate
