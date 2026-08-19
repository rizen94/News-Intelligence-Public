#!/usr/bin/env python3
"""Repair duplicate episodes — fold same-title / same-event stragglers into canonical episodes.

Usage:
  PYTHONPATH=api python3 api/scripts/repair_duplicate_episodes.py --domain politics
  PYTHONPATH=api python3 api/scripts/repair_duplicate_episodes.py --all --dry-run
"""

from __future__ import annotations

import argparse
import sys

from shared.database.connection import get_db_connection
from shared.domain_registry import get_pipeline_active_domain_keys


def main() -> int:
    ap = argparse.ArgumentParser(description="Merge duplicate episodes by shared title/events")
    ap.add_argument("--domain", help="Domain key (e.g. politics)")
    ap.add_argument("--all", action="store_true", help="Run for all pipeline-active domains")
    ap.add_argument("--limit", type=int, default=50, help="Max duplicate title groups per domain")
    ap.add_argument("--dry-run", action="store_true", help="Report only; do not merge")
    args = ap.parse_args()

    if not args.domain and not args.all:
        ap.error("Specify --domain or --all")

    domains = (
        get_pipeline_active_domain_keys()
        if args.all
        else [args.domain]
    )

    from services.episode_merge_service import scan_and_merge_duplicate_episodes

    conn = get_db_connection()
    if not conn:
        print("Database unavailable", file=sys.stderr)
        return 1

    total_merged = 0
    try:
        for domain in domains:
            result = scan_and_merge_duplicate_episodes(
                conn,
                domain_key=domain,
                limit=args.limit,
                dry_run=args.dry_run,
            )
            if not args.dry_run and result.get("merged", 0):
                conn.commit()
            print(
                f"{domain}: groups={result.get('groups')} "
                f"pairs={result.get('pairs_found')} merged={result.get('merged')} "
                f"dry_run={result.get('dry_run')}"
            )
            total_merged += int(result.get("merged") or 0)
    finally:
        try:
            conn.close()
        except Exception:
            pass

    print(f"Done. total_merged={total_merged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
