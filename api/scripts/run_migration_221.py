#!/usr/bin/env python3
"""Apply migration 221: provenance timestamps on articles, contexts, claims, facts, events.

  PYTHONPATH=api uv run python api/scripts/run_migration_221.py

Then register:

  PYTHONPATH=api uv run python api/scripts/register_applied_migration.py 221 \\
    --notes run_migration_221.py --file api/database/migrations/221_provenance_timestamps.sql
"""

from __future__ import annotations

import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

from shared.migration_sql_runner import run_by_migration_number

if __name__ == "__main__":
    raise SystemExit(run_by_migration_number("221"))
