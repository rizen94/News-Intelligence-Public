"""
Spine work queue service (v10.1) — claim/enqueue/count for enrichment, unified intake, spine tail.

Uses FOR UPDATE SKIP LOCKED pattern from content_refinement_queue_service.
"""

from __future__ import annotations

import logging
from typing import Any

from config.runtime import env_bool

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
        from shared.database.connection import get_db_connection_context

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
        from shared.database.connection import get_db_connection_context

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
        from shared.database.connection import get_db_connection_context

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
        from shared.database.connection import get_db_connection_context

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
        from shared.database.connection import get_db_connection_context

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
    from shared.domain_registry import pipeline_url_schema_pairs

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


def finalize_content_enrichment_queue_round(
    schema_name: str,
    article_ids: list[int],
) -> None:
    """Complete or release enrichment queue rows; enqueue unified intake on success."""
    if not article_ids:
        return
    try:
        from shared.database.connection import get_db_connection_context

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
        for article_id in article_ids:
            status, attempts = rows.get(article_id, (None, 0))
            norm = (status or "").strip().lower()
            if norm == "enriched":
                complete_queue_item(schema_name, "content_enrichment", article_id, failed=False)
                enqueue_article(schema_name, article_id, "unified_intake_extraction")
            elif norm in ("inaccessible", "failed") and attempts >= 3:
                complete_queue_item(schema_name, "content_enrichment", article_id, failed=True)
            elif article_id not in rows:
                complete_queue_item(schema_name, "content_enrichment", article_id, failed=True)
            else:
                release_queue_item(schema_name, "content_enrichment", article_id)
    except Exception as exc:
        logger.debug("finalize_content_enrichment_queue_round %s: %s", schema_name, exc)


def finalize_unified_intake_queue_round(
    schema_name: str,
    outcomes: dict[int, bool],
) -> None:
    """Complete or release unified intake queue rows from batch extraction outcomes."""
    for article_id, ok in outcomes.items():
        if ok:
            complete_queue_item(schema_name, "unified_intake_extraction", article_id, failed=False)
        else:
            release_queue_item(schema_name, "unified_intake_extraction", article_id, error="extraction_failed")


def count_all_pending(phase: str) -> int:
    from shared.domain_registry import get_schema_names_active

    return sum(count_pending_queue(s, phase) for s in get_schema_names_active())
