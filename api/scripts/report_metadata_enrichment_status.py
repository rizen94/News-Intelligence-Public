#!/usr/bin/env python3
"""
Report metadata enrichment coverage vs the same definition as backlog_metrics
``_count_metadata_enrichment_pending`` and ``run_metadata_enrichment_batch_for_domains``:

  Eligible: content IS NOT NULL AND LENGTH(content) > 50
  Done:     metadata->>'enrichment_done' = 'true' (set by enrich_article_for_schema)

Usage (repo root):

  PYTHONPATH=api uv run python api/scripts/report_metadata_enrichment_status.py

Optional:

  PYTHONPATH=api uv run python api/scripts/report_metadata_enrichment_status.py --schema politics
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

if (
    not os.environ.get("DB_PASSWORD")
    and Path(Path(__file__).resolve().parent.parent.parent / ".db_password_widow").is_file()
):
    try:
        with open(Path(__file__).resolve().parent.parent.parent / ".db_password_widow") as f:
            os.environ["DB_PASSWORD"] = f.read().strip()
    except OSError:
        pass

_API = Path(__file__).resolve().parent.parent
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Per-domain metadata enrichment coverage (enrichment_done in articles.metadata)"
    )
    parser.add_argument(
        "--schema",
        type=str,
        default="",
        help="Single Postgres schema (e.g. politics). Default: all active domain schemas from registry.",
    )
    args = parser.parse_args()

    from shared.database.connection import get_db_connection
    from shared.domain_registry import get_schema_names_active

    conn = get_db_connection()
    if not conn:
        raise SystemExit("No database connection")

    schemas = [args.schema.strip()] if args.schema.strip() else list(get_schema_names_active())

    grand = {"total": 0, "eligible": 0, "pending": 0, "done": 0, "done_qs": 0, "done_sent": 0}

    print("metadata enrichment — eligible = content length > 50; done = metadata.enrichment_done = true")
    print("-" * 100)
    print(
        f"{'schema':<22} {'total':>10} {'eligible':>10} {'pending':>10} {'done_elig':>10} "
        f"{'%elig':>8} {'qs_set':>8} {'sent_set':>8}"
    )
    print("-" * 100)

    try:
        with conn.cursor() as cur:
            for schema in schemas:
                cur.execute(
                    f"""
                    SELECT
                        COUNT(*)::bigint AS total,
                        COUNT(*) FILTER (WHERE content IS NOT NULL AND LENGTH(content) > 50)::bigint AS eligible,
                        COUNT(*) FILTER (
                            WHERE content IS NOT NULL AND LENGTH(content) > 50
                              AND (metadata IS NULL OR (metadata->>'enrichment_done') IS NULL)
                        )::bigint AS pending,
                        COUNT(*) FILTER (
                            WHERE content IS NOT NULL AND LENGTH(content) > 50
                              AND (metadata->>'enrichment_done') = 'true'
                        )::bigint AS done_eligible,
                        COUNT(*) FILTER (
                            WHERE (metadata->>'enrichment_done') = 'true'
                              AND NOT (content IS NOT NULL AND LENGTH(content) > 50)
                        )::bigint AS done_but_short,
                        COUNT(*) FILTER (
                            WHERE (metadata->>'enrichment_done') = 'true' AND quality_score IS NOT NULL
                        )::bigint AS done_qs,
                        COUNT(*) FILTER (
                            WHERE (metadata->>'enrichment_done') = 'true' AND sentiment_score IS NOT NULL
                        )::bigint AS done_sent
                    FROM {schema}.articles
                    """
                )
                row = cur.fetchone()
                total, eligible, pending, done_eligible, done_short, done_qs, done_sent = [
                    int(x or 0) for x in row
                ]
                pct = (100.0 * done_eligible / eligible) if eligible else 0.0
                print(
                    f"{schema:<22} {total:10d} {eligible:10d} {pending:10d} {done_eligible:10d} "
                    f"{pct:7.1f}% {done_qs:8d} {done_sent:8d}"
                    + (f"  (+{done_short} done w/ short content)" if done_short else "")
                )
                grand["total"] += total
                grand["eligible"] += eligible
                grand["pending"] += pending
                grand["done"] += done_eligible
                grand["done_qs"] += done_qs
                grand["done_sent"] += done_sent
    finally:
        conn.close()

    print("-" * 100)
    ge = grand["eligible"]
    gd = grand["done"]
    gp = grand["pending"]
    pct_all = (100.0 * gd / ge) if ge else 0.0
    print(
        f"{'ALL (sum)':<22} {grand['total']:10d} {ge:10d} {gp:10d} {gd:10d} {pct_all:7.1f}% "
        f"{grand['done_qs']:8d} {grand['done_sent']:8d}"
    )
    print("-" * 100)
    print("Interpretation:")
    print("  • pending should be ~0 if backlog is cleared (same filter as backlog_metrics.metadata_enrichment).")
    print("  • %elig = done among eligible rows only (content > 50); backlog is the pending column.")
    print("  • qs_set / sent_set = rows with enrichment_done and quality_score / sentiment_score populated.")
    if ge > 0 and gp == 0:
        print("  • Status: backlog complete for this definition.")
    elif ge > 0:
        print(f"  • Status: {gp} article(s) still pending metadata enrichment.")


if __name__ == "__main__":
    main()
