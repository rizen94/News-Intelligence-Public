#!/usr/bin/env python3
"""
Weekly batch: auto-merge high-confidence duplicate topic_clusters.

Default dry-run; pass --apply to execute merges (score >= 0.85).
"""

from __future__ import annotations

import argparse
import logging

from domains.content_analysis.services.topic_merge_suggestions import get_merge_suggestions
from shared.database.connection import get_db_connection_context
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema
from shared.topic_cluster_store import sync_cluster_article_count

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

AUTO_MERGE_SCORE = 0.85
MIN_SUGGESTION_SCORE = 0.55


def load_clusters(cur, schema: str, *, limit: int = 5000) -> list[dict]:
    cur.execute(
        f"""
        SELECT tc.id, tc.cluster_name, COALESCE(tc.article_count, 0) AS article_count,
               COALESCE(
                   (SELECT array_agg(tk.keyword ORDER BY tk.importance_score DESC)
                    FROM {schema}.topic_keywords tk
                    WHERE tk.topic_cluster_id = tc.id
                    LIMIT 20),
                   ARRAY[]::text[]
               ) AS keywords
        FROM {schema}.topic_clusters tc
        ORDER BY tc.article_count DESC NULLS LAST, tc.id ASC
        LIMIT %s
        """,
        (limit,),
    )
    rows = []
    for r in cur.fetchall():
        kw = r[3] or []
        rows.append(
            {
                "id": int(r[0]),
                "cluster_name": r[1],
                "article_count": int(r[2] or 0),
                "keywords": list(kw) if kw else [],
            }
        )
    return rows


def merge_pair(cur, schema: str, primary_id: int, secondary_id: int) -> None:
    cur.execute(
        f"""
        INSERT INTO {schema}.article_topic_clusters (article_id, topic_cluster_id, relevance_score, confidence_score)
        SELECT article_id, %s, relevance_score, confidence_score
        FROM {schema}.article_topic_clusters
        WHERE topic_cluster_id = %s
        ON CONFLICT (article_id, topic_cluster_id) DO UPDATE SET
            relevance_score = GREATEST({schema}.article_topic_clusters.relevance_score, EXCLUDED.relevance_score),
            confidence_score = GREATEST({schema}.article_topic_clusters.confidence_score, EXCLUDED.confidence_score)
        """,
        (primary_id, secondary_id),
    )
    cur.execute(
        f"DELETE FROM {schema}.article_topic_clusters WHERE topic_cluster_id = %s",
        (secondary_id,),
    )
    cur.execute(
        f"DELETE FROM {schema}.topic_keywords WHERE topic_cluster_id = %s",
        (secondary_id,),
    )
    cur.execute(f"DELETE FROM {schema}.topic_clusters WHERE id = %s", (secondary_id,))
    sync_cluster_article_count(cur, schema, primary_id)


def run_domain(schema: str, *, apply: bool, min_score: float, auto_score: float, limit: int) -> int:
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            clusters = load_clusters(cur, schema, limit=limit)
            suggestions = get_merge_suggestions(
                clusters, min_score=min_score, max_suggestions=200, name_key="cluster_name"
            )
            merged = 0
            seen_secondary: set[int] = set()
            for s in suggestions:
                if s["score"] < auto_score:
                    continue
                primary_id = int(s["primary"]["id"])
                secondary_id = int(s["secondary"]["id"])
                if secondary_id in seen_secondary or primary_id == secondary_id:
                    continue
                seen_secondary.add(secondary_id)
                msg = (
                    f"merge {s['secondary']['cluster_name']!r} -> {s['primary']['cluster_name']!r} "
                    f"(score={s['score']})"
                )
                if apply:
                    merge_pair(cur, schema, primary_id, secondary_id)
                    conn.commit()
                    logger.info("APPLIED %s", msg)
                else:
                    logger.info("DRY-RUN %s", msg)
                merged += 1
            return merged


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", action="append")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--min-score", type=float, default=MIN_SUGGESTION_SCORE)
    parser.add_argument("--auto-score", type=float, default=AUTO_MERGE_SCORE)
    parser.add_argument("--cluster-limit", type=int, default=5000)
    args = parser.parse_args()
    domains = args.domain or list(get_pipeline_active_domain_keys())
    total = 0
    for dk in domains:
        schema = resolve_domain_schema(dk)
        n = run_domain(
            schema,
            apply=args.apply,
            min_score=args.min_score,
            auto_score=args.auto_score,
            limit=args.cluster_limit,
        )
        logger.info("[%s] %s merges %s", dk, "applied" if args.apply else "suggested", n)
        total += n
    logger.info("total: %s", total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
