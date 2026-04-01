#!/usr/bin/env python3
"""Run migration 202: RSS feed URL corrections (SEC, FDIC, FDA, Treasury deactivate, Reuters Arc, BMJ).

From project root:
  PYTHONPATH=api uv run python api/scripts/run_migration_202.py

Then register (if you use the ledger):
  PYTHONPATH=api uv run python api/scripts/register_applied_migration.py 202 --notes "run_migration_202.py" \\
    --file api/database/migrations/202_rss_feed_url_corrections_mar2026.sql
"""

import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

from shared.migration_sql_runner import run_by_migration_number

if __name__ == "__main__":
    raise SystemExit(run_by_migration_number("202"))
