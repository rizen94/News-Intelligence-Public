#!/usr/bin/env python3
"""Run migration 166: add assignment_context and model_version to article_topic_assignments.

From project root:
  PYTHONPATH=api .venv/bin/python3 api/scripts/run_migration_166.py

Uses DB from env (DB_HOST, DB_NAME, DB_USER, DB_PASSWORD) or .db_password_widow.
Fixes: column assignment_context of relation article_topic_assignments does not exist
"""

import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

from shared.migration_sql_runner import run_by_migration_number

if __name__ == "__main__":
    raise SystemExit(run_by_migration_number("166"))
