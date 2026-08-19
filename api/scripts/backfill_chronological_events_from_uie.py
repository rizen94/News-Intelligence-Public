#!/usr/bin/env python3
"""
Re-extract chronological_events for UIE-complete articles that have none
(post-flush recovery). Does not re-run full unified intake.

Usage:
  ENVIRONMENT=production DB_PORT=5432 PYTHONPATH=api \\
    python3 api/scripts/backfill_chronological_events_from_uie.py --dry-run --limit 3
  ENVIRONMENT=production DB_PORT=5432 PYTHONPATH=api \\
    python3 api/scripts/backfill_chronological_events_from_uie.py --domain politics --limit 10
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill chronological_events via direct event extraction"
    )
    parser.add_argument("--domain", help="Single domain_key")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--lookback-days", type=int, default=180)
    parser.add_argument(
        "--llm-batch",
        type=int,
        help="Articles per LLM call (default CHRONOLOGICAL_EVENTS_CATCHUP_LLM_BATCH, 1 disables)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore CHRONOLOGICAL_EVENTS_CATCHUP_ENABLED=false",
    )
    args = parser.parse_args()

    from services.chronological_events_catchup_service import run_catchup_batch_sync

    stats = run_catchup_batch_sync(
        limit=args.limit,
        lookback_days=args.lookback_days,
        domain_key=args.domain,
        dry_run=args.dry_run,
        force=args.force or True,
        llm_batch=args.llm_batch,
    )
    print(json.dumps(stats, indent=2, default=str))
    if stats.get("skipped"):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
