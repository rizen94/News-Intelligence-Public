#!/usr/bin/env python3
"""
Mark stale unprocessed fact_change_log rows as processed (one-time backlog cut).

Does not run story updates; only clears the queue counter so story_enhancement
can focus on recent facts. Preview with --dry-run first.

  PYTHONPATH=api uv run python api/scripts/catchup_stale_fact_change_log.py --dry-run
  PYTHONPATH=api uv run python api/scripts/catchup_stale_fact_change_log.py --days 30
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent

try:
    from dotenv import load_dotenv

    load_dotenv(_root / "api" / ".env", override=False)
    load_dotenv(_root / ".env", override=False)
except ImportError:
    pass

if not os.environ.get("DB_PASSWORD") and (_pw := _root / ".db_password_widow").is_file():
    os.environ["DB_PASSWORD"] = _pw.read_text(encoding="utf-8").strip()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.database.connection import get_db_connection_context  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Mark stale fact_change_log rows processed")
    parser.add_argument("--days", type=int, default=30, help="Age threshold in days (default 30)")
    parser.add_argument("--dry-run", action="store_true", help="Preview counts only")
    args = parser.parse_args()
    days = max(1, args.days)

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.fact_change_log
                WHERE processed = FALSE
                """
            )
            total = int(cur.fetchone()[0])
            cur.execute(
                f"""
                SELECT COUNT(*) FROM intelligence.fact_change_log
                WHERE processed = FALSE
                  AND changed_at < NOW() - INTERVAL '{days} days'
                """
            )
            stale = int(cur.fetchone()[0])
            cur.execute(
                f"""
                SELECT MIN(changed_at), MAX(changed_at)
                FROM intelligence.fact_change_log
                WHERE processed = FALSE AND changed_at < NOW() - INTERVAL '{days} days'
                """
            )
            span = cur.fetchone()

    print(f"unprocessed_total={total} stale_older_than_{days}d={stale} would_remain={total - stale}")
    if span and span[0]:
        print(f"stale_span={span[0]} .. {span[1]}")

    if args.dry_run:
        print("dry-run: no changes")
        return 0

    if stale == 0:
        print("nothing to update")
        return 0

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE intelligence.fact_change_log
                SET processed = TRUE,
                    processed_at = NOW(),
                    story_updates_triggered = 0
                WHERE processed = FALSE
                  AND changed_at < NOW() - INTERVAL '{days} days'
                """
            )
            updated = cur.rowcount
        conn.commit()

    print(f"updated={updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
