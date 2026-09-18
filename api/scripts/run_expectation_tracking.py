#!/usr/bin/env python3
"""Harvest and resolve narrative expectations (forward-looking claims).

  PYTHONPATH=api python3 api/scripts/run_expectation_tracking.py
  PYTHONPATH=api python3 api/scripts/run_expectation_tracking.py --harvest-only
  PYTHONPATH=api python3 api/scripts/run_expectation_tracking.py --resolve-only
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("run_expectation_tracking")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--domain", default=None)
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--harvest-only", action="store_true")
    p.add_argument("--resolve-only", action="store_true")
    args = p.parse_args()

    from services.expectation_tracking_service import (
        harvest_expectations_from_claims,
        resolve_overdue_expectations,
    )

    if not args.resolve_only:
        h = harvest_expectations_from_claims(domain_key=args.domain, limit=args.limit)
        logger.info("harvest: %s", h)
    if not args.harvest_only:
        r = resolve_overdue_expectations(limit=args.limit)
        logger.info("resolve: %s", r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
