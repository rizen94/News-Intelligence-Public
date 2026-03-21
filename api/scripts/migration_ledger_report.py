#!/usr/bin/env python3
"""Compare public.applied_migrations to SQL files on disk (active + archive/historical).

From project root:
  PYTHONPATH=api uv run python api/scripts/migration_ledger_report.py
  PYTHONPATH=api uv run python api/scripts/migration_ledger_report.py --json
  PYTHONPATH=api uv run python api/scripts/migration_ledger_report.py --active-only

Exit code 0 always (reporting tool). Missing ledger table is printed as a warning.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict

try:
    from dotenv import load_dotenv

    api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(api_dir, ".env"), override=False)
    load_dotenv(os.path.join(api_dir, "..", ".env"), override=False)
except ImportError:
    pass

if not os.environ.get("DB_PASSWORD") and os.path.exists(
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", ".db_password_widow")
):
    pw_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", ".db_password_widow")
    try:
        with open(pw_path) as f:
            os.environ["DB_PASSWORD"] = f.read().strip()
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _stem(filename: str) -> str:
    return filename[:-4] if filename.endswith(".sql") else filename


def _num3(filename: str) -> str | None:
    m = re.match(r"^(\d{3})_", filename)
    return m.group(1) if m else None


def _files_by_prefix(files: list[tuple[str, str]]) -> dict[str, list[str]]:
    """prefix (3 digits) -> list of filenames."""
    d: dict[str, list[str]] = defaultdict(list)
    for name, _path in files:
        p = _num3(name)
        if p:
            d[p].append(name)
    return dict(d)


def _ledger_covers_stem(
    ledger_ids: set[str], stem: str, num: str | None, ambiguous_nums: set[str]
) -> bool:
    if stem in ledger_ids:
        return True
    if num and num not in ambiguous_nums and num in ledger_ids:
        return True
    return False


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    p.add_argument(
        "--active-only",
        action="store_true",
        help="Only flag SQL files in the active migrations root (ignore archive for the missing-file list)",
    )
    args = p.parse_args()

    from shared.database.connection import get_db_connection
    from shared.migration_sql_paths import (
        archive_historical_dir,
        list_sql_migrations,
        migrations_root,
    )

    files = list_sql_migrations(include_archive=True)
    stems = {_stem(name) for name, _p in files}
    by_prefix = _files_by_prefix(files)
    ambiguous_nums = {k for k, v in by_prefix.items() if len(v) > 1}

    active_names = {n for n, path in list_sql_migrations(include_archive=False)}

    conn = get_db_connection()
    if not conn:
        print("ERROR: no DB connection", file=sys.stderr)
        return 1

    ledger_rows: list[tuple[str, str | None, str | None]] = []
    ledger_ok = True
    err: str | None = None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT migration_id, applied_at::text, notes
                FROM public.applied_migrations
                ORDER BY applied_at NULLS LAST, migration_id
                """
            )
            ledger_rows = [(r[0], r[1], r[2]) for r in cur.fetchall()]
    except Exception as e:
        ledger_ok = False
        err = str(e)
    finally:
        conn.close()

    ledger_ids = {r[0] for r in ledger_rows}

    missing_ledger: list[dict] = []
    if ledger_ok:
        for name, path in sorted(files, key=lambda x: x[0]):
            stem = _stem(name)
            num = _num3(name)
            loc = "active" if name in active_names else "archive/historical"
            if not _ledger_covers_stem(ledger_ids, stem, num, ambiguous_nums):
                missing_ledger.append(
                    {"file": name, "location": loc, "path": path, "reason": "no_matching_row"}
                )

    orphan_ledger: list[dict] = []
    if ledger_ok:
        for mid, applied_at, notes in ledger_rows:
            stem_key = _stem(mid)
            matched = stem_key in stems
            if not matched and re.match(r"^\d{3}$", mid) and len(by_prefix.get(mid, [])) == 1:
                matched = True
            if not matched:
                orphan_ledger.append(
                    {"migration_id": mid, "applied_at": applied_at, "notes": notes}
                )

    missing_for_report = missing_ledger
    if args.active_only:
        missing_for_report = [m for m in missing_ledger if m.get("location") == "active"]

    payload = {
        "migrations_root": str(migrations_root()),
        "archive_historical": str(archive_historical_dir()),
        "ledger_table_ok": ledger_ok,
        "ledger_error": err if not ledger_ok else None,
        "file_count": len(files),
        "ledger_row_count": len(ledger_rows),
        "files_without_ledger_row": missing_for_report,
        "ledger_rows_without_file": orphan_ledger,
        "active_only_filter": bool(args.active_only),
    }

    if args.json:
        print(json.dumps(payload, indent=2))
        return 0

    print("Migration ledger report")
    print(f"  migrations root: {payload['migrations_root']}")
    print(f"  archive:         {payload['archive_historical']}")
    print(f"  SQL files (active + archive, deduped): {payload['file_count']}")
    if not ledger_ok:
        print(f"  WARNING: could not read public.applied_migrations ({err})")
        print("           Apply migration 176 and register_applied_migration as needed.")
    else:
        print(f"  ledger rows: {payload['ledger_row_count']}")
        print(
            "  Tip: rows in archive/historical usually have **no** ledger entry (pre-176 era);"
            " focus gaps on **active** files in the migrations root."
        )

    if missing_for_report:
        label = "Files with no matching ledger row"
        if args.active_only:
            label += " (active migrations only)"
        print(f"\n{label}:")
        for item in missing_for_report[:200]:
            print(f"  - [{item['location']}] {item['file']}")
        if len(missing_for_report) > 200:
            print(f"  ... and {len(missing_for_report) - 200} more")

    if orphan_ledger:
        print(
            "\nLedger IDs with no matching .sql on disk (typo, renamed file, or environment-specific):"
        )
        for item in orphan_ledger:
            print(f"  - {item['migration_id']} (applied_at={item['applied_at']})")

    if ledger_ok and not missing_for_report and not orphan_ledger:
        print(
            "\nOK: every file (per filter) has ledger coverage and every ledger row matches a file."
        )
    elif ledger_ok:
        print(
            "\nNote: Pre-176 files are often intentionally absent from the ledger;"
            " use `--active-only` to focus on **176+** files in the migrations root."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
