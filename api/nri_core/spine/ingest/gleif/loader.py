"""GLEIF LEI Golden Copy bulk ingest."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any, Iterator

from nri_core.config import get_config
from nri_core.spine.store import postgres_store

# GLEIF Golden Copy LEI-CDF v3.1 typical columns (subset)
LEI_COL = "LEI"
LEGAL_NAME_COL = "Entity.LegalName"
STATUS_COL = "Entity.EntityStatus"


def default_gleif_path() -> Path:
    cfg = get_config()
    return Path(cfg.nas_datasets_root) / "gleif" / "lei-golden-copy.csv"


def _entity_id_for_lei(lei: str) -> str:
    return hashlib.sha1(f"gleif:{lei}".encode()).hexdigest()[:16]


def iter_gleif_rows(path: Path) -> Iterator[dict[str, str]]:
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield row


def ingest_gleif_file(path: Path | None = None, limit: int | None = None) -> int:
    export_path = path or default_gleif_path()
    if not export_path.exists():
        return 0

    count = 0
    for row in iter_gleif_rows(export_path):
        lei = (row.get(LEI_COL) or row.get("lei") or "").strip()
        if not lei or len(lei) != 20:
            continue
        status = (row.get(STATUS_COL) or row.get("entity_status") or "ACTIVE").upper()
        if status and status not in {"ACTIVE", "ISSUED"}:
            continue
        legal_name = (
            row.get(LEGAL_NAME_COL)
            or row.get("legal_name")
            or row.get("Entity.LegalName.content")
            or lei
        ).strip()
        entity_id = _entity_id_for_lei(lei)
        postgres_store.upsert_entity(
            entity_id=entity_id,
            schema_name="Company",
            caption=legal_name,
            dataset="gleif",
            referents=[f"lei:{lei}"],
        )
        postgres_store.upsert_statement(
            entity_id=entity_id,
            dataset="gleif",
            schema_name="Company",
            prop="name",
            value=legal_name,
            origin="gleif",
        )
        postgres_store.upsert_statement(
            entity_id=entity_id,
            dataset="gleif",
            schema_name="Company",
            prop="lei",
            value=lei,
            origin="gleif",
        )
        postgres_store.upsert_anchor(entity_id, "lei", lei)
        count += 1
        if limit and count >= limit:
            break
    return count
