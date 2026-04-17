#!/usr/bin/env python3
"""
Batch spaCy entity cleanup — validates existing entity_canonical rows
and removes garbage that should never have been stored.

Usage:
    # Dry run (report only):
    PYTHONPATH=api uv run python scripts/run_spacy_entity_cleanup.py --dry-run

    # Live cleanup:
    PYTHONPATH=api uv run python scripts/run_spacy_entity_cleanup.py

    # Single domain:
    PYTHONPATH=api uv run python scripts/run_spacy_entity_cleanup.py --domain politics

    # Skip spaCy (heuristics only, fast):
    PYTHONPATH=api uv run python scripts/run_spacy_entity_cleanup.py --heuristics-only

    # Test with a small batch first:
    PYTHONPATH=api uv run python scripts/run_spacy_entity_cleanup.py --dry-run --limit 200
"""

import argparse
import gc
import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-6s %(message)s",
)
logger = logging.getLogger(__name__)

CHUNK_SIZE = 200


def main():
    parser = argparse.ArgumentParser(description="Batch entity cleanup with spaCy NER validation")
    parser.add_argument("--dry-run", action="store_true", help="Report only, no DB changes")
    parser.add_argument("--domain", type=str, default=None, help="Single domain key (default: all)")
    parser.add_argument("--heuristics-only", action="store_true", help="Skip spaCy, use heuristics only")
    parser.add_argument("--limit", type=int, default=None, help="Max entities to process per domain (for testing)")
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE, help="Rows per processing chunk")
    args = parser.parse_args()

    from shared.database.connection import get_db_connection
    from shared.domain_registry import get_active_domain_keys, domain_key_to_schema
    from shared.services.spacy_ner_service import get_spacy_ner_service, is_garbage_entity_name

    ner = get_spacy_ner_service()
    use_spacy = not args.heuristics_only and ner.is_available

    if use_spacy:
        logger.info("spaCy model: %s", ner.model_name)
    elif not args.heuristics_only:
        logger.warning("spaCy not available — falling back to heuristics only")
    else:
        logger.info("Heuristics-only mode (--heuristics-only)")

    domains = [args.domain] if args.domain else list(get_active_domain_keys())
    grand_total = 0
    grand_garbage = 0

    for domain_key in domains:
        schema = domain_key_to_schema(domain_key)
        logger.info("=== Processing domain: %s (schema: %s) ===", domain_key, schema)

        conn = get_db_connection()
        if not conn:
            logger.error("No DB connection for %s", domain_key)
            continue
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {schema}.entity_canonical")
                total = cur.fetchone()[0]
        except Exception as e:
            logger.error("Failed to count entity_canonical for %s: %s", domain_key, e)
            conn.close()
            continue
        conn.close()

        effective_total = min(total, args.limit) if args.limit else total
        grand_total += effective_total
        logger.info("  Found %d canonical entities (processing %d)", total, effective_total)

        if effective_total == 0:
            continue

        all_garbage_ids = []
        processed = 0
        offset = 0

        while processed < effective_total:
            chunk_limit = min(args.chunk_size, effective_total - processed)

            conn = get_db_connection()
            if not conn:
                logger.error("  Lost DB connection at offset %d", offset)
                break
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT id, canonical_name, entity_type
                        FROM {schema}.entity_canonical
                        ORDER BY id
                        LIMIT %s OFFSET %s
                        """,
                        (chunk_limit, offset),
                    )
                    rows = cur.fetchall()
            except Exception as e:
                logger.error("  Fetch failed at offset %d: %s", offset, e)
                conn.close()
                break
            conn.close()

            if not rows:
                break

            chunk_garbage = []
            chunk_remaining = []
            for row_id, name, etype in rows:
                if is_garbage_entity_name(name):
                    chunk_garbage.append(row_id)
                else:
                    chunk_remaining.append((row_id, name, etype))

            if use_spacy and chunk_remaining:
                to_validate = [
                    (rid, name, etype)
                    for rid, name, etype in chunk_remaining
                    if etype in ("person", "organization")
                ]
                for rid, name, etype in to_validate:
                    if not ner.validate_entity_name(name, entity_type=etype):
                        chunk_garbage.append(rid)

            all_garbage_ids.extend(chunk_garbage)
            processed += len(rows)
            offset += len(rows)

            logger.info(
                "  Chunk %d-%d: %d garbage / %d rows (running total: %d garbage)",
                offset - len(rows),
                offset,
                len(chunk_garbage),
                len(rows),
                len(all_garbage_ids),
            )

            del rows, chunk_remaining, chunk_garbage
            gc.collect()

        grand_garbage += len(all_garbage_ids)

        if all_garbage_ids:
            sample_ids = all_garbage_ids[:30]
            conn = get_db_connection()
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            f"""
                            SELECT id, canonical_name, entity_type
                            FROM {schema}.entity_canonical
                            WHERE id = ANY(%s)
                            """,
                            (sample_ids,),
                        )
                        samples = cur.fetchall()
                    logger.info("  Sample garbage entities:")
                    for sid, sname, stype in samples:
                        logger.info("    [%s] %s (id=%d)", stype, sname, sid)
                except Exception:
                    pass
                conn.close()

        if args.dry_run:
            logger.info("  DRY RUN: would remove %d entities", len(all_garbage_ids))
            continue

        if not all_garbage_ids:
            logger.info("  No garbage to remove")
            continue

        delete_batch_size = 500
        total_deleted = 0
        total_unlinked = 0

        for i in range(0, len(all_garbage_ids), delete_batch_size):
            batch_ids = all_garbage_ids[i : i + delete_batch_size]

            conn = get_db_connection()
            if not conn:
                logger.error("  No DB connection for deletion batch at %d", i)
                break

            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        UPDATE {schema}.article_entities
                        SET canonical_entity_id = NULL
                        WHERE canonical_entity_id = ANY(%s)
                        """,
                        (batch_ids,),
                    )
                    total_unlinked += cur.rowcount

                    for intel_sql in [
                        "DELETE FROM intelligence.old_entity_to_new WHERE domain_key = %s AND old_entity_id = ANY(%s)",
                        "DELETE FROM intelligence.entity_profiles WHERE domain_key = %s AND canonical_entity_id = ANY(%s)",
                    ]:
                        try:
                            cur.execute(intel_sql, (domain_key, batch_ids))
                        except Exception:
                            pass

                    cur.execute(
                        f"DELETE FROM {schema}.entity_canonical WHERE id = ANY(%s)",
                        (batch_ids,),
                    )
                    total_deleted += cur.rowcount

                conn.commit()
            except Exception as e:
                logger.error("  Deletion batch %d failed: %s", i, e)
                try:
                    conn.rollback()
                except Exception:
                    pass
            finally:
                conn.close()

        logger.info(
            "  DELETED %d garbage entities (%d article links cleared)",
            total_deleted,
            total_unlinked,
        )

    logger.info("=" * 60)
    logger.info(
        "DONE. Total entities: %d | Garbage found: %d | Clean: %d",
        grand_total,
        grand_garbage,
        grand_total - grand_garbage,
    )
    if args.dry_run:
        logger.info("(DRY RUN — no changes made. Remove --dry-run to delete.)")


if __name__ == "__main__":
    main()
