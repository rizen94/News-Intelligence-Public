"""
Backlog metrics — pending work counts per automation phase for orchestrator priority.
Used by the automation manager to: skip empty cycles, run backlog mode (shorter interval),
and queue tasks by amount of work (most first).
"""

import logging
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Cache TTL seconds; scheduler runs every 5s, we refresh counts every 30s
BACKLOG_CACHE_TTL = 30
_backlog_cache: Dict[str, int] = {}
_backlog_cache_time: float = 0


def get_all_backlog_counts() -> Dict[str, int]:
    """
    Return current backlog (pending work) count per phase. Cached for BACKLOG_CACHE_TTL.
    Phase names match automation_manager schedule keys. Missing/error => 0.
    """
    global _backlog_cache, _backlog_cache_time
    now = time.monotonic()
    if now - _backlog_cache_time <= BACKLOG_CACHE_TTL and _backlog_cache:
        return _backlog_cache.copy()

    out: Dict[str, int] = {}
    try:
        out["context_sync"] = _count_context_sync_backlog()
        out["event_tracking"] = _count_event_tracking_backlog()
        out["claim_extraction"] = _count_claim_extraction_backlog()
        out["entity_profile_build"] = _count_entity_profile_build_backlog()
        out["investigation_report_refresh"] = _count_investigation_report_backlog()
    except Exception as e:
        logger.warning("backlog_metrics get_all_backlog_counts: %s", e)
    _backlog_cache = out
    _backlog_cache_time = now
    return out.copy()


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
    """Contexts not yet linked to any event chronicle."""
    conn = _get_conn()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.contexts c
                WHERE NOT EXISTS (
                    SELECT 1 FROM intelligence.event_chronicles ec
                    WHERE ec.developments::text LIKE '%%"context_id": ' || c.id || '%%'
                )
                """
            )
            return cur.fetchone()[0] or 0
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


# Phases that should be skipped when backlog is 0 (avoid empty cycles)
SKIP_WHEN_EMPTY = frozenset({
    "context_sync",
    "event_tracking",
    "claim_extraction",
    "entity_profile_build",
    "investigation_report_refresh",
})

# When backlog exceeds this, use backlog-mode interval so we run more often
BACKLOG_HIGH_THRESHOLD = 200
# Effective min interval (seconds) when in backlog mode
BACKLOG_MODE_INTERVAL = 300
