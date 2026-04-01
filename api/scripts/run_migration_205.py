#!/usr/bin/env python3
"""Run migration 205: Update CBC RSS endpoints in politics_2.

  PYTHONPATH=api uv run python api/scripts/run_migration_205.py
  PYTHONPATH=api uv run python api/scripts/register_applied_migration.py 205 \\
    --notes \"run_migration_205.py\" \\
    --file api/database/migrations/205_rss_cbc_url_update_politics2.sql
"""

import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

from shared.migration_sql_runner import run_by_migration_number

if __name__ == "__main__":
    raise SystemExit(run_by_migration_number("205"))
