"""Obsidian-compatible vault read/write under NRI_VAULT_PATH."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.runtime import env_str

logger = logging.getLogger(__name__)


def vault_root() -> Path:
    root = Path(env_str("NRI_VAULT_PATH", "/data/vault"))
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def _safe_rel_path(rel: str) -> Path:
    rel = (rel or "").replace("\\", "/").lstrip("/")
    if ".." in rel.split("/"):
        raise ValueError("path traversal not allowed")
    if not rel.endswith(".md"):
        rel = f"{rel}.md" if not rel.endswith(".md") else rel
    return Path(rel)


def list_notes(subdir: str = "") -> list[dict[str, str]]:
    root = vault_root()
    base = root / subdir if subdir else root
    if not base.is_dir():
        return []
    out: list[dict[str, str]] = []
    for p in sorted(base.rglob("*.md")):
        rel = str(p.relative_to(root))
        out.append({"path": rel, "modified": datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat()})
    return out[:500]


def read_note(rel_path: str) -> dict[str, Any]:
    root = vault_root()
    path = root / _safe_rel_path(rel_path)
    if not path.is_file():
        return {"found": False, "path": rel_path}
    return {"found": True, "path": rel_path, "content": path.read_text(encoding="utf-8")}


def write_note(rel_path: str, content: str, *, append: bool = False) -> dict[str, Any]:
    if env_str("NRI_VAULT_WRITE", "true").lower() not in ("1", "true", "yes"):
        return {"ok": False, "error": "vault write disabled"}
    root = vault_root()
    path = root / _safe_rel_path(rel_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if append and path.is_file():
        existing = path.read_text(encoding="utf-8")
        content = existing.rstrip() + "\n\n" + content
    path.write_text(content, encoding="utf-8")
    return {"ok": True, "path": str(path.relative_to(root))}


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:80] or "note"
