"""
Sync Obsidian frontmatter tags + wikilinks → Postgres mirror.

Obsidian is SSOT for relational tags and soft links. Postgres caches them for
context-pack expansion. NI never invents rivalry/hate edges here.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from services.vault_bridge_service import (
    _FRONTMATTER_RE,
    _parse_frontmatter_rich,
    vault_root,
)
from services.vault_notes_registry_service import (
    apply_obsidian_tag_mirror,
    replace_vault_note_links,
    resolve_title_to_vault_path,
)
from shared.vault_note_contract import (
    VAULT_SYNC_ROOTS,
    extract_hash_tags,
    extract_wikilink_titles,
    merge_tags,
)

logger = logging.getLogger(__name__)


def _rel_path(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def _domain_from_fm_or_path(fm: dict[str, Any], rel: str) -> str:
    d = fm.get("ni_domain") or fm.get("domain")
    if d:
        return str(d)
    # 30_Stories/politics-123-...
    parts = rel.split("/")
    if parts and parts[-1].startswith("finance-"):
        return "finance"
    return "politics"


def _normalize_tags(fm: dict[str, Any], body: str) -> list[str]:
    fm_tags: list[str] = []
    raw = fm.get("tags")
    if isinstance(raw, list):
        fm_tags = [str(t).strip().lstrip("#") for t in raw if str(t).strip()]
    elif isinstance(raw, str) and raw.strip():
        fm_tags = [t.strip().lstrip("#") for t in raw.split(",") if t.strip()]
    body_tags = extract_hash_tags(body)
    return merge_tags(fm_tags, body_tags)


def sync_vault_file(path: Path, *, root: Path | None = None) -> dict[str, Any]:
    root = root or vault_root()
    if not path.is_file() or path.suffix.lower() != ".md":
        return {"ok": False, "error": "not_markdown"}
    if path.name.startswith("_"):
        return {"ok": True, "skipped": True, "reason": "index"}
    rel = _rel_path(path, root)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        return {"ok": False, "error": str(e), "path": rel}

    fm = _parse_frontmatter_rich(text)
    body = _FRONTMATTER_RE.sub("", text, count=1).lstrip("\n") if _FRONTMATTER_RE.match(text) else text
    domain_key = _domain_from_fm_or_path(fm, rel)
    tags = _normalize_tags(fm, body)
    title = fm.get("title") or (body.split("\n", 1)[0].lstrip("# ").strip() if body else path.stem)

    apply_obsidian_tag_mirror(
        rel, tags=tags, domain_key=domain_key, title=str(title) if title else None
    )

    links: list[dict[str, Any]] = []
    for wtitle in extract_wikilink_titles(body):
        dst = resolve_title_to_vault_path(wtitle)
        links.append(
            {
                "dst_title": wtitle,
                "dst_vault_path": dst,
                "link_kind": "wikilink",
            }
        )
    # tag_ref: tags that look like note paths are skipped; keep soft tags as tag_ref to title
    for tag in tags:
        if "/" in tag and not tag.startswith(("entity/", "place/", "domain/", "note/")):
            # e.g. relation/rival — no destination path
            links.append(
                {
                    "dst_title": f"#{tag}",
                    "dst_vault_path": None,
                    "link_kind": "tag_ref",
                }
            )

    n_links = replace_vault_note_links(
        domain_key=domain_key, src_vault_path=rel, links=links
    )
    return {
        "ok": True,
        "path": rel,
        "domain_key": domain_key,
        "tag_count": len(tags),
        "link_count": n_links,
        "tags": tags[:20],
    }


def sync_vault_tags_and_links(
    *,
    roots: tuple[str, ...] | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Walk vault sync roots and mirror tags/links into Postgres."""
    root = vault_root()
    if not root.is_dir():
        return {"ok": False, "error": f"vault root missing: {root}"}

    stats = {
        "ok": True,
        "scanned": 0,
        "synced": 0,
        "skipped": 0,
        "errors": 0,
        "links_total": 0,
        "paths": [],
    }
    dirs = roots or VAULT_SYNC_ROOTS
    files: list[Path] = []
    for d in dirs:
        base = root / d
        if not base.is_dir():
            continue
        files.extend(sorted(base.rglob("*.md")))

    for path in files:
        if limit is not None and stats["synced"] >= limit:
            break
        stats["scanned"] += 1
        try:
            result = sync_vault_file(path, root=root)
            if result.get("skipped"):
                stats["skipped"] += 1
            elif result.get("ok"):
                stats["synced"] += 1
                stats["links_total"] += int(result.get("link_count") or 0)
                if len(stats["paths"]) < 40:
                    stats["paths"].append(result.get("path"))
            else:
                stats["errors"] += 1
        except Exception as e:
            logger.warning("vault sync failed %s: %s", path, e)
            stats["errors"] += 1

    return stats
