#!/usr/bin/env python3
"""
Run entity consolidation: populate aliases from article mentions, then merge
duplicate canonicals (e.g. Donald Trump, Donald J Trump, Trump, King Trump)
into a single primary entity per person/org. Variants become aliases.

From project root (DB credentials in local .env or .db_password_widow):
  PYTHONPATH=api uv run python scripts/run_entity_consolidation.py [--domain DOMAIN] [--confidence 0.6] [--dry-run]
"""

import argparse
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# Load local .env and .db_password_widow so DB credentials work when run locally (DB may be on Widow)
if os.path.isfile(os.path.join(ROOT, ".env")):
    with open(os.path.join(ROOT, ".env")) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                if key.strip() in ("DB_PASSWORD", "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER"):
                    os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
if not os.environ.get("DB_PASSWORD") and os.path.isfile(os.path.join(ROOT, ".db_password_widow")):
    with open(os.path.join(ROOT, ".db_password_widow")) as f:
        os.environ.setdefault("DB_PASSWORD", f.read().splitlines()[0].strip())

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from services.entity_resolution_service import (
    ALL_DOMAINS,
    find_merge_candidates,
    auto_merge_high_confidence,
    populate_aliases_from_mentions,
    run_resolution_batch,
    split_role_merged_canonicals,
)


def main():
    parser = argparse.ArgumentParser(
        description="Consolidate duplicate entities (e.g. Trump / Donald Trump → one canonical with aliases)"
    )
    parser.add_argument(
        "--domain",
        default=None,
        help="Domain to run (politics, finance, science-tech). Omit for all.",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.6,
        help="Min confidence to auto-merge (default 0.6 for last-name / variant consolidation)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only find and print merge candidates; do not merge",
    )
    parser.add_argument(
        "--full-batch",
        action="store_true",
        help="Run full resolution batch for all domains (aliases + merge + cross-domain) with given confidence",
    )
    parser.add_argument(
        "--decouple",
        action="store_true",
        help="Only run decouple: split role-word merges (e.g. X executives / Y executives) into separate canonicals",
    )
    args = parser.parse_args()

    if args.decouple:
        domains = [args.domain] if args.domain else ALL_DOMAINS
        if args.domain and args.domain not in ALL_DOMAINS:
            print(f"Unknown domain: {args.domain}. Use one of {ALL_DOMAINS}")
            sys.exit(1)
        for domain_key in domains:
            print(f"\n--- decouple {domain_key} ---")
            result = split_role_merged_canonicals(domain_key)
            if not result.get("success"):
                print(f"  Error: {result.get('error')}")
                continue
            print(f"  Canonicals with 2+ role names: {result.get('canonicals_processed', 0)}")
            print(f"  Splits: {result.get('split_count', 0)}")
            for d in result.get("details", [])[:15]:
                print(f"    {d['canonical_name']!r} -> split off {d['split_off']!r} ({d['articles_reassigned']} articles)")
        print("\nDone.")
        return

    if args.full_batch and not args.dry_run:
        domains = []
    else:
        domains = [args.domain] if args.domain else ALL_DOMAINS
    if args.domain and args.domain not in ALL_DOMAINS:
        print(f"Unknown domain: {args.domain}. Use one of {ALL_DOMAINS}")
        sys.exit(1)

    for domain_key in (domains or []):
        print(f"\n--- {domain_key} ---")
        # 1. Populate aliases from article mentions so we have more overlap for matching
        r = populate_aliases_from_mentions(domain_key)
        if r.get("success"):
            print(f"  Aliases: {r.get('updated', 0)} entities updated, {r.get('new_aliases', 0)} new aliases")
        else:
            print(f"  Aliases failed: {r.get('error')}")

        # 2. Find merge candidates
        candidates = find_merge_candidates(
            domain_key, min_confidence=args.confidence, limit=200
        )
        if not candidates.get("success"):
            print(f"  Find candidates failed: {candidates.get('error')}")
            continue
        clist = candidates.get("candidates", [])
        print(f"  Merge candidates (confidence >= {args.confidence}): {len(clist)}")
        for c in clist[:15]:
            print(f"    {c['source_name']!r} + {c['target_name']!r} -> {c['reason']} ({c['confidence']})")
        if len(clist) > 15:
            print(f"    ... and {len(clist) - 15} more")

        if args.dry_run:
            continue

        # 3. Auto-merge (keeps primary/full name, merges variants into it)
        if clist:
            merge_result = auto_merge_high_confidence(
                domain_key, min_confidence=args.confidence
            )
            if merge_result.get("merges_performed"):
                print(f"  Merged: {merge_result['merges_performed']} pairs")
                for d in merge_result.get("details", [])[:10]:
                    print(f"    kept {d['kept']!r}, merged {d['merged']!r}")
            else:
                print("  No merges performed")
        else:
            print("  No candidates to merge")

    if args.full_batch and not args.dry_run:
        print("\n--- full resolution batch (all domains: aliases + merge + cross-domain link) ---")
        result = run_resolution_batch(
            auto_merge_confidence=args.confidence,
            cross_domain_confidence=0.8,
        )
        for dk, dr in result.get("domains", {}).items():
            merges = (dr.get("merges") or {}).get("merges_performed", 0)
            print(f"  {dk}: {merges} merges")
        cd = result.get("cross_domain", {})
        print(f"  cross_domain: linked={cd.get('linked', 0)}, relationships={cd.get('relationships_created', 0)}")

    print("\nDone.")


if __name__ == "__main__":
    main()
