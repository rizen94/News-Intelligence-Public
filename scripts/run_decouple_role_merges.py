#!/usr/bin/env python3
"""
Decouple bad merges (role-word and future steps) via the shared pipeline.
Routine data cleanliness: split entity_canonical rows that incorrectly merged
distinct entities (e.g. "X executives" + "Y executives" → separate canonicals).

Also runs automatically as part of data_cleanup (intelligence cleanup) when
entity_bad_merge_decouple is True in policy.

From project root:
  PYTHONPATH=api uv run python scripts/run_decouple_role_merges.py [--domain DOMAIN] [--dry-run] [--max-splits N]
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from services.entity_resolution_service import ALL_DOMAINS, run_entity_decouple_pipeline


def main():
    parser = argparse.ArgumentParser(
        description="Run entity decouple pipeline (split role-word and other bad merges)"
    )
    parser.add_argument(
        "--domain",
        default=None,
        help="Domain to run (politics, finance, science-tech). Omit for all.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be split without changing the database.",
    )
    parser.add_argument(
        "--max-splits",
        type=int,
        default=None,
        metavar="N",
        help="Cap total splits per domain (default: no cap).",
    )
    args = parser.parse_args()

    domain_keys = [args.domain] if args.domain else None
    if args.domain and args.domain not in ALL_DOMAINS:
        print(f"Unknown domain: {args.domain}. Use one of {ALL_DOMAINS}")
        sys.exit(1)

    result = run_entity_decouple_pipeline(
        domain_keys=domain_keys,
        dry_run=args.dry_run,
        max_splits_per_domain=args.max_splits,
    )
    total = result.get("total_splits", 0)
    if args.dry_run:
        print("(dry-run: no changes written)")

    for domain_key, dr in result.get("by_domain", {}).items():
        print(f"\n--- {domain_key} ---")
        rw = dr.get("role_word") or {}
        if dr.get("error"):
            print(f"  Error: {dr['error']}")
            continue
        n = dr.get("split_count", 0)
        print(f"  Canonicals with 2+ role names: {rw.get('canonicals_processed', 0)}")
        print(f"  Splits performed: {n}")
        for d in (rw.get("details") or [])[:20]:
            new_id = d.get("new_canonical_id")
            id_str = f"id={new_id}" if new_id is not None else "(would create)"
            print(f"    {d['canonical_name']!r} -> split off {d['split_off']!r} ({id_str}, {d.get('articles_reassigned', 0)} articles)")
        if len(rw.get("details") or []) > 20:
            print(f"    ... and {len(rw['details']) - 20} more")
    print(f"\nTotal splits: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
