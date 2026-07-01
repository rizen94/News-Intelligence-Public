#!/usr/bin/env python3
"""
Batched dedupe of intelligence.entity_relationships before unique index.

1. Normalize swapped (A,B)/(B,A) pairs for co_mentioned (keep lower id row, delete higher).
2. Delete exact duplicate rows keeping MIN(id) per edge key.

Usage:
  PYTHONPATH=. python3 scripts/dedupe_entity_relationships.py --dry-run
  PYTHONPATH=. python3 scripts/dedupe_entity_relationships.py --batch-size 50000
"""

from __future__ import annotations

import argparse
import logging
import time

from shared.database.connection import get_db_connection_context

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _estimate_rows(cur) -> int:
    cur.execute(
        """
        SELECT reltuples::bigint FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'intelligence' AND c.relname = 'entity_relationships'
        """
    )
    row = cur.fetchone()
    return int(row[0] or 0) if row else 0


def _count_exact_duplicates(cur) -> int:
    cur.execute(
        """
        SELECT COALESCE(SUM(cnt - 1), 0)::bigint FROM (
            SELECT COUNT(*)::bigint AS cnt
            FROM intelligence.entity_relationships
            GROUP BY source_domain, source_entity_id, target_domain, target_entity_id, relationship_type
            HAVING COUNT(*) > 1
        ) d
        """
    )
    return int(cur.fetchone()[0] or 0)


def dedupe_exact_duplicates(cur, *, batch_size: int, dry_run: bool) -> int:
    total = 0
    while True:
        if dry_run:
            logger.info("dry-run exact duplicates: skipped (use batched apply)")
            return 0
        cur.execute(
            f"""
            WITH dups AS (
                SELECT id
                FROM (
                    SELECT id,
                           ROW_NUMBER() OVER (
                               PARTITION BY source_domain, source_entity_id,
                                            target_domain, target_entity_id, relationship_type
                               ORDER BY id
                           ) AS rn
                    FROM intelligence.entity_relationships
                ) ranked
                WHERE rn > 1
                LIMIT %s
            )
            DELETE FROM intelligence.entity_relationships er
            USING dups
            WHERE er.id = dups.id
            """,
            (batch_size,),
        )
        deleted = int(cur.rowcount or 0)
        total += deleted
        if deleted == 0:
            break
        logger.info("deleted exact duplicate batch: %s (running total %s)", deleted, total)
    return total


def normalize_swapped_pairs(cur, *, batch_size: int, dry_run: bool) -> int:
    """Remove reverse-direction co_mentioned duplicates (keep canonical lower-id row)."""
    total = 0
    while True:
        if dry_run:
            logger.info("dry-run swapped pairs: skipped (use batched apply)")
            return 0
        cur.execute(
            f"""
            WITH reversed AS (
                SELECT b.id AS delete_id
                FROM intelligence.entity_relationships a
                JOIN intelligence.entity_relationships b
                  ON a.source_domain = b.target_domain
                 AND a.source_entity_id = b.target_entity_id
                 AND a.target_domain = b.source_domain
                 AND a.target_entity_id = b.source_entity_id
                 AND a.relationship_type = b.relationship_type
                 AND a.relationship_type = 'co_mentioned'
                 AND a.id < b.id
                LIMIT %s
            )
            DELETE FROM intelligence.entity_relationships er
            USING reversed
            WHERE er.id = reversed.delete_id
            """,
            (batch_size,),
        )
        deleted = int(cur.rowcount or 0)
        total += deleted
        if deleted == 0:
            break
        logger.info("deleted swapped-pair batch: %s (running total %s)", deleted, total)
    return total


def rebuild_deduped_table(cur) -> int:
    """One-pass dedupe via DISTINCT ON — faster than repeated full-table window scans."""
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS intelligence.entity_relationships_dedup (
            LIKE intelligence.entity_relationships INCLUDING DEFAULTS INCLUDING CONSTRAINTS
        )
        """
    )
    cur.execute("TRUNCATE intelligence.entity_relationships_dedup")
    cur.execute(
        """
        INSERT INTO intelligence.entity_relationships_dedup
        SELECT DISTINCT ON (
            source_domain, source_entity_id, target_domain, target_entity_id, relationship_type
        ) *
        FROM intelligence.entity_relationships
        ORDER BY source_domain, source_entity_id, target_domain, target_entity_id,
                 relationship_type, id
        """
    )
    cur.execute("SELECT COUNT(*)::bigint FROM intelligence.entity_relationships_dedup")
    new_count = int(cur.fetchone()[0] or 0)
    cur.execute(
        """
        ALTER TABLE intelligence.entity_relationships RENAME TO entity_relationships_pre_dedup;
        ALTER TABLE intelligence.entity_relationships_dedup RENAME TO entity_relationships;
        ALTER SEQUENCE intelligence.entity_relationships_id_seq OWNED BY intelligence.entity_relationships.id;
        """
    )
    logger.info(
        "rebuild complete: %s unique rows; old table renamed entity_relationships_pre_dedup "
        "(drop after: ALTER SEQUENCE ... OWNED BY already applied)",
        new_count,
    )
    return new_count


def main() -> int:
    parser = argparse.ArgumentParser(description="Dedupe intelligence.entity_relationships")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=50_000)
    parser.add_argument("--skip-swapped", action="store_true")
    parser.add_argument(
        "--rebuild-table",
        action="store_true",
        help="One-pass DISTINCT ON + table swap (preferred for 10M+ rows)",
    )
    args = parser.parse_args()

    t0 = time.time()
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = 0")
            est = _estimate_rows(cur)
            logger.info("estimated rows before: %s", est)
            if args.dry_run:
                logger.info(
                    "dry-run: estimated %s rows; use --rebuild-table or batched apply",
                    est,
                )
                return 0
            if args.rebuild_table:
                new_count = rebuild_deduped_table(cur)
                conn.commit()
                logger.info("done rebuild elapsed=%.1fs rows=%s", time.time() - t0, new_count)
                return 0
            swapped = 0 if args.skip_swapped else normalize_swapped_pairs(
                cur, batch_size=args.batch_size, dry_run=False
            )
            exact = dedupe_exact_duplicates(
                cur, batch_size=args.batch_size, dry_run=False
            )
            conn.commit()
            est_after = _estimate_rows(cur)
    logger.info(
        "done swapped=%s exact=%s dry_run=%s elapsed=%.1fs est_after=%s",
        swapped,
        exact,
        args.dry_run,
        time.time() - t0,
        est_after,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
