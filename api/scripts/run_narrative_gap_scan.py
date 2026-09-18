#!/usr/bin/env python3
"""Scan typed arcs for missing next-stage gaps and enqueue stimulus RAG tickets.

  PYTHONPATH=api python3 api/scripts/run_narrative_gap_scan.py
  PYTHONPATH=api python3 api/scripts/run_narrative_gap_scan.py --domain legal --dry-run
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("run_narrative_gap_scan")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--domain", action="append", dest="domains", default=None)
    p.add_argument("--limit", type=int, default=40)
    p.add_argument("--gap-days", type=int, default=None)
    p.add_argument("--dry-run", action="store_true", help="Detect only; do not enqueue")
    p.add_argument("--auto-queue", action="store_true")
    args = p.parse_args()

    from services.narrative_gap_service import scan_narrative_gaps

    stats = scan_narrative_gaps(
        domain_keys=args.domains,
        limit_per_domain=args.limit,
        gap_days=args.gap_days,
        enqueue=not args.dry_run,
        auto_queue=args.auto_queue,
    )
    logger.info("narrative_gap_scan: %s", stats)
    return 0 if stats.get("enabled", True) or stats.get("gaps", 0) >= 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
