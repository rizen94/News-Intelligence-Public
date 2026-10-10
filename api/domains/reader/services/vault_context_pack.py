"""
Canned research context packs from vault notes + mirrored links + geo parents.

Given entity IDs (or titles), expand 1–2 hops via vault_note_links and
geo_parent_entity_id, then return tags, linked paths, and significance excerpts
for article summary / editorial consumers.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from services.vault_bridge_service import _FRONTMATTER_RE, vault_root
from shared.database.connection import get_db_connection_context
from shared.vault_note_contract import (
    AUTO_SIGNIFICANCE_END,
    AUTO_SIGNIFICANCE_START,
    DEFAULT_PACK_HOPS,
    DEFAULT_PACK_MAX_NOTES,
)

logger = logging.getLogger(__name__)

_SIG_RE = re.compile(
    re.escape(AUTO_SIGNIFICANCE_START) + r"(.*?)" + re.escape(AUTO_SIGNIFICANCE_END),
    re.DOTALL,
)


def _read_significance(vault_path: str, *, max_chars: int = 900) -> str | None:
    path = vault_root() / vault_path
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    m = _SIG_RE.search(text)
    if m:
        return (m.group(1) or "").strip()[:max_chars]
    # Fallback: first non-frontmatter paragraph
    body = _FRONTMATTER_RE.sub("", text, count=1).lstrip()
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("#") or not line or line.startswith("<!--"):
            continue
        return line[:max_chars]
    return None


def _seed_rows_for_entities(
    domain_key: str, entity_ids: list[int]
) -> list[dict[str, Any]]:
    if not entity_ids:
        return []
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT vault_path, title, note_type, object_id, tags,
                       geo_parent_entity_id, place_kind, note_status, lifecycle
                FROM intelligence.vault_notes
                WHERE domain_key = %s
                  AND note_type = 'entity'
                  AND object_id = ANY(%s)
                  AND COALESCE(lifecycle, 'stub') NOT IN ('index', 'archived')
                """,
                (domain_key, list(entity_ids)),
            )
            rows = cur.fetchall()
    return [
        {
            "vault_path": r[0],
            "title": r[1],
            "note_type": r[2],
            "object_id": r[3],
            "tags": list(r[4] or []),
            "geo_parent_entity_id": r[5],
            "place_kind": r[6],
            "note_status": r[7],
            "lifecycle": r[8],
        }
        for r in rows
    ]


def _expand_hops(
    domain_key: str,
    seed_paths: list[str],
    *,
    hops: int,
    max_notes: int,
) -> list[str]:
    seen: set[str] = set(seed_paths)
    frontier = list(seed_paths)
    ordered = list(seed_paths)
    for _ in range(max(0, hops)):
        if not frontier or len(ordered) >= max_notes:
            break
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT COALESCE(dst_vault_path, '')
                    FROM intelligence.vault_note_links
                    WHERE domain_key = %s
                      AND src_vault_path = ANY(%s)
                      AND link_kind = 'wikilink'
                      AND dst_vault_path IS NOT NULL
                    """,
                    (domain_key, frontier),
                )
                next_paths = [r[0] for r in cur.fetchall() if r[0]]
                # Also follow geo parents of seed entities
                cur.execute(
                    """
                    SELECT vn2.vault_path
                    FROM intelligence.vault_notes vn
                    JOIN intelligence.vault_notes vn2
                      ON vn2.domain_key = vn.domain_key
                     AND vn2.note_type = 'entity'
                     AND vn2.object_id = vn.geo_parent_entity_id
                    WHERE vn.vault_path = ANY(%s)
                      AND vn.geo_parent_entity_id IS NOT NULL
                    """,
                    (frontier,),
                )
                next_paths.extend(r[0] for r in cur.fetchall() if r[0])
        # Prefer grounding wiki (timelines/stories/entities/connections) over
        # clipping volume so hand-curated ledgers stay in the pack window.
        def _hop_rank(p: str) -> tuple[int, str]:
            if p.startswith("40_Reference/timelines/"):
                return (0, p)
            if p.startswith("30_Stories/") and "/expansions/" not in p:
                return (1, p)
            if p.startswith("40_Reference/entities/") or p.startswith(
                "25_Connections/"
            ):
                return (2, p)
            if p.startswith("30_Stories/expansions/"):
                return (3, p)
            if p.startswith("20_Clippings/") or p.startswith("50_Science/20_Clippings/"):
                return (5, p)
            return (4, p)

        nxt: list[str] = []
        for p in sorted(next_paths, key=_hop_rank):
            if p in seen:
                continue
            seen.add(p)
            ordered.append(p)
            nxt.append(p)
            if len(ordered) >= max_notes:
                break
        frontier = nxt
    return ordered[:max_notes]


def _load_note_meta(paths: list[str]) -> dict[str, dict[str, Any]]:
    if not paths:
        return {}
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT vault_path, title, note_type, object_id, tags,
                       geo_parent_entity_id, place_kind, note_status, lifecycle,
                       domain_key
                FROM intelligence.vault_notes
                WHERE vault_path = ANY(%s)
                """,
                (paths,),
            )
            rows = cur.fetchall()
    return {
        r[0]: {
            "vault_path": r[0],
            "title": r[1],
            "note_type": r[2],
            "object_id": r[3],
            "tags": list(r[4] or []),
            "geo_parent_entity_id": r[5],
            "place_kind": r[6],
            "note_status": r[7],
            "lifecycle": r[8],
            "domain_key": r[9],
        }
        for r in rows
    }


def build_vault_context_pack(
    *,
    domain_key: str = "politics",
    entity_ids: list[int] | None = None,
    titles: list[str] | None = None,
    hops: int = DEFAULT_PACK_HOPS,
    max_notes: int = DEFAULT_PACK_MAX_NOTES,
) -> dict[str, Any]:
    """Assemble canned background for summarizers."""
    seeds = _seed_rows_for_entities(domain_key, entity_ids or [])
    if titles:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                for t in titles:
                    cur.execute(
                        """
                        SELECT vault_path, title, note_type, object_id, tags,
                               geo_parent_entity_id, place_kind, note_status, lifecycle
                        FROM intelligence.vault_notes
                        WHERE domain_key = %s AND lower(title) = lower(%s)
                        LIMIT 1
                        """,
                        (domain_key, t),
                    )
                    row = cur.fetchone()
                    if row:
                        seeds.append(
                            {
                                "vault_path": row[0],
                                "title": row[1],
                                "note_type": row[2],
                                "object_id": row[3],
                                "tags": list(row[4] or []),
                                "geo_parent_entity_id": row[5],
                                "place_kind": row[6],
                                "note_status": row[7],
                                "lifecycle": row[8],
                            }
                        )

    seed_paths = [s["vault_path"] for s in seeds if s.get("vault_path")]
    if not seed_paths:
        return {
            "ok": True,
            "domain_key": domain_key,
            "seeds": [],
            "notes": [],
            "actors": [],
            "message": "No vault notes registered for inputs.",
        }

    expanded = _expand_hops(
        domain_key, seed_paths, hops=hops, max_notes=max_notes
    )
    meta = _load_note_meta(expanded)

    notes_out: list[dict[str, Any]] = []
    actors: list[str] = []
    all_tags: list[str] = []
    for path in expanded:
        info = meta.get(path) or {"vault_path": path, "title": path}
        # Hide index/archived stubs from reader context packs (F7).
        if str(info.get("lifecycle") or "") in ("index", "archived"):
            continue
        sig = _read_significance(path)
        try:
            from shared.llm_text_sanitize import sanitize_reader_prose

            sig = sanitize_reader_prose(
                sig,
                title=str(info.get("title") or ""),
                max_length=400,
            )
        except Exception:
            pass
        entry = {
            **info,
            "significance_excerpt": sig,
            "is_seed": path in seed_paths,
        }
        notes_out.append(entry)
        if info.get("title"):
            actors.append(str(info["title"]))
        all_tags.extend(info.get("tags") or [])

    # Dedupe tags preserving order
    seen_t: set[str] = set()
    tags_unique: list[str] = []
    for t in all_tags:
        k = str(t).lower()
        if k in seen_t:
            continue
        seen_t.add(k)
        tags_unique.append(str(t))

    return {
        "ok": True,
        "domain_key": domain_key,
        "hops": hops,
        "seeds": seeds,
        "notes": notes_out,
        "actors": actors[:max_notes],
        "tags": tags_unique[:40],
        "note_count": len(notes_out),
    }


def render_vault_context_pack_for_llm(
    pack: dict[str, Any] | None, *, max_chars: int = 6000
) -> str:
    """Compact living-vault background for narrative / executive-summary prompts."""
    if not pack or not isinstance(pack, dict):
        return ""
    notes = pack.get("notes") if isinstance(pack.get("notes"), list) else []
    if not notes:
        return ""
    lines: list[str] = [
        "Living vault background (Obsidian knowledge notes — durable context, not new facts):"
    ]
    for n in notes:
        if not isinstance(n, dict):
            continue
        title = (n.get("title") or n.get("vault_path") or "Note").strip()
        tags = n.get("tags") if isinstance(n.get("tags"), list) else []
        tag_s = ", ".join(str(t) for t in tags[:8] if t)
        seed = " [seed]" if n.get("is_seed") else ""
        lines.append(f"- {title}{seed}" + (f" ({tag_s})" if tag_s else ""))
        sig = (n.get("significance_excerpt") or "").strip()
        if sig:
            lines.append(f"  Significance: {sig[:700]}")
    text = "\n".join(lines).strip()
    if len(text) > max_chars:
        return text[: max_chars - 20].rstrip() + "\n…"
    return text


def build_vault_pack_for_entity_ids(
    domain_key: str,
    entity_ids: list[int],
    *,
    hops: int = DEFAULT_PACK_HOPS,
    max_notes: int = DEFAULT_PACK_MAX_NOTES,
) -> dict[str, Any]:
    ids = [int(x) for x in entity_ids if isinstance(x, int) or str(x).isdigit()]
    if not ids:
        return {
            "ok": True,
            "domain_key": domain_key,
            "seeds": [],
            "notes": [],
            "actors": [],
            "message": "No entity ids",
        }
    return build_vault_context_pack(
        domain_key=domain_key,
        entity_ids=ids[:24],
        hops=hops,
        max_notes=max_notes,
    )
