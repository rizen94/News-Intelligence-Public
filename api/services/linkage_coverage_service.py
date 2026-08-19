"""Linkage coverage metrics for Monitor and connection diagnostics."""

from __future__ import annotations

import logging
from typing import Any

from config.runtime import env_int
from shared.database.connection import get_db_connection_context
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema

logger = logging.getLogger(__name__)


def _table_exists(cur, schema: str, table: str) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
          SELECT 1 FROM information_schema.tables
          WHERE table_schema = %s AND table_name = %s
        )
        """,
        (schema, table),
    )
    row = cur.fetchone()
    return bool(row and row[0])


def _dup_title_groups(cur, schema: str) -> int:
    cur.execute(
        f"""
        SELECT COUNT(*)::int FROM (
          SELECT 1
          FROM {schema}.storylines s
          WHERE s.merged_into_id IS NULL
            AND COALESCE(s.story_kind, '') <> 'container_index'
            AND s.status NOT IN ('archived', 'concluded')
            AND LENGTH(COALESCE(s.title, '')) >= 20
          GROUP BY LOWER(TRIM(s.title))
          HAVING COUNT(*) > 1
        ) t
        """
    )
    return int((cur.fetchone() or [0])[0] or 0)


def _domain_linkage(cur, domain_key: str, schema: str) -> dict[str, Any]:
    out: dict[str, Any] = {"domain_key": domain_key}
    has_articles = _table_exists(cur, schema, "articles")
    has_storylines = _table_exists(cur, schema, "storylines")

    if has_articles:
        cur.execute(
            f"""
            SELECT COUNT(*)::int
            FROM public.chronological_events ce
            WHERE EXISTS (SELECT 1 FROM {schema}.articles a WHERE a.id = ce.source_article_id)
            """
        )
        domain_ce = int((cur.fetchone() or [0])[0] or 0)
        cur.execute(
            f"""
            SELECT COUNT(DISTINCT ce.id)::int
            FROM public.chronological_events ce
            WHERE EXISTS (SELECT 1 FROM {schema}.articles a WHERE a.id = ce.source_article_id)
              AND EXISTS (
                SELECT 1 FROM intelligence.event_episode_links eel
                WHERE eel.event_id = ce.id
                  AND eel.domain_key = %s
                  AND eel.inference_stage <> 'quarantined'
              )
            """,
            (domain_key,),
        )
        linked = int((cur.fetchone() or [0])[0] or 0)
        out["chronological_events_in_domain"] = domain_ce
        out["chronological_events_linked"] = linked
        out["eel_link_pct"] = round(100.0 * linked / domain_ce, 1) if domain_ce else 0.0
    else:
        out["chronological_events_in_domain"] = 0
        out["chronological_events_linked"] = 0
        out["eel_link_pct"] = 0.0

    cur.execute(
        """
        SELECT COUNT(*)::int
        FROM intelligence.tracked_events te
        WHERE %s = ANY(COALESCE(te.domain_keys, '{}'))
        """,
        (domain_key,),
    )
    te_total = int((cur.fetchone() or [0])[0] or 0)
    cur.execute(
        """
        SELECT COUNT(*)::int
        FROM intelligence.tracked_events te
        WHERE %s = ANY(COALESCE(te.domain_keys, '{}'))
          AND te.storyline_id IS NOT NULL
        """,
        (domain_key,),
    )
    te_bridged = int((cur.fetchone() or [0])[0] or 0)
    out["tracked_events_total"] = te_total
    out["tracked_events_bridged"] = te_bridged
    out["te_bridge_pct"] = round(100.0 * te_bridged / te_total, 1) if te_total else 0.0

    if has_storylines:
        out["duplicate_title_groups"] = _dup_title_groups(cur, schema)
        cur.execute(
            f"""
            SELECT COUNT(*)::int
            FROM {schema}.storylines s
            WHERE s.merged_into_id IS NULL
              AND COALESCE(s.story_kind, '') <> 'container_index'
              AND s.status NOT IN ('archived', 'concluded')
            """
        )
        episodes = int((cur.fetchone() or [0])[0] or 0)
        cur.execute(
            """
            SELECT COUNT(DISTINCT nt.storyline_id)::int
            FROM intelligence.narrative_threads nt
            WHERE nt.domain_key = %s AND nt.storyline_id IS NOT NULL
            """,
            (domain_key,),
        )
        with_thread = int((cur.fetchone() or [0])[0] or 0)
        out["active_episodes"] = episodes
        out["episodes_with_narrative_thread"] = with_thread
        out["narrative_thread_pct"] = (
            round(100.0 * with_thread / episodes, 1) if episodes else 0.0
        )
    else:
        out["duplicate_title_groups"] = 0
        out["active_episodes"] = 0
        out["episodes_with_narrative_thread"] = 0
        out["narrative_thread_pct"] = 0.0

    return out


def get_linkage_coverage() -> dict[str, Any]:
    """Aggregate orphan/linkage coverage for Monitor and agents."""
    cap = max(100, env_int("LINKAGE_COVERAGE_ORPHAN_CLUSTER_CAP", 50000))
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '12s'")

                cur.execute("SELECT COUNT(*)::int FROM public.chronological_events")
                total_ce = int((cur.fetchone() or [0])[0] or 0)

                cur.execute(
                    """
                    SELECT COUNT(DISTINCT event_id)::int
                    FROM intelligence.event_episode_links
                    WHERE inference_stage <> 'quarantined'
                    """
                )
                linked_ce = int((cur.fetchone() or [0])[0] or 0)

                cur.execute(
                    f"""
                    SELECT COUNT(*)::int FROM (
                      SELECT ce.event_cluster_id
                      FROM public.chronological_events ce
                      WHERE ce.event_cluster_id IS NOT NULL
                        AND NOT EXISTS (
                          SELECT 1 FROM intelligence.event_episode_links eel
                          WHERE eel.event_id = ce.id
                            AND eel.inference_stage <> 'quarantined'
                        )
                      GROUP BY ce.event_cluster_id
                      LIMIT %s
                    ) t
                    """,
                    (cap,),
                )
                orphan_clusters = int((cur.fetchone() or [0])[0] or 0)

                cur.execute(
                    """
                    SELECT COUNT(*)::int FROM intelligence.tracked_events
                    WHERE storyline_id IS NULL
                    """
                )
                te_unlinked = int((cur.fetchone() or [0])[0] or 0)
                cur.execute("SELECT COUNT(*)::int FROM intelligence.tracked_events")
                te_total = int((cur.fetchone() or [0])[0] or 0)

                cur.execute(
                    "SELECT COUNT(*)::int FROM intelligence.narrative_threads"
                )
                narrative_threads = int((cur.fetchone() or [0])[0] or 0)

                graph_links: int | None = None
                if _table_exists(cur, "intelligence", "graph_connection_links"):
                    cur.execute(
                        """
                        SELECT COUNT(*)::int FROM intelligence.graph_connection_links
                        WHERE COALESCE(status, 'active') = 'active'
                        """
                    )
                    graph_links = int((cur.fetchone() or [0])[0] or 0)

                per_domain = []
                dup_total = 0
                for dk in get_pipeline_active_domain_keys():
                    schema = resolve_domain_schema(dk)
                    row = _domain_linkage(cur, dk, schema)
                    dup_total += int(row.get("duplicate_title_groups") or 0)
                    per_domain.append(row)

        return {
            "success": True,
            "global": {
                "chronological_events_total": total_ce,
                "chronological_events_linked": linked_ce,
                "eel_link_pct": round(100.0 * linked_ce / total_ce, 1) if total_ce else 0.0,
                "orphan_clusters": orphan_clusters,
                "orphan_clusters_capped": orphan_clusters >= cap,
                "tracked_events_total": te_total,
                "tracked_events_unlinked": te_unlinked,
                "te_bridge_pct": round(
                    100.0 * (te_total - te_unlinked) / te_total, 1
                )
                if te_total
                else 0.0,
                "duplicate_title_groups": dup_total,
                "narrative_threads": narrative_threads,
                "graph_connection_links_active": graph_links,
            },
            "domains": per_domain,
        }
    except Exception as exc:
        logger.warning("get_linkage_coverage: %s", exc)
        return {"success": False, "error": str(exc)[:240], "global": {}, "domains": []}
