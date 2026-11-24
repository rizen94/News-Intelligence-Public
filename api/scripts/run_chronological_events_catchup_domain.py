#!/usr/bin/env python3
"""Drain CE catchup for one domain (enriched+entity rows included)."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
for p in (ROOT, os.path.join(ROOT, "api")):
    if p not in sys.path:
        sys.path.insert(0, p)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from api.shared.domain_registry import resolve_domain_schema
    from services.chronological_events_catchup_service import (
        batch_limit,
        list_articles_needing_chrono,
        run_catchup_batch,
    )

    schema = resolve_domain_schema(args.domain)
    lim = min(args.limit, batch_limit() * 10)
    articles = list_articles_needing_chrono(schema=schema, limit=lim)
    print(f"domain={args.domain} schema={schema} backlog={len(articles)} dry_run={args.dry_run}")
    if args.dry_run or not articles:
        return 0

    async def _run() -> dict:
        return await run_catchup_batch(domain_key=args.domain, limit=lim, force=True)

    stats = asyncio.run(_run())
    print(stats)
    return 0 if stats.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())