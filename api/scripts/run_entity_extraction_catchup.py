#!/usr/bin/env python3
"""
Bulk entity extraction + entity profile sync for pipeline domains.

Mirrors automation_manager._execute_entity_extraction with post-sync profiles.

  PYTHONPATH=api uv run python api/scripts/run_entity_extraction_catchup.py
  PYTHONPATH=api uv run python api/scripts/run_entity_extraction_catchup.py --domains legal,medicine --max-articles 200
  PYTHONPATH=api uv run python api/scripts/run_entity_extraction_catchup.py --sync-only
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from shared.database.connection import get_db_connection_context
from shared.domain_registry import get_pipeline_active_domain_keys, pipeline_url_schema_pairs, resolve_domain_schema
from shared.pipeline_pass_marker import phase_backlog_uses_pass_marker, record_article_phase_pass, sql_article_pass_null
from shared.pipeline_article_selection import sql_order_created_at

logger = logging.getLogger(__name__)


def _pending_count(schema: str) -> int:
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT COUNT(*)
                FROM {schema}.articles a
                LEFT JOIN {schema}.article_entities ae ON ae.article_id = a.id
                WHERE ae.id IS NULL
                  AND a.content IS NOT NULL
                  AND LENGTH(a.content) > 100
                  AND COALESCE(
                    (a.metadata #>> '{{pipeline_skip,entity_extraction_skip}}')::boolean,
                    false
                  ) = false
                """
            )
            return int(cur.fetchone()[0] or 0)


def _fetch_batch(schema: str, *, limit: int) -> list[tuple[int, str, str]]:
    pass_clause = ""
    if phase_backlog_uses_pass_marker("entity_extraction"):
        pass_clause = f" AND ({sql_article_pass_null('entity_extraction', 'a')}) "
    _ord = sql_order_created_at()
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT a.id, a.title, a.content
                FROM {schema}.articles a
                LEFT JOIN {schema}.article_entities ae ON ae.article_id = a.id
                WHERE ae.id IS NULL
                  AND COALESCE(
                    (a.metadata #>> '{{pipeline_skip,entity_extraction_skip}}')::boolean,
                    false
                  ) = false
                  AND a.content IS NOT NULL
                  AND LENGTH(a.content) > 100
                  AND (
                    LENGTH(a.content) >= 500
                    OR a.created_at < NOW() - INTERVAL '2 hours'
                    OR COALESCE(a.enrichment_status, '') IN (
                        'enriched', 'failed', 'inaccessible'
                    )
                  )
                  {pass_clause}
                ORDER BY a.created_at {_ord}
                LIMIT %s
                """,
                (limit,),
            )
            return [(int(r[0]), r[1] or "", r[2] or "") for r in cur.fetchall()]


async def _extract_batch(
    domain_key: str,
    schema: str,
    rows: list[tuple[int, str, str]],
    *,
    parallel: int,
) -> dict[str, int]:
    from services.article_entity_extraction_service import ArticleEntityExtractionService

    extractor = ArticleEntityExtractionService()
    sem = asyncio.Semaphore(max(1, parallel))
    ok = 0
    fail = 0

    async def _one(article_id: int, title: str, content: str) -> bool:
        nonlocal ok, fail
        async with sem:
            try:
                result = await extractor.extract_and_store(
                    article_id=article_id,
                    title=title,
                    content=content,
                    schema=schema,
                )
                success = bool(result.get("success"))
                if success:
                    cnt = (result.get("counts") or {}).get("entities") or 0
                    record_article_phase_pass(
                        schema,
                        article_id,
                        "entity_extraction",
                        "entities_stored" if int(cnt) > 0 else "no_entities_stored",
                    )
                    ok += 1
                else:
                    fail += 1
                return success
            except Exception as e:
                logger.warning("extract article %s (%s): %s", article_id, domain_key, e)
                fail += 1
                return False

    if rows:
        await asyncio.gather(*[_one(aid, t, c) for aid, t, c in rows])
    return {"ok": ok, "fail": fail, "batch_size": len(rows)}


def _sync_domain(domain_key: str) -> dict[str, int]:
    from services.entity_profile_sync_service import backfill_entity_canonical, sync_domain_entity_profiles

    canonical_new = backfill_entity_canonical(domain_key)
    mappings_new = sync_domain_entity_profiles(domain_key)
    schema = resolve_domain_schema(domain_key)
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {schema}.entity_canonical")
            canonical = cur.fetchone()[0] or 0
            cur.execute(
                "SELECT COUNT(*) FROM intelligence.entity_profiles WHERE domain_key = %s",
                (domain_key,),
            )
            profiles = cur.fetchone()[0] or 0
    return {
        "canonical_new": canonical_new,
        "mappings_new": mappings_new,
        "entity_canonical": canonical,
        "entity_profiles": profiles,
    }


async def _run_domains(
    domains: list[str],
    *,
    batch_size: int,
    max_articles: int,
    parallel: int,
    sync_each_round: bool,
) -> dict[str, object]:
    pairs = [(dk, sch) for dk, sch in pipeline_url_schema_pairs() if dk in domains]
    summary: dict[str, object] = {}

    for domain_key, schema in pairs:
        processed = 0
        rounds = 0
        domain_stats: list[dict] = []
        pending_start = _pending_count(schema)
        print(f"\n=== {domain_key} pending={pending_start} ===")

        while processed < max_articles:
            pending = _pending_count(schema)
            if pending <= 0:
                print(f"  {domain_key}: idle (no pending articles)")
                break
            lim = min(batch_size, max_articles - processed, pending)
            rows = _fetch_batch(schema, limit=lim)
            if not rows:
                print(f"  {domain_key}: no eligible batch (pass markers / content gates?)")
                break
            batch = await _extract_batch(domain_key, schema, rows, parallel=parallel)
            processed += batch["batch_size"]
            rounds += 1
            domain_stats.append(batch)
            print(f"  round {rounds}: {json.dumps(batch)} pending_remaining≈{_pending_count(schema)}")
            if sync_each_round:
                sync = _sync_domain(domain_key)
                print(f"  sync: {json.dumps(sync)}")
            if batch["batch_size"] == 0:
                break

        if not sync_each_round:
            sync = _sync_domain(domain_key)
            print(f"  final sync: {json.dumps(sync)}")
        else:
            sync = _sync_domain(domain_key)

        summary[domain_key] = {
            "pending_start": pending_start,
            "articles_processed": processed,
            "rounds": rounds,
            "batches": domain_stats,
            "sync": sync,
            "pending_end": _pending_count(schema),
        }

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Entity extraction catch-up + profile sync")
    parser.add_argument(
        "--domains",
        default=",".join(get_pipeline_active_domain_keys()),
        help="Comma-separated domain keys",
    )
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument(
        "--max-articles",
        type=int,
        default=0,
        help="Max articles per domain (0 = drain all pending)",
    )
    parser.add_argument("--parallel", type=int, default=4)
    parser.add_argument(
        "--sync-only",
        action="store_true",
        help="Skip extraction; only backfill canonical + entity_profiles",
    )
    parser.add_argument(
        "--sync-each-round",
        action="store_true",
        default=True,
        help="Sync profiles after each batch (default on)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    domains = [d.strip() for d in args.domains.split(",") if d.strip()]
    max_articles = args.max_articles if args.max_articles > 0 else 10_000_000

    if args.sync_only:
        out = {}
        for dk in domains:
            print(f"\n=== sync-only {dk} ===")
            out[dk] = _sync_domain(dk)
            print(json.dumps(out[dk], indent=2))
        return 0

    summary = asyncio.run(
        _run_domains(
            domains,
            batch_size=max(5, min(120, args.batch_size)),
            max_articles=max_articles,
            parallel=max(1, min(16, args.parallel)),
            sync_each_round=args.sync_each_round,
        )
    )
    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
