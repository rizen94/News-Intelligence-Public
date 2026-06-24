"""OpenSanctions FtM bulk load from NAS-staged exports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from nri_core.config import get_config
from nri_core.spine.store import postgres_store


def iter_ftm_entities(export_path: Path) -> Iterator[dict[str, Any]]:
    with export_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def ingest_opensanctions_file(path: Path, limit: int | None = None) -> int:
    count = 0
    for entity in iter_ftm_entities(path):
        entity_id = entity.get("id")
        if not entity_id:
            continue
        schema_name = entity.get("schema", "LegalEntity")
        caption = entity.get("caption") or entity.get("properties", {}).get("name", [None])[0]
        postgres_store.upsert_entity(
            entity_id=entity_id,
            schema_name=schema_name,
            caption=caption,
            dataset="opensanctions",
            referents=entity.get("referents", []),
        )
        props = entity.get("properties", {})
        for prop, values in props.items():
            if not isinstance(values, list):
                values = [values]
            for value in values[:3]:
                if value is None:
                    continue
                postgres_store.upsert_statement(
                    entity_id=entity_id,
                    dataset="opensanctions",
                    schema_name=schema_name,
                    prop=prop,
                    value=str(value),
                    origin="opensanctions",
                )
                if prop in {"cik", "lei", "wikidataId", "opencorporates"}:
                    postgres_store.upsert_anchor(entity_id, prop, str(value))
        count += 1
        if limit and count >= limit:
            break
    return count


def default_export_path() -> Path:
    cfg = get_config()
    return Path(cfg.nas_datasets_root) / "opensanctions" / "entities.ftm.json"
