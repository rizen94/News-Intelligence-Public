#!/usr/bin/env python3
"""
Remove duplicate rows in intelligence.extracted_claims that share the same context and
normalized subject/predicate/object. Keeps the row with highest confidence (then lowest id).

Skips any claim id already referenced by intelligence.versioned_facts.metadata.source_claim_id.

Default is dry-run. Use --apply to delete in batches.

  PYTHONPATH=api uv run python scripts/merge_duplicate_extracted_claims.py
  PYTHONPATH=api uv run python scripts/merge_duplicate_extracted_claims.py --apply --batch-size 8000
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (ROOT, os.path.join(ROOT, "api")):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(ROOT, "api", ".env"), override=False)
    load_dotenv(os.path.join(ROOT, ".env"), override=False)
except ImportError:
    pass

if not os.environ.get("DB_PASSWORD") and os.path.exists(os.path.join(ROOT, ".db_password_widow")):
    try:
        with open(os.path.join(ROOT, ".db_password_widow")) as f:
            os.environ.setdefault("DB_PASSWORD", f.read().strip())
    except OSError:
        pass

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--apply",
        action="store_true",
        help="Perform deletes (default: dry-run count only)",
    )
    p.add_argument("--batch-size", type=int, default=8000, help="Rows per delete batch (default 8000)")
    p.add_argument("--max-batches", type=int, default=0, help="Stop after N batches (0 = unlimited)")
    args = p.parse_args()

    from services.extracted_claims_dedupe_service import (
        count_duplicate_extracted_claim_rows,
        delete_duplicate_extracted_claims_batch,
    )

    total_dup = count_duplicate_extracted_claim_rows()

    print(f"Duplicate rows (safe to remove, no versioned_fact): {total_dup:,}")
    if not args.apply or total_dup == 0:
        print("Dry-run only. Pass --apply to delete in batches.")
        return 0

    batch = max(100, min(50_000, int(args.batch_size)))
    max_batches = max(0, int(args.max_batches))
    deleted_total = 0
    batches = 0

    while True:
        n = delete_duplicate_extracted_claims_batch(batch)
        deleted_total += n
        batches += 1
        print(f"batch {batches}: deleted {n:,} (total {deleted_total:,})")
        if n == 0:
            break
        if max_batches and batches >= max_batches:
            print(f"Stopped after {max_batches} batch(es) (--max-batches).")
            break

    print(f"Done. Total deleted: {deleted_total:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
