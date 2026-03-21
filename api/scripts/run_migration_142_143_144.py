#!/usr/bin/env python3
"""Run migrations 142 (context-centric foundation), 143 (entity/claims/patterns), 144 (v6 events/dossiers).

From project root: cd api && python3 scripts/run_migration_142_143_144.py
Requires DB reachable (env DB_HOST, DB_NAME, DB_USER, DB_PASSWORD; or .db_password_widow).
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

# Load DB password from .db_password_widow if not in env
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
    from shared.migration_sql_paths import resolve_migration_sql_file

    for name in (
        "142_context_centric_foundation.sql",
        "143_context_centric_entity_claims.sql",
        "144_v6_events_entity_dossiers.sql",
    ):
        try:
            migration_path = resolve_migration_sql_file(name)
        except FileNotFoundError as e:
            print(f"ERROR: {e}")
            sys.exit(1)

        with open(migration_path, encoding="utf-8") as f:
            sql = f.read()

        conn = get_db_connection()
        if not conn:
            print("ERROR: Could not connect to database (check DB_HOST, DB_NAME, DB_USER, DB_PASSWORD)")
            sys.exit(1)

        try:
            with conn.cursor() as cur:
                cur.execute("SET statement_timeout = 0")
                cur.execute(sql)
            conn.commit()
            print(f"✅ {name} applied successfully")
        except Exception as e:
            conn.rollback()
            print(f"ERROR: {name} failed: {e}")
            sys.exit(1)
        finally:
            conn.close()

    print("✅ Migrations 142, 143, 144 complete. Context-centric and v6 tables ready.")


if __name__ == "__main__":
    main()
