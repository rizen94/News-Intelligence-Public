#!/usr/bin/env python3
"""Apply migration 222: longitudinal reference layer + wikidata QID.

  PYTHONPATH=api uv run python api/scripts/run_migration_222.py

Then register:

  PYTHONPATH=api uv run python api/scripts/register_applied_migration.py 222 \\
    --notes run_migration_222.py --file api/database/migrations/222_longitudinal_reference_layer.sql
"""

from __future__ import annotations

import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

from shared.migration_sql_runner import run_by_migration_number

if __name__ == "__main__":
    raise SystemExit(run_by_migration_number("222"))
