#!/usr/bin/env python3
"""
Per-feed RSS yield report — articles, quality scores, silencing candidates.

  PYTHONPATH=api uv run python api/scripts/rss_feed_yield_report.py
  PYTHONPATH=api uv run python api/scripts/rss_feed_yield_report.py --csv /tmp/feed_yield.csv
  PYTHONPATH=api uv run python api/scripts/rss_feed_yield_report.py --json
"""

from __future__ import annotations

import argparse
import csv
import json
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


def _load_db_password() -> None:
    import os

    root = Path(__file__).resolve().parent.parent.parent
    pw_file = root / ".db_password_widow"
    if not os.environ.get("DB_PASSWORD") and pw_file.is_file():
        os.environ.setdefault("DB_PASSWORD", pw_file.read_text().splitlines()[0].strip())


def _feed_rows(cur, schema: str, domain_key: str, min_quality: float, window_days: int) -> list[dict]:
    cur.execute(
        f"""
        SELECT
            rf.id,
            rf.feed_name,
            rf.feed_url,
            rf.is_active,
            rf.status,
            rf.tier,
            rf.warning_message,
            rf.last_fetched_at,
            rf.last_success,
            rf.last_error_message,
            rf.created_at,
            COALESCE((rf.filters->>'consecutive_empty_fetches')::int, 0),
            COUNT(a.id) FILTER (
                WHERE a.created_at >= NOW() - (%s || ' days')::interval
            )::bigint AS articles_window,
            MAX(a.quality_score) FILTER (
                WHERE a.created_at >= NOW() - (%s || ' days')::interval
            ) AS max_quality,
            AVG(a.quality_score) FILTER (
                WHERE a.created_at >= NOW() - (%s || ' days')::interval
            ) AS avg_quality,
            COUNT(a.id) FILTER (
                WHERE a.created_at >= NOW() - (%s || ' days')::interval
                  AND COALESCE(a.quality_score, 0) >= %s
            )::bigint AS above_threshold,
            MAX(a.created_at) AS last_insert_at
        FROM {schema}.rss_feeds rf
        LEFT JOIN {schema}.articles a ON (
            a.rss_feed_id = rf.id
            OR (a.rss_feed_id IS NULL AND a.source_domain = rf.feed_name)
        )
        GROUP BY rf.id
        ORDER BY rf.is_active DESC, articles_window ASC, rf.feed_name
        """,
        (window_days, window_days, window_days, window_days, min_quality),
    )
    rows = []
    for r in cur.fetchall():
        articles = int(r[12] or 0)
        above = int(r[16] or 0)
        max_q = float(r[13]) if r[13] is not None else None
        avg_q = float(r[14]) if r[14] is not None else None
        consec_empty = int(r[11] or 0)
        is_active = bool(r[3])
        created_at = r[10]
        reasons = []
        if is_active and r[9]:
            reasons.append("fetch_failure")
        if is_active and consec_empty >= 5:
            reasons.append("consecutive_empty")
        if is_active and articles == 0 and created_at:
            reasons.append("zero_yield")
        if is_active and articles >= 10 and above == 0:
            reasons.append("low_signal_yield")
        rows.append(
            {
                "domain_key": domain_key,
                "schema": schema,
                "feed_id": r[0],
                "feed_name": r[1],
                "feed_url": r[2],
                "is_active": is_active,
                "status": r[4],
                "tier": r[5],
                "warning_message": r[6],
                "last_fetched_at": str(r[7]) if r[7] else None,
                "last_success": str(r[8]) if r[8] else None,
                "last_error_message": (r[9] or "")[:200] or None,
                "consecutive_empty_fetches": consec_empty,
                f"articles_{window_days}d": articles,
                "max_quality": max_q,
                "avg_quality": round(avg_q, 3) if avg_q is not None else None,
                "pct_above_threshold": round(above / articles, 3) if articles else None,
                "above_threshold": above,
                "last_insert_at": str(r[17]) if r[17] else None,
                "warn_candidates": reasons,
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="RSS feed yield report")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--csv", metavar="PATH", help="Write CSV to path")
    parser.add_argument("--window-days", type=int, default=30)
    args = parser.parse_args()

    _load_db_password()

    from config.runtime import env_float
    from shared.database.connection import get_db_connection_context
    from shared.domain_registry import pipeline_url_schema_pairs

    min_q = env_float("RSS_FEED_SILENCE_MIN_QUALITY", env_float("ARTICLE_SIGNAL_FULL_MIN_QUALITY", 0.45))

    all_rows: list[dict] = []
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '30s'")
            for domain_key, schema in pipeline_url_schema_pairs():
                try:
                    all_rows.extend(_feed_rows(cur, schema, domain_key, min_q, args.window_days))
                except Exception as exc:
                    all_rows.append(
                        {"domain_key": domain_key, "schema": schema, "error": str(exc)[:200]}
                    )

    warn = [r for r in all_rows if r.get("warn_candidates") and r.get("is_active")]
    inactive = [r for r in all_rows if not r.get("is_active")]

    report = {
        "window_days": args.window_days,
        "min_quality_threshold": min_q,
        "feeds": all_rows,
        "warn_candidates": warn,
        "inactive_count": len(inactive),
        "active_count": sum(1 for r in all_rows if r.get("is_active")),
    }

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(f"=== RSS feed yield ({args.window_days}d, quality>={min_q}) ===")
        print(f"Active: {report['active_count']} | Warn candidates: {len(warn)}")
        for r in warn[:25]:
            print(
                f"  [{r.get('domain_key')}] {r.get('feed_name')}: "
                f"{r.get(f'articles_{args.window_days}d')} articles, "
                f"reasons={r.get('warn_candidates')}"
            )
        if len(warn) > 25:
            print(f"  ... and {len(warn) - 25} more")

    if args.csv:
        fields = [
            "domain_key",
            "feed_id",
            "feed_name",
            "feed_url",
            "is_active",
            "status",
            "tier",
            f"articles_{args.window_days}d",
            "max_quality",
            "avg_quality",
            "above_threshold",
            "pct_above_threshold",
            "consecutive_empty_fetches",
            "warn_candidates",
            "last_insert_at",
            "last_error_message",
        ]
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            for row in all_rows:
                out = dict(row)
                out["warn_candidates"] = ",".join(row.get("warn_candidates") or [])
                w.writerow(out)
        if not args.json:
            print(f"Wrote {args.csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
