#!/usr/bin/env python3
"""
Delete articles stuck in entity_extraction failed_needs_retry (bulk catch-up churn).

Reads IDs from CSV (schema_name,id,...) or queries DB when --from-db.

  PYTHONPATH=api .venv/bin/python3 api/scripts/delete_stuck_entity_extraction_articles.py --dry-run
  PYTHONPATH=api .venv/bin/python3 api/scripts/delete_stuck_entity_extraction_articles.py --csv docs/pipeline_repair/stuck_entity_extraction_articles_20260611.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

_REPO_ROOT = _API_ROOT.parent
BULK_SINCE = "2026-06-10T14:00:00"


def _load_env() -> None:
    env_file = _REPO_ROOT / ".env"
    if env_file.is_file():
        from dotenv import load_dotenv

        load_dotenv(env_file, override=False)


def _schema_has_table(cur, schema: str, table: str) -> bool:
    cur.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = %s AND table_name = %s
        """,
        (schema, table),
    )
    return cur.fetchone() is not None


def _fetch_from_db() -> dict[str, list[int]]:
    schemas = (
        "politics",
        "finance",
        "legal",
        "medicine",
        "artificial_intelligence",
    )
    out: dict[str, list[int]] = defaultdict(list)
    from shared.database.connection import get_db_connection_context

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for schema in schemas:
                cur.execute(
                    f"""
                    SELECT id FROM {schema}.articles
                    WHERE metadata::jsonb->'pipeline'->'entity_extraction'->>'last_terminal_state'
                          = 'failed_needs_retry'
                      AND metadata::jsonb->'pipeline'->'entity_extraction'->>'last_pass_at'
                          > %s
                    ORDER BY id
                    """,
                    (BULK_SINCE,),
                )
                out[schema] = [int(r[0]) for r in cur.fetchall()]
    return out


def _load_csv(path: Path) -> dict[str, list[int]]:
    out: dict[str, list[int]] = defaultdict(list)
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            schema = (row.get("schema_name") or row.get("schema") or "").strip()
            aid = int(row["id"])
            if schema:
                out[schema].append(aid)
    return out


def _delete_schema(cur, schema: str, ids: list[int], *, dry_run: bool) -> int:
    if not ids:
        return 0
    ph = ",".join(["%s"] * len(ids))
    if dry_run:
        return len(ids)
    if _schema_has_table(cur, schema, "article_topic_assignments"):
        cur.execute(
            f"DELETE FROM {schema}.article_topic_assignments WHERE article_id IN ({ph})",
            ids,
        )
    if _schema_has_table(cur, schema, "storyline_articles"):
        cur.execute(
            f"DELETE FROM {schema}.storyline_articles WHERE article_id IN ({ph})",
            ids,
        )
    cur.execute(f"DELETE FROM {schema}.articles WHERE id IN ({ph})", ids)
    return int(cur.rowcount or 0)


def main() -> int:
    _load_env()
    parser = argparse.ArgumentParser(description="Delete stuck entity-extraction articles")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--from-db", action="store_true")
    args = parser.parse_args()

    if args.csv:
        by_schema = _load_csv(args.csv)
    elif args.from_db:
        by_schema = _fetch_from_db()
    else:
        default_csv = _REPO_ROOT / "docs/pipeline_repair/stuck_entity_extraction_articles_20260611.csv"
        by_schema = _load_csv(default_csv) if default_csv.is_file() else _fetch_from_db()

    total_ids = sum(len(v) for v in by_schema.values())
    print(f"Articles to delete: {total_ids}")
    for schema, ids in sorted(by_schema.items()):
        print(f"  {schema}: {len(ids)} ids")

    if args.dry_run:
        print("Dry run — no deletes.")
        return 0

    from shared.database.connection import get_db_connection_context

    deleted = 0
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for schema, ids in sorted(by_schema.items()):
                n = _delete_schema(cur, schema, ids, dry_run=False)
                print(f"  deleted {schema}: {n}")
                deleted += n
        conn.commit()
    print(f"Done. Deleted {deleted} articles.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
