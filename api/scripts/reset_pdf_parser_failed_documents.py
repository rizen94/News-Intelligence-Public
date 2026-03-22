#!/usr/bin/env python3
"""
Clear permanent_failure for processed_documents that failed only because PDF
libraries were missing. Run after installing PDF deps (see below).

**Project root:** use your clone path (e.g. ~/Documents/projects/Projects/News Intelligence).
`/opt/news-intelligence` is only the default on some servers (e.g. Widow).

**Install PDF deps (PEP 668 / Pop!_OS — do not use system pip):**
  cd "<repo-root>"
  uv pip install -r api/requirements.txt
  # or: .venv/bin/python -m pip install -r api/requirements.txt

**Database:** this script loads repo-root `.env` (same as the API). You need
`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` (and any tunnel vars you use).

Usage (from repo root):
  PYTHONPATH=api uv run python api/scripts/reset_pdf_parser_failed_documents.py --dry-run
  PYTHONPATH=api uv run python api/scripts/reset_pdf_parser_failed_documents.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load_dotenv_from_repo_root() -> None:
    """Load project-root .env so DB_* are set when not running under uvicorn."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(override=False)
    repo_root = Path(__file__).resolve().parents[2]
    env_path = repo_root / ".env"
    if env_path.is_file():
        load_dotenv(env_path, override=False)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print matching IDs only; do not update",
    )
    args = parser.parse_args()

    _load_dotenv_from_repo_root()

    try:
        from shared.database.connection import get_db_connection_context
    except ImportError:
        print(
            "Import failed: run from repo root with PYTHONPATH=api "
            "(e.g. PYTHONPATH=api uv run python api/scripts/reset_pdf_parser_failed_documents.py)",
            file=sys.stderr,
        )
        return 1

    sql_select = """
        SELECT id, title,
               metadata->'processing'->>'error' AS err
        FROM intelligence.processed_documents
        WHERE COALESCE(metadata->'processing'->>'error', '') ILIKE '%%no pdf parser%%'
           OR COALESCE(metadata->'processing'->>'error', '') ILIKE '%%install pdfplumber%%'
        ORDER BY id
    """

    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(sql_select)
                rows = cur.fetchall()

            if not rows:
                print("No documents matched (processing.error contains PDF parser install message).")
                return 0

            print(f"Matched {len(rows)} document(s):")
            for rid, title, err in rows:
                et = (err or "")[:120]
                tshort = repr((title or "")[:60])
                print(f"  id={rid} title={tshort} error={et!r}")

            if args.dry_run:
                print("--dry-run: no updates applied.")
                return 0

            updated = 0
            for rid, _title, _err in rows:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT metadata FROM intelligence.processed_documents WHERE id = %s",
                        (rid,),
                    )
                    one = cur.fetchone()
                    if not one or one[0] is None:
                        continue
                    raw_meta = one[0]
                    if isinstance(raw_meta, dict):
                        meta = dict(raw_meta)
                    elif isinstance(raw_meta, str):
                        meta = json.loads(raw_meta)
                    else:
                        meta = dict(raw_meta) if hasattr(raw_meta, "keys") else {}

                    proc = meta.get("processing")
                    if not isinstance(proc, dict):
                        proc = {}
                    proc.pop("permanent_failure", None)
                    proc.pop("error", None)
                    proc["attempts"] = 0
                    proc["retry_reset_reason"] = "pdf_parser_dependencies_installed"
                    meta["processing"] = proc
                    cur.execute(
                        """
                        UPDATE intelligence.processed_documents
                        SET metadata = %s::jsonb, updated_at = NOW()
                        WHERE id = %s
                        """,
                        (json.dumps(meta), rid),
                    )
                    updated += cur.rowcount
            conn.commit()
            print(
                f"Updated {updated} row(s). Re-run document_processing automation to reprocess."
            )
    except Exception as e:
        err = str(e).lower()
        print(f"Database error: {e}", file=sys.stderr)
        if "password" in err or "fe_sendauth" in err:
            print(
                "Hint: set DB_PASSWORD in the project-root .env (or export DB_*). "
                "This script loads .env automatically when present.",
                file=sys.stderr,
            )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
