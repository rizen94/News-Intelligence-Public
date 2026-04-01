#!/usr/bin/env python3
"""Run migration 206: finance_2 extension tables (parity with legacy finance silo).

  PYTHONPATH=api uv run python api/scripts/run_migration_206.py
  PYTHONPATH=api uv run python api/scripts/register_applied_migration.py 206 \\
    --notes \"run_migration_206.py\" \\
    --file api/database/migrations/206_finance_2_legacy_silo_extensions.sql
"""

import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

from shared.migration_sql_runner import run_by_migration_number

if __name__ == "__main__":
    raise SystemExit(run_by_migration_number("206"))
