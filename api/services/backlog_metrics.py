"""
Backlog metrics — pending work counts per automation phase for orchestrator priority.
Used by the automation manager to: skip empty cycles, run backlog mode (shorter interval),
and queue tasks by amount of work (most first).

Backlog semantics: a task has a "backlog" only when the pending work exceeds what a
single batch can handle.  One or two items waiting is normal operation, not a backlog.
BATCH_SIZE_PER_TASK defines the batch size per task; the raw count is reduced by this
amount so that values <= 0 mean "no backlog" and values > 0 mean "real backlog."
"""

import logging
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Cache TTL seconds; scheduler runs every 5s, we refresh counts every 30s
BACKLOG_CACHE_TTL = 30
_backlog_cache: Dict[str, int] = {}
_backlog_cache_time: float = 0

# How many items each task processes per run.  Pending counts at or below this
# are normal throughput, not a backlog.  Anything above triggers backlog mode.
BATCH_SIZE_PER_TASK: Dict[str, int] = {
    "content_enrichment": 60,
    "context_sync": 100,
    "event_tracking": 300,
    "claim_extraction": 50,
    "entity_profile_build": 15,
    "investigation_report_refresh": 8,
    "document_processing": 10,
}


def _get_raw_pending_counts() -> Dict[str, int]:
    """Query all raw pending-work counts (not cached — called by the cached wrapper)."""
    raw: Dict[str, int] = {}
    try:
        raw["content_enrichment"] = _count_content_enrichment_backlog()
        raw["context_sync"] = _count_context_sync_backlog()
        raw["event_tracking"] = _count_event_tracking_backlog()
        raw["claim_extraction"] = _count_claim_extraction_backlog()
        raw["entity_profile_build"] = _count_entity_profile_build_backlog()
        raw["investigation_report_refresh"] = _count_investigation_report_backlog()
        raw["document_processing"] = _count_document_processing_backlog()
    except Exception as e:
        logger.warning("backlog_metrics _get_raw_pending_counts: %s", e)
    return raw


# Two cached dicts: raw pending (for SKIP_WHEN_EMPTY) and true backlog (for priority/interval)
_pending_cache: Dict[str, int] = {}
_pending_cache_time: float = 0


def _refresh_cache() -> None:
    """Refresh both pending and backlog caches."""
    global _backlog_cache, _backlog_cache_time, _pending_cache, _pending_cache_time
    now = time.monotonic()
    if now - _backlog_cache_time <= BACKLOG_CACHE_TTL and _backlog_cache:
        return

    raw = _get_raw_pending_counts()
    _pending_cache = raw.copy()
    _pending_cache_time = now

    out: Dict[str, int] = {}
    for task, pending in raw.items():
        batch = BATCH_SIZE_PER_TASK.get(task, 0)
        out[task] = max(pending - batch, 0)
    _backlog_cache = out
    _backlog_cache_time = now


def get_all_backlog_counts() -> Dict[str, int]:
    """
    Return current **backlog** count per phase — pending work *exceeding* one batch.
    Cached for BACKLOG_CACHE_TTL.  Values > 0 mean genuine backlog (more work than
    one run can handle); 0 means the task is keeping up or idle.
    Used for priority boosting and interval shortening.
    """
    _refresh_cache()
    return _backlog_cache.copy()


def get_all_pending_counts() -> Dict[str, int]:
    """
    Return raw pending-work counts per phase (items waiting, regardless of batch size).
    Used by SKIP_WHEN_EMPTY — a task with *any* pending work (even 1 item) should still run.
    """
    _refresh_cache()
    return _pending_cache.copy()


def get_backlog_count(task_name: str) -> Optional[int]:
    """Return backlog for one task; uses cache. Returns None if task has no backlog metric."""
    counts = get_all_backlog_counts()
    if task_name in counts:
        return counts[task_name]
    return None


def _get_conn():
    try:
        from shared.database.connection import get_db_connection
        return get_db_connection()
    except Exception:
        return None


def _count_content_enrichment_backlog() -> int:
    """Articles (across politics, finance, science_tech) pending full-text enrichment.
    Matches content_enrichment batch query: enrichment_status NULL/pending/failed, attempts < 3, has URL."""
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    try:
        for schema in ("politics", "finance", "science_tech"):
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.articles
                    WHERE (enrichment_status IS NULL OR enrichment_status IN ('pending', 'failed'))
                      AND COALESCE(enrichment_attempts, 0) < 3
                      AND url IS NOT NULL AND url != ''
                    """
                )
                total += cur.fetchone()[0] or 0
        return total
    except Exception as e:
        logger.debug("backlog content_enrichment count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_context_sync_backlog() -> int:
    """Articles (across politics, finance, science_tech) not yet in article_to_context."""
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    try:
        # domain_key in article_to_context: politics, finance, science-tech
        for schema, domain_key in [("politics", "politics"), ("finance", "finance"), ("science_tech", "science-tech")]:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.articles a
                    LEFT JOIN intelligence.article_to_context atc
                      ON atc.domain_key = %s AND atc.article_id = a.id
                    WHERE atc.context_id IS NULL
                    """,
                    (domain_key,),
                )
                total += cur.fetchone()[0] or 0
        return total
    except Exception as e:
        logger.debug("backlog context_sync count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_event_tracking_backlog() -> int:
    """Contexts not yet linked to any event chronicle.
    Uses a fast approximate count: total contexts minus contexts referenced
    in event_chronicles via JSONB containment (indexed).  Falls back to 0
    on any error so this never blocks the event loop for long."""
    conn = _get_conn()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '3s'")
            cur.execute("SELECT COUNT(*) FROM intelligence.contexts")
            total = cur.fetchone()[0] or 0
            cur.execute("SELECT COUNT(*) FROM intelligence.event_chronicles")
            chronicles = cur.fetchone()[0] or 0
            if chronicles == 0:
                return total
            return max(total - chronicles, 0)
    except Exception as e:
        logger.debug("backlog event_tracking count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_claim_extraction_backlog() -> int:
    """Contexts with no extracted_claims."""
    conn = _get_conn()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '3s'")
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.contexts c
                LEFT JOIN intelligence.extracted_claims ec ON ec.context_id = c.id
                WHERE ec.id IS NULL
                """
            )
            return cur.fetchone()[0] or 0
    except Exception as e:
        logger.debug("backlog claim_extraction count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_entity_profile_build_backlog() -> int:
    """Entity profiles that need sections built or refreshed."""
    conn = _get_conn()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '3s'")
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.entity_profiles ep
                WHERE ep.sections = '[]'::jsonb OR ep.sections IS NULL
                   OR ep.updated_at < NOW() - INTERVAL '7 days'
                """
            )
            return cur.fetchone()[0] or 0
    except Exception as e:
        logger.debug("backlog entity_profile_build count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_investigation_report_backlog() -> int:
    """Tracked events without an event_report (new reports needed)."""
    conn = _get_conn()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '3s'")
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.tracked_events te
                WHERE NOT EXISTS (
                    SELECT 1 FROM intelligence.event_reports er WHERE er.event_id = te.id
                )
                """
            )
            return cur.fetchone()[0] or 0
    except Exception as e:
        logger.debug("backlog investigation_report count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_document_processing_backlog() -> int:
    """Documents with source_url but not yet extracted (PDF download + section/entity extraction)."""
    conn = _get_conn()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '3s'")
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.processed_documents
                WHERE source_url IS NOT NULL AND source_url != ''
                  AND (extracted_sections IS NULL OR extracted_sections = '[]')
                """
            )
            return cur.fetchone()[0] or 0
    except Exception as e:
        logger.debug("backlog document_processing count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


# Phases that should be skipped when backlog is 0 (avoid empty cycles)
SKIP_WHEN_EMPTY = frozenset({
    "context_sync",
    "event_tracking",
    "claim_extraction",
    "entity_profile_build",
    "investigation_report_refresh",
    "document_processing",  # v7: skip when no unprocessed PDFs
})

# When backlog exceeds this, use backlog-mode interval so we run more often
BACKLOG_HIGH_THRESHOLD = 200
# Effective min interval (seconds) when in backlog mode (high backlog)
BACKLOG_MODE_INTERVAL = 300
# When any backlog > 0, use this so we don't wait full interval between runs (run as soon as eligible)
BACKLOG_ANY_INTERVAL = 30
