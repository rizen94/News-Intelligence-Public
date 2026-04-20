#!/usr/bin/env python3
"""
Run ANALYZE on high-churn tables to refresh planner statistics (safe, non-blocking).

Optional VACUUM (reclaims space; use during maintenance window only):
  PYTHONPATH=api uv run python scripts/db_maintenance_analyze.py --vacuum

From repo root:
  PYTHONPATH=api uv run python scripts/db_maintenance_analyze.py
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

TARGETS = [
    "public.chronological_events",
    "public.automation_run_history",
    "politics.articles",
    "finance.articles",
    "science_tech.articles",
    "intelligence.contexts",
    "intelligence.processed_documents",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--vacuum",
        action="store_true",
        help="Run VACUUM ANALYZE (longer locks; use in maintenance window)",
    )
    args = parser.parse_args()

    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        print("ERROR: no database connection")
        return 1

    conn.autocommit = True
    cmd = "VACUUM ANALYZE" if args.vacuum else "ANALYZE"

    try:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = 0")
            for qualified in TARGETS:
                schema, table = qualified.split(".", 1)
                sql = f'{cmd} "{schema}"."{table}"'
                print(sql)
                try:
                    cur.execute(sql)
                except Exception as e:
                    print(f"  skip {qualified}: {e}")
        print("Done.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
