#!/usr/bin/env python3
"""Run migration 192: RSS feed URL refresh (politics, finance, medicine, AI silos).

From project root:
  PYTHONPATH=api uv run python api/scripts/run_migration_192.py

Then register (if you use the ledger):
  PYTHONPATH=api uv run python api/scripts/register_applied_migration.py 192 --notes "run_migration_192.py" \\
    --file api/database/migrations/192_rss_feed_url_refresh_reviewed.sql

If feed id/name pairs differ on your DB, adjust the SQL or run targeted UPDATEs by feed_url.
"""

import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

from shared.migration_sql_runner import run_by_migration_number

if __name__ == "__main__":
    raise SystemExit(run_by_migration_number("192"))
