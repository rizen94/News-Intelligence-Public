#!/usr/bin/env python3
"""
Print RSS eligibility per domain (registry + active feed count), then run collect_rss_feeds() once.

Use after adding a domain silo to verify YAML is visible and feeds exist before expecting articles.

  cd /path/to/repo && PYTHONPATH=api uv run python api/scripts/force_rss_collection.py
  PYTHONPATH=api uv run python api/scripts/force_rss_collection.py --no-collect   # status only

Requires DB_* in env (same as API). On Widow: run from /opt/news-intelligence with .env loaded.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv

    _api = Path(__file__).resolve().parent.parent
    load_dotenv(_api / ".env", override=False)
    load_dotenv(_api.parent / ".env", override=False)
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-collect",
        action="store_true",
        help="Only print domain/feed status; do not run collection",
    )
    args = parser.parse_args()

    from shared.database.connection import get_db_connection
    from shared.domain_registry import url_schema_pairs

    pairs = list(url_schema_pairs())
    print(f"Domains in registry (YAML + built-ins, active): {len(pairs)}")
    if not pairs:
        print("No domains — add api/config/domains/<key>.yaml with is_active true (and restart API if needed).")
        return

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            for domain_key, schema in pairs:
                try:
                    cur.execute(
                        f"""
                        SELECT COUNT(*) FILTER (WHERE is_active = true),
                               COUNT(*) FROM {schema}.rss_feeds
                        """
                    )
                    row = cur.fetchone()
                    n_act, n_all = (row[0] or 0), (row[1] or 0)
                    print(f"  {domain_key:16} schema={schema:20} active_feeds={n_act:4} total_feeds={n_all:4}")
                except Exception as e:
                    print(f"  {domain_key:16} schema={schema:20} ERROR: {e}")
    finally:
        conn.close()

    if args.no_collect:
        return

    print("\nRunning collect_rss_feeds() …")
    from collectors.rss_collector import collect_rss_feeds

    n = collect_rss_feeds()
    print(f"Done. RSS activity this run (new inserts + same-URL updates): {n}")


if __name__ == "__main__":
    main()
