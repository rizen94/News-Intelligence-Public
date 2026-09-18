#!/usr/bin/env python3
"""
One-shot purge of legacy mega cross-domain correlation bags.

Deletes intelligence.cross_domain_correlations rows where
cardinality(event_ids) > 12 (same rule as cross_domain_synthesis).

  PYTHONPATH=api python3 api/scripts/purge_cross_domain_mega_bags.py --dry-run
  PYTHONPATH=api python3 api/scripts/purge_cross_domain_mega_bags.py --apply
"""

from __future__ import annotations

import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("purge_cross_domain_mega_bags")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report only")
    parser.add_argument("--apply", action="store_true", help="Delete mega bags")
    args = parser.parse_args()
    apply = bool(args.apply) and not args.dry_run

    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        logger.error("no db connection")
        return 1
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT correlation_id, domain_1, domain_2, correlation_type,
                       cardinality(COALESCE(event_ids, '{}')) AS n_events
                FROM intelligence.cross_domain_correlations
                WHERE cardinality(COALESCE(event_ids, '{}')) > 12
                ORDER BY n_events DESC
                LIMIT 200
                """
            )
            rows = cur.fetchall()
            logger.info("Found %s mega-bag correlation rows (showing up to 200)", len(rows))
            for r in rows[:30]:
                logger.info(
                    "  %s %s↔%s type=%s events=%s",
                    r[0],
                    r[1],
                    r[2],
                    r[3],
                    r[4],
                )
            if not apply:
                cur.execute(
                    """
                    SELECT COUNT(*)::int
                    FROM intelligence.cross_domain_correlations
                    WHERE cardinality(COALESCE(event_ids, '{}')) > 12
                    """
                )
                total = cur.fetchone()[0]
                logger.info("Dry-run: would delete %s rows", total)
                conn.rollback()
                return 0

            cur.execute(
                """
                DELETE FROM intelligence.cross_domain_correlations
                WHERE cardinality(COALESCE(event_ids, '{}')) > 12
                """
            )
            deleted = cur.rowcount or 0
            conn.commit()
            logger.info("Deleted %s mega-bag correlation rows", deleted)

            cur.execute(
                """
                SELECT COUNT(*)::int
                FROM intelligence.cross_domain_correlations
                WHERE cardinality(COALESCE(event_ids, '{}')) > 12
                """
            )
            remaining = cur.fetchone()[0]
            logger.info("Remaining mega-bags: %s", remaining)
            return 0 if remaining == 0 else 2
    except Exception as e:
        logger.error("purge failed: %s", e)
        conn.rollback()
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
