#!/usr/bin/env python3
r"""
Last 24 hours activity report for News Intelligence.
Shows what was collected, what ran (pipeline/orchestrator), and highlights areas
that may have been neglected or have no recorded runs.

Minimal deps: psycopg2-binary only. On externally-managed Python (PEP 668), use the wrapper script so no system pip is needed:

  cd /path/to/News Intelligence
  ./scripts/run_last_24h_report.sh

That creates .venv-report (once), installs psycopg2-binary there, and runs this script. .env is read from project root.
"""

import os
import sys
from datetime import datetime, timezone, timedelta

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _get_db_config():
    """Load DB config from .env / os.environ (same defaults as shared.database.connection)."""
    env_file = os.path.join(PROJECT_ROOT, ".env")
    if os.path.isfile(env_file):
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
        except ImportError:
            # No dotenv: parse .env by hand for DB_* only
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
        "connect_timeout": 5,
    }


def main():
    import psycopg2
    from psycopg2.extras import RealDictCursor

    cfg = _get_db_config()

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    print("=" * 60)
    print("NEWS INTELLIGENCE — Last 24 hours activity report")
    print(f"Since: {since.isoformat()}")
    print("=" * 60)

    # psycopg2 expects port as int; config may have it as string
    connect_kw = {k: v for k, v in cfg.items() if k != "connect_timeout"}
    connect_kw["connect_timeout"] = cfg.get("connect_timeout", 5)
    try:
        conn = psycopg2.connect(**connect_kw)
    except Exception as e:
        print(f"\n❌ Database connection failed: {e}")
        print("   Set DB_PASSWORD in .env and ensure API/DB are reachable.")
        return 1

    gaps = []

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # --- Articles collected (last 24h) per domain ---
            print("\n--- Articles collected (last 24h) ---")
            for schema in ["politics", "finance", "science_tech"]:
                cur.execute(
                    """
                    SELECT COUNT(*) as c
                    FROM """ + schema + """.articles
                    WHERE created_at >= %s
                    """,
                    (since,),
                )
                row = cur.fetchone()
                count = row["c"] if row else 0
                print(f"  {schema}: {count} articles")
                if count == 0:
                    gaps.append(f"  No new articles in last 24h for domain: {schema}")

            # --- RSS feed last fetch (feeds not fetched in 24h) ---
            print("\n--- RSS feeds: last fetch (active only) ---")
            for schema in ["politics", "finance", "science_tech"]:
                cur.execute(
                    """
                    SELECT COUNT(*) as total,
                           COUNT(*) FILTER (WHERE last_fetched_at >= %s) as fetched_24h,
                           COUNT(*) FILTER (WHERE last_fetched_at IS NULL OR last_fetched_at < %s) as stale
                    FROM """ + schema + """.rss_feeds
                    WHERE is_active = true
                    """,
                    (since, since),
                )
                row = cur.fetchone()
                if row:
                    print(f"  {schema}: {row['fetched_24h']} fetched in 24h, {row['stale']} not fetched in 24h (of {row['total']} active)")
                    if row["stale"] and row["stale"] == row["total"]:
                        gaps.append(f"  No RSS feed in {schema} was fetched in the last 24h")

            # --- Pipeline traces (triggered from UI or API) ---
            print("\n--- Pipeline traces (last 24h) ---")
            cur.execute(
                """
                SELECT trace_id, start_time, end_time, success, error_stage
                FROM pipeline_traces
                WHERE start_time >= %s
                ORDER BY start_time DESC
                LIMIT 20
                """,
                (since,),
            )
            rows = cur.fetchall()
            if not rows:
                print("  None (no pipeline runs recorded in last 24h)")
                gaps.append("  No pipeline_traces in last 24h (only recorded when 'Trigger pipeline' is used from Monitoring)")
            else:
                for r in rows:
                    status = "ok" if r["success"] else "error"
                    print(f"  {r['trace_id']}: {r['start_time']} — {status}" + (f" ({r['error_stage']})" if r["error_stage"] else ""))

            # --- Pipeline checkpoints (stages) ---
            cur.execute(
                """
                SELECT stage, status, COUNT(*) as c
                FROM pipeline_checkpoints
                WHERE timestamp >= %s
                GROUP BY stage, status
                ORDER BY stage, status
                """,
                (since,),
            )
            cp_rows = cur.fetchall()
            if cp_rows:
                print("\n--- Pipeline checkpoints by stage (last 24h) ---")
                for r in cp_rows:
                    print(f"  {r['stage']}: {r['status']} = {r['c']}")

            # --- System alerts (last 24h) ---
            print("\n--- System alerts (last 24h) ---")
            cur.execute(
                """
                SELECT id, severity, title, created_at
                FROM system_alerts
                WHERE created_at >= %s
                ORDER BY created_at DESC
                LIMIT 15
                """,
                (since,),
            )
            alert_rows = cur.fetchall()
            if not alert_rows:
                print("  None")
            else:
                for r in alert_rows:
                    print(f"  [{r['severity']}] {r['title']} @ {r['created_at']}")

        conn.close()
    except Exception as e:
        print(f"\n❌ Query error: {e}")
        conn.close()
        return 1

    # --- Orchestrator state (SQLite) ---
    print("\n--- Orchestrator coordinator state (in-process runs) ---")
    state_path = os.path.join(PROJECT_ROOT, "data", "orchestrator_state.db")
    if os.path.exists(state_path):
        try:
            import sqlite3
            import json
            db = sqlite3.connect(state_path)
            row = db.execute("SELECT state_json, updated_at FROM orchestrator_controller_state WHERE id = 1").fetchone()
            db.close()
            if row and row[0]:
                state = json.loads(row[0])
                updated = row[1]
                last_times = state.get("last_collection_times") or {}
                print(f"  State updated_at: {updated}")
                for source, ts in list(last_times.items())[:10]:
                    print(f"  last_collection_times[{source}]: {ts}")
                if not last_times:
                    gaps.append("  Orchestrator state has no last_collection_times (coordinator may not have run or DB is fresh)")
        except Exception as e:
            print(f"  Could not read orchestrator state: {e}")
    else:
        print("  No orchestrator_state.db found (data/orchestrator_state.db)")
        gaps.append("  Orchestrator state file missing — coordinator runs not persisted here")

    # --- Cron / log file (RSS collection with health check) ---
    print("\n--- Cron RSS collection log (last 24h) ---")
    log_path = os.path.expanduser("~/logs/news_intelligence/rss_collection.log")
    if not os.path.exists(log_path):
        log_path = os.path.join(PROJECT_ROOT, "logs", "rss_collection.log")
    if os.path.exists(log_path):
        try:
            with open(log_path) as f:
                lines = f.readlines()
            # show last N lines that are from last 24h (by timestamp in log)
            recent = [l for l in lines if l.strip()][-50:]
            print(f"  Log file: {log_path} (showing last {len(recent)} lines)")
            for line in recent[-15:]:
                print("   ", line.rstrip())
        except Exception as e:
            print(f"  Could not read log: {e}")
    else:
        print(f"  No log found at ~/logs/news_intelligence/rss_collection.log or {os.path.join(PROJECT_ROOT, 'logs', 'rss_collection.log')}")
        gaps.append("  Cron RSS log not found — if cron is used, ensure setup_rss_cron_with_health_check.sh was run and log dir exists")

    # --- Gaps / recommendations ---
    print("\n" + "=" * 60)
    print("POTENTIAL GAPS / NEGLECTED AREAS")
    print("=" * 60)
    if not gaps:
        print("  None identified from this report.")
    else:
        for g in gaps:
            print(g)
    print("\nNote:")
    print("  - RSS collection can run via: (1) Cron 6am/6pm, (2) OrchestratorCoordinator loop, (3) Manual 'Trigger pipeline'.")
    print("  - pipeline_traces are only written when 'Trigger pipeline' is used from the Monitoring UI (or equivalent API).")
    print("  - AutomationManager (health_check, consolidation, topic clustering) runs in-process; last_run is not persisted to DB.")
    print("  - To see AutomationManager activity, check API process logs (stdout / logs/api_server.log).")
    return 0

if __name__ == "__main__":
    sys.exit(main())
