#!/usr/bin/env python3
"""
Validate claims → versioned_facts after resolver / pg_trgm work.

Loads DB env like diagnose_claims_to_facts.py (api/.env, .env, .db_password_widow).

  PYTHONPATH=api uv run python scripts/validate_claims_to_facts.py
  PYTHONPATH=api uv run python scripts/validate_claims_to_facts.py --limit 1000 --dry-run

Then re-check productivity:

  PYTHONPATH=api uv run python scripts/verify_intelligence_phases_productivity.py --hours 24
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

if not os.environ.get("DB_PASSWORD") and os.path.exists(
    os.path.join(ROOT, ".db_password_widow")
):
    try:
        with open(os.path.join(ROOT, ".db_password_widow")) as f:
            os.environ.setdefault("DB_PASSWORD", f.read().strip())
    except OSError:
        pass


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Max claims to attempt per promote batch (default 500)",
    )
    p.add_argument(
        "--min-confidence",
        type=float,
        default=0.7,
        help="Minimum claim confidence (default 0.7)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print extension + row counts; do not call promote",
    )
    args = p.parse_args()

    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        print("ERROR: no DB connection (check DB_* env / .db_password_widow)")
        return 1

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm')"
            )
            (trgm,) = cur.fetchone()
            print(f"=== pg_trgm extension: {'yes' if trgm else 'NO (apply migration 189)'} ===")

            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.versioned_facts
                WHERE extraction_method = 'claim_extraction'
                  AND created_at >= NOW() - INTERVAL '24 hours'
                """
            )
            (vf_24h,) = cur.fetchone()
            print(f"versioned_facts (claim_extraction, last 24h): {vf_24h:,}")

            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.extracted_claims ec
                WHERE ec.confidence >= %s
                  AND NOT EXISTS (
                      SELECT 1 FROM intelligence.versioned_facts vf
                      WHERE vf.metadata->>'source_claim_id' = ec.id::text
                  )
                """,
                (args.min_confidence,),
            )
            (unpromoted,) = cur.fetchone()
            print(f"Unpromoted high-confidence claims: {unpromoted:,}")
    finally:
        conn.close()

    if args.dry_run:
        print("Dry run: skipped promote_claims_to_versioned_facts")
        return 0

    from services.claim_extraction_service import promote_claims_to_versioned_facts

    stats = promote_claims_to_versioned_facts(args.min_confidence, args.limit)
    promoted = int(stats.get("promoted", 0))
    print(
        f"=== promote batch: promoted={promoted} candidates={stats.get('candidates', 0)} "
        f"unresolved_subject={stats.get('unresolved_subject', 0)} "
        f"insert_failed={stats.get('insert_failed', 0)} ==="
    )
    if promoted == 0 and unpromoted > 0:
        print(
            "Hint: run scripts/diagnose_claims_to_facts.py; ensure migration "
            "189_pg_trgm_claim_resolution.sql is applied; restart API if trgm was just added."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
