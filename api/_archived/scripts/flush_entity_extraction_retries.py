#!/usr/bin/env python3
"""
Mark entity_extraction failed_needs_retry articles as processed_empty_legitimate (bulk flush).

Stops bulk/automation from re-attempting empty-extraction / transient-error rows.

  PYTHONPATH=api .venv/bin/python3 api/scripts/flush_entity_extraction_retries.py --dry-run
  PYTHONPATH=api .venv/bin/python3 api/scripts/flush_entity_extraction_retries.py
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

_REPO_ROOT = _API_ROOT.parent
ARCHIVE = _REPO_ROOT / "docs/pipeline_repair"


def _load_env() -> None:
    env_file = _REPO_ROOT / ".env"
    if env_file.is_file():
        from dotenv import load_dotenv

        load_dotenv(env_file, override=False)


def _fetch_retries() -> dict[str, list[tuple[int, str, str, int]]]:
    """schema -> [(id, title, outcome, content_len)]"""
    from shared.database.connection import get_db_connection_context
    from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema

    out: dict[str, list[tuple[int, str, str, int]]] = defaultdict(list)
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for dk in get_pipeline_active_domain_keys():
                schema = resolve_domain_schema(dk)
                cur.execute(
                    f"""
                    SELECT a.id, COALESCE(a.title, ''), LENGTH(COALESCE(a.content, '')),
                           COALESCE(a.metadata::jsonb->'pipeline'->'entity_extraction'->>'last_outcome', '')
                    FROM {schema}.articles a
                    WHERE a.metadata::jsonb->'pipeline'->'entity_extraction'->>'last_terminal_state'
                          = 'failed_needs_retry'
                    ORDER BY a.id
                    """
                )
                for row in cur.fetchall():
                    out[schema].append((int(row[0]), row[1], row[3], int(row[2] or 0)))
    return out


def main() -> int:
    _load_env()
    parser = argparse.ArgumentParser(description="Flush entity_extraction retry backlog")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from shared.pipeline_pass_marker import (
        TERMINAL_PROCESSED_EMPTY_LEGITIMATE,
        record_article_phase_pass,
    )

    by_schema = _fetch_retries()
    total = sum(len(v) for v in by_schema.values())
    print(f"Articles with failed_needs_retry: {total}")
    for schema, rows in sorted(by_schema.items()):
        print(f"  {schema}: {len(rows)}")

    if args.dry_run or total == 0:
        return 0

    ARCHIVE.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    csv_path = ARCHIVE / f"flushed_entity_retries_{stamp}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["schema", "article_id", "outcome", "content_len", "title"])
        for schema, rows in sorted(by_schema.items()):
            for aid, title, outcome, clen in rows:
                w.writerow([schema, aid, outcome, clen, title[:120]])

    flushed = 0
    for schema, rows in sorted(by_schema.items()):
        for aid, _title, _outcome, _clen in rows:
            record_article_phase_pass(
                schema,
                aid,
                "entity_extraction",
                "bulk_retry_flush",
                terminal_state=TERMINAL_PROCESSED_EMPTY_LEGITIMATE,
            )
            flushed += 1
    print(f"Flushed {flushed} articles -> processed_empty_legitimate (bulk_retry_flush)")
    print(f"Archive: {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
