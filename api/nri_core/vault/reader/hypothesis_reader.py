"""Read vault hypothesis markdown notes."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from nri_core.config import get_config

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)


def _parse_note(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    meta: dict[str, Any] = {}
    body = text
    match = _FRONTMATTER_RE.match(text)
    if match:
        meta = yaml.safe_load(match.group(1)) or {}
        body = match.group(2).strip()
    hyp_id = meta.get("hyp_id") or path.stem
    return {
        "hyp_id": hyp_id,
        "claim": meta.get("claim"),
        "status": meta.get("status"),
        "confidence": meta.get("confidence"),
        "test_status": meta.get("test_status"),
        "subject_ftm_id": meta.get("subject_ftm_id"),
        "iteration_introduced": meta.get("iteration_introduced"),
        "body": body,
        "path": str(path),
    }


def list_hypotheses(
    *,
    status: str | None = None,
    ftm_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    cfg = get_config()
    hyp_dir = Path(cfg.vault_path) / "hypotheses"
    if not hyp_dir.is_dir():
        return {"items": [], "total": 0, "limit": limit, "offset": offset}

    items: list[dict[str, Any]] = []
    for path in sorted(hyp_dir.glob("*.md")):
        note = _parse_note(path)
        if status and note.get("status") != status:
            continue
        if ftm_id and note.get("subject_ftm_id") != ftm_id:
            continue
        items.append({k: v for k, v in note.items() if k != "body"})

    total = len(items)
    page = items[offset : offset + limit]
    return {"items": page, "total": total, "limit": limit, "offset": offset}


def get_hypothesis(hyp_id: str) -> dict[str, Any] | None:
    cfg = get_config()
    hyp_dir = Path(cfg.vault_path) / "hypotheses"
    path = hyp_dir / f"{hyp_id}.md"
    if not path.is_file():
        matches = list(hyp_dir.glob(f"*{hyp_id}*.md"))
        if not matches:
            return None
        path = matches[0]
    return _parse_note(path)
