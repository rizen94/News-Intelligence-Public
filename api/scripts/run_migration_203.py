#!/usr/bin/env python3
"""Run migration 203: RSS bad-URL cleanup across all domain schemas.

  PYTHONPATH=api uv run python api/scripts/run_migration_203.py
  PYTHONPATH=api uv run python api/scripts/register_applied_migration.py 203 --notes run_migration_203.py \\
    --file api/database/migrations/203_rss_feeds_deactivate_bad_urls_all_schemas.sql
"""

import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

from shared.migration_sql_runner import run_by_migration_number

if __name__ == "__main__":
    raise SystemExit(run_by_migration_number("203"))
