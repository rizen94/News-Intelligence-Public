#!/usr/bin/env python3
"""Run migration 201: politics-2 / finance-2 silos (schemas politics_2, finance_2).

From project root:
  PYTHONPATH=api uv run python api/scripts/run_migration_201.py
Then record:
  PYTHONPATH=api uv run python api/scripts/register_applied_migration.py 201 \\
    --notes run_migration_201.py --file api/database/migrations/201_politics2_finance2_domain_silos.sql

Enable ``api/config/domains/politics-2.yaml`` and ``finance-2.yaml`` (already in repo), run
``seed_domain_rss_from_yaml.py`` or ``provision_domain.py`` to seed feeds. Set env
``RSS_INGEST_EXCLUDE_DOMAIN_KEYS=politics,finance`` when new feeds are ready so RSS targets the -2 silos only.
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


def main() -> None:
    from shared.database.connection import get_db_connection
    from shared.migration_sql_paths import resolve_migration_sql_file

    try:
        path = resolve_migration_sql_file("201_politics2_finance2_domain_silos.sql")
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    conn = get_db_connection()
    if not conn:
        print("ERROR: Could not connect to database (check DB_* env)")
        sys.exit(1)

    try:
        with open(path) as f:
            sql = f.read()
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = 0")
            cur.execute(sql)
        conn.commit()
        print("201_politics2_finance2_domain_silos.sql applied successfully")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
