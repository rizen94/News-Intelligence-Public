#!/usr/bin/env python3
"""Run migration 207: article duplicate source links table.

  PYTHONPATH=api uv run python api/scripts/run_migration_207.py
  PYTHONPATH=api uv run python api/scripts/register_applied_migration.py 207 \
    --notes "run_migration_207.py" \
    --file api/database/migrations/207_article_duplicate_sources.sql
"""

import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

from shared.migration_sql_runner import run_by_migration_number

if __name__ == "__main__":
    raise SystemExit(run_by_migration_number("207"))
