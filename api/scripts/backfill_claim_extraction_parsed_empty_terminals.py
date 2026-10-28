#!/usr/bin/env python3
"""
One-shot: set last_terminal_state=processed_empty_legitimate for contexts that already
have claim_extraction last_outcome=parsed_empty but are missing terminal_state.

Those rows are inventory (LLM returned no claims), not automation backlog. Without a
terminal they can confuse ops inventory; with the terminal they match modern pass markers.

  PYTHONPATH=api python api/scripts/backfill_claim_extraction_parsed_empty_terminals.py --dry-run
  PYTHONPATH=api python api/scripts/backfill_claim_extraction_parsed_empty_terminals.py
"""

from __future__ import annotations

import argparse
import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _API_ROOT not in sys.path:
    sys.path.insert(0, _API_ROOT)

from shared.database.connection import get_db_connection
from shared.pipeline_pass_marker import TERMINAL_PROCESSED_EMPTY_LEGITIMATE


def _match_where(alias: str = "c") -> str:
    a = alias
    return f"""
    NOT EXISTS (
        SELECT 1 FROM intelligence.extracted_claims ec WHERE ec.context_id = {a}.id
    )
    AND ({a}.metadata::jsonb->'pipeline'->'claim_extraction'->>'last_outcome')
        = 'parsed_empty'
    AND (
          ({a}.metadata::jsonb->'pipeline'->'claim_extraction'->>'last_terminal_state')
            IS NULL
       OR TRIM(
            COALESCE(
              {a}.metadata::jsonb->'pipeline'->'claim_extraction'->>'last_terminal_state',
              ''
            )
          ) = ''
    )
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill claim_extraction terminal for legacy parsed_empty markers"
    )
    parser.add_argument("--dry-run", action="store_true", help="Count only, no UPDATE")
    parser.add_argument("--limit", type=int, default=0, help="Max rows (0 = all)")
    args = parser.parse_args()

    conn = get_db_connection()
    if not conn:
        print("ERROR: no database connection", file=sys.stderr)
        return 1

    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '120s'")
            cur.execute(
                f"SELECT COUNT(*) FROM intelligence.contexts c WHERE {_match_where('c')}"
            )
            total = int(cur.fetchone()[0] or 0)
            print(f"Matching contexts (parsed_empty, missing terminal): {total}")
            if args.dry_run:
                return 0
            if total <= 0:
                print("Nothing to update")
                return 0
            params: list = [TERMINAL_PROCESSED_EMPTY_LEGITIMATE]
            lim_clause = ""
            if args.limit and args.limit > 0:
                lim_clause = " LIMIT %s"
                params.append(int(args.limit))
            cur.execute(
                f"""
                UPDATE intelligence.contexts c
                SET metadata =
                    jsonb_set(
                      COALESCE(c.metadata::jsonb, '{{}}'::jsonb),
                      '{{pipeline,claim_extraction,last_terminal_state}}',
                      to_jsonb(%s::text),
                      true
                    ),
                    updated_at = CURRENT_TIMESTAMP
                FROM (
                    SELECT c2.id
                    FROM intelligence.contexts c2
                    WHERE {_match_where('c2')}
                    ORDER BY c2.id
                    {lim_clause}
                ) sub
                WHERE c.id = sub.id
                """,
                tuple(params),
            )
            updated = int(cur.rowcount or 0)
        conn.commit()
        print(
            f"Set last_terminal_state={TERMINAL_PROCESSED_EMPTY_LEGITIMATE!r} "
            f"on {updated} context(s)"
        )
        return 0
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
