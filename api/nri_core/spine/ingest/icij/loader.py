"""ICIJ offshore leaks sample ingest (FtM-native JSON lines)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from nri_core.config import get_config
from nri_core.spine.store import postgres_store


def iter_icij_entities(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def ingest_icij_sample(path: Path | None = None, limit: int = 500) -> int:
    cfg = get_config()
    export_path = path or (Path(cfg.nas_datasets_root) / "icij" / "entities.ftm.json")
    if not export_path.exists():
        return 0

    count = 0
    for entity in iter_icij_entities(export_path):
        entity_id = entity.get("id")
        if not entity_id:
            continue
        schema_name = entity.get("schema", "LegalEntity")
        caption = entity.get("caption")
        postgres_store.upsert_entity(
            entity_id=entity_id,
            schema_name=schema_name,
            caption=caption,
            dataset="icij",
            referents=entity.get("referents", []),
        )
        for prop, values in entity.get("properties", {}).items():
            if not isinstance(values, list):
                values = [values]
            for value in values[:2]:
                if value:
                    postgres_store.upsert_statement(
                        entity_id=entity_id,
                        dataset="icij",
                        schema_name=schema_name,
                        prop=prop,
                        value=str(value),
                        origin="icij",
                    )
        count += 1
        if count >= limit:
            break
    return count
