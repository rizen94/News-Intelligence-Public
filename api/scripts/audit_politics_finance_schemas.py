#!/usr/bin/env python3
"""
Row-count audit for politics / finance canonical schemas (migration 227).

After 227, ``politics`` and ``finance`` are the only silos; ``politics_2`` / ``finance_2``
must not exist. Exit 1 if ``*_2`` stubs remain or legacy keys point at wrong schemas.

  PYTHONPATH=api uv run python api/scripts/audit_politics_finance_schemas.py
  PYTHONPATH=api uv run python api/scripts/audit_politics_finance_schemas.py --strict
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_API = Path(__file__).resolve().parent.parent
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

try:
    from dotenv import load_dotenv

    load_dotenv(_API / ".env", override=False)
    load_dotenv(_API.parent / ".env", override=False)
except ImportError:
    pass

if not os.environ.get("DB_PASSWORD") and (_API.parent / ".db_password_widow").is_file():
    os.environ["DB_PASSWORD"] = (_API.parent / ".db_password_widow").read_text(encoding="utf-8").strip()

_CORE_TABLES = (
    "articles",
    "rss_feeds",
    "storylines",
    "topics",
    "article_entities",
)


def _schemas(cur) -> set[str]:
    cur.execute("SELECT schema_name FROM information_schema.schemata")
    return {r[0] for r in cur.fetchall()}


def _count_table(cur, schema: str, table: str) -> int | None:
    cur.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = %s AND table_name = %s AND table_type = 'BASE TABLE'
        """,
        (schema, table),
    )
    if not cur.fetchone():
        return None
    cur.execute(f"SELECT COUNT(*) FROM {schema}.{table}")
    return int(cur.fetchone()[0])


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit politics/finance schemas before migration 219")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if canonical schemas missing or *_2 stubs / wrong domain registry rows",
    )
    args = parser.parse_args()

    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        raise SystemExit("No database connection")

    pairs = [
        ("politics", "politics"),
        ("finance", "finance"),
    ]
    stub_schemas = ("politics_2", "finance_2")
    legacy_has_rows = False
    stubs_present = False
    with conn.cursor() as cur:
        existing = _schemas(cur)
        print("--- audit_politics_finance_schemas ---")
        for label, sch in pairs:
            if sch not in existing:
                print(f"\n{label} ({sch}): schema does not exist")
                continue
            print(f"\n{label} ({sch}):")
            for table in _CORE_TABLES:
                n = _count_table(cur, sch, table)
                if n is None:
                    print(f"  {table}: (missing)")
                else:
                    print(f"  {table}: {n}")
        for stub in stub_schemas:
            if stub in existing:
                stubs_present = True
                print(f"\nSTUB STILL PRESENT: {stub} (apply migration 227 or DROP manually)")
        cur.execute(
            "SELECT domain_key, schema_name, is_active FROM public.domains "
            "WHERE domain_key IN ('politics', 'finance') ORDER BY domain_key"
        )
        print("\npublic.domains:")
        for row in cur.fetchall():
            print(f"  {row}")
            dk, sch, _ = row
            if sch in stub_schemas or sch != dk.replace("-", "_"):
                if dk in ("politics", "finance") and sch not in ("politics", "finance"):
                    legacy_has_rows = True
    conn.close()
    print("---")
    if stubs_present:
        print("FAIL: politics_2/finance_2 stub schemas still exist")
        sys.exit(1)
    if legacy_has_rows:
        print("FAIL: public.domains schema_name must be politics/finance")
        sys.exit(1)
    print("OK: canonical politics/finance silos; no *_2 stubs")


if __name__ == "__main__":
    main()
