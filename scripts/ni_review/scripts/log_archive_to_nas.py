#!/usr/bin/env python3
"""
Move local log files to PostgreSQL database (Widow or NAS).
Runs 2x/day via cron (6 AM, 6 PM). Load .env for DB_* (default: Widow).
NAS rollback: DB_HOST=localhost, DB_PORT=5433 + setup_nas_ssh_tunnel.sh.

Usage:
  ./scripts/log_archive_to_nas.py [--dry-run] [--keep-local]
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = PROJECT_ROOT / "logs"

# Log files to archive (source name -> path)
LOG_FILES = {
    "activity": "activity.jsonl",
    "llm_interaction": "llm_interactions.jsonl",
    "orchestrator_decision": "orchestrator_decisions.jsonl",
    "orchestrator_decision_outcome": "orchestrator_decisions_outcomes.jsonl",
    "task_span": "task_traces.jsonl",
}


def load_env():
    """Load .env for DB_* vars. Cron has minimal env; script loads from .env."""
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    v = v.strip().strip('"').strip("'")
                    if k.startswith("DB_") or k in ("NAS_HOST", "NAS_USER"):
                        os.environ.setdefault(k, v)
    os.environ.setdefault("DB_HOST", "192.168.93.101")
    os.environ.setdefault("DB_PORT", "5432")


def get_connection():
    """Connect to NAS PostgreSQL via SSH tunnel."""
    import psycopg2
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5433")),
        database=os.environ.get("DB_NAME", "news_intel"),
        user=os.environ.get("DB_USER", "newsapp"),
        password=os.environ.get("DB_PASSWORD", "newsapp_password"),
        connect_timeout=10,
    )


def parse_timestamp(entry: dict) -> datetime | None:
    """Extract timestamp from log entry."""
    ts = entry.get("timestamp")
    if not ts:
        return None
    try:
        if isinstance(ts, str) and "T" in ts:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        pass
    return None


def archive_file(conn, source: str, path: Path, dry_run: bool, keep_local: bool) -> int:
    """Read JSONL, insert into log_archive, optionally truncate file."""
    if not path.exists() or path.stat().st_size == 0:
        return 0
    rows = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if isinstance(entry, dict):
                    logged_at = parse_timestamp(entry)
                    rows.append((source, json.dumps(entry, default=str), logged_at))
            except json.JSONDecodeError:
                continue
    if not rows:
        return 0
    if dry_run:
        return len(rows)
    cur = conn.cursor()
    try:
        cur.executemany(
            """
            INSERT INTO log_archive (source, entry, logged_at)
            VALUES (%s, %s::jsonb, %s)
            """,
            [(r[0], r[1], r[2]) for r in rows],
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
    if not keep_local:
        path.write_text("")
    return len(rows)


def main():
    ap = argparse.ArgumentParser(description="Archive local logs to NAS PostgreSQL")
    ap.add_argument("--dry-run", action="store_true", help="Only count, do not insert or truncate")
    ap.add_argument("--keep-local", action="store_true", help="Do not truncate local files after archive")
    args = ap.parse_args()
    load_env()
    total = 0
    try:
        conn = get_connection()
    except Exception as e:
        print(f"Database connection failed: {e}", file=sys.stderr)
        print("Ensure SSH tunnel is running: ./scripts/setup_nas_ssh_tunnel.sh", file=sys.stderr)
        sys.exit(1)
    try:
        for source, fname in LOG_FILES.items():
            path = LOG_DIR / fname
            n = archive_file(conn, source, path, args.dry_run, args.keep_local)
            if n > 0:
                total += n
                action = "would archive" if args.dry_run else "archived"
                print(f"{action} {n} rows from {fname}")
    finally:
        conn.close()
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[{ts}] Total: {total} entries {'(dry-run)' if args.dry_run else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
