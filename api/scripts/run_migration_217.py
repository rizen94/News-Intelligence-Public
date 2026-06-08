#!/usr/bin/env python3
"""Run migration 217: user_profiles roles + table bootstrap for public web auth.

  PYTHONPATH=api uv run python api/scripts/run_migration_217.py
  PYTHONPATH=api uv run python api/scripts/register_applied_migration.py 217 \\
    --notes "run_migration_217.py" \\
    --file api/database/migrations/217_public_web_auth_user_profiles_roles.sql
"""

import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

from shared.migration_sql_runner import run_by_migration_number

if __name__ == "__main__":
    raise SystemExit(run_by_migration_number("217"))
