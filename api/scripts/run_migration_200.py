#!/usr/bin/env python3
"""Run migration 200: entity_type ``family`` on per-domain story_entity_index.

From project root:
  PYTHONPATH=api uv run python api/scripts/run_migration_200.py
Then record:
  PYTHONPATH=api uv run python api/scripts/register_applied_migration.py 200 \\
    --notes run_migration_200.py --file api/database/migrations/200_story_entity_index_family_type.sql
"""

import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

from shared.migration_sql_runner import run_by_migration_number

if __name__ == "__main__":
    raise SystemExit(run_by_migration_number("200"))
