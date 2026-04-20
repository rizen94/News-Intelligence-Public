#!/usr/bin/env python3
"""
Full database inventory: schemas, table row counts, empty tables, key expected objects.

Read-only. From repo root:
  PYTHONPATH=api uv run python scripts/db_full_inventory.py
  PYTHONPATH=api uv run python scripts/db_full_inventory.py --json > reports/db_inventory.json

Uses DB from env (same as api shared.database.connection).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (ROOT, os.path.join(ROOT, "api")):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(ROOT, "api", ".env"), override=False)
    load_dotenv(os.path.join(ROOT, ".env"), override=False)
except ImportError:
    pass

if not os.environ.get("DB_PASSWORD") and os.path.exists(
    os.path.join(ROOT, ".db_password_widow")
):
    try:
        with open(os.path.join(ROOT, ".db_password_widow")) as f:
            os.environ.setdefault("DB_PASSWORD", f.read().strip())
    except OSError:
        pass

DEFAULT_SCHEMAS = (
    "public",
    "politics",
    "finance",
    "science_tech",
    "intelligence",
    "orchestration",
)

EXPECTED_TABLES = [
    ("public", "domains"),
    ("public", "chronological_events"),
    ("public", "automation_run_history"),
    ("public", "automation_state"),
    ("politics", "articles"),
    ("politics", "storylines"),
    ("politics", "rss_feeds"),
    ("intelligence", "contexts"),
    ("intelligence", "processed_documents"),
    ("intelligence", "tracked_events"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="DB full inventory (read-only)")
    parser.add_argument("--json", action="store_true", help="Print JSON only")
    args = parser.parse_args()

    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        print("ERROR: Could not connect to database", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc).isoformat()
    out: dict = {"generated_at_utc": now, "schemas": {}, "expected_tables": [], "missing_expected": []}

    try:
        with conn.cursor() as cur:
            for schema in DEFAULT_SCHEMAS:
                cur.execute(
                    """
                    SELECT tablename FROM pg_tables WHERE schemaname = %s ORDER BY tablename
                    """,
                    (schema,),
                )
                names = [r[0] for r in cur.fetchall()]
                schema_info: dict = {"tables": []}
                for name in names:
                    # Identifiers from pg_tables only
                    cur.execute(f'SELECT COUNT(*) FROM "{schema}"."{name}"')
                    cnt = cur.fetchone()[0]
                    schema_info["tables"].append({"name": name, "row_count": cnt})
                empty = [t["name"] for t in schema_info["tables"] if t["row_count"] == 0]
                schema_info["empty_table_names"] = empty
                out["schemas"][schema] = schema_info

            for schema, table in EXPECTED_TABLES:
                cur.execute(
                    """
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = %s AND table_name = %s
                    """,
                    (schema, table),
                )
                ok = cur.fetchone() is not None
                out["expected_tables"].append({"schema": schema, "table": table, "present": ok})
                if not ok:
                    out["missing_expected"].append(f"{schema}.{table}")
    finally:
        conn.close()

    if args.json:
        print(json.dumps(out, indent=2))
        return 0 if not out["missing_expected"] else 1

    print("=" * 60)
    print(f"DB full inventory (UTC {now})")
    print("=" * 60)
    for schema, info in out["schemas"].items():
        n_tables = len(info["tables"])
        n_empty = len(info["empty_table_names"])
        print(f"\n[{schema}] tables={n_tables}, empty={n_empty}")
        if info["empty_table_names"]:
            for en in sorted(info["empty_table_names"])[:40]:
                print(f"  (empty) {en}")
            if len(info["empty_table_names"]) > 40:
                print(f"  ... +{len(info['empty_table_names']) - 40} more empty")
    print("\n--- Expected critical tables ---")
    for et in out["expected_tables"]:
        status = "OK" if et["present"] else "MISSING"
        print(f"  [{status}] {et['schema']}.{et['table']}")
    print("=" * 60)
    return 0 if not out["missing_expected"] else 1


if __name__ == "__main__":
    sys.exit(main())
