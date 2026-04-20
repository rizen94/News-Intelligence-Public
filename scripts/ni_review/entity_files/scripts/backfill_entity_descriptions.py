#!/usr/bin/env python3
"""
Backfill entity_canonical.description and wikipedia_page_id from local Wikipedia knowledge.

Run after migration 170. If intelligence.wikipedia_knowledge is empty, use --api-fallback to
fill descriptions via the Wikipedia API.
Usage (from project root; DB credentials in local .env or .db_password_widow):
  PYTHONPATH=api python scripts/backfill_entity_descriptions.py [--limit N] [--batch 500] [--api-fallback]
"""

import argparse
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# Load local .env and .db_password_widow so DB credentials work when run locally (DB may be on Widow)
if os.path.isfile(os.path.join(ROOT, ".env")):
    with open(os.path.join(ROOT, ".env")) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                if key.strip() in ("DB_PASSWORD", "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER"):
                    os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
if not os.environ.get("DB_PASSWORD") and os.path.isfile(os.path.join(ROOT, ".db_password_widow")):
    with open(os.path.join(ROOT, ".db_password_widow")) as f:
        os.environ.setdefault("DB_PASSWORD", f.read().splitlines()[0].strip())

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from shared.database.connection import get_db_connection


def main():
    parser = argparse.ArgumentParser(description="Backfill entity_canonical description from local wiki")
    parser.add_argument("--limit", type=int, default=None, help="Max entities to update per schema")
    parser.add_argument("--batch", type=int, default=500, help="Batch size for lookup")
    parser.add_argument("--api-fallback", action="store_true", help="Use Wikipedia API for names not in local DB")
    args = parser.parse_args()

    conn = get_db_connection()
    if not conn:
        print("ERROR: No database connection")
        sys.exit(1)

    from services.wikipedia_knowledge_service import lookup_batch, lookup_entity_with_fallback

    schemas = ["politics", "finance", "science_tech"]
    total_updated = 0
    for schema in schemas:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, canonical_name
                FROM {schema}.entity_canonical
                WHERE description IS NULL AND canonical_name IS NOT NULL AND canonical_name != ''
                ORDER BY id
                LIMIT %s
                """,
                (args.limit or 999999,),
            )
            rows = cur.fetchall()
        if not rows:
            continue
        ids = [r[0] for r in rows]
        names = [r[1] for r in rows]
        found = lookup_batch(names)
        if args.api_fallback:
            for name in names:
                if name in found:
                    continue
                summary = lookup_entity_with_fallback(name)
                if summary and summary.get("extract"):
                    found[name] = summary
                time.sleep(0.2)
        if not found:
            continue
        with conn.cursor() as cur:
            for (eid, name) in zip(ids, names):
                if name not in found:
                    continue
                rec = found[name]
                extract = (rec.get("extract") or "")[:500]
                page_id = rec.get("page_id")
                cur.execute(
                    f"""
                    UPDATE {schema}.entity_canonical
                    SET description = %s, wikipedia_page_id = %s, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (extract, page_id, eid),
                )
                total_updated += cur.rowcount
        conn.commit()
        print(f"Schema {schema}: updated {len([n for n in names if n in found])} entities")
    print(f"Total updated: {total_updated}")
    conn.close()


if __name__ == "__main__":
    main()
