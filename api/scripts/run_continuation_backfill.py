#!/usr/bin/env python3
"""Backfill unlinked events through story continuation (match + optional founding).

  PYTHONPATH=api python3 api/scripts/run_continuation_backfill.py --all --apply --limit 500
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))

from shared.database.connection import get_db_connection_context  # noqa: E402
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema  # noqa: E402
from services.story_continuation_service import StoryContinuationService  # noqa: E402
from services.story_continuation_service import continuation_recheck_due_sql  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("continuation_backfill")


async def backfill_domain(domain_key: str, *, limit: int, apply: bool) -> dict:
    schema = resolve_domain_schema(domain_key)
    stats = {"domain": domain_key, "processed": 0, "matched": 0, "founded": 0, "skipped": 0}

    recheck_sql, recheck_params = continuation_recheck_due_sql("ce")

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT ce.id
                FROM public.chronological_events ce
                JOIN public.articles a ON a.id = ce.source_article_id
                WHERE a.domain_key = %s
                  AND NOT EXISTS (
                    SELECT 1 FROM intelligence.event_episode_links eel
                    WHERE eel.event_id = ce.id
                      AND eel.inference_stage <> 'quarantined'
                  )
                  AND {recheck_sql}
                ORDER BY ce.extraction_timestamp DESC NULLS LAST
                LIMIT %s
                """,
                (domain_key, *recheck_params, int(limit)),
            )
            event_ids = [int(r[0]) for r in cur.fetchall() or []]

        svc = StoryContinuationService(conn, schema=schema)
        for eid in event_ids:
            stats["processed"] += 1
            if not apply:
                stats["skipped"] += 1
                continue
            try:
                result = await svc.match_event_to_storyline(eid)
            except Exception as exc:
                logger.debug("continuation event=%s: %s", eid, exc)
                stats["skipped"] += 1
                continue
            if not result:
                stats["skipped"] += 1
                continue
            if result.get("founded") or result.get("merge_redirect"):
                stats["founded"] += 1
            else:
                stats["matched"] += 1
            if stats["processed"] % 50 == 0:
                logger.info("%s progress %s", domain_key, stats)

    stats["apply"] = apply
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--domain")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=500)
    args = ap.parse_args()
    apply = bool(args.apply) and not args.dry_run
    domains = (
        list(get_pipeline_active_domain_keys())
        if args.all
        else ([args.domain] if args.domain else [])
    )
    if not domains:
        ap.error("Pass --domain or --all")

    async def _run():
        out = []
        for dk in domains:
            out.append(await backfill_domain(dk, limit=args.limit, apply=apply))
        return out

    results = asyncio.run(_run())
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
