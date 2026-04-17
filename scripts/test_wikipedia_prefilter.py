"""
Diagnostic: run the Wikipedia pre-filter against all entities and report
what would be resolved vs. skipped, broken down by entity_type and reason.

Usage:
    PYTHONPATH=api uv run python scripts/test_wikipedia_prefilter.py
    PYTHONPATH=api uv run python scripts/test_wikipedia_prefilter.py --show-samples 20
    PYTHONPATH=api uv run python scripts/test_wikipedia_prefilter.py --type subject
"""

import argparse
import logging
import os
import sys
from collections import Counter, defaultdict

import psycopg2
import psycopg2.extras

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.wikipedia_prefilter import is_wikipedia_resolvable

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

DB_URL = os.environ["DATABASE_URL"]


def main():
    parser = argparse.ArgumentParser(description="Test Wikipedia pre-filter against entity data")
    parser.add_argument("--show-samples", type=int, default=10,
                        help="Number of sample entities to show per category")
    parser.add_argument("--type", type=str, default=None,
                        help="Filter to a specific entity_type")
    parser.add_argument("--unresolved-only", action="store_true",
                        help="Only consider entities without a wikipedia_page_id")
    args = parser.parse_args()

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    query = """
        SELECT id, canonical_name, entity_type, wikipedia_page_id
        FROM politics.entity_canonical
        ORDER BY id
    """
    cur.execute(query)
    rows = cur.fetchall()
    conn.close()

    total = 0
    resolve_count = 0
    skip_count = 0
    already_resolved = 0

    by_type = Counter()
    resolve_by_type = Counter()
    skip_by_type = Counter()
    skip_by_reason = Counter()
    resolve_by_reason = Counter()

    skip_samples = defaultdict(list)
    resolve_samples = defaultdict(list)

    for row in rows:
        eid = row["id"]
        name = row["canonical_name"] or ""
        etype = row["entity_type"] or ""
        wp_id = row["wikipedia_page_id"]

        if args.type and etype != args.type:
            continue

        total += 1
        by_type[etype] += 1

        if wp_id is not None:
            already_resolved += 1
            if args.unresolved_only:
                continue
            resolve_by_type[etype] += 1
            continue

        resolvable, reason = is_wikipedia_resolvable(name, etype)

        if resolvable:
            resolve_count += 1
            resolve_by_type[etype] += 1
            resolve_by_reason[reason] += 1
            if len(resolve_samples[reason]) < args.show_samples:
                resolve_samples[reason].append((name, etype, eid))
        else:
            skip_count += 1
            skip_by_type[etype] += 1
            skip_by_reason[reason] += 1
            if len(skip_samples[reason]) < args.show_samples:
                skip_samples[reason].append((name, etype, eid))

    unresolved = total - already_resolved

    log.info("=" * 70)
    log.info("WIKIPEDIA PRE-FILTER DIAGNOSTIC REPORT")
    log.info("=" * 70)
    log.info("")
    log.info("Total entities:       %d", total)
    log.info("Already resolved:     %d  (have wikipedia_page_id)", already_resolved)
    log.info("Unresolved:           %d", unresolved)
    log.info("")
    if unresolved > 0:
        log.info("After pre-filter on unresolved:")
        log.info("  Would RESOLVE:      %d  (%.1f%% of unresolved)",
                 resolve_count, resolve_count / unresolved * 100)
        log.info("  Would SKIP:         %d  (%.1f%% of unresolved)",
                 skip_count, skip_count / unresolved * 100)
        log.info("")
        log.info("  API calls saved:    %d  (%.1f%% reduction)",
                 skip_count, skip_count / unresolved * 100)

    log.info("")
    log.info("-" * 70)
    log.info("BREAKDOWN BY ENTITY TYPE")
    log.info("-" * 70)
    log.info("%-20s %8s %8s %8s %8s", "Type", "Total", "Resolved", "Resolve", "Skip")
    log.info("%-20s %8s %8s %8s %8s", "-" * 20, "-" * 8, "-" * 8, "-" * 8, "-" * 8)
    for etype in sorted(by_type.keys()):
        log.info("%-20s %8d %8d %8d %8d",
                 etype, by_type[etype],
                 already_resolved if not args.type else resolve_by_type.get(etype, 0),
                 resolve_by_type.get(etype, 0),
                 skip_by_type.get(etype, 0))
    # Redo per-type with correct resolved counts
    log.info("")

    log.info("-" * 70)
    log.info("SKIP REASONS (entities that would NOT be sent to Wikipedia)")
    log.info("-" * 70)
    for reason, count in skip_by_reason.most_common():
        log.info("")
        log.info("  %s: %d entities", reason, count)
        for name, etype, eid in skip_samples[reason][:args.show_samples]:
            log.info("    [%s] %s (id=%d)", etype, name, eid)

    log.info("")
    log.info("-" * 70)
    log.info("RESOLVE REASONS (entities that WOULD be sent to Wikipedia)")
    log.info("-" * 70)
    for reason, count in resolve_by_reason.most_common():
        log.info("")
        log.info("  %s: %d entities", reason, count)
        for name, etype, eid in resolve_samples[reason][:args.show_samples]:
            log.info("    [%s] %s (id=%d)", etype, name, eid)

    log.info("")
    log.info("=" * 70)


if __name__ == "__main__":
    main()
