#!/usr/bin/env python3
"""
Remove all storylines and storyline-related rows across active domain schemas.

Does not delete articles, RSS feeds, or topic clusters. Safe for a storyline-only reset.

Usage (from repo root, with DB_* in environment or .env loaded):
  PYTHONPATH=api uv run python scripts/flush_all_storylines.py --dry-run
  PYTHONPATH=api uv run python scripts/flush_all_storylines.py --yes
"""

from __future__ import annotations

import argparse
import os
import sys

# Repo root / api on path
_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_API = os.path.join(_REPO, "api")
if _API not in sys.path:
    sys.path.insert(0, _API)

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(_REPO, "api", ".env"), override=False)
    load_dotenv(os.path.join(_REPO, ".env"), override=False)
except ImportError:
    pass

from shared.database.connection import get_db_connection  # noqa: E402
from shared.domain_registry import get_schema_names_active  # noqa: E402


def _table_exists(cur, schema: str, table: str) -> bool:
    cur.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = %s AND table_name = %s
        """,
        (schema, table),
    )
    return cur.fetchone() is not None


def _delete_from(cur, schema: str, table: str) -> int:
    if not _table_exists(cur, schema, table):
        return 0
    cur.execute(f'DELETE FROM "{schema}"."{table}"')
    return cur.rowcount


def _exec_optional(cur, savepoint: str, sql: str, label: str, counts: dict[str, int]) -> None:
    """Run sql under a savepoint so a missing table does not abort the whole transaction."""
    try:
        cur.execute(f"SAVEPOINT {savepoint}")
        cur.execute(sql)
        counts[label] = cur.rowcount
        cur.execute(f"RELEASE SAVEPOINT {savepoint}")
    except Exception:
        cur.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")


def flush_storylines() -> dict[str, int]:
    counts: dict[str, int] = {}
    schemas = get_schema_names_active()
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("No database connection (check DB_HOST, DB_* env vars).")

    try:
        cur = conn.cursor()

        _exec_optional(
            cur,
            "sp_refine_q",
            "DELETE FROM intelligence.content_refinement_queue",
            "intelligence.content_refinement_queue",
            counts,
        )

        _exec_optional(
            cur,
            "sp_storyline_states",
            "DELETE FROM intelligence.storyline_states",
            "intelligence.storyline_states",
            counts,
        )

        for schema in schemas:
            prefix = f"{schema}."
            for table in (
                "storyline_article_suggestions",
                "storyline_automation_log",
                "storyline_articles",
                "timeline_events",
                "story_entity_index",
                "storylines",
            ):
                key = prefix + table
                n = _delete_from(cur, schema, table)
                if n:
                    counts[key] = n

        for sp, sql, label in (
            ("sp_chrono", "TRUNCATE chronological_events CASCADE", "public.chronological_events"),
            ("sp_watch", "DELETE FROM watchlist", "public.watchlist"),
            ("sp_insights", "DELETE FROM storyline_insights", "public.storyline_insights"),
            ("sp_corr", "DELETE FROM storyline_correlations", "public.storyline_correlations"),
        ):
            _exec_optional(cur, sp, sql, label, counts)

        conn.commit()
        return counts
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> int:
    p = argparse.ArgumentParser(description="Delete all storylines (keeps articles and topics).")
    p.add_argument("--dry-run", action="store_true", help="Only verify DB connection and list schemas.")
    p.add_argument(
        "--yes",
        action="store_true",
        help="Required to perform deletes (safety guard).",
    )
    args = p.parse_args()

    if not args.dry_run and not args.yes:
        print("Refusing to delete without --yes. Use --dry-run to preview.", file=sys.stderr)
        return 2

    schemas = get_schema_names_active()
    if args.dry_run:
        print("Dry run: would flush storylines for schemas:", ", ".join(schemas))
        try:
            conn = get_db_connection()
        except Exception as e:
            print(f"ERROR: Cannot connect to database: {e}", file=sys.stderr)
            return 1
        if not conn:
            print("ERROR: No DB connection.", file=sys.stderr)
            return 1
        conn.close()
        print("DB connection OK.")
        return 0

    counts = flush_storylines()
    print("Flush complete. Summary:")
    for k, v in sorted(counts.items()):
        if v and v != -1:
            print(f"  {k}: {v}")
        elif v == -1:
            print(f"  {k}: truncated")
    if not counts:
        print("  (nothing reported)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
