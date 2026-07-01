#!/usr/bin/env python3
"""
Sample fused vs legacy extraction quality on recent articles (pre-rollout gate).

Usage:
  PYTHONPATH=api python3 api/scripts/verify_intake_fusion_quality.py --limit 100
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from config.catchup_defaults import apply_catchup_env_defaults
from shared.database.connection import get_db_connection_context
from shared.domain_registry import pipeline_url_schema_pairs
from shared.pipeline_pass_marker import sql_article_pass_cleared


def _load_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    apply_catchup_env_defaults()


def _fetch_sample_articles(limit: int) -> list[dict[str, Any]]:
    per_schema = max(5, limit // 5)
    rows: list[dict[str, Any]] = []
    for domain_key, schema in pipeline_url_schema_pairs():
        if len(rows) >= limit:
            break
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT a.id, a.title, a.content, a.published_at,
                           (
                               SELECT sa.storyline_id::text
                               FROM {schema}.storyline_articles sa
                               WHERE sa.article_id = a.id
                               ORDER BY sa.added_at DESC NULLS LAST
                               LIMIT 1
                           ) AS storyline_id
                    FROM {schema}.articles a
                    WHERE a.content IS NOT NULL
                      AND LENGTH(a.content) > 200
                      AND ({sql_article_pass_cleared("unified_intake_extraction", "a")})
                    ORDER BY a.updated_at DESC NULLS LAST
                    LIMIT %s
                    """,
                    (per_schema,),
                )
                for r in cur.fetchall():
                    rows.append(
                        {
                            "article_id": int(r[0]),
                            "title": r[1] or "",
                            "content": r[2],
                            "pub_date": r[3],
                            "storyline_id": r[4],
                            "schema": schema,
                            "domain_key": domain_key,
                        }
                    )
                    if len(rows) >= limit:
                        break
    return rows[:limit]


def _entity_count(schema: str, article_id: int) -> int:
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) FROM {schema}.article_entities WHERE article_id = %s",
                (article_id,),
            )
            return int(cur.fetchone()[0] or 0)


def _event_count(article_id: int) -> int:
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM public.chronological_events WHERE source_article_id = %s",
                (article_id,),
            )
            return int(cur.fetchone()[0] or 0)


def _claim_count(schema: str, article_id: int) -> int:
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(ec.id)
                FROM intelligence.extracted_claims ec
                JOIN intelligence.article_to_context atc ON atc.context_id = ec.context_id
                WHERE atc.article_id = %s AND atc.domain_key = %s
                """,
                (article_id, schema.replace("_", "-")),
            )
            return int(cur.fetchone()[0] or 0)


async def _run_fusion_sample(articles: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    from services.unified_intake_extraction_service import UnifiedIntakeExtractionService

    svc = UnifiedIntakeExtractionService()
    try:
        batch_size = 6
        out: dict[int, dict[str, Any]] = {}
        for i in range(0, len(articles), batch_size):
            chunk = articles[i : i + batch_size]
            results = await svc.extract_batch(chunk)
            out.update(results)
        return out
    finally:
        await svc.close()


def main() -> int:
    _load_env()
    parser = argparse.ArgumentParser(description="Intake fusion quality regression sample")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true", help="Only report DB baselines, no LLM")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    articles = _fetch_sample_articles(args.limit)
    if not articles:
        print("No unified-complete sample articles found.", file=sys.stderr)
        return 1

    baseline = []
    for art in articles:
        aid = int(art["article_id"])
        schema = art["schema"]
        baseline.append(
            {
                "article_id": aid,
                "schema": schema,
                "entities": _entity_count(schema, aid),
                "events": _event_count(aid),
                "claims": _claim_count(schema, aid),
            }
        )

    report: dict[str, Any] = {
        "sample_size": len(articles),
        "baseline": baseline,
        "fusion_rerun": None,
    }

    if not args.dry_run:
        fusion = asyncio.run(_run_fusion_sample(articles))
        deltas = []
        for art in articles:
            aid = int(art["article_id"])
            schema = art["schema"]
            base = next(b for b in baseline if b["article_id"] == aid)
            fr = fusion.get(aid) or {}
            deltas.append(
                {
                    "article_id": aid,
                    "schema": schema,
                    "fusion_success": bool(fr.get("success")),
                    "entities_delta": int(fr.get("entities") or 0) - base["entities"],
                    "events_delta": int(fr.get("events") or 0) - base["events"],
                    "claims_delta": int(fr.get("claims") or 0) - base["claims"],
                }
            )
        report["fusion_rerun"] = deltas
        empty_ok = sum(1 for d in deltas if d["fusion_success"])
        report["fusion_success_rate"] = round(empty_ok / max(1, len(deltas)), 3)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(f"Sample articles: {len(articles)}")
        if report.get("fusion_rerun") is not None:
            print(f"Fusion success rate: {report.get('fusion_success_rate')}")
            regressions = [
                d
                for d in report["fusion_rerun"]
                if d["entities_delta"] < -3 or d["events_delta"] < -1
            ]
            print(f"Large regressions (entities<-3 or events<-1): {len(regressions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
