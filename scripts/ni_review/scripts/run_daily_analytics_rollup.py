#!/usr/bin/env python3
"""
Daily analytics rollup for long-term analytics.

Rolls up:
  1) automation_run_history -> automation_run_history_daily (per UTC day + phase)
  2) log_archive -> log_archive_daily_rollup (per UTC day + source)

This supports weekly/monthly analytics from summarized daily data without querying
every raw per-run/per-log row.

Usage:
  cd "/home/pete/Documents/projects/Projects/News Intelligence"
  PYTHONPATH=api uv run python scripts/run_daily_analytics_rollup.py --date 2026-03-18
  # Default: yesterday UTC
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone, date

from shared.database.connection import get_db_connection


def _parse_date(d: str) -> date:
    return datetime.fromisoformat(d).date()


def _utc_day_bounds(d: date) -> tuple[datetime, datetime]:
    start = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    return start, end


def _run_rollups(conn, day: date) -> None:
    day_start, day_end = _utc_day_bounds(day)

    with conn.cursor() as cur:
        # 1) automation_run_history -> automation_run_history_daily
        cur.execute(
            """
            INSERT INTO automation_run_history_daily (
                day,
                phase_name,
                run_count,
                success_count,
                failure_count,
                avg_duration_seconds,
                total_duration_seconds,
                updated_at
            )
            SELECT
                date_trunc('day', finished_at AT TIME ZONE 'UTC')::date AS day_bucket,
                phase_name,
                COUNT(*) AS run_count,
                SUM(CASE WHEN success THEN 1 ELSE 0 END) AS success_count,
                SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) AS failure_count,
                AVG(EXTRACT(EPOCH FROM (finished_at - started_at))) FILTER (
                    WHERE started_at IS NOT NULL AND finished_at IS NOT NULL
                ) AS avg_duration_seconds,
                SUM(EXTRACT(EPOCH FROM (finished_at - started_at))) FILTER (
                    WHERE started_at IS NOT NULL AND finished_at IS NOT NULL
                ) AS total_duration_seconds,
                NOW() AS updated_at
            FROM automation_run_history
            WHERE finished_at >= %s
              AND finished_at < %s
            GROUP BY 1, 2
            ON CONFLICT (day, phase_name) DO UPDATE SET
                run_count = EXCLUDED.run_count,
                success_count = EXCLUDED.success_count,
                failure_count = EXCLUDED.failure_count,
                avg_duration_seconds = EXCLUDED.avg_duration_seconds,
                total_duration_seconds = EXCLUDED.total_duration_seconds,
                updated_at = EXCLUDED.updated_at
            """,
            (day_start, day_end),
        )

        # 2) log_archive -> log_archive_daily_rollup
        cur.execute(
            """
            INSERT INTO log_archive_daily_rollup (
                day,
                source,
                total_entries,
                error_count,
                warning_count,
                info_count,
                debug_count,
                updated_at
            )
            SELECT
                date_trunc('day', logged_at AT TIME ZONE 'UTC')::date AS day_bucket,
                source,
                COUNT(*) AS total_entries,
                SUM(CASE WHEN LOWER(COALESCE(entry->>'level', '')) = 'error' THEN 1 ELSE 0 END) AS error_count,
                SUM(CASE WHEN LOWER(COALESCE(entry->>'level', '')) = 'warning' THEN 1 ELSE 0 END) AS warning_count,
                SUM(CASE WHEN LOWER(COALESCE(entry->>'level', '')) = 'info' THEN 1 ELSE 0 END) AS info_count,
                SUM(CASE WHEN LOWER(COALESCE(entry->>'level', '')) = 'debug' THEN 1 ELSE 0 END) AS debug_count,
                NOW() AS updated_at
            FROM log_archive
            WHERE logged_at IS NOT NULL
              AND logged_at >= %s
              AND logged_at < %s
            GROUP BY 1, 2
            ON CONFLICT (day, source) DO UPDATE SET
                total_entries = EXCLUDED.total_entries,
                error_count = EXCLUDED.error_count,
                warning_count = EXCLUDED.warning_count,
                info_count = EXCLUDED.info_count,
                debug_count = EXCLUDED.debug_count,
                updated_at = EXCLUDED.updated_at
            """,
            (day_start, day_end),
        )


def main() -> int:
    ap = argparse.ArgumentParser(description="Daily analytics rollup for automation runs and log volume")
    ap.add_argument(
        "--date",
        type=str,
        default="",
        help="UTC date to roll up (YYYY-MM-DD). Default: yesterday UTC",
    )
    args = ap.parse_args()

    if args.date:
        rollup_day = _parse_date(args.date)
    else:
        rollup_day = (datetime.now(timezone.utc) - timedelta(days=1)).date()

    print(f"Rolling up analytics for UTC day: {rollup_day.isoformat()}")

    conn = None
    try:
        conn = get_db_connection()
        _run_rollups(conn, rollup_day)
        try:
            conn.commit()
        except Exception:
            # Some pooled connections may already be in autocommit; ignore.
            pass
        print("Rollup complete.")
        return 0
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())

