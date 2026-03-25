#!/usr/bin/env python3
"""Run migration 204: deactivate dead FT/Blaze/C-SPAN rows in politics_2."""

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
    except OSError:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    from shared.database.connection import get_db_connection
    from shared.migration_sql_paths import resolve_migration_sql_file

    try:
        path = resolve_migration_sql_file("204_rss_deactivate_politics2_dead_feeds.sql")
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return 1

    conn = get_db_connection()
    if not conn:
        print("ERROR: Could not connect to database")
        return 1

    try:
        with open(path) as f:
            sql = f.read()
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = 0")
            cur.execute(sql)
        conn.commit()
        print("204_rss_deactivate_politics2_dead_feeds.sql applied successfully")
        return 0
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
