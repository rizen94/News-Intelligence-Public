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
from shared.domain_registry import get_pipeline_active_domain_keys  # noqa: E402
from services.episode_assembly_maintenance_service import continuation_backfill_domain  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


async def _run_domains(domains: list[str], *, limit: int, apply: bool, force_recheck: bool) -> list[dict]:
    results = []
    with get_db_connection_context() as conn:
        for dk in domains:
            results.append(
                await continuation_backfill_domain(
                    conn, dk, limit=limit, force_recheck=force_recheck, apply=apply
                )
            )
    return results


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

    results = asyncio.run(
        _run_domains(domains, limit=args.limit, apply=apply, force_recheck=bool(args.force_recheck))
    )
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
