#!/usr/bin/env python3
"""Run migrations 161, 164, 165, 167 in order (idempotent). Use to catch up if any were skipped.

From project root:
  PYTHONPATH=api .venv/bin/python3 api/scripts/run_migrations_161_164_165_167.py

Uses DB from env or .db_password_widow. Sets statement_timeout = 0 for each migration.
"""

import os
import sys

try:
    from dotenv import load_dotenv
    api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(api_dir, ".env"), override=False)
    load_dotenv(os.path.join(api_dir, "..", ".env"), override=False)
except ImportError:
    pass

if not os.environ.get("DB_PASSWORD") and os.path.exists(
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", ".db_password_widow")
):
    pw_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", ".db_password_widow")
    try:
        with open(pw_path) as f:
            os.environ["DB_PASSWORD"] = f.read().strip()
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FILES = [
    "161_automation_run_history.sql",
    "164_content_quality_tiers.sql",
    "165_storyline_quality_integration.sql",
    "167_enrichment_tracking.sql",
]


def main():
    from shared.database.connection import get_db_connection

    api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    migrations_dir = os.path.join(api_dir, "database", "migrations")

    conn = get_db_connection()
    if not conn:
        print("ERROR: Could not connect to database (check DB_HOST, DB_NAME, DB_USER, DB_PASSWORD)")
        sys.exit(1)

    for name in FILES:
        path = os.path.join(migrations_dir, name)
        if not os.path.exists(path):
            print(f"SKIP (file missing): {name}")
            continue
        with open(path, encoding="utf-8") as f:
            sql = f.read()
        try:
            with conn.cursor() as cur:
                cur.execute("SET statement_timeout = 0")
                cur.execute(sql)
            conn.commit()
            print(f"  {name}")
        except Exception as e:
            conn.rollback()
            print(f"ERROR: {name} failed: {e}")
            sys.exit(1)

    conn.close()
    print("  Done. Run verify_migrations_160_167.py to confirm.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
