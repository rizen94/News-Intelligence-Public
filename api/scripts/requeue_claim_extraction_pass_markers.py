#!/usr/bin/env python3
"""
Clear claim_extraction pass markers for contexts that exited with no_claims_after_filters
so automation can retry (e.g. after narrowing CLAIM_EXTRACTION_REQUIRE_SEEDED_DOMAIN_KEYS).

  PYTHONPATH=api uv run python api/scripts/requeue_claim_extraction_pass_markers.py --dry-run
  PYTHONPATH=api uv run python api/scripts/requeue_claim_extraction_pass_markers.py --limit 5000
"""

from __future__ import annotations

import argparse
import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _API_ROOT not in sys.path:
    sys.path.insert(0, _API_ROOT)

from shared.database.connection import get_db_connection


def main() -> int:
    parser = argparse.ArgumentParser(description="Requeue claim_extraction pass markers")
    parser.add_argument("--dry-run", action="store_true", help="Count only, no UPDATE")
    parser.add_argument("--limit", type=int, default=10_000, help="Max contexts to clear")
    parser.add_argument(
        "--outcome",
        default="no_claims_after_filters",
        help="last_outcome value to match (default: no_claims_after_filters)",
    )
    args = parser.parse_args()

    conn = get_db_connection()
    if not conn:
        print("ERROR: no database connection", file=sys.stderr)
        return 1
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '30s'")
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.contexts c
                LEFT JOIN intelligence.extracted_claims ec ON ec.context_id = c.id
                WHERE ec.id IS NULL
                  AND (c.metadata::jsonb->'pipeline'->'claim_extraction'->>'last_outcome') = %s
                """,
                (args.outcome,),
            )
            total = int(cur.fetchone()[0] or 0)
            print(f"Matching contexts (no claims, outcome={args.outcome!r}): {total}")
            if args.dry_run:
                return 0
            cur.execute(
                """
                UPDATE intelligence.contexts c
                SET metadata = c.metadata::jsonb
                    #- '{pipeline,claim_extraction}'
                FROM (
                    SELECT c2.id
                    FROM intelligence.contexts c2
                    LEFT JOIN intelligence.extracted_claims ec ON ec.context_id = c2.id
                    WHERE ec.id IS NULL
                      AND (c2.metadata::jsonb->'pipeline'->'claim_extraction'->>'last_outcome') = %s
                    ORDER BY c2.id
                    LIMIT %s
                ) sub
                WHERE c.id = sub.id
                """,
                (args.outcome, args.limit),
            )
            updated = cur.rowcount
        conn.commit()
        print(f"Cleared claim_extraction pass marker on {updated} context(s)")
    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
