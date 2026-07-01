"""
Signal-first article lane selection: full LLM vs light defer vs skip.

Used by unified intake, entity extraction, and topic clustering selection SQL.
Config via env (SSOT accessors below) and orchestrator_governance quality_thresholds.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from config.runtime import env_bool, env_float, env_int, env_str

logger = logging.getLogger(__name__)

_TRENDING_CACHE: dict[str, tuple[float, set[int]]] = {}
_TRENDING_TTL_SEC = 3600


def article_signal_enabled() -> bool:
    try:
        from config.orchestrator_governance import get_orchestrator_governance_config

        sf = get_orchestrator_governance_config().get("signal_first") or {}
        if isinstance(sf, dict) and "article_signal_enabled" in sf:
            return bool(sf.get("article_signal_enabled"))
    except Exception:
        pass
    return env_bool("ARTICLE_SIGNAL_ENABLED", False)


def article_signal_full_min_quality() -> float:
    try:
        from config.orchestrator_governance import get_orchestrator_governance_config

        gov = get_orchestrator_governance_config()
        qt = (gov.get("quality_thresholds") or {}).get("min_importance_for_processing")
        if qt is not None:
            return max(0.0, min(1.0, float(qt)))
    except Exception:
        pass
    return max(0.0, min(1.0, env_float("ARTICLE_SIGNAL_FULL_MIN_QUALITY", 0.45)))


def article_signal_trending_top_n() -> int:
    return max(1, min(50, env_int("ARTICLE_SIGNAL_TRENDING_TOP_N", 15)))


def article_signal_trending_hours() -> int:
    return max(1, min(168, env_int("ARTICLE_SIGNAL_TRENDING_HOURS", 72)))


def _cred_tier_sql(alias: str) -> str:
    return f"COALESCE({alias}.metadata->'source_credibility'->>'tier', 'tier_3')"


def sql_trending_cluster_ids_subquery(schema: str, top_n: int | None = None) -> str:
    """Subquery returning topic_cluster ids in the trending window."""
    n = top_n if top_n is not None else article_signal_trending_top_n()
    hours = article_signal_trending_hours()
    return f"""
        SELECT tc.id
        FROM {schema}.topic_clusters tc
        JOIN {schema}.article_topic_clusters atc ON tc.id = atc.topic_cluster_id
        JOIN {schema}.articles ar ON ar.id = atc.article_id
        WHERE ar.created_at >= NOW() - ({hours} || ' hours')::interval
        GROUP BY tc.id
        ORDER BY COUNT(atc.article_id) DESC
        LIMIT {int(n)}
    """


def sql_article_in_trending_cluster(schema: str, alias: str = "a") -> str:
    sub = sql_trending_cluster_ids_subquery(schema)
    return f"""EXISTS (
        SELECT 1 FROM {schema}.article_topic_clusters atc
        WHERE atc.article_id = {alias}.id
          AND atc.topic_cluster_id IN ({sub})
    )"""


def sql_article_signal_full_lane_filter(
    alias: str = "a",
    schema: str | None = None,
) -> str:
    """
    SQL AND fragment: article qualifies for full LLM lane.
    Empty string when ARTICLE_SIGNAL_ENABLED is false.
    """
    if not article_signal_enabled():
        return ""
    if not schema:
        return ""
    min_q = article_signal_full_min_quality()
    tier = _cred_tier_sql(alias)
    trending = sql_article_in_trending_cluster(schema, alias)
    return f"""(
        {tier} = 'tier_1'
        OR ({tier} = 'tier_2' AND COALESCE({alias}.quality_score, 0) >= {min_q})
        OR COALESCE({alias}.quality_score, 0) >= {min_q}
        OR ({trending})
    )"""


def sql_article_signal_light_lane_filter(
    alias: str = "a",
    schema: str | None = None,
) -> str:
    """SQL AND fragment: enriched article in light lane (not full)."""
    if not article_signal_enabled() or not schema:
        return "FALSE"
    full = sql_article_signal_full_lane_filter(alias, schema)
    return f"(NOT ({full}))"


def article_signal_tier(
    article_row: dict[str, Any],
    domain_key: str,
    *,
    trending_article_ids: set[int] | None = None,
) -> str:
    """
    Python tier resolver for single rows: 'full' | 'light' | 'skip'.
    skip = not enriched / too short (caller should gate on content first).
    """
    if not article_signal_enabled():
        return "full"

    content = (article_row.get("content") or "").strip()
    if len(content) <= 100:
        return "skip"

    enrich = (article_row.get("enrichment_status") or "").strip().lower()
    if enrich not in ("enriched", "failed", "inaccessible") and len(content) < 500:
        return "skip"

    min_q = article_signal_full_min_quality()
    quality = float(article_row.get("quality_score") or 0.0)
    meta = article_row.get("metadata") or {}
    if isinstance(meta, str):
        import json

        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}
    cred = (meta.get("source_credibility") or {}) if isinstance(meta, dict) else {}
    tier = str(cred.get("tier") or "tier_3")

    article_id = int(article_row.get("id") or 0)
    if tier == "tier_1":
        return "full"
    if tier == "tier_2" and quality >= min_q:
        return "full"
    if quality >= min_q:
        return "full"
    if trending_article_ids and article_id in trending_article_ids:
        return "full"
    return "light"


def load_trending_article_ids(schema: str) -> set[int]:
    """Cached set of article ids linked to top-N trending clusters."""
    now = time.time()
    cached = _TRENDING_CACHE.get(schema)
    if cached and (now - cached[0]) < _TRENDING_TTL_SEC:
        return cached[1]

    ids: set[int] = set()
    try:
        from shared.database.connection import get_db_connection_context

        sub = sql_trending_cluster_ids_subquery(schema)
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT DISTINCT atc.article_id
                    FROM {schema}.article_topic_clusters atc
                    WHERE atc.topic_cluster_id IN ({sub})
                    """
                )
                ids = {int(r[0]) for r in cur.fetchall()}
    except Exception as exc:
        logger.debug("load_trending_article_ids %s: %s", schema, exc)

    _TRENDING_CACHE[schema] = (now, ids)
    return ids


def defer_signal_light_unified_intake_batch(
    *,
    per_domain_limit: int = 200,
) -> dict[str, int]:
    """
    Mark light-lane articles as signal_deferred for unified_intake_extraction
    without LLM calls. Returns counts per schema.
    """
    if not article_signal_enabled():
        return {}

    from shared.database.connection import get_db_connection_context
    from shared.domain_registry import pipeline_url_schema_pairs
    from shared.pipeline_pass_marker import (
        TERMINAL_PROCESSED_EMPTY_LEGITIMATE,
        bulk_record_article_phase_pass,
        phase_backlog_uses_pass_marker,
        sql_article_pass_null,
    )
    from shared.article_processing_gates import sql_ml_ready_and_content_bounds

    if not phase_backlog_uses_pass_marker("unified_intake_extraction"):
        return {}

    ml_ready = sql_ml_ready_and_content_bounds("a")
    pass_clause = f" AND ({sql_article_pass_null('unified_intake_extraction', 'a')}) "
    counts: dict[str, int] = {}

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for domain_key, schema_name in pipeline_url_schema_pairs():
                light_filter = sql_article_signal_light_lane_filter("a", schema_name)
                if light_filter == "FALSE":
                    continue
                try:
                    cur.execute(
                        f"""
                        SELECT a.id
                        FROM {schema_name}.articles a
                        WHERE COALESCE(
                            (a.metadata #>> '{{pipeline_skip,unified_intake_extraction_skip}}')::boolean,
                            false
                        ) = false
                          AND a.content IS NOT NULL
                          AND LENGTH(a.content) > 100
                          AND ({ml_ready})
                          AND (
                              LENGTH(a.content) >= 500
                              OR a.created_at < NOW() - INTERVAL '2 hours'
                              OR COALESCE(a.enrichment_status, '') IN (
                                  'enriched', 'failed', 'inaccessible'
                              )
                          )
                          AND ({light_filter})
                          {pass_clause}
                        ORDER BY a.created_at ASC
                        LIMIT %s
                        """,
                        (per_domain_limit,),
                    )
                    ids = [int(r[0]) for r in cur.fetchall()]
                except Exception as exc:
                    logger.warning(
                        "defer_signal_light unified_intake %s: %s", schema_name, exc
                    )
                    ids = []

                if ids:
                    bulk_record_article_phase_pass(
                        schema_name,
                        ids,
                        "unified_intake_extraction",
                        "signal_deferred",
                        TERMINAL_PROCESSED_EMPTY_LEGITIMATE,
                    )
                counts[schema_name] = len(ids)

    return counts
