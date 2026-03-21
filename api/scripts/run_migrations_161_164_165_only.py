#!/usr/bin/env python3
"""Run migrations 161, 164, 165 only (no 167). Use when 167 is still running or blocked.

From project root:
  PYTHONPATH=api .venv/bin/python3 api/scripts/run_migrations_161_164_165_only.py
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
]


def main():
    from shared.database.connection import get_db_connection
    from shared.migration_sql_paths import resolve_migration_sql_file

    conn = get_db_connection()
    if not conn:
        print("ERROR: Could not connect to database (check DB_HOST, DB_NAME, DB_USER, DB_PASSWORD)")
        sys.exit(1)

    for name in FILES:
        try:
            path = resolve_migration_sql_file(name)
        except FileNotFoundError:
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
    print("  Done. Run 167 with: PYTHONPATH=api .venv/bin/python3 api/scripts/run_migration_167.py")
    print("  Then verify: PYTHONPATH=api .venv/bin/python3 api/scripts/verify_migrations_160_167.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
