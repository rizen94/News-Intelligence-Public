#!/usr/bin/env python3
"""Record a migration as applied in public.applied_migrations (after successful run).

From project root:
  PYTHONPATH=api uv run python api/scripts/register_applied_migration.py 176 --notes "run_migration_176.py"
"""

import argparse
import hashlib
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


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("migration_id", help="e.g. 176 or 176_applied_migrations_ledger")
    p.add_argument("--notes", default="", help="Free text")
    p.add_argument("--env", default="", help="environment label e.g. dev, staging, prod")
    p.add_argument("--file", help="Optional path to migration SQL for checksum")
    args = p.parse_args()

    checksum = None
    if args.file and os.path.isfile(args.file):
        with open(args.file, "rb") as f:
            checksum = hashlib.sha256(f.read()).hexdigest()[:64]

    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        print("ERROR: no DB connection")
        return 1

    env = args.env.strip() or None
    notes = args.notes.strip() or None

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.applied_migrations (migration_id, checksum, environment, notes)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (migration_id) DO UPDATE SET
                    applied_at = NOW(),
                    checksum = COALESCE(EXCLUDED.checksum, public.applied_migrations.checksum),
                    environment = COALESCE(EXCLUDED.environment, public.applied_migrations.environment),
                    notes = COALESCE(EXCLUDED.notes, public.applied_migrations.notes)
                """,
                (args.migration_id, checksum, env, notes),
            )
        conn.commit()
        print(f"Recorded applied_migrations: {args.migration_id}")
        return 0
    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
