#!/usr/bin/env python3
"""
Operator dry-run for graph link drift review (does not require env flag).

  PYTHONPATH=api python3 api/scripts/run_graph_link_drift_dry_run.py
  PYTHONPATH=api python3 api/scripts/run_graph_link_drift_dry_run.py --limit 20 --apply
"""

from __future__ import annotations

import argparse
import logging
import os

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("run_graph_link_drift_dry_run")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually update/quarantine (default: inspect candidates only)",
    )
    args = parser.parse_args()

    from shared.database.connection import get_db_connection
    from services.graph_link_drift_service import (
        _batch_limit,
        _conf_max,
        _drift_days,
        rescore_active_graph_links,
    )

    days = _drift_days()
    conf_max = _conf_max()
    lim = args.limit or _batch_limit()

    conn = get_db_connection()
    if not conn:
        logger.error("no db")
        return 1
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)::int
                FROM intelligence.graph_connection_links
                WHERE status = 'active'
                  AND (
                    COALESCE(confidence, 0) < %s
                    OR last_scored_at IS NULL
                    OR last_scored_at < NOW() - (%s || ' days')::interval
                  )
                """,
                (conf_max, days),
            )
            eligible = cur.fetchone()[0]
        logger.info(
            "Eligible active links for drift (conf<%s or stale>%sdays): %s",
            conf_max,
            days,
            eligible,
        )
    finally:
        conn.close()

    if not args.apply:
        logger.info(
            "Dry-run only (candidate count). Pass --apply to rescore/quarantine "
            "(writes). Env GRAPH_LINK_DRIFT_REVIEW_ENABLED not required for this script."
        )
        return 0

    # Force-enabled path: call rescore directly
    os.environ.setdefault("GRAPH_LINK_DRIFT_REVIEW_ENABLED", "true")
    stats = rescore_active_graph_links(limit=lim)
    logger.info("rescore_active_graph_links: %s", stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
