"""
Resource & Health Dashboard — database stats, device disk/processes, aggregated health feeds.
Serves the monitoring tab across all domains.
Remote devices: use agent_url for HTTP metrics endpoint, or host + SSH (df + ps) when agent_url is not set.
See docs/MONITORING_SSH_SETUP.md for SSH. HTTP agent contract: GET {agent_url} returns JSON with
disk, project_usage_bytes, processes (same shape as SSH response).
"""

import asyncio
import logging
import os
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import psutil
import requests
import yaml
from fastapi import APIRouter, HTTPException
from shared.database.connection import get_ui_db_connection as get_db_connection
from shared.services.response_cache import cached_response

logger = logging.getLogger(__name__)

# Minimum processed count in the last 4 days to prefer 4d average throughput over 1h/24h spikes.
BACKLOG_AVG_4D_MIN_SAMPLES = 12
BACKLOG_AVG_4D_MIN_DOCUMENTS = 8
BACKLOG_WORKLOAD_WINDOW_DAYS = 4


def _rollback_db_connection(conn) -> None:
    """Clear aborted transaction so the next query on this connection can run (psycopg2)."""
    try:
        conn.rollback()
    except Exception:
        pass


def _blend_throughput_per_hour(
    *,
    per_4d: float,
    per_1h: float,
    per_mid: float,
    cap: float,
    fallback: float,
    mid_is_24h: bool,
) -> tuple[float, str]:
    """
    ETA throughput: use max(4d avg, 1h, mid window) capped.

    A sluggish 4-day average must not hide a healthy last-hour rate (otherwise
    entity profile ETAs show multi-year drains while 1h work is ~30+/hr).
    """
    raw = max(per_4d, per_1h, per_mid)
    if raw <= 0:
        return fallback, "estimated"
    rate = min(raw, cap)
    if per_1h > 0 and abs(raw - per_1h) < 1e-6:
        return rate, "measured_1h"
    if per_mid > 0 and abs(raw - per_mid) < 1e-6:
        return rate, "measured_24h" if mid_is_24h else "measured_2h"
    if per_4d > 0:
        return rate, "avg_4d"
    return rate, "measured_24h" if mid_is_24h else "measured_2h"


# Default SSH user for remote monitoring (env MONITORING_SSH_USER or per-device ssh_user in config)
DEFAULT_SSH_TIMEOUT_SECONDS = 12

router = APIRouter(
    prefix="/api/system_monitoring",
    tags=["System Monitoring - Resource Dashboard"],
)

# Path to monitoring config (devices + health feeds)
_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "config",
    "monitoring_devices.yaml",
)


def _load_monitoring_config() -> dict[str, Any]:
    """Load monitoring_devices.yaml; return empty dict if missing."""
    if not os.path.isfile(_CONFIG_PATH):
        return {"devices": [], "health_feeds": [], "health_check_interval_seconds": 60}
    try:
        with open(_CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning("Failed to load monitoring config: %s", e)
        return {"devices": [], "health_feeds": [], "health_check_interval_seconds": 60}


# ---------------------------------------------------------------------------
# Database stats: size, table count, record counts
# ---------------------------------------------------------------------------


@router.get("/database/stats")
@cached_response(ttl=120)
async def get_database_stats():
    """
    Database size (current DB), number of tables per schema, and record counts.
    Used by the monitoring tab across all domains.
    """
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        try:
            with conn.cursor() as cur:
                # Total size of current database
                cur.execute("""
                    SELECT pg_database.datname,
                           pg_size_pretty(pg_database_size(pg_database.datname)) AS size_pretty,
                           pg_database_size(pg_database.datname) AS size_bytes
                    FROM pg_database
                    WHERE datname = current_database()
                """)
                db_row = cur.fetchone()
                db_name = db_row[0] if db_row else "unknown"
                size_pretty = db_row[1] if db_row else "0 bytes"
                size_bytes = db_row[2] if db_row else 0

                # Table count per schema (public + domain schemas)
                cur.execute("""
                    SELECT table_schema, COUNT(*) AS table_count
                    FROM information_schema.tables
                    WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                      AND table_type = 'BASE TABLE'
                    GROUP BY table_schema
                    ORDER BY table_schema
                """)
                schemas = [{"schema": row[0], "table_count": row[1]} for row in cur.fetchall()]

                # Record counts for domain silos — use domain_registry (same as pipeline), not only public.domains,
                # so monitor counts stay aligned when DB catalog and YAML drift.
                from shared.domain_registry import get_schema_names_active

                domain_schemas = list(get_schema_names_active())

                table_record_counts: list[dict[str, Any]] = []
                for schema in domain_schemas:
                    for table in ("articles", "storylines", "rss_feeds"):
                        try:
                            from psycopg2 import sql

                            cur.execute(
                                sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
                                    sql.Identifier(schema), sql.Identifier(table)
                                )
                            )
                            table_record_counts.append(
                                {
                                    "schema": schema,
                                    "table": table,
                                    "count": cur.fetchone()[0],
                                }
                            )
                        except Exception:
                            pass

                # Total records (sum over domain articles + storylines + feeds)
                total_articles = sum(
                    r["count"] for r in table_record_counts if r["table"] == "articles"
                )
                total_storylines = sum(
                    r["count"] for r in table_record_counts if r["table"] == "storylines"
                )
                total_feeds = sum(
                    r["count"] for r in table_record_counts if r["table"] == "rss_feeds"
                )

            return {
                "success": True,
                "data": {
                    "database_name": db_name,
                    "size_pretty": size_pretty,
                    "size_bytes": size_bytes,
                    "schemas": schemas,
                    "total_tables": sum(s["table_count"] for s in schemas),
                    "table_record_counts": table_record_counts,
                    "totals": {
                        "articles": total_articles,
                        "storylines": total_storylines,
                        "rss_feeds": total_feeds,
                    },
                },
            }
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Database stats error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Backlog status: articles/documents/storylines remaining and catch-up ETA
# ---------------------------------------------------------------------------


@router.get("/backlog_status")
@cached_response(ttl=15)
def get_backlog_status() -> dict[str, Any]:
    """
    Backlog progression: articles to enrich, documents to process, storylines to synthesize,
    with throughput and catch-up ETA. Throughput prefers a rolling average over the last
    four days when enough samples exist, then 1h/24h measurements, then static estimates.
    Includes steady_state (automation backlog clear + pipeline queues clear + non-growing
    article trend + overall iterations at baseline). Adds nightly_catchup: unified nightly
    window schedule, drain-phase automation backlogs, sequential phases still holding work,
    and recent nightly_enrichment_context runs from automation_run_history. Used by the Monitor page.

    **Latency:** Runs many sequential queries (per active domain + intelligence.*). Under load,
    total time can exceed tens of seconds; the Monitor client uses a 60s timeout. Responses are
    cached briefly (`cached_response` ttl) to avoid hammering the DB on every poll.
    """
    # get_db_connection() raises ConnectionError when UI pool is exhausted or DB is down (no longer returns None).
    try:
        conn = get_db_connection()
    except Exception as e:
        logger.warning("backlog_status: database unavailable: %s", e)
        return {"success": False, "error": str(e)[:200], "data": None}

    try:
        cur = conn.cursor()
        nightly_recent_runs: list[dict[str, Any]] = []
        try:
            # Keep monitor responsive under DB load: each statement fails fast.
            cur.execute("SET LOCAL statement_timeout = '3s'")
        except Exception:
            _rollback_db_connection(conn)
        article_backlog = 0
        articles_created_24h = 0
        articles_short_created_24h = 0
        enriched_last_1h = 0
        enriched_last_24h = 0
        enriched_last_4d = 0
        from shared.domain_registry import get_schema_names_active, pipeline_url_schema_pairs

        for schema in get_schema_names_active():
            try:
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.articles
                    WHERE (enrichment_status IS NULL OR enrichment_status IN ('pending', 'failed'))
                      AND COALESCE(enrichment_attempts, 0) < 3
                      AND url IS NOT NULL AND url != ''
                    """
                )
                article_backlog += cur.fetchone()[0] or 0
                cur.execute(
                    f"""
                    SELECT COUNT(*),
                           COUNT(*) FILTER (WHERE (enrichment_status IS NULL OR enrichment_status IN ('pending', 'failed')) AND COALESCE(enrichment_attempts, 0) < 3 AND url IS NOT NULL AND url != '')
                    FROM {schema}.articles
                    WHERE created_at >= NOW() - INTERVAL '24 hours'
                    """
                )
                row = cur.fetchone()
                articles_created_24h += row[0] or 0
                articles_short_created_24h += row[1] or 0
                # Measured throughput: articles enriched in last 1h/24h (enrichment_status = 'enriched')
                cur.execute(
                    f"""
                    SELECT
                        COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '1 hour'),
                        COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '24 hours')
                    FROM {schema}.articles
                    WHERE enrichment_status = 'enriched' AND url IS NOT NULL AND url != ''
                      AND updated_at >= NOW() - INTERVAL '24 hours'
                    """
                )
                r = cur.fetchone()
                if r:
                    enriched_last_1h += r[0] or 0
                    enriched_last_24h += r[1] or 0
                cur.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM {schema}.articles
                    WHERE enrichment_status = 'enriched' AND url IS NOT NULL AND url != ''
                      AND updated_at >= NOW() - INTERVAL '{BACKLOG_WORKLOAD_WINDOW_DAYS} days'
                    """
                )
                enriched_last_4d += cur.fetchone()[0] or 0
            except Exception:
                _rollback_db_connection(conn)

        doc_backlog = 0
        try:
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.processed_documents
                WHERE (extracted_sections IS NULL OR extracted_sections = '[]')
                  AND (metadata IS NULL OR (metadata->'processing'->>'permanent_failure') IS DISTINCT FROM 'true')
                """
            )
            doc_backlog = cur.fetchone()[0] or 0
        except Exception:
            _rollback_db_connection(conn)

        storyline_backlog = 0
        for schema in get_schema_names_active():
            try:
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.storylines s
                    JOIN (SELECT storyline_id, COUNT(*) AS c FROM {schema}.storyline_articles GROUP BY storyline_id) sa
                      ON sa.storyline_id = s.id AND sa.c >= 3
                    WHERE s.synthesized_content IS NULL
                       OR EXISTS (
                         SELECT 1 FROM {schema}.storyline_articles sa2
                         JOIN {schema}.articles a ON a.id = sa2.article_id
                         WHERE sa2.storyline_id = s.id
                         AND a.created_at > COALESCE(s.synthesized_at, '1970-01-01'::timestamptz)
                       )
                    """
                )
                storyline_backlog += cur.fetchone()[0] or 0
            except Exception:
                _rollback_db_connection(conn)

        # Contexts: total, backlog (no claims yet), and throughput (contexts that got claims in last 1h/24h)
        context_total = 0
        context_backlog = 0
        contexts_claim_extracted_last_1h = 0
        contexts_claim_extracted_last_24h = 0
        contexts_claim_extracted_last_4d = 0
        contexts_created_last_1h = 0
        contexts_created_last_24h = 0
        try:
            cur.execute("SET LOCAL statement_timeout = '5s'")
            cur.execute("SELECT COUNT(*) FROM intelligence.contexts")
            context_total = cur.fetchone()[0] or 0
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.contexts c
                LEFT JOIN intelligence.extracted_claims ec ON ec.context_id = c.id
                WHERE ec.id IS NULL
                """
            )
            context_backlog = cur.fetchone()[0] or 0
            cur.execute(
                """
                SELECT
                    COUNT(DISTINCT context_id) FILTER (WHERE ec.created_at >= NOW() - INTERVAL '1 hour'),
                    COUNT(DISTINCT context_id) FILTER (WHERE ec.created_at >= NOW() - INTERVAL '24 hours')
                FROM intelligence.extracted_claims ec
                """
            )
            r = cur.fetchone()
            if r:
                contexts_claim_extracted_last_1h = r[0] or 0
                contexts_claim_extracted_last_24h = r[1] or 0
            cur.execute(
                f"""
                SELECT COUNT(DISTINCT context_id)
                FROM intelligence.extracted_claims
                WHERE created_at >= NOW() - INTERVAL '{BACKLOG_WORKLOAD_WINDOW_DAYS} days'
                """
            )
            contexts_claim_extracted_last_4d = cur.fetchone()[0] or 0
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '1 hour'),
                    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '24 hours')
                FROM intelligence.contexts
                """
            )
            r = cur.fetchone()
            if r:
                contexts_created_last_1h = r[0] or 0
                contexts_created_last_24h = r[1] or 0
        except Exception:
            _rollback_db_connection(conn)

        # Entity profiles: total, backlog (empty sections or stale), throughput (updated with sections in last 1h/24h)
        entity_profile_total = 0
        entity_profile_backlog = 0
        entity_profiles_updated_last_1h = 0
        entity_profiles_updated_last_24h = 0
        entity_profiles_updated_4d = 0
        entity_profiles_any_updated_last_1h = 0
        entity_profiles_any_updated_last_24h = 0
        entity_profiles_any_updated_4d = 0
        try:
            cur.execute("SELECT COUNT(*) FROM intelligence.entity_profiles")
            entity_profile_total = cur.fetchone()[0] or 0
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.entity_profiles ep
                WHERE ep.sections = '[]'::jsonb OR ep.sections IS NULL
                   OR ep.updated_at < NOW() - INTERVAL '7 days'
                """
            )
            entity_profile_backlog = cur.fetchone()[0] or 0
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '1 hour' AND sections IS NOT NULL AND sections != '[]'::jsonb),
                    COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '24 hours' AND sections IS NOT NULL AND sections != '[]'::jsonb),
                    COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '1 hour'),
                    COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '24 hours')
                FROM intelligence.entity_profiles
                """
            )
            r = cur.fetchone()
            if r:
                entity_profiles_updated_last_1h = r[0] or 0
                entity_profiles_updated_last_24h = r[1] or 0
                entity_profiles_any_updated_last_1h = r[2] or 0
                entity_profiles_any_updated_last_24h = r[3] or 0
            cur.execute(
                f"""
                SELECT
                    COUNT(*) FILTER (
                        WHERE updated_at >= NOW() - INTERVAL '{BACKLOG_WORKLOAD_WINDOW_DAYS} days'
                          AND sections IS NOT NULL AND sections != '[]'::jsonb
                    ),
                    COUNT(*) FILTER (
                        WHERE updated_at >= NOW() - INTERVAL '{BACKLOG_WORKLOAD_WINDOW_DAYS} days'
                    )
                FROM intelligence.entity_profiles
                """
            )
            r4 = cur.fetchone()
            if r4:
                entity_profiles_updated_4d = r4[0] or 0
                entity_profiles_any_updated_4d = r4[1] or 0
        except Exception:
            _rollback_db_connection(conn)

        # Documents processed in last 1h/24h (for measured throughput)
        docs_processed_last_1h = 0
        docs_processed_last_24h = 0
        docs_processed_4d = 0
        docs_attempted_last_1h = 0
        docs_attempted_last_24h = 0
        docs_failed_last_1h = 0
        docs_failed_last_24h = 0
        docs_permanent_failed_total = 0
        docs_top_failure_reasons: list[dict[str, Any]] = []
        try:
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '1 hour'),
                    COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '24 hours')
                FROM intelligence.processed_documents
                WHERE extracted_sections IS NOT NULL AND extracted_sections != '[]'::jsonb
                """
            )
            r = cur.fetchone()
            if r:
                docs_processed_last_1h = r[0] or 0
                docs_processed_last_24h = r[1] or 0
            cur.execute(
                f"""
                SELECT COUNT(*)
                FROM intelligence.processed_documents
                WHERE extracted_sections IS NOT NULL AND extracted_sections != '[]'::jsonb
                  AND updated_at >= NOW() - INTERVAL '{BACKLOG_WORKLOAD_WINDOW_DAYS} days'
                """
            )
            docs_processed_4d = cur.fetchone()[0] or 0
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE updated_at >= NOW() - INTERVAL '1 hour'
                          AND COALESCE(metadata->'processing'->>'method', '') IN ('pdf_auto', 'pdf_failed')
                    ),
                    COUNT(*) FILTER (
                        WHERE updated_at >= NOW() - INTERVAL '24 hours'
                          AND COALESCE(metadata->'processing'->>'method', '') IN ('pdf_auto', 'pdf_failed')
                    ),
                    COUNT(*) FILTER (
                        WHERE updated_at >= NOW() - INTERVAL '1 hour'
                          AND COALESCE(metadata->'processing'->>'method', '') = 'pdf_failed'
                    ),
                    COUNT(*) FILTER (
                        WHERE updated_at >= NOW() - INTERVAL '24 hours'
                          AND COALESCE(metadata->'processing'->>'method', '') = 'pdf_failed'
                    ),
                    COUNT(*) FILTER (
                        WHERE (metadata->'processing'->>'permanent_failure') = 'true'
                    )
                FROM intelligence.processed_documents
                """
            )
            r = cur.fetchone()
            if r:
                docs_attempted_last_1h = r[0] or 0
                docs_attempted_last_24h = r[1] or 0
                docs_failed_last_1h = r[2] or 0
                docs_failed_last_24h = r[3] or 0
                docs_permanent_failed_total = r[4] or 0
            cur.execute(
                """
                SELECT COALESCE(NULLIF(metadata->'processing'->>'error', ''), 'unknown') AS reason, COUNT(*) AS c
                FROM intelligence.processed_documents
                WHERE COALESCE(metadata->'processing'->>'method', '') = 'pdf_failed'
                  AND updated_at >= NOW() - INTERVAL '24 hours'
                GROUP BY 1
                ORDER BY c DESC
                LIMIT 5
                """
            )
            docs_top_failure_reasons = [
                {"reason": row[0], "count": row[1] or 0} for row in (cur.fetchall() or [])
            ]
        except Exception:
            _rollback_db_connection(conn)

        # Synthesis per domain: align with automation ``_execute_storyline_synthesis`` (pipeline scope only).
        # Legacy builtins (politics/finance) still appear in ``url_schema_pairs()``; use ``PIPELINE_EXCLUDE_DOMAIN_KEYS``
        # to stop processing them — this block then omits them from the breakdown so Monitor matches actual work.
        synthesis_last_1h: dict[str, int] = {}
        synthesis_last_2h: dict[str, int] = {}
        synthesis_last_4d: dict[str, int] = {}
        for domain_key, schema in pipeline_url_schema_pairs():
            try:
                cur.execute(
                    f"""
                    SELECT
                        COUNT(*) FILTER (WHERE synthesized_at >= NOW() - INTERVAL '1 hour'),
                        COUNT(*) FILTER (WHERE synthesized_at >= NOW() - INTERVAL '2 hours'),
                        COUNT(*) FILTER (WHERE synthesized_at >= NOW() - INTERVAL '{BACKLOG_WORKLOAD_WINDOW_DAYS} days')
                    FROM {schema}.storylines
                    WHERE synthesized_at IS NOT NULL
                    """
                )
                r = cur.fetchone()
                if r:
                    synthesis_last_1h[domain_key] = r[0] or 0
                    synthesis_last_2h[domain_key] = r[1] or 0
                    synthesis_last_4d[domain_key] = r[2] or 0
                else:
                    synthesis_last_1h[domain_key] = 0
                    synthesis_last_2h[domain_key] = 0
                    synthesis_last_4d[domain_key] = 0
            except Exception:
                _rollback_db_connection(conn)
                synthesis_last_1h[domain_key] = 0
                synthesis_last_2h[domain_key] = 0
                synthesis_last_4d[domain_key] = 0

        try:
            cur.execute(
                """
                SELECT phase_name, started_at, finished_at, success,
                       LEFT(COALESCE(error_message, ''), 200)
                FROM automation_run_history
                WHERE phase_name = 'nightly_enrichment_context'
                ORDER BY COALESCE(finished_at, started_at) DESC NULLS LAST
                LIMIT 14
                """
            )
            for row in cur.fetchall() or []:
                nightly_recent_runs.append(
                    {
                        "phase_name": row[0],
                        "started_at": row[1].isoformat() if row[1] else None,
                        "finished_at": row[2].isoformat() if row[2] else None,
                        "success": bool(row[3]) if row[3] is not None else None,
                        "error_snippet": row[4] or None,
                    }
                )
        except Exception:
            _rollback_db_connection(conn)

        cur.close()
        conn.close()
    except Exception as e:
        logger.warning("backlog_status: query failed: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)[:200], "data": None}

    # Throughput: prefer rolling average over the last 4 days when enough samples exist,
    # then 1h / 24h (or 2h for storylines), then static estimates. Caps match prior behaviour.
    hours_4d = 24.0 * BACKLOG_WORKLOAD_WINDOW_DAYS

    if enriched_last_4d >= BACKLOG_AVG_4D_MIN_SAMPLES:
        articles_per_hour = min(enriched_last_4d / hours_4d, 700)
        per_hour_source = "avg_4d"
    elif enriched_last_1h >= 10:
        articles_per_hour = min(enriched_last_1h, 700)
        per_hour_source = "measured_1h"
    elif enriched_last_24h > 0:
        articles_per_hour = min(round(enriched_last_24h / 24.0), 700)
        per_hour_source = "measured_24h"
    else:
        articles_per_hour = 300
        per_hour_source = "estimated"
    articles_per_day = articles_per_hour * 24

    if docs_processed_4d >= BACKLOG_AVG_4D_MIN_DOCUMENTS:
        docs_per_hour = min(docs_processed_4d / hours_4d, 100)
        docs_per_hour_source = "avg_4d"
    elif docs_processed_last_1h > 0:
        docs_per_hour = min(docs_processed_last_1h, 100)
        docs_per_hour_source = "measured_1h"
    elif docs_processed_last_24h > 0:
        docs_per_hour = min(round(docs_processed_last_24h / 24.0), 100)
        docs_per_hour_source = "measured_24h"
    else:
        docs_per_hour = 20
        docs_per_hour_source = "estimated"

    if contexts_claim_extracted_last_4d >= BACKLOG_AVG_4D_MIN_SAMPLES:
        context_claims_per_hour = min(contexts_claim_extracted_last_4d / hours_4d, 200)
        context_claims_per_hour_source = "avg_4d"
    elif contexts_claim_extracted_last_1h >= 5:
        context_claims_per_hour = min(contexts_claim_extracted_last_1h, 200)
        context_claims_per_hour_source = "measured_1h"
    elif contexts_claim_extracted_last_24h > 0:
        context_claims_per_hour = min(round(contexts_claim_extracted_last_24h / 24.0), 200)
        context_claims_per_hour_source = "measured_24h"
    else:
        context_claims_per_hour = 100
        context_claims_per_hour_source = "estimated"

    entity_per_4d = (
        entity_profiles_updated_4d / hours_4d
        if entity_profiles_updated_4d >= BACKLOG_AVG_4D_MIN_SAMPLES
        else 0.0
    )
    entity_per_1h = (
        float(entity_profiles_updated_last_1h)
        if entity_profiles_updated_last_1h >= 1
        else 0.0
    )
    entity_per_24h = (
        entity_profiles_updated_last_24h / 24.0
        if entity_profiles_updated_last_24h > 0
        else 0.0
    )
    entity_per_hour, entity_per_hour_source = _blend_throughput_per_hour(
        per_4d=entity_per_4d,
        per_1h=entity_per_1h,
        per_mid=entity_per_24h,
        cap=50.0,
        fallback=15.0,
        mid_is_24h=True,
    )

    storylines_synthesized_last_1h = sum(synthesis_last_1h.values())
    storylines_synthesized_last_2h = sum(synthesis_last_2h.values())
    storylines_synthesized_last_4d = sum(synthesis_last_4d.values())
    st_per_4d = (
        storylines_synthesized_last_4d / hours_4d
        if storylines_synthesized_last_4d >= BACKLOG_AVG_4D_MIN_SAMPLES
        else 0.0
    )
    st_per_1h = float(storylines_synthesized_last_1h) if storylines_synthesized_last_1h >= 1 else 0.0
    st_per_2h = (
        storylines_synthesized_last_2h / 2.0 if storylines_synthesized_last_2h > 0 else 0.0
    )
    storylines_per_hour, storylines_per_hour_source = _blend_throughput_per_hour(
        per_4d=st_per_4d,
        per_1h=st_per_1h,
        per_mid=st_per_2h,
        cap=50.0,
        fallback=12.0,
        mid_is_24h=False,
    )

    def eta_hours(backlog: int, per_hour: float) -> float:
        if per_hour <= 0:
            return 0.0
        return backlog / per_hour

    now = datetime.now(timezone.utc)
    h_articles = eta_hours(article_backlog, articles_per_hour)
    h_docs = eta_hours(doc_backlog, docs_per_hour)
    h_storylines = eta_hours(storyline_backlog, storylines_per_hour)
    h_contexts = eta_hours(context_backlog, context_claims_per_hour)
    h_entities = eta_hours(entity_profile_backlog, entity_per_hour)

    eta_articles = (now + timedelta(hours=h_articles)).isoformat() if article_backlog else None
    eta_docs = (now + timedelta(hours=h_docs)).isoformat() if doc_backlog else None
    eta_storylines = (
        (now + timedelta(hours=h_storylines)).isoformat() if storyline_backlog else None
    )
    overall_h = max(h_articles, h_docs, h_storylines, h_contexts, h_entities)
    eta_overall = (
        (now + timedelta(hours=overall_h)).isoformat()
        if (
            article_backlog
            or doc_backlog
            or storyline_backlog
            or context_backlog
            or entity_profile_backlog
        )
        else None
    )

    # Iterations to baseline: one "iteration" = one 2h collection/analysis cycle
    def iterations_2h(hours: float) -> int:
        if hours <= 0:
            return 0
        return max(1, int((hours + 1.99) // 2))

    # Article trend: compare **measured** 24h gross ingest vs **measured** enrichments in the same window.
    # (Older logic used modeled `articles_per_day`, which falls back to 300/h → 7200/day when samples are
    # thin — that made "shrinking" almost always true and was not trustworthy.)
    # Positive net = more articles created than enriched in 24h → backlog tends to grow from ingest.
    # Negative net = more enrichments than new rows → drain (often clearing older backlog too).
    net_articles_per_day = articles_created_24h - enriched_last_24h
    if articles_created_24h == 0 and enriched_last_24h == 0:
        backlog_trend = "stable"
    elif net_articles_per_day > 0:
        backlog_trend = "growing"
    elif net_articles_per_day < 0:
        backlog_trend = "shrinking"
    else:
        backlog_trend = "stable"

    overall_iterations = iterations_2h(overall_h)

    pipeline_alerts: list[str] = []
    try:
        art_alert = int(os.environ.get("NEWS_INTEL_ALERT_ARTICLE_BACKLOG", "2000"))
    except ValueError:
        art_alert = 2000
    if article_backlog > art_alert:
        pipeline_alerts.append(
            f"article_enrichment_backlog_high:{article_backlog}>{art_alert}"
        )
    try:
        ctx_alert = int(os.environ.get("NEWS_INTEL_ALERT_CONTEXT_BACKLOG", "500"))
    except ValueError:
        ctx_alert = 500
    if context_backlog > ctx_alert:
        pipeline_alerts.append(f"context_claims_backlog_high:{context_backlog}>{ctx_alert}")

    automation_backlog_nonzero: list[str] = []
    automation_backlog_clear = True
    _bc: dict[str, int] = {}
    try:
        from services.backlog_metrics import get_all_backlog_counts

        _bc = get_all_backlog_counts()
        for name, cnt in sorted(_bc.items()):
            if int(cnt or 0) > 0:
                automation_backlog_clear = False
                automation_backlog_nonzero.append(f"{name}={cnt}")
    except Exception as ex:
        automation_backlog_clear = False
        automation_backlog_nonzero.append(f"backlog_metrics_unavailable:{str(ex)[:120]}")

    nightly_catchup: dict[str, Any] = {}
    try:
        from services.nightly_ingest_window_service import (
            nightly_pipeline_window_info,
            nightly_sequential_phases,
        )

        seq_phases = nightly_sequential_phases()
        window_info = nightly_pipeline_window_info()
        drain_keys = ("content_enrichment", "context_sync", "content_refinement_queue")
        drain_phases_backlog = {k: int(_bc.get(k, 0) or 0) for k in drain_keys}
        sequential_with_backlog: list[dict[str, Any]] = []
        for p in seq_phases:
            c = int(_bc.get(p, 0) or 0)
            if c > 0:
                sequential_with_backlog.append({"phase": p, "count": c})
        nightly_drain_idle = (
            drain_phases_backlog["content_enrichment"] == 0
            and drain_phases_backlog["context_sync"] == 0
            and drain_phases_backlog["content_refinement_queue"] == 0
            and not sequential_with_backlog
        )
        recent_ok = sum(
            1 for r in nightly_recent_runs if r.get("success") is True
        )
        recent_fail = sum(
            1 for r in nightly_recent_runs if r.get("success") is False
        )
        nightly_catchup = {
            "window": window_info,
            "sequential_phase_order": seq_phases,
            "drain_phases_backlog": drain_phases_backlog,
            "sequential_phases_with_backlog": sequential_with_backlog[:40],
            "nightly_drain_idle": nightly_drain_idle,
            "recent_unified_runs": nightly_recent_runs,
            "recent_run_summary": {
                "listed": len(nightly_recent_runs),
                "success": recent_ok,
                "failure": recent_fail,
            },
        }
    except Exception as ex:
        nightly_catchup = {"error": str(ex)[:200]}

    pipeline_queues_clear = (
        article_backlog == 0
        and doc_backlog == 0
        and storyline_backlog == 0
        and context_backlog == 0
        and entity_profile_backlog == 0
    )
    articles_trend_ok = backlog_trend in ("stable", "shrinking")
    overall_iterations_at_baseline = overall_iterations <= 1
    steady_ok = (
        automation_backlog_clear
        and pipeline_queues_clear
        and articles_trend_ok
        and overall_iterations_at_baseline
    )
    steady_reasons: list[str] = []
    if not automation_backlog_clear:
        tail = automation_backlog_nonzero[:15]
        more = len(automation_backlog_nonzero) - len(tail)
        steady_reasons.append(
            "Automation queues over one-batch depth: "
            + ", ".join(tail)
            + (f" …(+{more} more)" if more > 0 else "")
        )
    if not pipeline_queues_clear:
        steady_reasons.append(
            "Monitor SQL backlogs remain (articles, documents, contexts, entity profiles, or storylines)"
        )
    if not articles_trend_ok:
        steady_reasons.append(
            f"Article inflow vs throughput trend is “{backlog_trend}” (need stable or shrinking)"
        )
    if not overall_iterations_at_baseline:
        steady_reasons.append(
            f"Overall catch-up iterations ({overall_iterations}) exceeds baseline threshold (>1)"
        )

    try:
        from config.settings import MODELS as _MODELS

        ollama_models_payload = {"primary": _MODELS["primary"], "secondary": _MODELS["secondary"]}
    except Exception:
        ollama_models_payload = {}

    return {
        "success": True,
        "data": {
            "workload_window_days": BACKLOG_WORKLOAD_WINDOW_DAYS,
            "pipeline_alerts": pipeline_alerts,
            "ollama_models": ollama_models_payload,
            "steady_state": {
                "ok": steady_ok,
                "checks": {
                    "automation_backlog_clear": automation_backlog_clear,
                    "pipeline_queues_clear": pipeline_queues_clear,
                    "articles_trend_ok": articles_trend_ok,
                    "overall_iterations_at_baseline": overall_iterations_at_baseline,
                },
                "reasons": steady_reasons,
            },
            "nightly_catchup": nightly_catchup,
            "articles": {
                "backlog": article_backlog,
                "per_hour": round(articles_per_hour, 2),
                "per_hour_source": per_hour_source,
                "processed_last_1h": enriched_last_1h,
                "processed_last_24h": enriched_last_24h,
                "processed_last_4d": enriched_last_4d,
                "enriched_last_1h": enriched_last_1h,
                "enriched_last_24h": enriched_last_24h,
                "per_day": articles_per_day,
                "eta_hours": round(h_articles, 1),
                "eta_utc": eta_articles,
                "iterations_to_baseline": iterations_2h(h_articles),
                "created_last_24h": articles_created_24h,
                "short_created_last_24h": articles_short_created_24h,
                "net_per_day": net_articles_per_day,
                "backlog_trend": backlog_trend,
            },
            "documents": {
                "backlog": doc_backlog,
                "per_hour": round(docs_per_hour, 2),
                "per_hour_source": docs_per_hour_source,
                "processed_last_1h": docs_processed_last_1h,
                "processed_last_24h": docs_processed_last_24h,
                "processed_last_4d": docs_processed_4d,
                "attempted_last_1h": docs_attempted_last_1h,
                "attempted_last_24h": docs_attempted_last_24h,
                "failed_last_1h": docs_failed_last_1h,
                "failed_last_24h": docs_failed_last_24h,
                "permanent_failed_total": docs_permanent_failed_total,
                "top_failure_reasons_24h": docs_top_failure_reasons,
                "eta_hours": round(h_docs, 1),
                "eta_utc": eta_docs,
                "iterations_to_baseline": iterations_2h(h_docs),
            },
            "contexts": {
                "total": context_total,
                "backlog": context_backlog,
                "per_hour": round(context_claims_per_hour, 2),
                "per_hour_source": context_claims_per_hour_source,
                "processed_last_1h": contexts_claim_extracted_last_1h,
                "processed_last_24h": contexts_claim_extracted_last_24h,
                "processed_last_4d": contexts_claim_extracted_last_4d,
                "created_last_1h": contexts_created_last_1h,
                "created_last_24h": contexts_created_last_24h,
                "eta_hours": round(h_contexts, 1),
                "iterations_to_baseline": iterations_2h(h_contexts),
            },
            "entity_profiles": {
                "total": entity_profile_total,
                "backlog": entity_profile_backlog,
                "per_hour": round(entity_per_hour, 2),
                "per_hour_source": entity_per_hour_source,
                "throughput_scope": "nonempty_sections",
                "any_updated_last_1h": entity_profiles_any_updated_last_1h,
                "any_updated_last_24h": entity_profiles_any_updated_last_24h,
                "any_updated_last_4d": entity_profiles_any_updated_4d,
                "processed_last_1h": entity_profiles_updated_last_1h,
                "processed_last_24h": entity_profiles_updated_last_24h,
                "processed_last_4d": entity_profiles_updated_4d,
                "eta_hours": round(h_entities, 1),
                "iterations_to_baseline": iterations_2h(h_entities),
            },
            "storylines": {
                "backlog": storyline_backlog,
                "per_hour": round(storylines_per_hour, 2),
                "per_hour_source": storylines_per_hour_source,
                "processed_last_1h": storylines_synthesized_last_1h,
                "processed_last_2h": storylines_synthesized_last_2h,
                "processed_last_4d": storylines_synthesized_last_4d,
                "synthesis_per_domain_last_1h": synthesis_last_1h,
                "synthesis_per_domain_last_2h": synthesis_last_2h,
                "synthesis_per_domain_last_4d": synthesis_last_4d,
                "eta_hours": round(h_storylines, 1),
                "eta_utc": eta_storylines,
                "iterations_to_baseline": iterations_2h(h_storylines),
            },
            "overall_eta_hours": round(overall_h, 1),
            "overall_eta_utc": eta_overall,
            "overall_iterations_to_baseline": overall_iterations,
            "cycle_hours": 2,
        },
    }


# ---------------------------------------------------------------------------
# Document sources: failure profile by collector (403/404 vs parser vs success)
# ---------------------------------------------------------------------------


@router.get("/document_sources/health")
@cached_response(ttl=60)
def get_document_sources_health(window_days: int = 30) -> dict[str, Any]:
    """
    Aggregate intelligence.processed_documents by source_type/source_name for the
    last *window_days* days. Use this to decide whether a collector (CRS, GAO,
    CBO, arXiv, etc.) is worth keeping: persistent HTTP 403/404 means the source
    is not providing fetchable PDFs to this environment, not that downstream
    parsing is the bottleneck.
    """
    wd = max(1, min(int(window_days or 30), 365))
    try:
        conn = get_db_connection()
    except Exception as e:
        logger.warning("document_sources/health: database unavailable: %s", e)
        return {"success": False, "error": str(e)[:200], "data": None}

    automated: list[str] = []
    try:
        from config.orchestrator_governance import get_orchestrator_governance_config

        cfg = get_orchestrator_governance_config() or {}
        ds = cfg.get("document_sources") or {}
        automated = list(ds.get("automated_sources") or [])
    except Exception:
        pass

    try:
        cur = conn.cursor()
        try:
            cur.execute("SET LOCAL statement_timeout = '8s'")
        except Exception:
            _rollback_db_connection(conn)

        cur.execute(
            f"""
            SELECT
                COALESCE(NULLIF(TRIM(source_type), ''), '(unknown)') AS st,
                COALESCE(NULLIF(TRIM(source_name), ''), '(unknown)') AS sn,
                COUNT(*)::bigint AS n_total,
                COUNT(*) FILTER (
                    WHERE extracted_sections IS NOT NULL
                      AND extracted_sections::text NOT IN ('[]', 'null')
                )::bigint AS n_success,
                COUNT(*) FILTER (
                    WHERE metadata->'processing'->>'method' = 'pdf_failed'
                )::bigint AS n_pdf_failed,
                COUNT(*) FILTER (
                    WHERE COALESCE(metadata->'processing'->>'error', '')
                      ILIKE '%%HTTP 403%%'
                )::bigint AS n_http_403,
                COUNT(*) FILTER (
                    WHERE COALESCE(metadata->'processing'->>'error', '')
                      ILIKE '%%HTTP 404%%'
                )::bigint AS n_http_404,
                COUNT(*) FILTER (
                    WHERE COALESCE(metadata->'processing'->>'error', '')
                      ILIKE '%%No PDF parser available%%'
                )::bigint AS n_parser_missing,
                COUNT(*) FILTER (
                    WHERE (metadata->'processing'->>'permanent_failure') = 'true'
                )::bigint AS n_permanent
            FROM intelligence.processed_documents
            WHERE created_at >= NOW() - INTERVAL '{wd} days'
            GROUP BY 1, 2
            ORDER BY n_pdf_failed DESC, n_http_403 + n_http_404 DESC, n_total DESC
            """
        )
        rows = cur.fetchall() or []

        cur.execute(
            f"""
            SELECT
                COUNT(*) FILTER (
                    WHERE COALESCE(metadata->'processing'->>'error', '')
                      ILIKE '%%HTTP 403%%'
                )::bigint,
                COUNT(*) FILTER (
                    WHERE COALESCE(metadata->'processing'->>'error', '')
                      ILIKE '%%HTTP 404%%'
                )::bigint,
                COUNT(*)::bigint
            FROM intelligence.processed_documents
            WHERE created_at >= NOW() - INTERVAL '{wd} days'
            """
        )
        tot_row = cur.fetchone() or (0, 0, 0)
        cur.close()
        conn.close()
    except Exception as e:
        logger.warning("document_sources/health: query failed: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)[:200], "data": None}

    sources: list[dict[str, Any]] = []
    for st, sn, n_total, n_success, n_pdf_failed, n403, n404, n_parser, n_perm in rows:
        access_failures = int(n403 or 0) + int(n404 or 0)
        review = False
        if int(n_total or 0) > 0:
            if int(n404 or 0) >= 3 or int(n403 or 0) >= 5:
                review = True
            elif int(n_pdf_failed or 0) >= 5 and access_failures >= int(n_pdf_failed or 0) // 2:
                review = True
        if int(n_total or 0) == 0:
            health = "no_rows"
        elif review:
            health = "review_source_or_disable_collector"
        else:
            health = "ok"

        sources.append(
            {
                "source_type": st,
                "source_name": sn,
                "documents_in_window": int(n_total or 0),
                "success_processed_count": int(n_success or 0),
                "pdf_failed_count": int(n_pdf_failed or 0),
                "http_403_count": int(n403 or 0),
                "http_404_count": int(n404 or 0),
                "parser_missing_count": int(n_parser or 0),
                "permanent_failure_count": int(n_perm or 0),
                "health": health,
            }
        )

    t403, t404, t_all = (int(tot_row[0] or 0), int(tot_row[1] or 0), int(tot_row[2] or 0))
    rec_parts: list[str] = []
    if t403 + t404 > 0:
        rec_parts.append(
            "High HTTP 403/404 counts usually mean the origin is blocking or the PDF URL is wrong; "
            "remove or fix the corresponding key under document_sources.automated_sources in "
            "api/config/orchestrator_governance.yaml (crs, gao, cbo, arxiv)."
        )
    if not rec_parts:
        rec_parts.append(
            "No major HTTP access-error signal in this window; failures may be parser, size, or one-off."
        )

    return {
        "success": True,
        "data": {
            "window_days": wd,
            "configured_automated_sources": automated,
            "sources": sources,
            "summary": {
                "documents_in_window_total": t_all,
                "http_403_total": t403,
                "http_404_total": t404,
                "recommendation": " ".join(rec_parts),
            },
        },
    }


# ---------------------------------------------------------------------------
# Context-entity coverage diagnostic (Phase 3B)
# ---------------------------------------------------------------------------


@router.get("/context_entity_coverage")
def get_context_entity_coverage() -> dict[str, Any]:
    """
    Diagnostic: contexts with vs without context_entity_mentions.
    Run entity_profile_sync + backfill to improve coverage.
    """
    try:
        from services.context_processor_service import get_context_entity_mentions_coverage

        data = get_context_entity_mentions_coverage()
        return {"success": "error" not in data, "data": data}
    except Exception as e:
        return {"success": False, "error": str(e)[:200], "data": None}


# ---------------------------------------------------------------------------
# Devices: disk usage and processes (local now; remote via agent_url later)
# ---------------------------------------------------------------------------


def _get_local_disk_and_processes(project_path: str | None = None) -> dict[str, Any]:
    """Get disk usage and top processes for the local machine."""
    disk_root = psutil.disk_usage("/")
    result = {
        "disk": {
            "total_bytes": disk_root.total,
            "used_bytes": disk_root.used,
            "free_bytes": disk_root.free,
            "percent": disk_root.percent,
            "mountpoint": "/",
        },
        "project_usage_bytes": None,
        "processes": [],
    }
    if project_path and os.path.isdir(project_path):
        try:
            # Approximate project size (directory tree)
            total = 0
            for _root, _dirs, files in os.walk(project_path):
                for f in files:
                    fp = os.path.join(_root, f)
                    try:
                        total += os.path.getsize(fp)
                    except OSError:
                        pass
            result["project_usage_bytes"] = total
        except Exception:
            pass
    # Top processes by memory
    procs = []
    for p in psutil.process_iter(["pid", "name", "memory_percent", "cpu_percent"]):
        try:
            pinfo = p.info
            procs.append(
                {
                    "pid": pinfo.get("pid"),
                    "name": pinfo.get("name") or "?",
                    "memory_percent": round(pinfo.get("memory_percent") or 0, 1),
                    "cpu_percent": round(pinfo.get("cpu_percent") or 0, 1),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procs.sort(key=lambda x: x["memory_percent"] or 0, reverse=True)
    result["processes"] = procs[:50]
    return result


def _get_remote_disk_and_processes_via_ssh(
    host: str,
    ssh_user: str | None = None,
    timeout_seconds: int = DEFAULT_SSH_TIMEOUT_SECONDS,
    project_path_remote: str | None = None,
) -> dict[str, Any]:
    """
    Run df and ps on remote host via SSH; return same shape as _get_local_disk_and_processes.
    Requires passwordless SSH (e.g. key-based) from API host to host. See docs/MONITORING_SSH_SETUP.md.
    """
    user = ssh_user or os.environ.get("MONITORING_SSH_USER") or os.environ.get("USER", "newsapp")
    target = f"{user}@{host}"
    result = {
        "disk": None,
        "project_usage_bytes": None,
        "processes": [],
        "error": None,
    }

    # SSH options: no password prompt, short connect timeout
    ssh_opts = "-o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=accept-new"

    # 1. Disk: df -B1 for bytes; use root "/" row
    try:
        cmd = f"ssh {ssh_opts} {target} \"df -B1 --output=size,used,avail,pcent,target 2>/dev/null | awk 'NR==2 || / \\/ $/ {{print; exit}}'\""
        out = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        if out.returncode == 0 and out.stdout.strip():
            parts = out.stdout.strip().split()
            if len(parts) >= 5:
                total_b = int(parts[0])
                used_b = int(parts[1])
                avail_b = int(parts[2])
                pct_str = parts[3].rstrip("%")
                mount = parts[4] if len(parts) > 4 else "/"
                try:
                    pct = float(pct_str)
                except ValueError:
                    pct = (used_b / total_b * 100) if total_b else 0
                result["disk"] = {
                    "total_bytes": total_b,
                    "used_bytes": used_b,
                    "free_bytes": avail_b,
                    "percent": round(pct, 1),
                    "mountpoint": mount,
                }
        else:
            # Fallback: df without GNU --output (e.g. BusyBox)
            cmd2 = f"ssh {ssh_opts} {target} \"df -B1 2>/dev/null | awk 'NR==2 {{print $2,$3,$4,$5,$6}}'\""
            out2 = subprocess.run(
                cmd2, shell=True, capture_output=True, text=True, timeout=timeout_seconds
            )
            if out2.returncode == 0 and out2.stdout.strip():
                parts = out2.stdout.strip().split()
                if len(parts) >= 4:
                    total_b = int(parts[0])
                    used_b = int(parts[1])
                    avail_b = int(parts[2])
                    pct_str = parts[3].rstrip("%")
                    try:
                        pct = float(pct_str)
                    except ValueError:
                        pct = (used_b / total_b * 100) if total_b else 0
                    result["disk"] = {
                        "total_bytes": total_b,
                        "used_bytes": used_b,
                        "free_bytes": avail_b,
                        "percent": round(pct, 1),
                        "mountpoint": parts[4] if len(parts) > 4 else "/",
                    }
    except subprocess.TimeoutExpired:
        result["error"] = "ssh timeout (df)"
        return result
    except Exception as e:
        result["error"] = str(e)[:200]
        return result

    # 2. Processes: ps -o pid,comm,%mem,%cpu (Linux)
    try:
        cmd = f'ssh {ssh_opts} {target} "ps -o pid,comm,%mem,%cpu --no-headers -e 2>/dev/null | head -51"'
        out = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout_seconds
        )
        if out.returncode == 0 and out.stdout.strip():
            procs = []
            for line in out.stdout.strip().split("\n")[:50]:
                parts = line.split(
                    None, 3
                )  # pid, comm, %mem, %cpu (comm may contain spaces; last 2 are numbers)
                if len(parts) >= 4:
                    try:
                        procs.append(
                            {
                                "pid": int(parts[0]),
                                "name": (parts[1] or "?")[:50],
                                "memory_percent": round(float(parts[2].replace(",", ".")), 1),
                                "cpu_percent": round(float(parts[3].replace(",", ".")), 1),
                            }
                        )
                    except (ValueError, IndexError):
                        continue
                elif len(parts) == 3:
                    try:
                        procs.append(
                            {
                                "pid": int(parts[0]),
                                "name": (parts[1] or "?")[:50],
                                "memory_percent": round(float(parts[2].replace(",", ".")), 1),
                                "cpu_percent": 0.0,
                            }
                        )
                    except (ValueError, IndexError):
                        continue
            procs.sort(key=lambda x: x["memory_percent"], reverse=True)
            result["processes"] = procs[:50]
    except subprocess.TimeoutExpired:
        result["error"] = result.get("error") or "ssh timeout (ps)"
    except Exception as e:
        result["error"] = result.get("error") or str(e)[:200]

    # 3. Optional: project path size on remote (du -sb)
    if project_path_remote and result["error"] is None:
        try:
            cmd = f'ssh {ssh_opts} {target} "du -sb {project_path_remote} 2>/dev/null | cut -f1"'
            out = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=timeout_seconds
            )
            if out.returncode == 0 and out.stdout.strip():
                result["project_usage_bytes"] = int(out.stdout.strip().split()[0])
        except Exception:
            pass

    return result


def _fetch_remote_via_http(agent_url: str, timeout_seconds: int = 10) -> dict[str, Any]:
    """
    Fetch device metrics from a remote HTTP agent. Expects GET {agent_url} to return JSON:
    disk (dict with total_gb, used_gb, free_gb, percent), project_usage_bytes (int or null),
    processes (list of {pid, name, memory_percent, cpu_percent}).
    Returns same shape as _get_remote_disk_and_processes_via_ssh for consistency.
    """
    result: dict[str, Any] = {
        "disk": None,
        "project_usage_bytes": None,
        "processes": [],
        "error": None,
    }
    try:
        r = requests.get(agent_url, timeout=timeout_seconds)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        result["error"] = str(e)[:200]
        return result
    except (ValueError, TypeError) as e:
        result["error"] = f"Invalid JSON: {e}"[:200]
        return result

    disk_in = data.get("disk")
    if isinstance(disk_in, dict):
        result["disk"] = {
            "total_gb": disk_in.get("total_gb"),
            "used_gb": disk_in.get("used_gb"),
            "free_gb": disk_in.get("free_gb"),
            "percent": disk_in.get("percent"),
        }
    pu = data.get("project_usage_bytes")
    result["project_usage_bytes"] = int(pu) if pu is not None and str(pu).isdigit() else None
    procs = data.get("processes")
    if isinstance(procs, list):
        for p in procs[:50]:
            if isinstance(p, dict):
                result["processes"].append(
                    {
                        "pid": int(p.get("pid", 0)),
                        "name": (p.get("name") or "?")[:50],
                        "memory_percent": round(float(p.get("memory_percent", 0) or 0), 1),
                        "cpu_percent": round(float(p.get("cpu_percent", 0) or 0), 1),
                    }
                )
    return result


@router.get("/devices")
@cached_response(ttl=60)
async def get_devices():
    """
    Disk usage and processes per device (Legion, Widow, NAS, Pi).
    Local device uses psutil; remote devices use SSH (df + ps) when host is set and agent_url is not.
    See docs/MONITORING_SSH_SETUP.md for SSH key setup on remote hosts.
    """
    config = _load_monitoring_config()
    devices_config = config.get("devices") or []
    project_path = os.environ.get("PROJECT_ROOT") or os.getcwd()
    loop = asyncio.get_event_loop()
    timeout = config.get("ssh_timeout_seconds") or DEFAULT_SSH_TIMEOUT_SECONDS

    result: list[dict[str, Any]] = []
    for dev in devices_config:
        name = dev.get("name") or "unknown"
        dtype = (dev.get("type") or "remote").lower()
        if dtype == "local":
            data = _get_local_disk_and_processes(dev.get("project_path") or project_path)
            result.append(
                {
                    "name": name,
                    "type": "local",
                    "description": dev.get("description") or "",
                    "disk": data["disk"],
                    "project_usage_bytes": data["project_usage_bytes"],
                    "processes": data["processes"],
                    "status": "ok",
                }
            )
        else:
            agent_url = dev.get("agent_url")
            host = dev.get("host")
            if agent_url:
                try:
                    data = await loop.run_in_executor(
                        None,
                        lambda u=agent_url, t=timeout: _fetch_remote_via_http(u, timeout_seconds=t),
                    )
                except Exception as e:
                    logger.warning("HTTP agent fetch for %s (%s) failed: %s", name, agent_url, e)
                    data = {
                        "disk": None,
                        "project_usage_bytes": None,
                        "processes": [],
                        "error": str(e)[:200],
                    }
                result.append(
                    {
                        "name": name,
                        "type": "remote",
                        "description": dev.get("description") or "",
                        "host": host,
                        "disk": data.get("disk"),
                        "project_usage_bytes": data.get("project_usage_bytes"),
                        "processes": data.get("processes") or [],
                        "status": "ok" if data.get("error") is None else "error",
                        "message": data.get("error") if data.get("error") else None,
                    }
                )
            elif host:
                # SSH-based disk/process fetch (passwordless keys required)
                ssh_user = dev.get("ssh_user") or os.environ.get("MONITORING_SSH_USER")
                project_path_remote = dev.get("project_path_remote")
                try:
                    data = await loop.run_in_executor(
                        None,
                        lambda h=host, u=ssh_user, t=timeout, p=project_path_remote: (
                            _get_remote_disk_and_processes_via_ssh(h, u, t, p)
                        ),
                    )
                except Exception as e:
                    logger.warning("SSH fetch for %s (%s) failed: %s", name, host, e)
                    data = {
                        "disk": None,
                        "project_usage_bytes": None,
                        "processes": [],
                        "error": str(e)[:200],
                    }
                result.append(
                    {
                        "name": name,
                        "type": "remote",
                        "description": dev.get("description") or "",
                        "host": host,
                        "disk": data.get("disk"),
                        "project_usage_bytes": data.get("project_usage_bytes"),
                        "processes": data.get("processes") or [],
                        "status": "ok" if data.get("error") is None else "error",
                        "message": data.get("error") if data.get("error") else None,
                    }
                )
            else:
                result.append(
                    {
                        "name": name,
                        "type": "remote",
                        "description": dev.get("description") or "",
                        "host": None,
                        "disk": None,
                        "project_usage_bytes": None,
                        "processes": None,
                        "status": "unconfigured",
                        "message": "Add host (and SSH keys) or agent_url to config",
                    }
                )

    # Total project space across devices (for now only local)
    total_project_bytes = None
    for r in result:
        if r.get("project_usage_bytes") is not None:
            total_project_bytes = (total_project_bytes or 0) + r["project_usage_bytes"]

    return {
        "success": True,
        "data": {
            "devices": result,
            "total_project_usage_bytes": total_project_bytes,
        },
    }


# ---------------------------------------------------------------------------
# Processing progress (Monitor pulse — same router as backlog_status)
# ---------------------------------------------------------------------------


@router.get("/processing_progress")
@cached_response(ttl=90)
def get_processing_progress() -> dict[str, Any]:
    """
    Pipeline dimension throughput, per-phase pending/backlog row counts, pass/fail rates from
    ``automation_run_history``, and 72h hourly buckets. Implemented in ``processing_progress.py``
    and mounted here so the path is always ``/api/system_monitoring/processing_progress``.
    """
    from .processing_progress import compute_processing_progress_response

    out = compute_processing_progress_response()
    if out.get("success") and isinstance(out.get("data"), dict):
        out["data"]["workload_window_days_note"] = BACKLOG_WORKLOAD_WINDOW_DAYS
    return out


# ---------------------------------------------------------------------------
# Health feeds: last results from health monitor orchestrator (in-memory state)
# ---------------------------------------------------------------------------

# In-memory state populated by health_monitor_orchestrator
_health_feed_results: dict[str, dict[str, Any]] = {}
_health_feed_results_ts: float | None = None


def set_health_feed_results(results: dict[str, dict[str, Any]]) -> None:
    """Called by health monitor orchestrator to store last poll results."""
    global _health_feed_results, _health_feed_results_ts
    import time

    _health_feed_results.clear()
    _health_feed_results.update(results)
    _health_feed_results_ts = time.time()


@router.get("/health/feeds")
async def get_health_feeds():
    """
    Aggregated status of all configured health feeds (API health, route supervisor, orchestrator).
    Populated by the health monitor orchestrator; if it has not run yet, returns config only.
    """
    config = _load_monitoring_config()
    feeds_config = config.get("health_feeds") or []
    results = []
    for feed in feeds_config:
        name = feed.get("name") or feed.get("url") or "unknown"
        last = _health_feed_results.get(name) if _health_feed_results else None
        results.append(
            {
                "name": name,
                "url": feed.get("url"),
                "method": feed.get("method", "GET"),
                "last_ok": last.get("ok") if last else None,
                "last_status_code": last.get("status_code") if last else None,
                "last_message": last.get("message") if last else None,
                "last_check_at": last.get("checked_at") if last else None,
            }
        )
    return {
        "success": True,
        "data": {
            "feeds": results,
            "last_updated_at": _health_feed_results_ts,
            "interval_seconds": config.get("health_check_interval_seconds", 60),
        },
    }
