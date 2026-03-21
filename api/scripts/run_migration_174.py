#!/usr/bin/env python3
"""Run migration 174: context_grouping_feedback table.

From project root:
  PYTHONPATH=api .venv/bin/python3 api/scripts/run_migration_174.py
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


def main():
    from shared.database.connection import get_db_connection

    api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(api_dir, "database", "migrations", "174_context_grouping_feedback.sql")
    if not os.path.isfile(path):
        print(f"ERROR: Migration file not found: {path}")
        sys.exit(1)

    with open(path) as f:
        sql = f.read()

    conn = get_db_connection()
    if not conn:
        print("ERROR: No database connection")
        sys.exit(1)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        print("OK: migration 174 applied (context_grouping_feedback)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
