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

    from config.settings import (
        get_rss_ingest_excluded_domain_keys,
        rss_ingest_mirror_pipeline_enabled,
    )
    from shared.database.connection import get_db_connection
    from shared.domain_registry import pipeline_url_schema_pairs, url_schema_pairs

    from_registry = list(url_schema_pairs())
    mirror = rss_ingest_mirror_pipeline_enabled()
    skip_dk = get_rss_ingest_excluded_domain_keys()
    base_pairs = list(pipeline_url_schema_pairs()) if mirror else from_registry
    effective = [
        (dk, sch)
        for dk, sch in base_pairs
        if str(dk).strip().lower() not in skip_dk
    ]

    def _p(msg: str) -> None:
        print(msg, flush=True)

    _p(f"Domains in registry (YAML + built-ins, active): {len(from_registry)}")
    _p(f"RSS_INGEST_MIRROR_PIPELINE: {mirror}  (if true, same silos as pipeline_url_schema_pairs)")
    if skip_dk:
        _p(f"RSS_INGEST_EXCLUDE_DOMAIN_KEYS: {sorted(skip_dk)}")
    _p(f"Effective RSS collect domains this run: {len(effective)} -> {[k for k, _ in effective]}")
    if not effective:
        _p("No domains to collect — check feeds, YAML, and mirror/exclude env.")
        return

    conn = get_db_connection()
    if not conn:
        print("ERROR: no database connection")
        return
    try:
        with conn.cursor() as cur:
            for domain_key, schema in from_registry:
                try:
                    cur.execute(
                        f"""
                        SELECT COUNT(*) FILTER (WHERE is_active = true),
                               COUNT(*) FROM {schema}.rss_feeds
                        """
                    )
                    row = cur.fetchone()
                    n_act, n_all = (row[0] or 0), (row[1] or 0)
                    tag = " [collect]" if (domain_key, schema) in effective else ""
                    _p(f"  {domain_key:24} schema={schema:22} active_feeds={n_act:4} total_feeds={n_all:4}{tag}")
                except Exception as e:
                    _p(f"  {domain_key:24} schema={schema:22} ERROR: {e}")
    finally:
        conn.close()

    if args.no_collect:
        return

    _p("\nRunning collect_rss_feeds() …")
    from collectors.rss_collector import collect_rss_feeds

    n = collect_rss_feeds()
    _p(f"Done. RSS activity this run (new inserts + same-URL updates): {n}")

    conn = get_db_connection()
    if not conn:
        return
    try:
        _p(
            "\nRows with created_at in the last 45 minutes (new URLs). "
            "Updates to existing URLs do not change created_at — use collector logs per feed for those."
        )
        with conn.cursor() as cur:
            for domain_key, schema in effective:
                try:
                    cur.execute(
                        f"""
                        SELECT COUNT(*), COALESCE(MAX(created_at)::text, '')
                        FROM {schema}.articles
                        WHERE created_at >= NOW() - INTERVAL '45 minutes'
                        """
                    )
                    r = cur.fetchone()
                    cnt, mx = (r[0] or 0), (r[1] or "")
                    cur.execute(
                        f"""
                        SELECT id, LEFT(COALESCE(source_domain, ''), 42), LEFT(title, 55), LEFT(url, 72)
                        FROM {schema}.articles
                        WHERE created_at >= NOW() - INTERVAL '45 minutes'
                        ORDER BY created_at DESC
                        LIMIT 4
                        """
                    )
                    samples = cur.fetchall()
                    _p(f"  {domain_key} ({schema}): new_rows={cnt}  latest_created={mx}")
                    for sid, fn, title, url in samples:
                        _p(f"      id={sid}  source_domain={fn!r}")
                        _p(f"            title={title!r}")
                        _p(f"            url={url!r}")
                except Exception as e:
                    _p(f"  {domain_key} ({schema}): ERROR {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
