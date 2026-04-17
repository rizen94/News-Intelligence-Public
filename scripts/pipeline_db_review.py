#!/usr/bin/env python3
"""
Pull pipeline automation history and related tables from PostgreSQL using credentials
from the project root ``.env`` (``DB_*``), and print ASCII tables.

Paths with spaces (e.g. ``News Intelligence``) must be quoted when you ``cd``.

**From the repository root** (recommended)::

  cd "/path/to/News Intelligence"
  ./scripts/run_pipeline_db_review.sh
  uv run python scripts/pipeline_db_review.py --days 7 --top-errors 25

**From the ``scripts/`` directory**, do not prefix ``scripts/`` again — use::

  uv run python pipeline_db_review.py

Requires ``psycopg2-binary`` in the active environment (``uv sync`` / project ``.venv``).
Running ``./pipeline_db_review.py`` directly uses system Python and will fail unless
you use the launcher or ``uv run`` as above.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _get_db_config():
    """Load DB config from ``.env`` (same pattern as ``automation_run_analysis.py``)."""
    env_file = os.path.join(PROJECT_ROOT, ".env")
    if os.path.isfile(env_file):
        try:
            from dotenv import load_dotenv

            load_dotenv(env_file)
        except ImportError:
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        k, v = k.strip(), v.strip().strip("'\"")
                        if k.startswith("DB_"):
                            os.environ.setdefault(k, v)
    return {
        "host": os.getenv("DB_HOST", "192.168.93.101"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "database": os.getenv("DB_NAME", "news_intel"),
        "user": os.getenv("DB_USER", "newsapp"),
        "password": os.getenv("DB_PASSWORD", ""),
        "connect_timeout": 15,
    }


def _fmt_num(v, nd: int = 1) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


def _print_table(headers: list[str], rows: list[tuple], col_widths: list[int] | None = None) -> None:
    """Fixed-width table; ``rows`` are tuples of stringifiable cells."""
    if not rows and not headers:
        return
    n = len(headers)
    str_rows: list[list[str]] = []
    for r in rows:
        cells = list(r) + [""] * max(0, n - len(r))
        str_rows.append(["" if c is None else str(c) for c in cells[:n]])
    if col_widths is None:
        col_widths = [len(h) for h in headers]
        for r in str_rows:
            for i, cell in enumerate(r):
                col_widths[i] = max(col_widths[i], len(cell))
    sep = "  "
    head = sep.join(headers[i].ljust(col_widths[i]) for i in range(n))
    print(head)
    print(sep.join("-" * col_widths[i] for i in range(n)))
    for r in str_rows:
        print(sep.join(r[i].ljust(col_widths[i]) if i < len(r) else "".ljust(col_widths[i]) for i in range(n)))
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description="Pipeline DB review tables (automation_run_history, traces)")
    ap.add_argument("--days", type=int, default=21, help="Look-back window in days (default 21)")
    ap.add_argument(
        "--top-errors",
        type=int,
        default=40,
        help="Max rows in the phase/error bucket table (default 40)",
    )
    ap.add_argument(
        "--fast-runs-min",
        type=int,
        default=50,
        help="Min runs to list a phase as possibly empty/fast (default 50)",
    )
    ap.add_argument(
        "--fast-avg-seconds",
        type=float,
        default=2.0,
        help="Avg duration below this flags 'possibly empty cycles' (default 2.0)",
    )
    args = ap.parse_args()
    days = max(1, min(args.days, 366))

    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        print("psycopg2 is not installed for this Python interpreter.", file=sys.stderr)
        print("From the repo root, use one of:", file=sys.stderr)
        print("  ./scripts/run_pipeline_db_review.sh", file=sys.stderr)
        print("  uv run python scripts/pipeline_db_review.py", file=sys.stderr)
        print("  .venv/bin/python scripts/pipeline_db_review.py   # after uv sync", file=sys.stderr)
        return 1

    cfg = _get_db_config()
    connect_kw = {k: v for k, v in cfg.items() if k != "connect_timeout"}
    connect_kw["connect_timeout"] = cfg.get("connect_timeout", 15)

    since = datetime.now(timezone.utc) - timedelta(days=days)

    print("=" * 88)
    print("NEWS INTELLIGENCE — Pipeline DB review")
    print(f"Window: last {days} day(s)  |  Since (UTC): {since.isoformat()}")
    print("=" * 88)

    try:
        conn = psycopg2.connect(**connect_kw)
    except Exception as e:
        print(f"\nDatabase connection failed: {e}", file=sys.stderr)
        print("Set DB_* in .env and ensure PostgreSQL is reachable.", file=sys.stderr)
        return 1

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL statement_timeout = '60s'")

            # --- Summary: total phase completions ---
            cur.execute(
                """
                SELECT COUNT(*) AS total
                FROM public.automation_run_history
                WHERE finished_at >= %s
                """,
                (since,),
            )
            total_runs = (cur.fetchone() or {}).get("total", 0)
            print(f"\nAutomation phase completions (rows in automation_run_history): {total_runs}")
            print()

            # --- Per-phase stats ---
            cur.execute(
                """
                SELECT phase_name,
                       COUNT(*) AS runs,
                       COUNT(*) FILTER (WHERE success IS TRUE) AS ok,
                       COUNT(*) FILTER (WHERE success IS NOT TRUE) AS failed,
                       ROUND(
                           100.0 * COUNT(*) FILTER (WHERE success IS NOT TRUE) / NULLIF(COUNT(*), 0),
                           2
                       ) AS fail_pct,
                       AVG(EXTRACT(EPOCH FROM (finished_at - started_at)))
                         FILTER (WHERE started_at IS NOT NULL) AS avg_s,
                       MIN(EXTRACT(EPOCH FROM (finished_at - started_at)))
                         FILTER (WHERE started_at IS NOT NULL) AS min_s,
                       MAX(EXTRACT(EPOCH FROM (finished_at - started_at)))
                         FILTER (WHERE started_at IS NOT NULL) AS max_s
                FROM public.automation_run_history
                WHERE finished_at >= %s
                GROUP BY phase_name
                ORDER BY runs DESC, phase_name
                """,
                (since,),
            )
            phase_rows = cur.fetchall() or []
            hdr = ["phase_name", "runs", "ok", "failed", "fail_pct", "avg_s", "min_s", "max_s"]
            tbl: list[tuple] = []
            for r in phase_rows:
                tbl.append(
                    (
                        r.get("phase_name") or "",
                        r.get("runs"),
                        r.get("ok"),
                        r.get("failed"),
                        _fmt_num(r.get("fail_pct"), 2),
                        _fmt_num(r.get("avg_s"), 1),
                        _fmt_num(r.get("min_s"), 1),
                        _fmt_num(r.get("max_s"), 1),
                    )
                )
            print("--- Per-phase automation runs ---")
            _print_table(hdr, tbl)

            # --- Failure buckets ---
            cur.execute(
                """
                SELECT phase_name,
                       LEFT(
                           COALESCE(NULLIF(TRIM(error_message), ''), '(no message)'),
                           100
                       ) AS err_sample,
                       COUNT(*) AS cnt
                FROM public.automation_run_history
                WHERE finished_at >= %s
                  AND (
                        success IS NOT TRUE
                        OR (error_message IS NOT NULL AND btrim(error_message) <> '')
                      )
                GROUP BY phase_name,
                         LEFT(
                           COALESCE(NULLIF(TRIM(error_message), ''), '(no message)'),
                           100
                         )
                ORDER BY cnt DESC
                LIMIT %s
                """,
                (since, args.top_errors),
            )
            fb = cur.fetchall() or []
            print("--- Top failure / error-message buckets ---")
            if not fb:
                print("(none)")
                print()
            else:
                _print_table(
                    ["phase_name", "err_sample (trunc)", "count"],
                    [(r.get("phase_name") or "", r.get("err_sample") or "", r.get("cnt")) for r in fb],
                    col_widths=[28, 52, 6],
                )

            # --- Possibly empty / very fast cycles ---
            cur.execute(
                """
                SELECT phase_name,
                       COUNT(*) AS runs,
                       COUNT(*) FILTER (WHERE success IS TRUE) AS ok,
                       AVG(EXTRACT(EPOCH FROM (finished_at - started_at))) AS avg_s
                FROM public.automation_run_history
                WHERE finished_at >= %s
                  AND started_at IS NOT NULL
                GROUP BY phase_name
                HAVING COUNT(*) >= %s
                   AND AVG(EXTRACT(EPOCH FROM (finished_at - started_at))) < %s
                ORDER BY runs DESC
                """,
                (since, args.fast_runs_min, args.fast_avg_seconds),
            )
            fast = cur.fetchall() or []
            print(
                f"--- Possibly empty / fast cycles (runs>={args.fast_runs_min}, avg duration < {args.fast_avg_seconds}s) ---"
            )
            if not fast:
                print("(none)")
                print()
            else:
                _print_table(
                    ["phase_name", "runs", "ok", "avg_s"],
                    [
                        (
                            r.get("phase_name") or "",
                            r.get("runs"),
                            r.get("ok"),
                            _fmt_num(r.get("avg_s"), 2),
                        )
                        for r in fast
                    ],
                )

            # --- pipeline_traces ---
            try:
                cur.execute(
                    """
                    SELECT COUNT(*) AS n,
                           COUNT(*) FILTER (WHERE success IS TRUE) AS ok,
                           COUNT(*) FILTER (WHERE success IS NOT TRUE OR success IS NULL) AS bad
                    FROM pipeline_traces
                    WHERE start_time >= %s
                    """,
                    (since,),
                )
                pt = cur.fetchone() or {}
                print("--- pipeline_traces (orchestrator / manual pipeline runs) ---")
                _print_table(
                    ["traces", "success_true", "fail_or_null"],
                    [(pt.get("n"), pt.get("ok"), pt.get("bad"))],
                )
            except Exception as e:
                print("--- pipeline_traces ---")
                print(f"(skipped: {e})")
                print()

            # --- Checkpoint failures by stage ---
            try:
                cur.execute(
                    """
                    SELECT stage,
                           COUNT(*) AS cnt
                    FROM pipeline_checkpoints
                    WHERE timestamp >= %s
                      AND (
                            lower(coalesce(status, '')) IN ('failed', 'error')
                            OR (error_message IS NOT NULL AND btrim(error_message) <> '')
                          )
                    GROUP BY stage
                    ORDER BY cnt DESC
                    LIMIT 30
                    """,
                    (since,),
                )
                cp = cur.fetchall() or []
                print("--- pipeline_checkpoints: failure-like rows by stage ---")
                if not cp:
                    print("(none)")
                    print()
                else:
                    _print_table(
                        ["stage", "count"],
                        [(r.get("stage") or "", r.get("cnt")) for r in cp],
                    )
            except Exception as e:
                print("--- pipeline_checkpoints ---")
                print(f"(skipped: {e})")
                print()

    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
