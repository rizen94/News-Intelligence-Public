#!/usr/bin/env python3
"""
Remove chronological_events with blank storyline_id (orphan spine rows).

These rows are not used by build_storyline_spine / historical context.

  PYTHONPATH=api uv run python api/scripts/prune_blank_spine_chronological_events.py --dry-run
  PYTHONPATH=api uv run python api/scripts/prune_blank_spine_chronological_events.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.database.connection import get_db_connection_context  # noqa: E402

_WHERE = """
    storyline_id IS NULL OR btrim(storyline_id::text) = ''
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Prune blank-spine chronological_events")
    parser.add_argument("--dry-run", action="store_true", help="Count only, no DELETE")
    args = parser.parse_args()

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) FROM public.chronological_events WHERE {_WHERE}"
            )
            n = int(cur.fetchone()[0])
            print(f"blank_spine_rows={n}")
            if args.dry_run or n == 0:
                if args.dry_run:
                    print("dry-run: no changes")
                return 0
            cur.execute(
                f"DELETE FROM public.chronological_events WHERE {_WHERE}"
            )
            deleted = cur.rowcount
        conn.commit()
    print(f"deleted={deleted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
