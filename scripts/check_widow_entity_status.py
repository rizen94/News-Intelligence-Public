#!/usr/bin/env python3
"""
Check entity pipeline status on the database: per-domain entity_canonical and
article_entities counts, description backfill coverage, and recent update times.
Run on Widow (with local .env) or from Primary (DB points at Widow).
  PYTHONPATH=api python scripts/check_widow_entity_status.py
"""
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
API = os.path.join(ROOT, "api")
if API not in sys.path:
    sys.path.insert(0, API)

# Load .env
env_path = os.path.join(ROOT, ".env")
if os.path.isfile(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                key = key.strip()
                if key in ("DB_PASSWORD", "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER"):
                    os.environ.setdefault(key, val.strip().strip('"').strip("'"))
if not os.environ.get("DB_PASSWORD") and os.path.isfile(os.path.join(ROOT, ".db_password_widow")):
    with open(os.path.join(ROOT, ".db_password_widow")) as f:
        os.environ.setdefault("DB_PASSWORD", f.read().splitlines()[0].strip())


def main():
    try:
        from shared.database.connection import get_db_connection
    except Exception as e:
        print(f"Import failed: {e}")
        return 1
    conn = get_db_connection()
    if not conn:
        print("Database connection failed (check DB_HOST, DB_PASSWORD, .env)")
        return 1

    domains = [("politics", "politics"), ("finance", "finance"), ("science_tech", "science-tech")]
    print("Entity pipeline status (entity_canonical, article_entities, descriptions, last updated)")
    print("=" * 72)
    try:
        for schema, domain_key in domains:
            cur = conn.cursor()
            # entity_canonical counts
            cur.execute(
                f"SELECT COUNT(*) FROM {schema}.entity_canonical",
            )
            (canon_count,) = cur.fetchone()
            cur.execute(
                f"SELECT COUNT(*) FROM {schema}.entity_canonical WHERE description IS NOT NULL AND description != ''",
            )
            (with_desc,) = cur.fetchone()
            cur.execute(
                f"SELECT MAX(updated_at) FROM {schema}.entity_canonical",
            )
            (last_updated,) = cur.fetchone()
            cur.execute(
                f"SELECT COUNT(*) FROM {schema}.article_entities",
            )
            (mentions_count,) = cur.fetchone()
            cur.execute(
                f"SELECT COUNT(*) FROM {schema}.article_entities WHERE canonical_entity_id IS NOT NULL",
            )
            (resolved_count,) = cur.fetchone()

            last_str = last_updated.isoformat() if last_updated else "n/a"
            pct = (100 * with_desc / canon_count) if canon_count else 0
            print(f"\n  {domain_key}")
            print(f"    entity_canonical:     {canon_count:,}")
            print(f"    with description:     {with_desc:,} ({pct:.1f}%)")
            print(f"    last_updated:         {last_str}")
            print(f"    article_entities:     {mentions_count:,} (resolved to canonical: {resolved_count:,})")
        print()
        conn.close()
        print("OK — DB reachable, entity tables present.")
        return 0
    except Exception as e:
        print(f"\nError: {e}")
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
