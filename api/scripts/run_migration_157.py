#!/usr/bin/env python3
"""Run migration 157 (anomaly_investigations). From project root: .venv/bin/python api/scripts/run_migration_157.py"""

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

    try:
        from shared.migration_sql_paths import resolve_migration_sql_file
        migration_path = resolve_migration_sql_file("157_anomaly_investigations.sql")
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    with open(migration_path, encoding="utf-8") as f:
        sql = f.read()

    conn = get_db_connection()
    if not conn:
        print("ERROR: Could not connect to database")
        sys.exit(1)

    try:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = 0")
            cur.execute(sql)
        conn.commit()
        print("✅ 157_anomaly_investigations.sql applied successfully")
    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
