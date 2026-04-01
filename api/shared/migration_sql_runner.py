"""
Apply a single migration SQL file using pooled DB config (.env, optional .db_password_widow).

Used by ``api/scripts/run_migration.py`` and thin ``run_migration_NNN.py`` wrappers so
bootstrap + execute logic lives in one place.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def bootstrap_migration_env() -> None:
    """Load dotenv from api/ and repo root; optional Widow password file."""
    try:
        from dotenv import load_dotenv

        api_dir = Path(__file__).resolve().parent.parent
        load_dotenv(api_dir / ".env", override=False)
        load_dotenv(api_dir.parent / ".env", override=False)
    except ImportError:
        pass

    if os.environ.get("DB_PASSWORD"):
        return
    repo_root = Path(__file__).resolve().parent.parent.parent
    pw_path = repo_root / ".db_password_widow"
    if pw_path.is_file():
        try:
            os.environ["DB_PASSWORD"] = pw_path.read_text().strip()
        except OSError:
            pass


def apply_sql_at_path(sql_path: str) -> int:
    """
    Read SQL from path, execute with statement_timeout=0, commit.
    Returns 0 on success, 1 on failure.
    """
    bootstrap_migration_env()
    api_root = str(Path(__file__).resolve().parent.parent)
    if api_root not in sys.path:
        sys.path.insert(0, api_root)

    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        print("ERROR: Could not connect to database (check DB_* env)", file=sys.stderr)
        return 1

    try:
        with open(sql_path, encoding="utf-8") as f:
            sql = f.read()
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = 0")
            cur.execute(sql)
        conn.commit()
        print(f"Applied successfully: {Path(sql_path).name}")
        return 0
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()


def run_by_basename(filename: str) -> int:
    """Resolve ``filename`` via active migrations + archive, then apply."""
    bootstrap_migration_env()
    api_root = str(Path(__file__).resolve().parent.parent)
    if api_root not in sys.path:
        sys.path.insert(0, api_root)

    from shared.migration_sql_paths import resolve_migration_sql_file

    try:
        path = resolve_migration_sql_file(filename)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return apply_sql_at_path(path)


def run_by_migration_number(migration_id: str) -> int:
    """
    Find ``NNN_*.sql`` for three-digit ``migration_id`` (active dir first), then apply.
    """
    bootstrap_migration_env()
    api_root = str(Path(__file__).resolve().parent.parent)
    if api_root not in sys.path:
        sys.path.insert(0, api_root)

    from shared.migration_sql_paths import find_migration_sql_by_prefix

    try:
        path = find_migration_sql_by_prefix(migration_id)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return apply_sql_at_path(path)


def cli_main(argv: list[str] | None = None) -> int:
    import argparse

    argv = list(argv if argv is not None else sys.argv[1:])
    parser = argparse.ArgumentParser(
        description="Apply one migration SQL file (single NNN_*.sql). "
        "For multi-file bundles (e.g. 140+141), use the dedicated script."
    )
    parser.add_argument(
        "migration_id",
        nargs="?",
        help="Three-digit id: resolves NNN_*.sql (e.g. 206)",
    )
    parser.add_argument(
        "--file",
        "-f",
        dest="sql_file",
        metavar="NAME.sql",
        help="Exact SQL basename under migrations/ or archive/historical/",
    )
    ns = parser.parse_args(argv)
    if ns.sql_file:
        return run_by_basename(ns.sql_file)
    if ns.migration_id:
        return run_by_migration_number(ns.migration_id)
    parser.print_help()
    return 2
