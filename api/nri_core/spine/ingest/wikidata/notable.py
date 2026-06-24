"""Wikidata Phase 2 — notable slice (optional, if park rate still high after Phase 1)."""

from __future__ import annotations

import json
from pathlib import Path

from nri_core.config import get_config
from nri_core.spine.ingest.wikidata.crosswalk import _entity_id_for_qid, ingest_crosswalk_file
from nri_core.spine.store import postgres_store


def ingest_notable_file(path: Path | None = None, limit: int | None = None) -> int:
    """Notable entities JSONL: qid, label, schema — may lack crosswalk (broader index)."""
    cfg = get_config()
    export_path = path or (Path(cfg.nas_datasets_root) / "wikidata" / "notable.jsonl")
    if not export_path.exists():
        return 0

    count = 0
    with export_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            qid = str(record.get("qid", "")).upper()
            if not qid.startswith("Q"):
                qid = f"Q{qid}"
            entity_id = _entity_id_for_qid(qid)
            postgres_store.upsert_entity(
                entity_id=entity_id,
                schema_name=record.get("schema", "Person"),
                caption=record.get("label", qid),
                dataset="wikidata_notable",
                referents=[f"wikidata:{qid}"],
            )
            postgres_store.upsert_anchor(entity_id, "qid", qid)
            count += 1
            if limit and count >= limit:
                break
    return count
