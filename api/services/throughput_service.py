"""
Throughput measurement service for News Intelligence pipeline.

Extracted from ``api/domains/system_monitoring/routes/resource_dashboard.py`` so that
the route, AutomationManager status endpoint, and any future consumer share one source
of truth for throughput calculations.

Key decisions (documented at docs/RESOURCE_BUDGETS_AND_LEAN_PIPELINE.md):
- Throughput prefers a rolling 4-day average when enough samples exist, then falls
  back to 1h / 24h measured rates, then static estimates.
- Caps match prior dashboard behaviour: articles capped at 700/hr, documents at 100/hr.
- Context/entity throughput uses the blended rate with domain-scoped SQL queries.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (mirrors resource_dashboard.py defaults)
# ---------------------------------------------------------------------------

BACKLOG_WORKLOAD_WINDOW_DAYS: int = 4
BACKLOG_AVG_4D_MIN_SAMPLES: int = 50
BACKLOG_AVG_4D_MIN_DOCUMENTS: int = 20


def _blend_throughput_per_hour(
    *,
    count_1h: int,
    count_24h: int,
    count_4d: int,
    cap: int,
    estimated: float | None = None,
    domain_table: str | None = None,
) -> tuple[float, str]:
    """Return (rate_per_hour, source_label) using the dashboard's blending logic.

    Blending order (same as resource_dashboard):
    1. Rolling 4-day average when count_4d >= threshold
    2. Measured 1h rate when it exceeds minimum samples
    3. Measured 24h / 24 rate
    4. Static estimate
    """
    hours_4d = 24.0 * BACKLOG_WORKLOAD_WINDOW_DAYS

    if count_4d >= BACKLOG_AVG_4D_MIN_SAMPLES:
        rate = min(count_4d / hours_4d, cap)
        source = f"avg_4d{f'/{domain_table}' if domain_table else ''}"
        return rate, source

    if count_1h >= 10:
        rate = min(count_1h, cap)
        source = f"measured_1h{f'/{domain_table}' if domain_table else ''}"
        return rate, source

    if count_24h > 0:
        rate = min(round(count_24h / 24.0), cap)
        source = f"measured_24h{f'/{domain_table}' if domain_table else ''}"
        return rate, source

    fallback = estimated if estimated is not None else float(cap)
    return fallback, "estimated"


def compute_article_throughput(cur: Any) -> dict[str, Any]:
    """Measure article enrichment throughput from the database cursor."""
    enriched_last_1h = enriched_last_24h = enriched_last_4d = 0
    claimed_4d = claimed_inflight = 0

    try:
        cur.execute(
            "SELECT COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '1 hour'),"
            " COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '24 hours')"
            " FROM intelligence.articles WHERE enrichment_status = 'enriched'"
        )
        r = cur.fetchone()
        if r:
            enriched_last_1h, enriched_last_24h = (r[0] or 0), (r[1] or 0)

        cur.execute(
            "SELECT COUNT(*) FROM intelligence.articles WHERE enrichment_status = 'enriched'"
            f" AND updated_at >= NOW() - INTERVAL '{BACKLOG_WORKLOAD_WINDOW_DAYS} days'"
        )
        enriched_last_4d = cur.fetchone()[0] or 0

        for dk in ("politics", "finance", "science-tech"):
            try:
                cur.execute(f"SELECT COUNT(*) FROM {dk}.pipeline_contexts")
                claimed_4d += cur.fetchone()[0] or 0
                cur.execute(
                    f"SELECT COUNT(*) FROM {dk}.pipeline_contexts WHERE valid_from IS NULL"
                )
                claimed_inflight += cur.fetchone()[0] or 0
            except Exception:
                pass

    except Exception as e:
        logger.warning("compute_article_throughput query failed: %s", e)
        return {
            "rate_per_hour": 300.0, "rate_source": "estimated", "rate_per_day": 7200.0,
            "enriched_1h": 0, "enriched_24h": 0, "enriched_4d": 0,
            "claimed_4d": 0, "claimed_inflight": 0,
            "backlog_trend": "unknown", "net_articles_per_day": 0,
        }

    rate_ph, src = _blend_throughput_per_hour(
        count_1h=enriched_last_1h, count_24h=enriched_last_24h,
        count_4d=enriched_last_4d, cap=700,
    )
    net_art = enriched_last_1h - enriched_last_24h / 24.0 if enriched_last_24h > 0 else 0

    return {
        "rate_per_hour": rate_ph, "rate_source": src,
        "rate_per_day": rate_ph * 24,
        "enriched_1h": enriched_last_1h, "enriched_24h": enriched_last_24h,
        "enriched_4d": enriched_last_4d, "claimed_4d": claimed_4d,
        "claimed_inflight": claimed_inflight,
        "backlog_trend": "growing" if net_art > 0 else ("stable" if enriched_last_1h == 0 and enriched_last_24h == 0 else "shrinking"),
        "net_articles_per_day": net_art,
    }


def compute_document_throughput(cur: Any) -> dict[str, Any]:
    """Measure document processing throughput."""
    proc_1h = proc_24h = proc_4d = att_1h = att_24h = fail_1h = fail_24h = 0

    try:
        cur.execute(
            "SELECT COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '1 hour'),"
            " COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '24 hours')"
            " FROM intelligence.processed_documents"
            " WHERE extracted_sections IS NOT NULL AND extracted_sections != '[]'::jsonb"
        )
        r = cur.fetchone()
        if r:
            proc_1h, proc_24h = (r[0] or 0), (r[1] or 0)

        cur.execute(
            "SELECT COUNT(*) FROM intelligence.processed_documents"
            " WHERE extracted_sections IS NOT NULL AND extracted_sections != '[]'::jsonb"
            f" AND updated_at >= NOW() - INTERVAL '{BACKLOG_WORKLOAD_WINDOW_DAYS} days'"
        )
        proc_4d = cur.fetchone()[0] or 0

        for method in [("'pdf_auto', 'pdf_failed'", "att"), ("'pdf_failed'", "fail")]:
            cur.execute(
                "SELECT COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '1 hour'),"
                " COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '24 hours')"
                f" FROM intelligence.processed_documents"
                f" WHERE COALESCE(metadata->>'processing'->>'method', '') IN ({method[0]})"
            )
            r = cur.fetchone()
            if r:
                if method[1] == "att":
                    att_1h, att_24h = (r[0] or 0), (r[1] or 0)
                else:
                    fail_1h, fail_24h = (r[0] or 0), (r[1] or 0)

    except Exception as e:
        logger.warning("compute_document_throughput query failed: %s", e)

    rate_ph, src = _blend_throughput_per_hour(
        count_1h=proc_1h, count_24h=proc_24h, count_4d=proc_4d, cap=100,
    )
    return {
        "rate_per_hour": rate_ph, "rate_source": src,
        "processed_1h": proc_1h, "processed_24h": proc_24h,
        "processed_4d": proc_4d, "attempted_1h": att_1h,
        "attempted_24h": att_24h, "failed_1h": fail_1h,
        "failed_24h": fail_24h,
    }


def compute_context_throughput(cur: Any) -> dict[str, Any]:
    """Measure context_claims throughput across pipeline_domains."""
    ctx_total = ctx_backlog_no_claims = 0
    ctx_claims_1h = ctx_claims_24h = ctx_claims_4d = 0

    try:
        from services.pipeline_domains import pipeline_url_schema_pairs

        for _, schema in pipeline_url_schema_pairs():
            cur.execute(f"SELECT COUNT(*) FROM {schema}.pipeline_contexts")
            ctx_total += cur.fetchone()[0] or 0
            cur.execute(
                f"SELECT COUNT(*) FROM {schema}.pipeline_contexts WHERE valid_from IS NULL"
            )
            ctx_backlog_no_claims += cur.fetchone()[0] or 0

        if ctx_total > 0:
            for w, iv in [
                ("1h", "'1 hour'"), ("24h", "'24 hours'"),
                ("4d", f"'{BACKLOG_WORKLOAD_WINDOW_DAYS} days'"),
            ]:
                q = " UNION ALL ".join(
                    f"(SELECT COUNT(*) FROM {s}.pipeline_contexts"
                    f" WHERE valid_from >= NOW() - INTERVAL {iv})"
                    for _, s in pipeline_url_schema_pairs()
                )
                cur.execute(f"SELECT COALESCE(SUM(cnt), 0) FROM ({q}) _x(cnt)")
                v = cur.fetchone()[0] or 0
                if w == "1h":
                    ctx_claims_1h = v
                elif w == "24h":
                    ctx_claims_24h = v
                else:
                    ctx_claims_4d = v

    except Exception as e:
        logger.warning("compute_context_throughput query failed: %s", e)

    rate_ph, src = _blend_throughput_per_hour(
        count_1h=ctx_claims_1h, count_24h=ctx_claims_24h,
        count_4d=ctx_claims_4d, cap=500,
    )
    return {
        "contexts_total": ctx_total, "context_backlog_no_claims": ctx_backlog_no_claims,
        "contexts_with_claims_1h": ctx_claims_1h,
        "contexts_with_claims_24h": ctx_claims_24h,
        "contexts_with_claims_4d": ctx_claims_4d,
        "rate_per_hour": rate_ph, "rate_source": src,
    }


def compute_entity_profile_throughput(cur: Any) -> dict[str, Any]:
    """Measure entity_profiles throughput across pipeline_domains."""
    prof_total = prof_stale = 0
    prof_1h = prof_24h = prof_4d = 0

    try:
        from services.pipeline_domains import pipeline_url_schema_pairs

        for _, schema in pipeline_url_schema_pairs():
            cur.execute(f"SELECT COUNT(*) FROM {schema}.entity_profiles")
            prof_total += cur.fetchone()[0] or 0
            cur.execute(
                f"SELECT COUNT(*) FROM {schema}.entity_profiles"
                " WHERE (sections IS NULL OR sections = '[]'::jsonb)"
                " OR updated_at < NOW() - INTERVAL '7 days'"
            )
            prof_stale += cur.fetchone()[0] or 0

        if prof_total > 0:
            for w, iv in [
                ("1h", "'1 hour'"), ("24h", "'24 hours'"),
                ("4d", f"'{BACKLOG_WORKLOAD_WINDOW_DAYS} days'"),
            ]:
                q = " UNION ALL ".join(
                    f"(SELECT COUNT(*) FROM {s}.entity_profiles"
                    f" WHERE updated_at >= NOW() - INTERVAL {iv})"
                    for _, s in pipeline_url_schema_pairs()
                )
                cur.execute(f"SELECT COALESCE(SUM(cnt), 0) FROM ({q}) _x(cnt)")
                v = cur.fetchone()[0] or 0
                if w == "1h":
                    prof_1h = v
                elif w == "24h":
                    prof_24h = v
                else:
                    prof_4d = v

    except Exception as e:
        logger.warning("compute_entity_profile_throughput query failed: %s", e)

    rate_ph, src = _blend_throughput_per_hour(
        count_1h=prof_1h, count_24h=prof_24h, count_4d=prof_4d, cap=500,
    )
    return {
        "profiles_total": prof_total,
        "profile_backlog_empty_or_stale": prof_stale,
        "profiles_updated_1h": prof_1h,
        "profiles_updated_24h": prof_24h,
        "profiles_updated_4d": prof_4d,
        "rate_per_hour": rate_ph, "rate_source": src,
    }


def compute_full_throughput_snapshot() -> dict[str, Any]:
    """Compute a complete throughput snapshot without requiring a caller-owned DB cursor."""
    from api.shared.database import get_db_connection_context

    snap = {"articles": None, "documents": None, "contexts": None, "entity_profiles": None}

    with get_db_connection_context() as conn:
        try:
            cur = conn.cursor()
            snap["articles"] = compute_article_throughput(cur)
            snap["documents"] = compute_document_throughput(cur)
            snap["contexts"] = compute_context_throughput(cur)
            snap["entity_profiles"] = compute_entity_profile_throughput(cur)
        except Exception as e:
            logger.warning("compute_full_throughput_snapshot failed: %s", e)
            snap["error"] = str(e)[:200]

    return snap


__all__ = [
    "BACKLOG_WORKLOAD_WINDOW_DAYS",
    "BACKLOG_AVG_4D_MIN_SAMPLES",
    "BACKLOG_AVG_4D_MIN_DOCUMENTS",
    "_blend_throughput_per_hour",
    "compute_article_throughput",
    "compute_document_throughput",
    "compute_context_throughput",
    "compute_entity_profile_throughput",
    "compute_full_throughput_snapshot",
]
