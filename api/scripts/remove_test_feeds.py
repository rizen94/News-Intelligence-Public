#!/usr/bin/env python3
"""
Remove test/sample RSS feeds from politics, finance, and science_tech.rss_feeds.
Matches: feed_name containing 'test' or 'sample' (case-insensitive), or feed_url containing 'example.com'.
Articles reference feeds with ON DELETE SET NULL, so feed rows can be deleted safely.

Usage:
  # Preview only (default)
  python api/scripts/remove_test_feeds.py

  # Actually delete
  python api/scripts/remove_test_feeds.py --execute
"""

import os
import sys
import argparse

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

DOMAIN_SCHEMAS = [("politics", "politics"), ("finance", "finance"), ("science_tech", "science-tech")]


def main():
    parser = argparse.ArgumentParser(description="Remove test/sample RSS feeds from domain tables.")
    parser.add_argument("--execute", action="store_true", help="Actually delete; default is dry-run.")
    args = parser.parse_args()
    do_delete = args.execute

    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database.")
        sys.exit(1)

    total_found = 0
    to_delete_by_schema = []

    try:
        for schema, domain_key in DOMAIN_SCHEMAS:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, feed_name, feed_url
                    FROM {schema}.rss_feeds
                    WHERE feed_name ILIKE %s
                       OR feed_name ILIKE %s
                       OR feed_url ILIKE %s
                    ORDER BY id
                    """,
                    ("%test%", "%sample%", "%example.com%"),
                )
                rows = cur.fetchall()
            if rows:
                to_delete_by_schema.append((schema, domain_key, rows))
                total_found += len(rows)

        if total_found == 0:
            print("No test/sample feeds found in any domain.")
            conn.close()
            return

        print(f"Found {total_found} test/sample feed(s) across domains:\n")
        for schema, domain_key, rows in to_delete_by_schema:
            print(f"  {schema} ({domain_key}):")
            for r in rows:
                print(f"    id={r[0]}  {r[1][:50]}  {r[2][:60]}")
            print()

        if not do_delete:
            print("Dry-run. Run with --execute to delete these feeds.")
            conn.close()
            return

        deleted = 0
        for schema, _domain_key, rows in to_delete_by_schema:
            ids = [r[0] for r in rows]
            with conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM {schema}.rss_feeds WHERE id = ANY(%s)",
                    (ids,),
                )
                deleted += cur.rowcount
            conn.commit()
        print(f"Deleted {deleted} feed(s).")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
