"""
Spine work queue service (v10.1) — claim/enqueue/count for enrichment, unified intake, spine tail.

Uses FOR UPDATE SKIP LOCKED pattern from content_refinement_queue_service.
"""

from __future__ import annotations

import logging
from typing import Any

from api.config.runtime import env_bool

logger = logging.getLogger(__name__)


def spine_work_queues_enabled() -> bool:
    return env_bool("SPINE_USE_WORK_QUEUES", True)


def _queue_table_for_phase(phase: str) -> str | None:
    if phase == "content_enrichment":
        return "content_enrichment_queue"
    if phase == "unified_intake_extraction":
        return "unified_intake_queue"
    return None


def enqueue_article(schema_name: str, article_id: int, phase: str, *, priority: int = 2) -> bool:
    table = _queue_table_for_phase(phase)
    if not table or not spine_work_queues_enabled():
        return False
    try:
        api.shared.database import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {schema_name}.{table} (article_id, status, priority)
                    VALUES (%s, 'pending', %s)
                    ON CONFLICT (article_id) DO NOTHING
                    """,
                    (article_id, priority),
                )
            conn.commit()
        return True
    except Exception as exc:
        logger.debug("enqueue_article %s %s %s: %s", schema_name, article_id, phase, exc)
        return False


def claim_queue_batch(schema_name: str, phase: str, limit: int) -> list[int]:
    table = _queue_table_for_phase(phase)
    if not table or not spine_work_queues_enabled():
        return []
    try:
        api.shared.database import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    WITH cte AS (
                        SELECT id, article_id
                        FROM {schema_name}.{table}
                        WHERE status = 'pending'
                          AND (next_retry_at IS NULL OR next_retry_at <= NOW())
                        ORDER BY priority DESC, created_at ASC
                        LIMIT %s
                        FOR UPDATE SKIP LOCKED
                    )
                    UPDATE {schema_name}.{table} q
                    SET status = 'processing', started_at = NOW()
                    FROM cte
                    WHERE q.id = cte.id
                    RETURNING q.article_id
                    """,
                    (limit,),
                )
                ids = [int(r[0]) for r in cur.fetchall()]
            conn.commit()
        return ids
    except Exception as exc:
        logger.debug("claim_queue_batch %s %s: %s", schema_name, phase, exc)
        return []


def complete_queue_item(schema_name: str, phase: str, article_id: int, *, failed: bool = False) -> None:
    table = _queue_table_for_phase(phase)
    if not table:
        return
    status = "failed" if failed else "completed"
    try:
        api.shared.database import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE {schema_name}.{table}
                    SET status = %s, completed_at = NOW()
                    WHERE article_id = %s AND status = 'processing'
                    """,
                    (status, article_id),
                )
            conn.commit()
    except Exception as exc:
        logger.debug("complete_queue_item: %s", exc)


def count_pending_queue(schema_name: str, phase: str) -> int:
    table = _queue_table_for_phase(phase)
    if not table or not spine_work_queues_enabled():
        return 0
    try:
        api.shared.database import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema_name}.{table}
                    WHERE status = 'pending'
                    """
                )
                return int(cur.fetchone()[0] or 0)
    except Exception:
        return 0


def release_queue_item(schema_name: str, phase: str, article_id: int, *, error: str | None = None) -> None:
    """Return a claimed item to pending for retry."""
    table = _queue_table_for_phase(phase)
    if not table:
        return
    try:
        api.shared.database import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE {schema_name}.{table}
                    SET status = 'pending',
                        started_at = NULL,
                        retry_count = retry_count + 1,
                        last_attempt_at = NOW(),
                        next_retry_at = NOW() + INTERVAL '5 minutes',
                        error_message = %s
                    WHERE article_id = %s AND status = 'processing'
                    """,
                    (error, article_id),
                )
            conn.commit()
    except Exception as exc:
        logger.debug("release_queue_item: %s", exc)


def claim_fair_share_batch(phase: str, batch_size: int) -> dict[str, list[int]]:
    """Claim pending queue rows across active domains (fair share)."""
    api.shared.domain_registry import pipeline_url_schema_pairs

    pairs = list(pipeline_url_schema_pairs())
    if not pairs or batch_size <= 0:
        return {}
    share = max(1, (batch_size + len(pairs) - 1) // len(pairs))
    claimed: dict[str, list[int]] = {}
    remaining = batch_size
    for _domain_key, schema_name in pairs:
        if remaining <= 0:
            break
        limit = min(share, remaining)
        ids = claim_queue_batch(schema_name, phase, limit)
        if ids:
            claimed[schema_name] = ids
            remaining -= len(ids)
    return claimed


def reclaim_stale_content_enrichment_processing(
    *,
    older_than_minutes: float | None = None,
) -> int:
    """
    Return long-stuck ``processing`` enrichment queue rows to ``pending``.

    Prevents crash/restart leftovers from blocking claim loops. Called at the
    start of each content_enrichment drain round.
    """
    try:
        from api.config.runtime import env_float

        minutes = float(
            older_than_minutes
            if older_than_minutes is not None
            else env_float("CONTENT_ENRICHMENT_STALE_PROCESSING_MINUTES", 60.0)
        )
    except Exception:
        minutes = 60.0
    minutes = max(5.0, min(24 * 60.0, minutes))
    if not spine_work_queues_enabled():
        return 0

    total = 0
    try:
        api.shared.domain_registry import get_schema_names_active
        api.shared.database import get_db_connection_context

        schemas = list(get_schema_names_active())
    except Exception as exc:
        logger.debug("reclaim_stale_content_enrichment_processing: schemas: %s", exc)
        return 0

    for schema_name in schemas:
        table = _queue_table_for_phase("content_enrichment")
        if not table:
            continue
        try:
            with get_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        UPDATE {schema_name}.{table}
                        SET status = 'pending',
                            started_at = NULL,
                            retry_count = retry_count + 1,
                            last_attempt_at = NOW(),
                            next_retry_at = NOW() + INTERVAL '2 minutes',
                            error_message = COALESCE(error_message, '')
                                || ' [reclaimed_stale_processing>'
                                || %s::text || 'm]'
                        WHERE status = 'processing'
                          AND started_at IS NOT NULL
                          AND started_at < NOW() - (%s || ' minutes')::interval
                        """,
                        (str(int(minutes)), str(minutes)),
                    )
                    n = int(cur.rowcount or 0)
                conn.commit()
            total += n
        except Exception as exc:
            logger.debug(
                "reclaim_stale_content_enrichment_processing %s: %s",
                schema_name,
                exc,
            )
    if total:
        logger.warning(
            "content_enrichment reclaim: reset %s stale processing rows (>%sm)",
            total,
            int(minutes),
        )
    return total


def finalize_content_enrichment_queue_round(
    schema_name: str,
    article_ids: list[int],
) -> None:
    """Complete or release enrichment queue rows atomically; enqueue unified intake on success.

    Uses a single DB connection with partial-failure isolation so individual UPDATE/INSERT
    failures don't silently leave articles orphaned in the enrichment queue (stuck "processing" state).
    """
    if not article_ids:
        return
    try:
        api.shared.database import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, enrichment_status, COALESCE(enrichment_attempts, 0)
                    FROM {schema_name}.articles
                    WHERE id = ANY(%s)
                    """,
                    (article_ids,),
                )
                rows = {int(r[0]): (r[1], int(r[2] or 0)) for r in cur.fetchall()}
        enriched_ids: list[int] = []
        completed_failed_ids: list[int] = []
        released_ids: list[int] = []
        missing_ids: list[int] = []

        for article_id in article_ids:
            status, attempts = rows.get(article_id, (None, 0))
            norm = (status or "").strip().lower()
            if norm == "enriched":
                enriched_ids.append(article_id)
            elif norm in ("inaccessible", "failed") and attempts >= 3:
                completed_failed_ids.append(article_id)
            elif article_id not in rows:
                completed_failed_ids.append(article_id)
                missing_ids.append(article_id)
            else:
                released_ids.append(article_id)

        failures: dict[str, list[int]] = {}

        try:
            with get_db_connection_context() as conn:
                with conn.cursor() as cur:
                    if released_ids:
                        try:
                            cur.execute(
                                f"""
                                SELECT id FROM {schema_name}.content_enrichment_queue
                                WHERE article_id = ANY(%s) AND status = 'processing'
                                """,
                                (released_ids,),
                            )
                            live_released = [int(r[0]) for r in cur.fetchall()]
                            if live_released:
                                cur.execute(
                                    f"""
                                    UPDATE {schema_name}.content_enrichment_queue
                                    SET status = 'pending',
                                        started_at = NULL,
                                        retry_count = retry_count + 1,
                                        last_attempt_at = NOW(),
                                        next_retry_at = NOW() + INTERVAL '5 minutes'
                                    WHERE id = ANY(%s)
                                    """,
                                    (live_released,),
                                )
                            else:
                                logger.debug(
                                    "finalize_content_enrichment_queue_round: no processing rows to release for %d article(s)",
                                    len(released_ids),
                                )
                        except Exception as exc:
                            failures["released"] = released_ids
                            logger.warning(
                                "finalize_content_enrichment_queue_round: failed to release %d enrichment queue item(s) for schema %s",
                                len(released_ids),
                                schema_name,
                            )

                    if completed_failed_ids:
                        try:
                            cur.execute(
                                f"""
                                SELECT id FROM {schema_name}.content_enrichment_queue
                                WHERE article_id = ANY(%s) AND status = 'processing'
                                """,
                                (completed_failed_ids,),
                            )
                            live_completed = [int(r[0]) for r in cur.fetchall()]
                            if live_completed:
                                failed_status = "failed" if missing_ids else "completed"
                                cur.execute(
                                    f"""
                                    UPDATE {schema_name}.content_enrichment_queue
                                    SET status = %s, completed_at = NOW()
                                    WHERE id = ANY(%s)
                                    """,
                                    (failed_status, live_completed),
                                )
                            else:
                                logger.debug(
                                    "finalize_content_enrichment_queue_round: no processing rows to complete for %d article(s)",
                                    len(completed_failed_ids),
                                )
                        except Exception as exc:
                            failures["completed"] = completed_failed_ids
                            logger.warning(
                                "finalize_content_enrichment_queue_round: failed to complete %d enrichment queue item(s) for schema %s",
                                len(completed_failed_ids),
                                schema_name,
                            )

        finally:
            if enriched_ids:
                try:
                    api.shared.database import get_db_connection_context as gdc

                    with gdc() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                f"""
                                INSERT INTO {schema_name}.unified_intake_queue (article_id, status, priority)
                                SELECT unnest(%s), 'pending', 2
                                ON CONFLICT (article_id) DO UPDATE
                                SET status = CASE WHEN unified_intake_queue.status = 'pending'
                                    THEN 'pending' ELSE unified_intake_queue.status END
                                """,
                                (enriched_ids,),
                            )
                except Exception as exc:
                    logger.warning(
                        "finalize_content_enrichment_queue_round: failed to enqueue %d enriched article(s) to unified_intake queue for schema %s",
                        len(enriched_ids),
                        schema_name,
                    )

        if failures:
            total_fails = sum(len(v) for v in failures.values())
            logger.warning(
                "finalize_content_enrichment_queue_round: %d failure(s) across groups (%s)",
                total_fails,
                ", ".join(f"{k}: {len(v)}" for k, v in failures.items()),
            )

    except Exception as exc:
        logger.warning("finalize_content_enrichment_queue_round %s: %s", schema_name, exc)


def finalize_unified_intake_queue_round(
    schema_name: str,
    outcomes: dict[int, bool],
) -> None:
    """Complete or release unified intake queue rows atomically from batch extraction outcomes."""
    if not outcomes:
        return
    try:
        api.shared.database import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                completed_ids = [aid for aid, ok in outcomes.items() if ok]
                released_ids = [aid for aid, ok in outcomes.items() if not ok]
                failures: dict[str, list[int]] = {}

                if completed_ids:
                    try:
                        cur.execute(
                            f"""
                            UPDATE {schema_name}.unified_intake_queue
                            SET status = 'completed', completed_at = NOW()
                            WHERE article_id = ANY(%s) AND status = 'processing'
                            """,
                            (completed_ids,),
                        )
                    except Exception as exc:
                        failures["completed"] = list(completed_ids)
                        logger.warning(
                            "finalize_unified_intake_queue_round: failed to complete %d unified intake item(s) for schema %s",
                            len(completed_ids),
                            schema_name,
                        )

                if released_ids:
                    try:
                        cur.execute(
                            f"""
                            UPDATE {schema_name}.unified_intake_queue
                            SET status = 'pending',
                                started_at = NULL,
                                retry_count = retry_count + 1,
                                last_attempt_at = NOW(),
                                next_retry_at = NOW() + INTERVAL '5 minutes',
                                error_message = %s
                            WHERE article_id = ANY(%s) AND status = 'processing'
                            """,
                            ("extraction_failed", released_ids),
                        )
                    except Exception as exc:
                        failures["released"] = released_ids
                        logger.warning(
                            "finalize_unified_intake_queue_round: failed to release %d unified intake item(s) for schema %s",
                            len(released_ids),
                            schema_name,
                        )

                if failures:
                    total_fails = sum(len(v) for v in failures.values())
                    logger.warning(
                        "finalize_unified_intake_queue_round: %d failure(s) across groups (%s)",
                        total_fails,
                        ", ".join(f"{k}: {len(v)}" for k, v in failures.items()),
                    )

    except Exception as exc:
        logger.warning("finalize_unified_intake_queue_round %s: %s", schema_name, exc)


def count_all_pending(phase: str) -> int:
    api.shared.domain_registry import get_schema_names_active

    return sum(count_pending_queue(s, phase) for s in get_schema_names_active())
