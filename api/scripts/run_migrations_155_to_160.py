#!/usr/bin/env python3
"""Run migrations 155 through 160 in order.

From project root:
  PYTHONPATH=api .venv/bin/python3 api/scripts/run_migrations_155_to_160.py

Or from api/:
  python3 scripts/run_migrations_155_to_160.py

Uses DB from env (DB_HOST, DB_NAME, DB_USER, DB_PASSWORD) or .db_password_widow.
Skips migrations whose file is missing. Stops on first error.
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

# Ordered list: (number, filename). Two 158s: claim_merges then persistent_editorial_documents.
# 161: automation_run_history — monitoring "last 24h" survives API restart
MIGRATIONS_155_160 = [
    (155, "155_quality_feedback_schema.sql"),
    (156, "156_cross_domain_correlations.sql"),
    (157, "157_anomaly_investigations.sql"),
    (158, "158_claim_merges.sql"),
    (158, "158_persistent_editorial_documents.sql"),
    (159, "159_international_commodity_feeds.sql"),
    (160, "160_processed_documents_t3.sql"),
    (161, "161_automation_run_history.sql"),
]


def main():
    from shared.database.connection import get_db_connection

    api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    migrations_dir = os.path.join(api_dir, "database", "migrations")

    conn = get_db_connection()
    if not conn:
        print("ERROR: Could not connect to database (check DB_HOST, DB_NAME, DB_USER, DB_PASSWORD)")
        sys.exit(1)

    applied = 0
    for _num, name in MIGRATIONS_155_160:
        path = os.path.join(migrations_dir, name)
        if not os.path.exists(path):
            print(f"SKIP (file missing): {name}")
            continue
        with open(path, encoding="utf-8") as f:
            sql = f.read()
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
            print(f"✅ {name}")
            applied += 1
        except Exception as e:
            conn.rollback()
            print(f"ERROR: {name} failed: {e}")
            sys.exit(1)

    conn.close()
    print(f"✅ Migrations 155–161 complete. Applied {applied} file(s).")


if __name__ == "__main__":
    main()
