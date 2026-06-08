#!/usr/bin/env python3
"""Apply migration 219: consolidate politics_2/finance_2 → politics/finance schemas.

From project root (after backup + audit_politics_finance_schemas.py):

  PYTHONPATH=api uv run python api/scripts/run_migration_219.py

Then record:

  PYTHONPATH=api uv run python api/scripts/register_applied_migration.py 219 \\
    --notes run_migration_219.py --file api/database/migrations/219_consolidate_politics_finance_schemas.sql
"""

from __future__ import annotations

import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

from shared.migration_sql_runner import run_by_migration_number

if __name__ == "__main__":
    raise SystemExit(run_by_migration_number("219"))
