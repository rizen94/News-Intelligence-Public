"""
One-shot pass: apply pre-filters to all unresolved entity strings
in extracted_claims and write negative-cache entries so the resolver
skips them.
"""

import argparse
import logging
import os
import sys

import psycopg2
import psycopg2.extras

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.entity_filters import classify_bad_entity

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-password", required=True)
    parser.add_argument("--dry-run", action="store_true",
                        help="Count only, don't write to DB")
    parser.add_argument("--batch-size", type=int, default=5000)
    args = parser.parse_args()

    conn = psycopg2.connect(
        host="192.168.93.101",
        port=5432,
        dbname="news_intel",
        user="newsapp",
        password=args.db_password,
    )
    cur = conn.cursor()

    # Fetch all unresolved entity strings (same query the resolver uses)
    log.info("Fetching unresolved entity strings ...")
    cur.execute("""
        SELECT DISTINCT lower(trim(ec.subject_text)) AS entity
          FROM intelligence.extracted_claims ec
     LEFT JOIN intelligence.wikipedia_negative_cache nc
            ON nc.title_lower = lower(trim(ec.subject_text))
         WHERE nc.title_lower IS NULL
           AND trim(ec.subject_text) != ''
           AND ec.subject_text != '_skip'
         ORDER BY entity
    """)
    rows = cur.fetchall()
    log.info("Found %d unresolved entity strings.", len(rows))

    filtered = 0
    passed = 0
    sample_passed = []

    for i, (entity,) in enumerate(rows):
        reason = classify_bad_entity(entity, None)
        if reason:
            filtered += 1
            if not args.dry_run:
                cur.execute("""
                    INSERT INTO intelligence.wikipedia_negative_cache
                           (title_lower, reason, methods_tried, attempts,
                            first_seen, last_attempted)
                    VALUES (%s, %s, %s, 1, NOW(), NOW())
                    ON CONFLICT (title_lower) DO NOTHING
                """, (entity, f"pre-filter: {reason}", ["pre-filter"]))
        else:
            passed += 1
            if len(sample_passed) < 50:
                sample_passed.append(entity)

        if (i + 1) % args.batch_size == 0:
            if not args.dry_run:
                conn.commit()
            log.info("  processed %d / %d  (filtered: %d, passed: %d)",
                     i + 1, len(rows), filtered, passed)

    if not args.dry_run:
        conn.commit()

    cur.close()
    conn.close()

    log.info("Done. Total: %d | Filtered: %d | Passed (real entities): %d",
             len(rows), filtered, passed)

    if sample_passed:
        log.info("Sample entities that PASSED the filter (will need Wikipedia lookup):")
        for e in sample_passed:
            log.info("  %s", e)


if __name__ == "__main__":
    main()
