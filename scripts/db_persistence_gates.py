#!/usr/bin/env python3
"""
Persistence verification gates: critical tables exist; automation history has recent activity.

Read-only. From repo root:
  PYTHONPATH=api uv run python scripts/db_persistence_gates.py
  PYTHONPATH=api uv run python scripts/db_persistence_gates.py --hours 48 --require-automation

Exit 1 if a gate fails.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

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
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=int, default=72, help="Window for automation_run_history")
    parser.add_argument(
        "--require-automation",
        action="store_true",
        help="Fail if no successful automation_run_history row in window",
    )
    args = parser.parse_args()

    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        print("FAIL: database connection")
        return 1

    ok = True
    cutoff = datetime.now(timezone.utc) - timedelta(hours=args.hours)

    checks = [
        ("public.chronological_events", "SELECT COUNT(*) FROM public.chronological_events"),
        ("public.automation_run_history", "SELECT COUNT(*) FROM public.automation_run_history"),
        ("politics.articles", "SELECT COUNT(*) FROM politics.articles"),
    ]

    try:
        with conn.cursor() as cur:
            for label, sql in checks:
                try:
                    cur.execute(sql)
                    n = cur.fetchone()[0]
                    print(f"OK  {label} row_count={n}")
                except Exception as e:
                    print(f"FAIL {label}: {e}")
                    ok = False

            cur.execute(
                """
                SELECT COUNT(*) FROM public.automation_run_history
                WHERE finished_at >= %s AND success = true
                """,
                (cutoff,),
            )
            recent_ok = cur.fetchone()[0]
            print(f"OK  automation_run_history successful runs (last {args.hours}h) = {recent_ok}")
            if args.require_automation and recent_ok == 0:
                print("FAIL --require-automation: no successful runs in window")
                ok = False
    finally:
        conn.close()

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
