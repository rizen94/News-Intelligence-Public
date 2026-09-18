"""Gather delta since last run for an entity."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from nri_core.config import get_config


def gather_delta(entity_ftm_id: str) -> dict[str, Any]:
    cfg = get_config()
    vault_root = Path(cfg.vault_path)
    facts: list[str] = []
    hypotheses: list[str] = []
    new_fact_ids: list[str] = []

    for section, bucket in (("facts", facts), ("hypotheses", hypotheses)):
        section_dir = vault_root / section
        if not section_dir.exists():
            continue
        for path in section_dir.glob("*.md"):
            text = path.read_text(encoding="utf-8")
            if not text.startswith("---"):
                continue
            meta = yaml.safe_load(text.split("---", 2)[1]) or {}
            if meta.get("subject_ftm_id") == entity_ftm_id or meta.get("ftm_id") == entity_ftm_id:
                bucket.append(path.stem)
                if section == "facts":
                    new_fact_ids.append(path.stem)

    return {
        "entity_ftm_id": entity_ftm_id,
        "facts": facts,
        "hypotheses": hypotheses,
        "new_fact_ids": new_fact_ids,
    }
