#!/usr/bin/env python3
"""Run migration 192: RSS feed URL refresh (politics, finance, medicine, AI silos).

From project root:
  PYTHONPATH=api uv run python api/scripts/run_migration_192.py

Then register (if you use the ledger):
  PYTHONPATH=api uv run python api/scripts/register_applied_migration.py 192 --notes "run_migration_192.py" \\
    --file api/database/migrations/192_rss_feed_url_refresh_reviewed.sql

If feed id/name pairs differ on your DB, adjust the SQL or run targeted UPDATEs by feed_url.
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
    except OSError:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    from shared.database.connection import get_db_connection

    try:
        from shared.migration_sql_paths import resolve_migration_sql_file

        path = resolve_migration_sql_file("192_rss_feed_url_refresh_reviewed.sql")
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
        print("✅ 192_rss_feed_url_refresh_reviewed.sql applied successfully")
        return 0
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
