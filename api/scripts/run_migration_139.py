#!/usr/bin/env python3
"""Run migration 139 (log_archive table) using project DB config."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    from shared.database.connection import get_db_connection

    migration_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "database",
        "migrations",
        "139_log_archive_tables.sql",
    )

    if not os.path.exists(migration_path):
        print(f"ERROR: Migration file not found: {migration_path}")
        sys.exit(1)

    with open(migration_path, encoding="utf-8") as f:
        sql = f.read()

    conn = get_db_connection()
    if not conn:
        print("ERROR: Could not connect to database (ensure SSH tunnel is running)")
        sys.exit(1)

    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        print("✅ Migration 139 (log_archive) applied successfully")
    except Exception as e:
        conn.rollback()
        print(f"ERROR: Migration failed: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
