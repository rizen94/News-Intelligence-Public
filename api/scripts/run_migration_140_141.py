#!/usr/bin/env python3
"""Run migrations 140 (orchestration schema) and 141 (intelligence schema) for Newsroom Orchestrator v6.

From project root: cd api && python3 scripts/run_migration_140_141.py
Requires DB reachable (env DB_HOST, DB_NAME, DB_USER, DB_PASSWORD; default Widow 192.168.93.101).
"""

import os
import sys

# Load .env from api/ or project root so DB_PASSWORD is set
try:
    from dotenv import load_dotenv
    api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(api_dir, ".env"), override=False)
    load_dotenv(os.path.join(api_dir, "..", ".env"), override=False)
except ImportError:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    from shared.database.connection import get_db_connection

    api_dir = os.path.dirname(os.path.dirname(__file__))
    migrations_dir = os.path.join(api_dir, "database", "migrations")

    for name in ("140_orchestration_schema.sql", "141_intelligence_schema.sql"):
        migration_path = os.path.join(migrations_dir, name)
        if not os.path.exists(migration_path):
            print(f"ERROR: Migration file not found: {migration_path}")
            sys.exit(1)

        with open(migration_path, encoding="utf-8") as f:
            sql = f.read()

        conn = get_db_connection()
        if not conn:
            print("ERROR: Could not connect to database (check DB_HOST, tunnel if using NAS)")
            sys.exit(1)

        try:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
            print(f"✅ {name} applied successfully")
        except Exception as e:
            conn.rollback()
            print(f"ERROR: {name} failed: {e}")
            sys.exit(1)
        finally:
            conn.close()

    print("✅ Migrations 140 and 141 complete. Newsroom Orchestrator schemas ready.")


if __name__ == "__main__":
    main()
