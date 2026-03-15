#!/usr/bin/env python3
"""
One-off: Remove research topics that were saved as gold but are actually platinum
(2023 platinum price drop test cases).

From project root: .venv/bin/python api/scripts/remove_corrupted_platinum_research_topics.py
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

def main():
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        print("Database unavailable. Set DB_PASSWORD and ensure DB is reachable.")
        sys.exit(1)

    try:
        with conn.cursor() as cur:
            # Select platinum-related topics that were incorrectly stored as topic='gold'
            cur.execute(
                """
                SELECT id, name, query, topic, created_at
                FROM finance.research_topics
                WHERE topic = 'gold'
                  AND (name ILIKE '%platinum%' OR query ILIKE '%platinum%')
                ORDER BY id
                """
            )
            rows = cur.fetchall()
        if not rows:
            print("No corrupted platinum-as-gold research topics found.")
            conn.close()
            return

        print(f"Found {len(rows)} topic(s) to remove (platinum content saved as gold):")
        for r in rows:
            print(f"  id={r[0]} name={r[1][:50]}... query={r[2][:60]}... topic={r[3]}")

        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM finance.research_topics
                WHERE topic = 'gold'
                  AND (name ILIKE '%platinum%' OR query ILIKE '%platinum%')
                """
            )
            deleted = cur.rowcount
        conn.commit()
        print(f"Deleted {deleted} row(s).")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
