"""
Preseed Obsidian vault notes from Postgres top entities and major storylines.

Writes structured stubs under 40_Reference/entities (shared refs) and
50_Science/40_Topics (science subjects), plus 40_Reference/events /
30_Stories as appropriate.
registers rows in intelligence.vault_notes, and seeds key connection threads.

Does not overwrite existing vault files unless force=True.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from shared.database.connection import get_db_connection_context
from shared.vault_note_contract import (
    AUTO_POSTURE_END,
    AUTO_POSTURE_START,
    AUTO_SIGNIFICANCE_END,
    AUTO_SIGNIFICANCE_START,
    AUTO_TIMELINE_END,
    AUTO_TIMELINE_START,
    connection_vault_rel_path,
    entity_vault_rel_path,
    storyline_vault_rel_path,
    structural_tags_for_note,
)
from services.vault_bridge_service import (
    _render_frontmatter,
    merge_write_vault_markdown,
    vault_root,
    vault_write_enabled,
)
from services.vault_notes_registry_service import upsert_vault_note

logger = logging.getLogger(__name__)

# Media / noise orgs — skip as entity pages
_SKIP_NAME_RE = re.compile(
    r"^(breitbart|bloomberg|guardian|the guardian|bbc|cnn|npr|reuters|"
    r"associated press|ap news|fox news|washington post|new york times|"
    r"hearing|trial|election|elections|war|american|u\.s\.|"
    r"trump|the trump administration|white house)$",
    re.I,
)

# Prefer full canonical over short duplicates (slug collision handled separately)
_ALIAS_SKIP_NAMES = frozenset(
    {
        "trump",
        "the trump administration",
        "white house",
        "jill biden",
        "andrew paul johnson",
        "bjp",
        "labour",
    }
)

# Always include these politics people even if ranking fluctuates
_PRIORITY_ENTITY_IDS = (
    35465,  # Donald J. Trump
    490,  # Benjamin Netanyahu
    4496,  # Sir Keir Starmer
    478623,  # Andy Burnham
    18607,  # Pete Hegseth
    2990,  # Marco Rubio
    31932,  # Ali Khamenei
    2423,  # Iran
    2571,  # Israel
)

# Prefer clean titles / paths that match existing vault cards
_PREFERRED_ENTITY_NAMES: dict[int, str] = {
    18607: "Pete Hegseth",
    31932: "Ali Khamenei",
    35465: "Donald J. Trump",
    490: "Benjamin Netanyahu",
}

_CONNECTION_SEEDS = (
    (35465, 490, "Donald J. Trump", "Benjamin Netanyahu"),
    (35465, 2423, "Donald J. Trump", "Iran"),
    (2571, 490, "Israel", "Benjamin Netanyahu"),
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_skip_entity(name: str, entity_type: str | None) -> bool:
    n = (name or "").strip()
    if len(n) < 3:
        return True
    if n.lower() in _ALIAS_SKIP_NAMES:
        return True
    if _SKIP_NAME_RE.match(n):
        return True
    # Prefer people + geo/orgs; skip vague subjects
    if (entity_type or "").lower() in ("subject", "recurring_event"):
        if n.lower() not in ("iran", "israel"):
            return True
    return False


def fetch_top_entities(
    domain_key: str = "politics",
    *,
    limit: int = 40,
    min_mentions: int = 80,
) -> list[dict[str, Any]]:
    schema = domain_key.replace("-", "_")
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT ae.canonical_entity_id,
                       ec.canonical_name,
                       ec.entity_type,
                       COUNT(*)::int AS mentions,
                       LEFT(COALESCE(ec.description, ''), 800) AS description
                FROM {schema}.article_entities ae
                JOIN {schema}.entity_canonical ec ON ec.id = ae.canonical_entity_id
                WHERE ae.canonical_entity_id IS NOT NULL
                GROUP BY ae.canonical_entity_id, ec.canonical_name, ec.entity_type, ec.description
                HAVING COUNT(*) >= %s
                ORDER BY COUNT(*) DESC
                LIMIT %s
                """,
                (min_mentions, limit * 2),
            )
            rows = cur.fetchall()

            # Ensure priority IDs present
            missing = [i for i in _PRIORITY_ENTITY_IDS if i not in {r[0] for r in rows}]
            if missing:
                cur.execute(
                    f"""
                    SELECT ec.id, ec.canonical_name, ec.entity_type,
                           COALESCE((
                             SELECT COUNT(*)::int FROM {schema}.article_entities ae
                             WHERE ae.canonical_entity_id = ec.id
                           ), 0) AS mentions,
                           LEFT(COALESCE(ec.description, ''), 800)
                    FROM {schema}.entity_canonical ec
                    WHERE ec.id = ANY(%s)
                    """,
                    (list(missing),),
                )
                rows = list(rows) + list(cur.fetchall())

    candidates: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for r in rows:
        eid, name, etype, mentions, desc = r
        if eid in seen_ids or _is_skip_entity(str(name), etype):
            continue
        seen_ids.add(int(eid))
        display = _PREFERRED_ENTITY_NAMES.get(int(eid), str(name))
        candidates.append(
            {
                "id": int(eid),
                "name": display,
                "entity_type": etype,
                "mentions": int(mentions or 0),
                "description": (desc or "").strip(),
            }
        )

    # Collapse path-slug collisions — keep highest mention count
    by_path: dict[str, dict[str, Any]] = {}
    for ent in sorted(candidates, key=lambda e: -e["mentions"]):
        path = entity_vault_rel_path(
            ent["name"],
            domain_key=domain_key,
            entity_type=ent.get("entity_type"),
        ).lower()
        if path not in by_path:
            by_path[path] = ent
    out = sorted(by_path.values(), key=lambda e: -e["mentions"])[:limit]
    return out


def fetch_entity_profile_basics(domain_key: str, entity_id: int) -> str:
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sections, relationships_summary
                FROM intelligence.entity_profiles
                WHERE domain_key = %s AND canonical_entity_id = %s
                ORDER BY updated_at DESC NULLS LAST
                LIMIT 1
                """,
                (domain_key, entity_id),
            )
            row = cur.fetchone()
    if not row:
        return ""
    sections = row[0]
    if isinstance(sections, str):
        try:
            sections = json.loads(sections)
        except json.JSONDecodeError:
            sections = None
    parts: list[str] = []
    if isinstance(sections, list):
        for sec in sections[:4]:
            if not isinstance(sec, dict):
                continue
            title = (sec.get("title") or "Section").strip()
            content = (sec.get("content") or "").strip()
            if content:
                parts.append(f"**{title}:** {content[:600]}")
    elif isinstance(sections, dict):
        for k, v in list(sections.items())[:4]:
            if isinstance(v, str) and v.strip():
                parts.append(f"**{k}:** {v.strip()[:600]}")
    rel = row[1]
    if isinstance(rel, str):
        try:
            rel = json.loads(rel)
        except json.JSONDecodeError:
            rel = None
    if isinstance(rel, list) and rel:
        bullets = []
        for item in rel[:8]:
            if isinstance(item, dict):
                tgt = item.get("target") or item.get("name") or ""
                relation = item.get("relation") or item.get("type") or "related"
                if tgt:
                    bullets.append(f"- [[{tgt}]] — {relation}")
            elif isinstance(item, str):
                bullets.append(f"- {item}")
        if bullets:
            parts.append("**Profile relationships:**\n" + "\n".join(bullets))
    return "\n\n".join(parts).strip()


def fetch_recent_article_bullets(
    domain_key: str, entity_id: int, *, limit: int = 8
) -> list[str]:
    schema = domain_key.replace("-", "_")
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT a.published_at::date, a.title, a.id
                FROM {schema}.article_entities ae
                JOIN {schema}.articles a ON a.id = ae.article_id
                WHERE ae.canonical_entity_id = %s
                  AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                ORDER BY a.published_at DESC NULLS LAST
                LIMIT %s
                """,
                (entity_id, limit),
            )
            rows = cur.fetchall()
    bullets: list[str] = []
    for pub, title, aid in rows:
        day = pub.isoformat() if pub else "undated"
        bullets.append(f"- {day} — {(title or 'Untitled').strip()[:160]} (article:{aid})")
    return bullets


_PRIORITY_STORYLINE_IDS = (8267, 8261, 11146, 3845, 12154, 12248, 11911)


def fetch_major_storylines(
    domain_key: str = "politics", *, limit: int = 20, min_articles: int = 12
) -> list[dict[str, Any]]:
    schema = domain_key.replace("-", "_")

    def _row_to_dict(r: tuple) -> dict[str, Any]:
        return {
            "id": int(r[0]),
            "title": r[1] or f"Storyline {r[0]}",
            "article_count": int(r[2] or 0),
            "status": r[3],
            "description": (r[4] or "").strip(),
            "canonical_narrative": (r[5] or "").strip(),
        }

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            # Force-include curated hubs (even thin article_count)
            cur.execute(
                f"""
                SELECT id, title, COALESCE(article_count, 0), status,
                       LEFT(COALESCE(description, analysis_summary, ''), 1200),
                       LEFT(COALESCE(canonical_narrative, ''), 2000)
                FROM {schema}.storylines
                WHERE id = ANY(%s) AND merged_into_id IS NULL
                """,
                (list(_PRIORITY_STORYLINE_IDS),),
            )
            priority_rows = cur.fetchall()

            cur.execute(
                f"""
                SELECT id, title, COALESCE(article_count, 0), status,
                       LEFT(COALESCE(description, analysis_summary, ''), 1200),
                       LEFT(COALESCE(canonical_narrative, ''), 2000)
                FROM {schema}.storylines
                WHERE merged_into_id IS NULL
                  AND (
                    title ILIKE '%%Gaza%%'
                    OR title ILIKE '%%Hormuz%%'
                    OR title ILIKE '%%Netanyahu%%'
                    OR title ILIKE '%%Iran%%'
                    OR title ILIKE '%%Hezbollah%%'
                    OR title ILIKE '%%Lebanon%%'
                  )
                  AND COALESCE(article_count, 0) >= 10
                ORDER BY article_count DESC NULLS LAST
                LIMIT %s
                """,
                (max(limit, 15),),
            )
            curated = cur.fetchall()
            cur.execute(
                f"""
                SELECT id, title, COALESCE(article_count, 0), status,
                       LEFT(COALESCE(description, analysis_summary, ''), 1200),
                       LEFT(COALESCE(canonical_narrative, ''), 2000)
                FROM {schema}.storylines
                WHERE merged_into_id IS NULL
                  AND COALESCE(article_count, 0) >= %s
                ORDER BY article_count DESC NULLS LAST, updated_at DESC NULLS LAST
                LIMIT %s
                """,
                (min_articles, limit),
            )
            rows = cur.fetchall()

    by_id: dict[int, dict[str, Any]] = {}
    for r in list(priority_rows) + list(curated) + list(rows):
        title = (r[1] or "").lower()
        if any(x in title for x in ("tupac", "berkshire", "alphabet", "dimon", "gun buyback")):
            continue
        by_id[int(r[0])] = _row_to_dict(r)

    priority_set = set(_PRIORITY_STORYLINE_IDS)
    priority = [by_id[i] for i in _PRIORITY_STORYLINE_IDS if i in by_id]
    rest = sorted(
        (v for k, v in by_id.items() if k not in priority_set),
        key=lambda x: -x["article_count"],
    )
    return (priority + rest)[:limit]


def _write_file(rel: str, content: str, *, force: bool) -> dict[str, Any]:
    if not vault_write_enabled():
        return {"ok": False, "error": "vault write disabled", "path": rel}
    root = vault_root()
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and not force:
        return {"ok": True, "path": rel, "created": False, "skipped": True}
    existing = path.read_text(encoding="utf-8") if path.is_file() else None
    # Preserve Obsidian tags when overwriting with force
    if existing and force:
        from shared.vault_note_contract import split_frontmatter_body

        new_fm, new_body = split_frontmatter_body(content)
        content = merge_write_vault_markdown(
            existing,
            ni_frontmatter=new_fm,
            body=new_body,
            structural_tags=new_fm.get("tags") if isinstance(new_fm.get("tags"), list) else None,
        )
    path.write_text(content, encoding="utf-8")
    return {"ok": True, "path": rel, "created": existing is None, "skipped": False}


def build_entity_note_markdown(
    *,
    domain_key: str,
    entity: dict[str, Any],
    basics: str,
    timeline_bullets: list[str],
) -> str:
    title = entity["name"]
    eid = entity["id"]
    mentions = entity.get("mentions") or 0
    lifecycle = "living" if mentions >= 100 else "seeded"
    tags = structural_tags_for_note(
        note_type="entity",
        domain_key=domain_key,
        entity_type=entity.get("entity_type"),
        extra=["preseed"],
    )
    fm = {
        "ni_domain": domain_key,
        "note_type": "entity",
        "canonical_entity_id": eid,
        "entity_type": entity.get("entity_type") or "",
        "mention_count": mentions,
        "lifecycle": lifecycle,
        "ni_auto": True,
        "tags": tags,
        "preseeded_at": _now_iso(),
        "updated": _now_iso()[:10],
        "status": "ongoing",
    }
    basics_block = basics or entity.get("description") or "_No profile basics in DB yet._"
    timeline = "\n".join(timeline_bullets) if timeline_bullets else "- _No recent articles pulled._"
    body = f"""# {title}

## Basics

{basics_block}

## Current posture

{AUTO_POSTURE_START}
_Preseeded from NI mention volume ({mentions}). Agent will refresh as news arrives._
{AUTO_POSTURE_END}

## Relationships

- _Wikilinks and pair threads fill in as the vault writer runs._

## Timeline

{AUTO_TIMELINE_START}
{timeline}
{AUTO_TIMELINE_END}

## Significance

{AUTO_SIGNIFICANCE_START}
_Significance synthesised when living updates land._
{AUTO_SIGNIFICANCE_END}

## Open questions

- _

## Sources

- domain: `{domain_key}`
- canonical_entity_id: `{eid}`
- mention_count: `{mentions}`
"""
    return _render_frontmatter(fm) + body


def build_storyline_event_note(domain_key: str, sl: dict[str, Any]) -> str:
    sid = sl["id"]
    title = sl["title"]
    tags = structural_tags_for_note(
        note_type="storyline", domain_key=domain_key, extra=["preseed"]
    )
    fm = {
        "ni_domain": domain_key,
        "note_type": "storyline",
        "storyline_id": sid,
        "article_count": sl.get("article_count") or 0,
        "status": sl.get("status") or "",
        "ni_auto": True,
        "tags": tags,
        "preseeded_at": _now_iso(),
    }
    desc = sl.get("description") or ""
    narrative = sl.get("canonical_narrative") or ""
    significance = narrative[:1500] if narrative else (desc[:1200] if desc else "_Thin in DB._")
    body = f"""# {title}

## Summary

{desc or "_No description._"}

## Significance

{AUTO_SIGNIFICANCE_START}
{significance}
{AUTO_SIGNIFICANCE_END}

## Timeline

{AUTO_TIMELINE_START}
- _Expand from chronological events linked to storyline {sid}._
{AUTO_TIMELINE_END}

## Sources

- storyline_id: `{sid}`
- article_count: `{sl.get("article_count")}`
- domain: `{domain_key}`
"""
    return _render_frontmatter(fm) + body


def build_connection_note(
    domain_key: str,
    *,
    id_a: int,
    id_b: int,
    name_a: str,
    name_b: str,
) -> str:
    tags = structural_tags_for_note(
        note_type="connection", domain_key=domain_key, extra=["preseed"]
    )
    fm = {
        "ni_domain": domain_key,
        "note_type": "connection",
        "entity_ids": [id_a, id_b],
        "ni_auto": True,
        "tags": tags,
        "preseeded_at": _now_iso(),
    }
    body = f"""# {name_a} ↔ {name_b}

Pair thread for [[{name_a}]] and [[{name_b}]].

## Arc

{AUTO_SIGNIFICANCE_START}
_Preseeded connection shell — vault writer appends dated evidence from co-anchored storylines._
{AUTO_SIGNIFICANCE_END}

## Timeline

{AUTO_TIMELINE_START}
{AUTO_TIMELINE_END}

## Sources

- entity_a: `{id_a}` ({name_a})
- entity_b: `{id_b}` ({name_b})
- domain: `{domain_key}`
"""
    return _render_frontmatter(fm) + body


def preseed_vault_notes(
    *,
    domain_key: str = "politics",
    entity_limit: int = 35,
    storyline_limit: int = 20,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Seed vault + registry from DB. Returns counts and sample paths.
    """
    entities = fetch_top_entities(domain_key, limit=entity_limit)
    storylines = fetch_major_storylines(domain_key, limit=storyline_limit)
    stats = {
        "entities_considered": len(entities),
        "entities_written": 0,
        "entities_skipped": 0,
        "storylines_written": 0,
        "storylines_skipped": 0,
        "connections_written": 0,
        "registry_upserts": 0,
        "paths": [],
        "dry_run": dry_run,
        "vault_root": str(vault_root()),
    }

    for ent in entities:
        path = entity_vault_rel_path(
            ent["name"],
            domain_key=domain_key,
            entity_type=ent.get("entity_type"),
        )
        basics = fetch_entity_profile_basics(domain_key, ent["id"])
        bullets = fetch_recent_article_bullets(domain_key, ent["id"], limit=8)
        md = build_entity_note_markdown(
            domain_key=domain_key,
            entity=ent,
            basics=basics,
            timeline_bullets=bullets,
        )
        lifecycle = "living" if (ent.get("mentions") or 0) >= 100 else "seeded"
        if dry_run:
            stats["paths"].append(path)
            stats["entities_written"] += 1
            continue
        result = _write_file(path, md, force=force)
        if result.get("skipped"):
            stats["entities_skipped"] += 1
        elif result.get("ok"):
            stats["entities_written"] += 1
            stats["paths"].append(path)
        upsert_vault_note(
            domain_key=domain_key,
            note_type="entity",
            object_id=ent["id"],
            vault_path=path,
            title=ent["name"],
            note_status="note_ready" if result.get("ok") else "note_pending",
            lifecycle=lifecycle,
            mention_count=int(ent.get("mentions") or 0),
            tags=[str(ent.get("entity_type") or "entity"), "preseed"],
            metadata={"preseed": True},
        )
        stats["registry_upserts"] += 1

    for sl in storylines:
        # Prefer storyline path for major hubs
        path = storyline_vault_rel_path(domain_key, sl["id"], sl["title"])
        md = build_storyline_event_note(domain_key, sl)
        if dry_run:
            stats["storylines_written"] += 1
            stats["paths"].append(path)
            continue
        result = _write_file(path, md, force=force)
        if result.get("skipped"):
            stats["storylines_skipped"] += 1
        elif result.get("ok"):
            stats["storylines_written"] += 1
            stats["paths"].append(path)
        upsert_vault_note(
            domain_key=domain_key,
            note_type="storyline",
            object_id=sl["id"],
            vault_path=path,
            title=sl["title"],
            note_status="note_ready" if result.get("ok") else "note_pending",
            lifecycle="seeded",
            mention_count=int(sl.get("article_count") or 0),
            tags=["storyline", "preseed"],
            metadata={"preseed": True, "status": sl.get("status")},
        )
        stats["registry_upserts"] += 1

    # Connection seeds (Trump↔Netanyahu etc.)
    name_by_id = {e["id"]: e["name"] for e in entities}
    for id_a, id_b, fallback_a, fallback_b in _CONNECTION_SEEDS:
        name_a = name_by_id.get(id_a, fallback_a)
        name_b = name_by_id.get(id_b, fallback_b)
        path = connection_vault_rel_path(name_a, name_b)
        md = build_connection_note(
            domain_key, id_a=id_a, id_b=id_b, name_a=name_a, name_b=name_b
        )
        if dry_run:
            stats["connections_written"] += 1
            stats["paths"].append(path)
            continue
        result = _write_file(path, md, force=force)
        if result.get("ok") and not result.get("skipped"):
            stats["connections_written"] += 1
            stats["paths"].append(path)
        elif result.get("skipped"):
            pass
        upsert_vault_note(
            domain_key=domain_key,
            note_type="connection",
            object_id=min(id_a, id_b),
            object_id_secondary=max(id_a, id_b),
            vault_path=path,
            title=f"{name_a} ↔ {name_b}",
            note_status="note_ready",
            lifecycle="seeded",
            tags=["connection", "preseed"],
            metadata={"preseed": True, "entity_ids": [id_a, id_b]},
        )
        stats["registry_upserts"] += 1

    # README index
    if not dry_run:
        index_rel = "40_Reference/entities/_index.md"
        index_path = vault_root() / index_rel
        lines = [
            "# Entity notes (NI preseed)",
            "",
            f"_Generated {_now_iso()}_",
            "",
            f"- Entities written this run: **{stats['entities_written']}** "
            f"(skipped existing: {stats['entities_skipped']})",
            f"- Storyline explainers: **{stats['storylines_written']}**",
            f"- Connection threads: **{stats['connections_written']}**",
            "",
            "## Recent paths",
            "",
        ]
        for p in stats["paths"][:60]:
            lines.append(f"- [[{p.replace('.md', '')}]]" if False else f"- `{p}`")
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return stats
