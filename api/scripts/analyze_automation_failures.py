#!/usr/bin/env python3
"""
Summarize automation_run_history failures for the last N hours (real schema: no severity column).

Usage (repo root):

  PYTHONPATH=api uv run python api/scripts/analyze_automation_failures.py
  PYTHONPATH=api uv run python api/scripts/analyze_automation_failures.py --hours 48 --limit 25
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

_API = Path(__file__).resolve().parent.parent
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--hours", type=float, default=24.0)
    p.add_argument("--limit", type=int, default=20, help="Top N groups per section")
    args = p.parse_args()

    try:
        from dotenv import load_dotenv

        load_dotenv(_API / ".env", override=False)
        load_dotenv(_API.parent / ".env", override=False)
    except Exception:
        pass

    since = datetime.now(timezone.utc) - timedelta(hours=args.hours)

    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        print("No database connection.", file=sys.stderr)
        return 1

    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '30s'")
            cur.execute(
                """
                SELECT phase_name,
                       success,
                       COALESCE(left(error_message, 400), '') AS err_snip,
                       count(*)::bigint AS cnt,
                       max(finished_at) AS last_finished
                FROM automation_run_history
                WHERE finished_at >= %s
                  AND (success = false OR (error_message IS NOT NULL AND btrim(error_message) <> ''))
                GROUP BY phase_name, success, COALESCE(left(error_message, 400), '')
                ORDER BY cnt DESC
                LIMIT %s
                """,
                (since, args.limit),
            )
            rows = cur.fetchall() or []

            cur.execute(
                """
                SELECT phase_name,
                       count(*) FILTER (WHERE success = true) AS ok,
                       count(*) FILTER (WHERE success = false) AS failed
                FROM automation_run_history
                WHERE finished_at >= %s
                GROUP BY phase_name
                HAVING count(*) FILTER (WHERE success = false) > 0
                ORDER BY failed DESC
                LIMIT %s
                """,
                (since, min(args.limit, 50)),
            )
            health = cur.fetchall() or []
    finally:
        conn.close()

    print(f"Window: last {args.hours}h since {since.isoformat()} UTC\n")
    print("=== Top failure groups (phase + success + error snippet) ===\n")
    for phase, success, err_snip, cnt, last_f in rows:
        print(f"  count={cnt}  phase={phase!r}  success={success}")
        if err_snip:
            print(f"    error_snippet: {err_snip[:300]!r}")
        print(f"    last_finished: {last_f}")
        print()

    print("=== Phase success vs failure (rows with any failure) ===\n")
    for phase, ok, failed in health:
        tot = ok + failed
        pct = (100.0 * ok / tot) if tot else 0.0
        print(f"  {phase}: success={ok} failed={failed} ({pct:.1f}% ok)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
