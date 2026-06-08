#!/usr/bin/env python3
"""Apply migration 223: pgvector + embedding_chunks.

  PYTHONPATH=api uv run python api/scripts/run_migration_223.py

Then register:

  PYTHONPATH=api uv run python api/scripts/register_applied_migration.py 223 \\
    --notes run_migration_223.py --file api/database/migrations/223_pgvector_embedding_chunks.sql
"""

from __future__ import annotations

import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

from shared.migration_sql_runner import run_by_migration_number

if __name__ == "__main__":
    raise SystemExit(run_by_migration_number("223"))
