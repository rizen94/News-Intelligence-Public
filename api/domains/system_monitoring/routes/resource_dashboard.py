"""
Resource & Health Dashboard — database stats, device disk/processes, aggregated health feeds.
Serves the monitoring tab across all domains.
Remote devices: use agent_url for HTTP metrics endpoint, or host + SSH (df + ps) when agent_url is not set.
See docs/MONITORING_SSH_SETUP.md for SSH. HTTP agent contract: GET {agent_url} returns JSON with
disk, project_usage_bytes, processes (same shape as SSH response).
"""

import asyncio
import os
import logging
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import psutil
import requests
import yaml
from fastapi import APIRouter, HTTPException

from shared.database.connection import get_ui_db_connection as get_db_connection
from shared.services.response_cache import cached_response

logger = logging.getLogger(__name__)


def _rollback_db_connection(conn) -> None:
    """Clear aborted transaction so the next query on this connection can run (psycopg2)."""
    try:
        conn.rollback()
    except Exception:
        pass


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


def _load_monitoring_config() -> Dict[str, Any]:
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

                # Record counts for known domain tables (articles, storylines, rss_feeds per schema)
                try:
                    cur.execute("""
                        SELECT schema_name FROM domains WHERE is_active = true ORDER BY schema_name
                    """)
                    domain_schemas = [row[0] for row in cur.fetchall()]
                except Exception:
                    domain_schemas = []
                if not domain_schemas:
                    domain_schemas = ["politics", "finance", "science_tech"]

                table_record_counts: List[Dict[str, Any]] = []
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
def get_backlog_status() -> Dict[str, Any]:
    """
    Backlog progression: articles to enrich, documents to process, storylines to synthesize,
    with estimated throughput and catch-up ETA. Used by the Monitor page.
    """
    # get_db_connection() raises ConnectionError when UI pool is exhausted or DB is down (no longer returns None).
    try:
        conn = get_db_connection()
    except Exception as e:
        logger.warning("backlog_status: database unavailable: %s", e)
        return {"success": False, "error": str(e)[:200], "data": None}

    try:
        cur = conn.cursor()
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
        for schema in ("politics", "finance", "science_tech"):
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
                articles_created_24h += (row[0] or 0)
                articles_short_created_24h += (row[1] or 0)
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
                    enriched_last_1h += (r[0] or 0)
                    enriched_last_24h += (r[1] or 0)
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
        for schema in ("politics", "finance", "science_tech"):
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
                    COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '24 hours' AND sections IS NOT NULL AND sections != '[]'::jsonb)
                FROM intelligence.entity_profiles
                """
            )
            r = cur.fetchone()
            if r:
                entity_profiles_updated_last_1h = r[0] or 0
                entity_profiles_updated_last_24h = r[1] or 0
        except Exception:
            _rollback_db_connection(conn)

        # Documents processed in last 1h/24h (for measured throughput)
        docs_processed_last_1h = 0
        docs_processed_last_24h = 0
        docs_attempted_last_1h = 0
        docs_attempted_last_24h = 0
        docs_failed_last_1h = 0
        docs_failed_last_24h = 0
        docs_permanent_failed_total = 0
        docs_top_failure_reasons: List[Dict[str, Any]] = []
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
                {"reason": row[0], "count": row[1] or 0}
                for row in (cur.fetchall() or [])
            ]
        except Exception:
            pass

        # Synthesis results per domain (storylines synthesized in last 1h and 2h)
        synthesis_last_1h: Dict[str, int] = {}
        synthesis_last_2h: Dict[str, int] = {}
        for schema, domain_key in [("politics", "politics"), ("finance", "finance"), ("science_tech", "science_tech")]:
            try:
                cur.execute(
                    f"""
                    SELECT
                        COUNT(*) FILTER (WHERE synthesized_at >= NOW() - INTERVAL '1 hour'),
                        COUNT(*) FILTER (WHERE synthesized_at >= NOW() - INTERVAL '2 hours')
                    FROM {schema}.storylines
                    WHERE synthesized_at IS NOT NULL
                    """
                )
                r = cur.fetchone()
                if r:
                    synthesis_last_1h[domain_key] = r[0] or 0
                    synthesis_last_2h[domain_key] = r[1] or 0
                else:
                    synthesis_last_1h[domain_key] = 0
                    synthesis_last_2h[domain_key] = 0
            except Exception:
                _rollback_db_connection(conn)
                synthesis_last_1h[domain_key] = 0
                synthesis_last_2h[domain_key] = 0

        cur.close()
        conn.close()
    except Exception as e:
        logger.warning("backlog_status: query failed: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)[:200], "data": None}

    # Throughput: use measured enrichment when available (articles updated to full content in last 1h/24h)
    # so ETA and trend reflect reality. Fallback 300/hr when no recent data; cap at 700 (burst max).
    if enriched_last_1h >= 10:
        articles_per_hour = min(enriched_last_1h, 700)
        per_hour_source = "measured_1h"
    elif enriched_last_24h > 0:
        articles_per_hour = min(round(enriched_last_24h / 24.0), 700)
        per_hour_source = "measured_24h"
    else:
        articles_per_hour = 300
        per_hour_source = "estimated"
    articles_per_day = articles_per_hour * 24

    # Documents: measured from last 1h/24h when available
    if docs_processed_last_1h > 0:
        docs_per_hour = min(docs_processed_last_1h, 100)
        docs_per_hour_source = "measured_1h"
    elif docs_processed_last_24h > 0:
        docs_per_hour = min(round(docs_processed_last_24h / 24.0), 100)
        docs_per_hour_source = "measured_24h"
    else:
        docs_per_hour = 20
        docs_per_hour_source = "estimated"

    # Context claim-extraction throughput (contexts that got claims in last 1h/24h)
    if contexts_claim_extracted_last_1h >= 5:
        context_claims_per_hour = min(contexts_claim_extracted_last_1h, 200)
        context_claims_per_hour_source = "measured_1h"
    elif contexts_claim_extracted_last_24h > 0:
        context_claims_per_hour = min(round(contexts_claim_extracted_last_24h / 24.0), 200)
        context_claims_per_hour_source = "measured_24h"
    else:
        context_claims_per_hour = 100  # ~50/run every 30 min
        context_claims_per_hour_source = "estimated"

    # Entity profile build throughput
    if entity_profiles_updated_last_1h >= 1:
        entity_per_hour = min(entity_profiles_updated_last_1h, 50)
        entity_per_hour_source = "measured_1h"
    elif entity_profiles_updated_last_24h > 0:
        entity_per_hour = min(round(entity_profiles_updated_last_24h / 24.0), 50)
        entity_per_hour_source = "measured_24h"
    else:
        entity_per_hour = 15  # ~25/run every 30 min, conservative
        entity_per_hour_source = "estimated"

    # Storyline synthesis: use sum of last 1h per domain when available
    storylines_synthesized_last_1h = sum(synthesis_last_1h.values())
    storylines_synthesized_last_2h = sum(synthesis_last_2h.values())
    if storylines_synthesized_last_1h >= 1:
        storylines_per_hour = min(storylines_synthesized_last_1h, 50)
        storylines_per_hour_source = "measured_1h"
    elif storylines_synthesized_last_2h > 0:
        storylines_per_hour = min(round(storylines_synthesized_last_2h / 2.0), 50)
        storylines_per_hour_source = "measured_2h"
    else:
        storylines_per_hour = 12
        storylines_per_hour_source = "estimated"

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
    eta_storylines = (now + timedelta(hours=h_storylines)).isoformat() if storyline_backlog else None
    overall_h = max(h_articles, h_docs, h_storylines, h_contexts, h_entities)
    eta_overall = (now + timedelta(hours=overall_h)).isoformat() if (article_backlog or doc_backlog or storyline_backlog or context_backlog or entity_profile_backlog) else None

    # Iterations to baseline: one "iteration" = one 2h collection/analysis cycle
    def iterations_2h(hours: float) -> int:
        if hours <= 0:
            return 0
        return max(1, int((hours + 1.99) // 2))

    # Net rate: inflow (short created 24h) minus outflow (enriched per day); positive = backlog growing
    net_articles_per_day = articles_short_created_24h - articles_per_day
    backlog_trend = "growing" if net_articles_per_day > 0 else ("shrinking" if net_articles_per_day < 0 else "stable")

    return {
        "success": True,
        "data": {
            "articles": {
                "backlog": article_backlog,
                "per_hour": articles_per_hour,
                "per_hour_source": per_hour_source,
                "processed_last_1h": enriched_last_1h,
                "processed_last_24h": enriched_last_24h,
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
                "per_hour": docs_per_hour,
                "per_hour_source": docs_per_hour_source,
                "processed_last_1h": docs_processed_last_1h,
                "processed_last_24h": docs_processed_last_24h,
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
                "per_hour": context_claims_per_hour,
                "per_hour_source": context_claims_per_hour_source,
                "processed_last_1h": contexts_claim_extracted_last_1h,
                "processed_last_24h": contexts_claim_extracted_last_24h,
                "created_last_1h": contexts_created_last_1h,
                "created_last_24h": contexts_created_last_24h,
                "eta_hours": round(h_contexts, 1),
                "iterations_to_baseline": iterations_2h(h_contexts),
            },
            "entity_profiles": {
                "total": entity_profile_total,
                "backlog": entity_profile_backlog,
                "per_hour": entity_per_hour,
                "per_hour_source": entity_per_hour_source,
                "processed_last_1h": entity_profiles_updated_last_1h,
                "processed_last_24h": entity_profiles_updated_last_24h,
                "eta_hours": round(h_entities, 1),
                "iterations_to_baseline": iterations_2h(h_entities),
            },
            "storylines": {
                "backlog": storyline_backlog,
                "per_hour": storylines_per_hour,
                "per_hour_source": storylines_per_hour_source,
                "processed_last_1h": storylines_synthesized_last_1h,
                "processed_last_2h": storylines_synthesized_last_2h,
                "synthesis_per_domain_last_1h": synthesis_last_1h,
                "synthesis_per_domain_last_2h": synthesis_last_2h,
                "eta_hours": round(h_storylines, 1),
                "eta_utc": eta_storylines,
                "iterations_to_baseline": iterations_2h(h_storylines),
            },
            "overall_eta_hours": round(overall_h, 1),
            "overall_eta_utc": eta_overall,
            "overall_iterations_to_baseline": iterations_2h(overall_h),
            "cycle_hours": 2,
        },
    }


# ---------------------------------------------------------------------------
# Context-entity coverage diagnostic (Phase 3B)
# ---------------------------------------------------------------------------

@router.get("/context_entity_coverage")
def get_context_entity_coverage() -> Dict[str, Any]:
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

def _get_local_disk_and_processes(project_path: Optional[str] = None) -> Dict[str, Any]:
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
    procs.sort(key=lambda x: (x["memory_percent"] or 0), reverse=True)
    result["processes"] = procs[:50]
    return result


def _get_remote_disk_and_processes_via_ssh(
    host: str,
    ssh_user: Optional[str] = None,
    timeout_seconds: int = DEFAULT_SSH_TIMEOUT_SECONDS,
    project_path_remote: Optional[str] = None,
) -> Dict[str, Any]:
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
        cmd = f'ssh {ssh_opts} {target} "df -B1 --output=size,used,avail,pcent,target 2>/dev/null | awk \'NR==2 || / \\/ $/ {{print; exit}}\'"'
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
            cmd2 = f'ssh {ssh_opts} {target} "df -B1 2>/dev/null | awk \'NR==2 {{print $2,$3,$4,$5,$6}}\'"'
            out2 = subprocess.run(cmd2, shell=True, capture_output=True, text=True, timeout=timeout_seconds)
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
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout_seconds)
        if out.returncode == 0 and out.stdout.strip():
            procs = []
            for line in out.stdout.strip().split("\n")[:50]:
                parts = line.split(None, 3)  # pid, comm, %mem, %cpu (comm may contain spaces; last 2 are numbers)
                if len(parts) >= 4:
                    try:
                        procs.append({
                            "pid": int(parts[0]),
                            "name": (parts[1] or "?")[:50],
                            "memory_percent": round(float(parts[2].replace(",", ".")), 1),
                            "cpu_percent": round(float(parts[3].replace(",", ".")), 1),
                        })
                    except (ValueError, IndexError):
                        continue
                elif len(parts) == 3:
                    try:
                        procs.append({
                            "pid": int(parts[0]),
                            "name": (parts[1] or "?")[:50],
                            "memory_percent": round(float(parts[2].replace(",", ".")), 1),
                            "cpu_percent": 0.0,
                        })
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
            out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout_seconds)
            if out.returncode == 0 and out.stdout.strip():
                result["project_usage_bytes"] = int(out.stdout.strip().split()[0])
        except Exception:
            pass

    return result


def _fetch_remote_via_http(agent_url: str, timeout_seconds: int = 10) -> Dict[str, Any]:
    """
    Fetch device metrics from a remote HTTP agent. Expects GET {agent_url} to return JSON:
    disk (dict with total_gb, used_gb, free_gb, percent), project_usage_bytes (int or null),
    processes (list of {pid, name, memory_percent, cpu_percent}).
    Returns same shape as _get_remote_disk_and_processes_via_ssh for consistency.
    """
    result: Dict[str, Any] = {"disk": None, "project_usage_bytes": None, "processes": [], "error": None}
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
                result["processes"].append({
                    "pid": int(p.get("pid", 0)),
                    "name": (p.get("name") or "?")[:50],
                    "memory_percent": round(float(p.get("memory_percent", 0) or 0), 1),
                    "cpu_percent": round(float(p.get("cpu_percent", 0) or 0), 1),
                })
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

    result: List[Dict[str, Any]] = []
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
                    data = {"disk": None, "project_usage_bytes": None, "processes": [], "error": str(e)[:200]}
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
                        lambda h=host, u=ssh_user, t=timeout, p=project_path_remote: _get_remote_disk_and_processes_via_ssh(h, u, t, p),
                    )
                except Exception as e:
                    logger.warning("SSH fetch for %s (%s) failed: %s", name, host, e)
                    data = {"disk": None, "project_usage_bytes": None, "processes": [], "error": str(e)[:200]}
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
# Health feeds: last results from health monitor orchestrator (in-memory state)
# ---------------------------------------------------------------------------

# In-memory state populated by health_monitor_orchestrator
_health_feed_results: Dict[str, Dict[str, Any]] = {}
_health_feed_results_ts: Optional[float] = None


def set_health_feed_results(results: Dict[str, Dict[str, Any]]) -> None:
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
    import time
    return {
        "success": True,
        "data": {
            "feeds": results,
            "last_updated_at": _health_feed_results_ts,
            "interval_seconds": config.get("health_check_interval_seconds", 60),
        },
    }
