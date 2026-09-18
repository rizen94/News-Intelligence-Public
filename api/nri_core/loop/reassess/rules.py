"""Mandatory prune/kill/decay rules before new writes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from nri_core.config import get_config

DECAY_FACTOR = 0.95
DORMANT_AFTER_ITERATIONS = 4


@dataclass
class ReassessMetrics:
    killed: int = 0
    demoted: int = 0
    dormant: int = 0
    added: int = 0

    def net_negative_count(self) -> int:
        return self.killed + self.demoted + self.dormant


def _parse_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    return yaml.safe_load(parts[1]) or {}


def _write_frontmatter(path: Path, meta: dict[str, Any], body: str) -> None:
    import yaml as yaml_lib

    header = yaml_lib.dump(meta, default_flow_style=False, allow_unicode=True)
    path.write_text(f"---\n{header}---\n\n{body}", encoding="utf-8")


def reassess_hypotheses(
    entity_ftm_id: str,
    new_evidence_ids: list[str] | None = None,
    iteration: int = 0,
) -> ReassessMetrics:
    cfg = get_config()
    vault_root = Path(cfg.vault_path)
    hyp_dir = vault_root / "hypotheses"
    metrics = ReassessMetrics()
    if not hyp_dir.exists():
        return metrics

    new_evidence_ids = new_evidence_ids or []
    for path in hyp_dir.glob("*.md"):
        meta = _parse_frontmatter(path)
        if meta.get("status") in {"refuted", "dormant"}:
            continue
        if meta.get("subject_ftm_id") and meta.get("subject_ftm_id") != entity_ftm_id:
            continue

        supports = set(meta.get("supports", []))
        touched = bool(supports & set(new_evidence_ids))
        confidence = float(meta.get("confidence", 0.5))
        iterations_since = int(meta.get("iterations_since_support", 0))

        if meta.get("disconfirming_result") == "failed":
            meta["status"] = "refuted"
            meta["confidence"] = 0.0
            metrics.killed += 1
        elif not touched:
            iterations_since += 1
            meta["iterations_since_support"] = iterations_since
            confidence *= DECAY_FACTOR ** iterations_since
            meta["confidence"] = round(confidence, 4)
            if iterations_since >= DORMANT_AFTER_ITERATIONS:
                meta["status"] = "dormant"
                metrics.dormant += 1
            elif confidence < 0.2:
                meta["status"] = "dormant"
                metrics.demoted += 1
            else:
                metrics.demoted += 1
        else:
            meta["iterations_since_support"] = 0
            meta["confidence"] = min(confidence + 0.05, 0.85)

        meta["last_reassessed"] = iteration
        body = path.read_text(encoding="utf-8").split("---", 2)[-1].strip()
        _write_frontmatter(path, meta, body)

    return metrics
