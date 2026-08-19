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
from shared.chronological_event_domain import unlinked_event_domain_predicate  # noqa: E402
from shared.domain_registry import (  # noqa: E402
    get_pipeline_active_domain_keys,
    resolve_domain_schema,
)
from services.story_continuation_service import (  # noqa: E402
    StoryContinuationService,
    continuation_recheck_due_sql,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("continuation_backfill")


async def backfill_domain(domain_key: str, *, limit: int, apply: bool, force_recheck: bool) -> dict:
    schema = resolve_domain_schema(domain_key)
    stats = {"domain": domain_key, "processed": 0, "matched": 0, "founded": 0, "skipped": 0}

    recheck_sql, recheck_params = continuation_recheck_due_sql("ce")
    domain_pred, domain_params = unlinked_event_domain_predicate(schema, domain_key)
    recheck_clause = "TRUE" if force_recheck else recheck_sql
    recheck_bind = () if force_recheck else recheck_params

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT ce.id
                FROM public.chronological_events ce
                WHERE NOT EXISTS (
                    SELECT 1 FROM intelligence.event_episode_links eel
                    WHERE eel.event_id = ce.id
                      AND eel.inference_stage <> 'quarantined'
                  )
                  AND {domain_pred}
                  AND {recheck_clause}
                ORDER BY ce.extraction_timestamp DESC NULLS LAST
                LIMIT %s
                """,
                (*domain_params, *recheck_bind, int(limit)),
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
    ap.add_argument(
        "--force-recheck",
        action="store_true",
        help="Ignore continuation backoff — process events even if recently checked",
    )
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
            out.append(
                await backfill_domain(
                    dk, limit=args.limit, apply=apply, force_recheck=bool(args.force_recheck)
                )
            )
        return out

    results = asyncio.run(_run())
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
