"""
Backlog metrics — pending work counts per automation phase for orchestrator priority.
Counts are defined to match each phase’s real eligibility (what automation would select),
not coarse table totals, so Monitor ``pending_records`` reflects actionable backlog.

Used by the automation manager to: skip empty cycles, run backlog mode (shorter interval),
and queue tasks by amount of work (most first). When workload-driven scheduling is on,
phases listed here are eligible every tick (subject to cooldown) when they have work;
phases not listed still use interval-based scheduling. Adding more phases to
_get_raw_pending_counts and BATCH_SIZE_PER_TASK makes more of the pipeline workload-driven.
"""

import logging
import os
import time
from typing import Dict, Optional

from shared.article_processing_gates import (
    sql_context_sync_article_ready,
    sql_ml_ready_and_content_bounds,
)
from shared.domain_registry import get_pipeline_schema_names_active, pipeline_url_schema_pairs

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
    "entity_profile_build": 25,  # v8
    "investigation_report_refresh": 8,
    "document_processing": 10,
    "content_refinement_queue": 4,
    # Unified nightly phase: enrichment + context_sync + refinement queue
    "nightly_enrichment_context": 0,
    # Per-run throughput (automation_manager batch limits × domain count where applicable)
    "metadata_enrichment": 15,  # 5 × politics/finance/science_tech
    "ml_processing": 150,  # 50 × 3 schemas
    "entity_extraction": 60,  # 20 × 3
    "sentiment_analysis": 300,  # 100 × 3
    "quality_scoring": 150,  # 50 × 3
    "storyline_processing": 24,  # ~8 storylines worth of summary work per full pass
    "topic_clustering": 60,  # ~20 × 3 standard domains (approximates automation)
    "timeline_generation": 36,  # 12 × 3
    "storyline_discovery": 50,  # unlinked-in-newest-N proxy (see _count_storyline_discovery_pending)
    "proactive_detection": 1000,  # proactive candidate pool cap per domain
    "storyline_automation": 5,  # automation_manager LIMIT storylines per domain per tick
    "rag_enhancement": 9,  # few storylines enhanced per tick per domain
    "event_extraction": 90,  # 30 × 3
    "claims_to_facts": 10_000,  # overridden by get_claims_to_facts_batch_limit() when available
    "legislative_references": 8,  # articles scanned per domain per run (Congress.gov rate limits)
    "entity_profile_sync": 40,  # canonical rows mapped per domain batch (approx)
    "entity_enrichment": 20,  # run_enrichment_batch limit
    "entity_dossier_compile": 20,  # _run_scheduled_dossier_compiles max per run
    "story_enhancement": 50,  # fact_change_log + story_update_queue proxy per cycle
    "storyline_synthesis": 16,  # ~4 storylines × active domains per _execute_storyline_synthesis tick
    "pending_db_flush": 200,  # rough lines replayed per successful flush (order-of-magnitude)
}

# Phases where backlog = pending (orchestrator / not row-batched in this model).
NO_BACKLOG_BATCH_SUBTRACT_PHASES = frozenset({"nightly_enrichment_context"})


def _default_batch_for_unknown_phase() -> int:
    """When a phase has pending counts but no BATCH_SIZE_PER_TASK entry, subtract at least this many rows per run so row-excess backlog != pending (scheduler); Monitor shows ceil(pending/batch) as batches_to_drain."""
    try:
        v = int(os.environ.get("BACKLOG_METRICS_DEFAULT_BATCH_SIZE", "1"))
    except (TypeError, ValueError):
        v = 1
    return max(1, min(v, 50_000))


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
        try:
            from shared.database.pending_db_writes import pending_line_count

            raw["pending_db_flush"] = pending_line_count()
        except Exception:
            raw["pending_db_flush"] = 0
        raw["content_refinement_queue"] = _count_content_refinement_queue_pending()
        raw["metadata_enrichment"] = _count_metadata_enrichment_pending()
        raw["ml_processing"] = _count_ml_processing_pending()
        raw["entity_extraction"] = _count_entity_extraction_pending()
        raw["sentiment_analysis"] = _count_sentiment_analysis_pending()
        raw["quality_scoring"] = _count_quality_scoring_pending()
        raw["storyline_processing"] = _count_storyline_processing_pending()
        raw["topic_clustering"] = _count_topic_clustering_pending()
        raw["timeline_generation"] = _count_timeline_generation_pending()
        raw["storyline_discovery"] = _count_storyline_discovery_pending()
        raw["rag_enhancement"] = _count_rag_enhancement_pending()
        raw["event_extraction"] = _count_event_extraction_pending()
        raw["proactive_detection"] = _count_proactive_detection_pending()
        raw["storyline_automation"] = _count_storyline_automation_pending()
        raw["claims_to_facts"] = _count_claims_to_facts_pending()
        raw["legislative_references"] = _count_legislative_references_backlog()
        raw["entity_profile_sync"] = _count_entity_profile_sync_pending()
        raw["entity_enrichment"] = _count_entity_enrichment_pending()
        raw["nightly_enrichment_context"] = (
            int(raw.get("content_enrichment", 0) or 0)
            + int(raw.get("context_sync", 0) or 0)
            + int(raw.get("content_refinement_queue", 0) or 0)
        )
    except Exception as e:
        logger.warning("backlog_metrics _get_raw_pending_counts: %s", e)
    return raw


# Two cached dicts: raw pending (for SKIP_WHEN_EMPTY) and true backlog (for priority/interval)
_pending_cache: Dict[str, int] = {}
_pending_cache_time: float = 0


def invalidate_backlog_metrics_cache() -> None:
    """Force the next get_all_pending_counts / get_all_backlog_counts to re-query the DB."""
    global _backlog_cache_time
    _backlog_cache_time = 0.0


def _per_run_batch_size(task: str) -> int:
    """Align backlog subtraction with actual automation batch sizes (env-tunable for claim phases)."""
    if task in NO_BACKLOG_BATCH_SUBTRACT_PHASES:
        return 0
    if task == "entity_extraction":
        try:
            n = int(os.environ.get("ENTITY_EXTRACTION_ARTICLES_PER_DOMAIN", "20"))
            n = max(5, min(120, n))
            doms = len(get_pipeline_schema_names_active()) or 1
            return n * doms
        except Exception:
            pass
    if task == "claim_extraction":
        try:
            from services.claim_extraction_service import get_claim_extraction_batch_limit

            return int(get_claim_extraction_batch_limit())
        except Exception:
            pass
    if task == "claims_to_facts":
        try:
            from services.claim_extraction_service import get_claims_to_facts_batch_limit

            return int(get_claims_to_facts_batch_limit())
        except Exception:
            pass
    if task == "topic_clustering":
        try:
            doms = len(get_pipeline_schema_names_active()) or 1
            return 20 * doms
        except Exception:
            pass
    if task == "storyline_automation":
        try:
            from shared.domain_registry import get_pipeline_active_domain_keys

            doms = len(get_pipeline_active_domain_keys()) or 1
            return 5 * doms
        except Exception:
            pass
    if task in BATCH_SIZE_PER_TASK:
        return int(BATCH_SIZE_PER_TASK[task])
    return _default_batch_for_unknown_phase()


def get_per_run_batch_size_for_phase(phase_name: str) -> int:
    """Rows/items assumed processed in one automation run of ``phase_name`` (for Monitor / processing_progress)."""
    return _per_run_batch_size(phase_name)


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
        batch = _per_run_batch_size(task)
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


def _event_tracking_scan_window_params() -> tuple[int, int]:
    """Max age (days) and min content length — must match ``discover_events_from_contexts``."""
    try:
        from config.settings import event_tracking_max_age_days, event_tracking_min_content_len

        return int(event_tracking_max_age_days()), int(event_tracking_min_content_len())
    except Exception:
        d = int(os.environ.get("EVENT_TRACKING_MAX_AGE_DAYS", "14") or 14)
        n = int(os.environ.get("EVENT_TRACKING_MIN_CONTENT_LEN", "180") or 180)
        return max(1, min(d, 365)), max(1, min(n, 50_000))


def _claim_extraction_min_text_length() -> int:
    """Matches ``extract_claims_for_context`` (title+body strip length gate)."""
    try:
        n = int(os.environ.get("CLAIM_EXTRACTION_MIN_TEXT_LEN", "80"))
    except (TypeError, ValueError):
        n = 80
    return max(40, min(n, 2000))


def _count_content_enrichment_backlog() -> int:
    """Articles (across active domain schemas) pending full-text enrichment.
    Matches content_enrichment batch query: enrichment_status NULL/pending/failed, attempts < 3, has URL."""
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    try:
        for schema in get_pipeline_schema_names_active():
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
    """Articles not yet in article_to_context — matches ``sync_domain_articles_to_contexts`` (excludes removed)."""
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    ready = sql_context_sync_article_ready("a")
    try:
        for domain_key, schema in pipeline_url_schema_pairs():
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.articles a
                    LEFT JOIN intelligence.article_to_context atc
                      ON atc.domain_key = %s AND atc.article_id = a.id
                    WHERE atc.context_id IS NULL
                      AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                      AND ({ready})
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
    """Contexts the ``event_tracking`` phase can select: same window, min length, and
    ``NOT EXISTS`` chronicle link predicate as ``discover_events_from_contexts`` (not
    ``COUNT(contexts) - COUNT(event_chronicles)``, which is not meaningful work remaining)."""
    max_age_days, min_len = _event_tracking_scan_window_params()
    conn = _get_conn()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '30s'")
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.contexts c
                WHERE c.created_at >= NOW() - (%s * INTERVAL '1 day')
                  AND LENGTH(COALESCE(c.content, '')) >= %s
                  AND NOT EXISTS (
                      SELECT 1 FROM intelligence.event_chronicles ec
                      WHERE ec.developments::text LIKE '%%"context_id": ' || c.id::text || '%%'
                  )
                """,
                (max_age_days, min_len),
            )
            return int(cur.fetchone()[0] or 0)
    except Exception as e:
        logger.warning("backlog event_tracking count failed (showing 0): %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_claim_extraction_backlog() -> int:
    """Contexts with no extracted_claims and enough text for extraction (matches batch gate)."""
    conn = _get_conn()
    if not conn:
        return 0
    min_text = _claim_extraction_min_text_length()
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '8s'")
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.contexts c
                LEFT JOIN intelligence.extracted_claims ec ON ec.context_id = c.id
                WHERE ec.id IS NULL
                  AND (
                      LENGTH(COALESCE(c.content, '')) + LENGTH(COALESCE(c.title, ''))
                  ) >= %s
                """,
                (min_text,),
            )
            return int(cur.fetchone()[0] or 0)
    except Exception as e:
        logger.debug("backlog claim_extraction count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_entity_profile_build_backlog() -> int:
    """Profiles matching ``get_entity_profile_ids_to_build`` that also have at least one
    context mention (``build_profile_sections`` no-ops without mentions)."""
    conn = _get_conn()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '8s'")
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.entity_profiles ep
                WHERE (ep.sections = '[]'::jsonb OR ep.sections IS NULL
                       OR ep.updated_at < NOW() - INTERVAL '7 days')
                  AND EXISTS (
                      SELECT 1 FROM intelligence.context_entity_mentions cem
                      WHERE cem.entity_profile_id = ep.id
                  )
                """
            )
            return int(cur.fetchone()[0] or 0)
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


def _count_content_refinement_queue_pending() -> int:
    """Rows in intelligence.content_refinement_queue waiting for workers (migration 181)."""
    conn = _get_conn()
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
        logger.debug("backlog content_refinement_queue count: %s", e)
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
                  AND (extracted_sections IS NULL OR extracted_sections = '[]'::jsonb)
                  AND (metadata IS NULL OR (metadata->'processing'->>'permanent_failure') IS DISTINCT FROM 'true')
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


def _count_metadata_enrichment_pending() -> int:
    """Articles pending metadata batch (matches run_metadata_enrichment_batch_for_domains)."""
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    try:
        for schema in get_pipeline_schema_names_active():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '3s'")
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.articles
                    WHERE content IS NOT NULL AND LENGTH(content) > 50
                      AND (metadata IS NULL OR (metadata->>'enrichment_done') IS NULL)
                    """
                )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("backlog metadata_enrichment count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_ml_processing_pending() -> int:
    """Articles not yet through ML background queue (ml_processed)."""
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    ml_ready = sql_ml_ready_and_content_bounds()
    try:
        for schema in get_pipeline_schema_names_active():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '3s'")
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.articles
                    WHERE ml_processed = FALSE
                      AND ({ml_ready})
                    """
                )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("backlog ml_processing count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_entity_extraction_pending() -> int:
    """Articles eligible for entity extraction (matches automation_manager join filter)."""
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    try:
        for schema in get_pipeline_schema_names_active():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '3s'")
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.articles a
                    LEFT JOIN {schema}.article_entities ae ON ae.article_id = a.id
                    WHERE ae.id IS NULL
                      AND COALESCE((a.metadata #>> '{{pipeline_skip,entity_extraction_skip}}')::boolean, false) = false
                      AND a.content IS NOT NULL
                      AND LENGTH(a.content) > 100
                      AND (
                          LENGTH(a.content) >= 500
                          OR a.created_at < NOW() - INTERVAL '2 hours'
                          OR COALESCE(a.enrichment_status, '') IN (
                              'enriched', 'failed', 'inaccessible'
                          )
                      )
                    """
                )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("backlog entity_extraction count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_sentiment_analysis_pending() -> int:
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    ml_ready = sql_ml_ready_and_content_bounds()
    try:
        for schema in get_pipeline_schema_names_active():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '3s'")
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.articles
                    WHERE sentiment_score IS NULL
                      AND COALESCE((metadata #>> '{{pipeline_skip,sentiment_analysis_skip}}')::boolean, false) = false
                      AND ({ml_ready})
                    """
                )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("backlog sentiment_analysis count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_quality_scoring_pending() -> int:
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    ml_ready = sql_ml_ready_and_content_bounds()
    try:
        for schema in get_pipeline_schema_names_active():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '3s'")
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.articles
                    WHERE quality_score IS NULL
                      AND COALESCE((metadata #>> '{{pipeline_skip,quality_scoring_skip}}')::boolean, false) = false
                      AND ({ml_ready})
                    """
                )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("backlog quality_scoring count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_storyline_processing_pending() -> int:
    """Active storylines with articles but short/absent analysis summary (matches storyline_processing)."""
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    try:
        for schema in get_pipeline_schema_names_active():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '3s'")
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.storylines s
                    WHERE s.status = 'active'
                      AND EXISTS (
                          SELECT 1 FROM {schema}.storyline_articles sa
                          WHERE sa.storyline_id = s.id
                      )
                      AND LENGTH(
                          TRIM(COALESCE(s.analysis_summary, '') || COALESCE(s.master_summary, ''))
                      ) < 100
                    """
                )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("backlog storyline_processing count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_topic_clustering_pending() -> int:
    """Articles not fully graduated in topic assignments (matches topic_clustering priority filter)."""
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    try:
        from config.settings import topic_clustering_graduation_confidence

        conf = float(topic_clustering_graduation_confidence())
    except Exception:
        conf = 0.88
    try:
        for schema in get_pipeline_schema_names_active():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '3s'")
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM (
                        SELECT a.id
                        FROM {schema}.articles a
                        LEFT JOIN {schema}.article_topic_assignments ata
                          ON a.id = ata.article_id
                        WHERE a.content IS NOT NULL
                          AND LENGTH(a.content) > 100
                        GROUP BY a.id
                        HAVING COUNT(ata.id) = 0
                            OR COALESCE(AVG(ata.confidence_score), 0) < %s
                    ) t
                    """,
                    (conf,),
                )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("backlog topic_clustering count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_timeline_generation_pending() -> int:
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    try:
        for schema in get_pipeline_schema_names_active():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '3s'")
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.storylines s
                    WHERE s.status = 'active'
                      AND EXISTS (
                          SELECT 1 FROM {schema}.storyline_articles sa
                          WHERE sa.storyline_id = s.id
                      )
                      AND (
                          s.timeline_summary IS NULL
                          OR LENGTH(COALESCE(s.timeline_summary, '')) < 100
                      )
                    """
                )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("backlog timeline_generation count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_storyline_discovery_pending() -> int:
    """Newest-N articles per schema (same cap as discovery fetch) that are not on any storyline — linkage backlog."""
    try:
        from services.ai_storyline_discovery import STORYLINE_DISCOVERY_ARTICLE_LIMIT as cap
    except Exception:
        cap = 10000
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    try:
        for schema in get_pipeline_schema_names_active():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '5s'")
                cur.execute(
                    f"""
                    WITH cand AS (
                        SELECT id FROM {schema}.articles
                        ORDER BY created_at DESC
                        LIMIT %s
                    )
                    SELECT COUNT(*) FROM cand c
                    WHERE NOT EXISTS (
                        SELECT 1 FROM {schema}.storyline_articles sa
                        WHERE sa.article_id = c.id
                    )
                    """,
                    (cap,),
                )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("backlog storyline_discovery count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_proactive_detection_pending() -> int:
    """Recent articles (72h) with no storyline_articles row — matches proactive_detection candidate query."""
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    try:
        for schema in get_pipeline_schema_names_active():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '5s'")
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.articles a
                    LEFT JOIN {schema}.storyline_articles sa ON sa.article_id = a.id
                    WHERE COALESCE(a.published_at, a.created_at) >= NOW() - INTERVAL '72 hours'
                      AND sa.article_id IS NULL
                    """
                )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("backlog proactive_detection count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_storyline_automation_pending() -> int:
    """Storylines with ``automation_enabled`` (recurring pool the phase rotates through, not one-shot work)."""
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    try:
        for schema in get_pipeline_schema_names_active():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '3s'")
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.storylines
                    WHERE automation_enabled = true
                    """
                )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("backlog storyline_automation count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_rag_enhancement_pending() -> int:
    """Storylines due for RAG enhancement (stale or never enhanced)."""
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    try:
        for schema in get_pipeline_schema_names_active():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '3s'")
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.storylines s
                    WHERE s.status = 'active'
                      AND EXISTS (
                          SELECT 1 FROM {schema}.storyline_articles sa
                          WHERE sa.storyline_id = s.id
                      )
                      AND (
                          s.rag_enhanced_at IS NULL
                          OR s.rag_enhanced_at < NOW() - INTERVAL '1 hour'
                      )
                    """
                )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("backlog rag_enhancement count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_claims_to_facts_pending() -> int:
    """Unpromoted high-confidence claims for Monitor (see ``build_claims_to_facts_backlog_where_suffix``).

    Default ``CLAIMS_TO_FACTS_BACKLOG_COUNT_MODE=promotable_hint``: excludes generic subjects and requires
    an exact-resolution signal (context mention, profile canonical/display, or article_entities name),
    so the number tracks work closer to what can promote without fuzzy/trgm. Use ``batch_candidate``
    for the larger SQL-candidate pool (pre-resolution, still excludes generic subjects and uses merged-id
    guard when ``CLAIMS_TO_FACTS_CHECK_MERGED_SOURCE_IDS`` is on).
    """
    try:
        from services.claim_extraction_service import (
            build_claims_to_facts_backlog_where_suffix,
            get_claims_to_facts_min_confidence,
        )

        min_conf = float(get_claims_to_facts_min_confidence())
        suffix = build_claims_to_facts_backlog_where_suffix()
    except Exception:
        min_conf = 0.75
        suffix = """
  AND NOT EXISTS (
    SELECT 1 FROM intelligence.versioned_facts vf
    WHERE vf.metadata->>'source_claim_id' = ec.id::text
  )
"""
    conn = _get_conn()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '30s'")
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.extracted_claims ec
                WHERE ec.confidence >= %s
                """
                + suffix,
                (min_conf,),
            )
            return int(cur.fetchone()[0] or 0)
    except Exception as e:
        logger.debug("backlog claims_to_facts count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_entity_profile_sync_pending() -> int:
    """entity_canonical rows without intelligence.old_entity_to_new mapping (per domain)."""
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    try:
        for domain_key, schema in pipeline_url_schema_pairs():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '5s'")
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.entity_canonical ec
                    WHERE NOT EXISTS (
                        SELECT 1 FROM intelligence.old_entity_to_new o
                        WHERE o.domain_key = %s AND o.old_entity_id = ec.id
                    )
                    """,
                    (domain_key,),
                )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("backlog entity_profile_sync count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_entity_enrichment_pending() -> int:
    """1 if get_entity_profile_ids_to_enrich finds work, else 0 (cheap presence check)."""
    try:
        from services.entity_enrichment_service import get_entity_profile_ids_to_enrich

        ids = get_entity_profile_ids_to_enrich(limit=1)
        return 1 if ids else 0
    except Exception as e:
        logger.debug("backlog entity_enrichment count: %s", e)
        return 0


def _count_event_extraction_pending() -> int:
    """Articles eligible for v5 event extraction (timeline_processed)."""
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    try:
        for schema in get_pipeline_schema_names_active():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '3s'")
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.articles a
                    WHERE a.timeline_processed = false
                      AND COALESCE((a.metadata #>> '{{pipeline_skip,event_extraction_skip}}')::boolean, false) = false
                      AND a.content IS NOT NULL
                      AND LENGTH(a.content) > 100
                      AND (
                          a.processing_status = 'completed'
                          OR a.enrichment_status IN ('completed', 'enriched')
                      )
                    """
                )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("backlog event_extraction count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_entity_dossier_compile_pending() -> int:
    """entity_profiles missing dossier or dossier older than stale window (matches dossier_compiler schedule)."""
    conn = _get_conn()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '8s'")
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.entity_profiles ep
                LEFT JOIN intelligence.entity_dossiers ed
                  ON ed.domain_key = ep.domain_key AND ed.entity_id = ep.canonical_entity_id
                WHERE ep.canonical_entity_id IS NOT NULL
                  AND (ed.id IS NULL OR ed.compilation_date < CURRENT_DATE - INTERVAL '7 days')
                """
            )
            return int(cur.fetchone()[0] or 0)
    except Exception as e:
        logger.debug("backlog entity_dossier_compile count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_story_enhancement_pending() -> int:
    """Unprocessed story-state queues driving run_enhancement_cycle."""
    conn = _get_conn()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '5s'")
            cur.execute(
                """
                SELECT
                  COALESCE((SELECT COUNT(*) FROM intelligence.fact_change_log WHERE processed = FALSE), 0)
                + COALESCE((SELECT COUNT(*) FROM intelligence.story_update_queue WHERE processed = FALSE), 0)
                AS n
                """
            )
            return int(cur.fetchone()[0] or 0)
    except Exception as e:
        logger.debug("backlog story_enhancement count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_storyline_synthesis_pending() -> int:
    """Storylines with 3+ articles needing synthesized_content (aligns with storyline_synthesis task)."""
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    try:
        for schema in get_pipeline_schema_names_active():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '5s'")
                try:
                    cur.execute(
                        f"""
                        SELECT COUNT(*) FROM {schema}.storylines s
                        INNER JOIN (
                            SELECT storyline_id FROM {schema}.storyline_articles
                            GROUP BY storyline_id HAVING COUNT(*) >= 3
                        ) sa ON sa.storyline_id = s.id
                        WHERE s.synthesized_content IS NULL
                        """
                    )
                    total += int(cur.fetchone()[0] or 0)
                except Exception:
                    try:
                        cur.execute(
                            f"""
                            SELECT COUNT(*) FROM {schema}.storylines s
                            INNER JOIN (
                                SELECT storyline_id FROM {schema}.storyline_articles
                                GROUP BY storyline_id HAVING COUNT(*) >= 3
                            ) sa ON sa.storyline_id = s.id
                            """
                        )
                        total += int(cur.fetchone()[0] or 0)
                    except Exception as e2:
                        logger.debug(
                            "backlog storyline_synthesis count schema=%s: %s", schema, e2
                        )
        return total
    except Exception as e:
        logger.debug("backlog storyline_synthesis count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_legislative_references_backlog() -> int:
    """Politics/legal articles without a legislative_article_scans row (bill-citation pass)."""
    try:
        from shared.database.connection import get_db_connection_context
        from shared.domain_registry import is_valid_domain_key, resolve_domain_schema
        from services.legislative_reference_service import (
            LEGISLATIVE_SCAN_DOMAIN_KEYS,
            SCAN_ARTICLE_DAYS,
        )
    except Exception as e:
        logger.debug("legislative_references backlog import: %s", e)
        return 0
    total = 0
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                for dk in LEGISLATIVE_SCAN_DOMAIN_KEYS:
                    if not is_valid_domain_key(dk):
                        continue
                    schema = resolve_domain_schema(dk)
                    cur.execute(
                        f"""
                        SELECT COUNT(*) FROM {schema}.articles a
                        WHERE (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                          AND a.created_at > NOW() - INTERVAL '{int(SCAN_ARTICLE_DAYS)} days'
                          AND NOT EXISTS (
                              SELECT 1 FROM intelligence.legislative_article_scans s
                              WHERE s.domain_key = %s AND s.article_id = a.id
                          )
                        """,
                        (dk,),
                    )
                    total += int(cur.fetchone()[0] or 0)
    except Exception as e:
        logger.debug("legislative_references backlog query: %s", e)
        return 0
    return total


# Phases that should be skipped when backlog is 0 (avoid empty cycles)
# document_processing omitted so it runs on interval even if backlog count is wrong (e.g. DB timeout)
# content_refinement_queue omitted: must run on interval when idle so automation history updates;
# empty queue completes in milliseconds.
SKIP_WHEN_EMPTY = frozenset({
    "content_enrichment",
    "context_sync",
    "event_tracking",
    "claim_extraction",
    "entity_profile_build",
    "investigation_report_refresh",
    "pending_db_flush",
    "nightly_enrichment_context",
    "metadata_enrichment",
    "ml_processing",
    "entity_extraction",
    "sentiment_analysis",
    "quality_scoring",
    "storyline_processing",
    "topic_clustering",
    "timeline_generation",
    "storyline_discovery",
    "proactive_detection",
    "storyline_automation",
    "rag_enhancement",
    "event_extraction",
    "claims_to_facts",
    "legislative_references",
    "entity_profile_sync",
    "entity_enrichment",
    "entity_dossier_compile",
    "story_enhancement",
    "storyline_synthesis",
})

# When backlog exceeds this, use backlog-mode interval so we run more often
BACKLOG_HIGH_THRESHOLD = 200
# Effective min interval (seconds) when in backlog mode (high backlog)
BACKLOG_MODE_INTERVAL = 300
# When any backlog > 0, use this so we don't wait full interval between runs (run as soon as eligible)
BACKLOG_ANY_INTERVAL = 30
