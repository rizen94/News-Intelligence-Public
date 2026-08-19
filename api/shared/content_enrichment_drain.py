"""
Queue-first content enrichment drain (U5).

Claim content_enrichment_queue → scoped enrich → finalize (complete + enqueue UIE).
Falls back to article eligibility SQL when the queue is empty but backlog remains.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def run_content_enrichment_batch(*, batch_size: int = 60) -> int:
    """
    One enrichment round. Prefer spine work-queue claim; SQL scan only as fallback.

    Returns number of articles processed by enrich_articles_batch.
    """
    from services.article_content_enrichment_service import enrich_articles_batch
    from services.spine_work_queue_service import (
        claim_fair_share_batch,
        count_all_pending,
        finalize_content_enrichment_queue_round,
        reclaim_stale_content_enrichment_processing,
        spine_work_queues_enabled,
    )

    try:
        reclaim_stale_content_enrichment_processing()
    except Exception as e:
        logger.debug("content_enrichment reclaim skipped: %s", e)

    bs = max(1, int(batch_size))
    claimed: dict[str, list[int]] = {}
    use_queue = False

    if spine_work_queues_enabled():
        try:
            claimed = claim_fair_share_batch("content_enrichment", bs) or {}
            use_queue = bool(claimed)
            if not use_queue:
                pending_q = int(count_all_pending("content_enrichment") or 0)
                if pending_q > 0:
                    logger.info(
                        "content_enrichment: empty claim with queue pending=%s — SQL fallback",
                        pending_q,
                    )
        except Exception as e:
            logger.warning("content_enrichment claim failed: %s", e)
            claimed = {}
            use_queue = False

    n = int(
        enrich_articles_batch(
            batch_size=bs,
            scoped_ids_by_schema=claimed if use_queue else None,
        )
        or 0
    )

    if use_queue and claimed:
        for schema_name, article_ids in claimed.items():
            try:
                finalize_content_enrichment_queue_round(schema_name, article_ids)
            except Exception as e:
                logger.warning(
                    "content_enrichment finalize %s: %s", schema_name, e
                )

    return n


async def run_content_enrichment_batch_async(*, batch_size: int = 60) -> int:
    """Async wrapper for AutomationManager / nightly loops."""
    import asyncio

    loop = asyncio.get_event_loop()
    return int(
        await loop.run_in_executor(
            None, lambda: run_content_enrichment_batch(batch_size=batch_size)
        )
        or 0
    )


def content_enrichment_drain_summary(*, batch_size: int = 60) -> dict[str, Any]:
    """Sync drain once; dict shape for phase_drain_dispatch."""
    processed = run_content_enrichment_batch(batch_size=batch_size)
    return {"processed": processed}
