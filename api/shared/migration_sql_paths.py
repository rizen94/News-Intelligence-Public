"""
Resolve SQL migration file paths: active `api/database/migrations/` first,
then `api/database/migrations/archive/historical/` (archived, pre–ledger era).

Used by `api/scripts/run_migration_*.py` so runners keep working after archival.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Optional, Tuple

# api/ (parent of shared/)
_API_ROOT = Path(__file__).resolve().parent.parent
_MIGRATIONS = _API_ROOT / "database" / "migrations"
_ARCHIVE_HISTORICAL = _MIGRATIONS / "archive" / "historical"


def migrations_root() -> Path:
    return _MIGRATIONS


def archive_historical_dir() -> Path:
    return _ARCHIVE_HISTORICAL


def resolve_migration_sql_file(filename: str) -> str:
    """
    Return absolute path to filename in active migrations or archive/historical.
    Raises FileNotFoundError if missing.
    """
    for base in (_MIGRATIONS, _ARCHIVE_HISTORICAL):
        p = base / filename
        if p.is_file():
            return str(p)
    raise FileNotFoundError(
        f"Migration SQL not found: {filename} (searched {_MIGRATIONS} and {_ARCHIVE_HISTORICAL})"
    )


def find_migration_sql_by_prefix(migration_id: str) -> str:
    """
    Find a single .sql file whose name starts with migration_id + '_'
    (e.g. '167' -> 167_enrichment_tracking.sql). Searches active then archive.
    Raises FileNotFoundError or ValueError if ambiguous.
    """
    if not re.match(r"^\d{3}$", migration_id):
        raise ValueError(f"migration_id must be three digits, got {migration_id!r}")
    matches: List[Path] = []
    for base in (_MIGRATIONS, _ARCHIVE_HISTORICAL):
        if not base.is_dir():
            continue
        for p in base.glob(f"{migration_id}_*.sql"):
            matches.append(p)
    if not matches:
        raise FileNotFoundError(f"No {migration_id}_*.sql in migrations or archive/historical")
    if len(matches) > 1:
        raise FileNotFoundError(
            f"Ambiguous migration {migration_id}: {matches!r}"
        )
    return str(matches[0])


def list_sql_migrations(include_archive: bool = True) -> List[Tuple[str, Path]]:
    """
    Return sorted (filename, path) for NNN_*.sql under active and optionally archive.
    Active files are listed before archive when both exist (dedupe by filename: prefer active).
    """
    seen: dict[str, Path] = {}
    dirs: List[Path] = [_MIGRATIONS]
    if include_archive and _ARCHIVE_HISTORICAL.is_dir():
        dirs.append(_ARCHIVE_HISTORICAL)
    for base in dirs:
        if not base.is_dir():
            continue
        for p in sorted(base.glob("[0-9][0-9][0-9]_*.sql")):
            if p.name not in seen:
                seen[p.name] = p
    return sorted(seen.items(), key=lambda x: x[0])
