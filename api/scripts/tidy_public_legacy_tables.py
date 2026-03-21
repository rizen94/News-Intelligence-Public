#!/usr/bin/env python3
"""
Back up public.articles and public.rss_feeds (legacy after migration 125), then truncate them.
Domain data lives in politics/finance/science_tech; this tidies the public schema.

Run from project root:
  .venv/bin/python api/scripts/tidy_public_legacy_tables.py

Or with full paths (e.g. from home):
  "/path/to/News Intelligence/.venv/bin/python" "/path/to/News Intelligence/api/scripts/tidy_public_legacy_tables.py"
"""

import os
import subprocess
import sys
from datetime import datetime

try:
    from dotenv import load_dotenv

    api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(api_dir, ".env"), override=False)
    load_dotenv(os.path.join(api_dir, "..", ".env"), override=False)
except ImportError:
    pass

if not os.environ.get("DB_PASSWORD") and os.path.exists(
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", ".db_password_widow")
):
    pw_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", ".db_password_widow")
    try:
        with open(pw_path) as f:
            os.environ["DB_PASSWORD"] = f.read().strip()
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    from shared.database.connection import get_db_config, get_db_connection

    api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    backup_dir = os.path.join(api_dir, "scripts", "backups")
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"public_legacy_articles_rss_feeds_{stamp}.sql")

    cfg = get_db_config()
    env = os.environ.copy()
    if cfg.get("password"):
        env["PGPASSWORD"] = str(cfg["password"])

    print("--- 1. Backing up public.articles and public.rss_feeds ---")
    cmd = [
        "pg_dump",
        "-h",
        cfg["host"],
        "-p",
        str(cfg["port"]),
        "-U",
        cfg["user"],
        "-d",
        cfg["database"],
        "-t",
        "public.articles",
        "-t",
        "public.rss_feeds",
        "--data-only",
        "--no-owner",
        "-f",
        backup_file,
    ]
    r = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"pg_dump failed: {r.stderr or r.stdout}")
        sys.exit(1)
    print(f"  Backup written to: {backup_file}")

    print("--- 2. Truncating public.articles and public.rss_feeds ---")
    conn = get_db_connection()
    if not conn:
        print("ERROR: Could not connect to database")
        sys.exit(1)
    try:
        with conn.cursor() as cur:
            # CASCADE truncates tables that FK to these (e.g. public.storyline_articles -> public.articles)
            cur.execute("TRUNCATE TABLE public.articles CASCADE;")
            cur.execute("TRUNCATE TABLE public.rss_feeds CASCADE;")
        conn.commit()
        print("  public.articles truncated (and any public tables that referenced it).")
        print("  public.rss_feeds truncated.")
    finally:
        conn.close()

    print(
        "--- Done. Run diagnose_db_legacy_data.py again to confirm; new data will land in domain schemas. ---"
    )


if __name__ == "__main__":
    main()
