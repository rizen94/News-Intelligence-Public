#!/usr/bin/env python3
"""
Clean polluted event chronicles for all (or one) tracked events.

Fixes historical damage from loose chronicle matching:
same-day duplicate rows, off-topic related contexts, bloated domain_keys.

Usage (Widow, maintenance DB port):
  cd /opt/news-intelligence
  DB_PORT=5432 PYTHONPATH=api .venv/bin/python api/scripts/hygiene_event_chronicles.py --dry-run
  DB_PORT=5432 PYTHONPATH=api .venv/bin/python api/scripts/hygiene_event_chronicles.py
  DB_PORT=5432 PYTHONPATH=api .venv/bin/python api/scripts/hygiene_event_chronicles.py --event-id 2532
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("hygiene_event_chronicles")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report only; no writes")
    parser.add_argument("--event-id", type=int, default=None, help="Single event id")
    parser.add_argument("--limit", type=int, default=None, help="Max events to process")
    parser.add_argument(
        "--progress-every",
        type=int,
        default=100,
        help="Log progress every N events",
    )
    args = parser.parse_args()

    # Prefer direct Postgres for bulk maintenance when available.
    if not os.environ.get("DB_PORT"):
        os.environ["DB_PORT"] = os.environ.get("DB_MAINTENANCE_PORT") or "5432"

    from services.event_chronicle_hygiene_service import (
        hygiene_all_tracked_event_chronicles,
    )

    result = hygiene_all_tracked_event_chronicles(
        dry_run=args.dry_run,
        limit=args.limit,
        event_id=args.event_id,
        progress_every=args.progress_every,
    )
    if not result.get("success"):
        logger.error("failed: %s", result)
        return 1
    logger.info(
        "done dry_run=%s events=%s deleted_dupes=%s deleted_empty=%s "
        "filtered_out_devs=%s kept_devs=%s",
        result.get("dry_run"),
        result.get("events"),
        result.get("deleted_dupes"),
        result.get("deleted_empty"),
        result.get("filtered_out_devs"),
        result.get("kept_devs"),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
