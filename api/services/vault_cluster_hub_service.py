"""
Vault cluster hub writer — Obsidian index pages for topic clusters.

Hubs index member storylines / entities / timeline. They do NOT merge
storyline_articles membership bags.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timezone
from typing import Any

from shared.database.connection import get_db_connection_context
from shared.domain_registry import resolve_domain_schema
from shared.vault_note_contract import (
    AUTO_BRIEF_END,
    AUTO_BRIEF_START,
    AUTO_SIGNIFICANCE_END,
    AUTO_SIGNIFICANCE_START,
    AUTO_TIMELINE_END,
    AUTO_TIMELINE_START,
    cluster_object_id,
    cluster_vault_rel_path,
    slugify_entity_name,
)

logger = logging.getLogger(__name__)

# Legacy Iran hub path kept for bootstrap continuity
LEGACY_IRAN_WAR_PATH = "40_Reference/entities/iran_war.md"
IRAN_WAR_CLUSTER_KEY = "iran_war"
IRAN_WAR_SEED_ENTITY_IDS = (2423, 2538, 2571, 490, 2110, 2054, 68572, 31932)
IRAN_WAR_PRIORITY_STORYLINES = (
    3845,
    11146,
    8267,
    8261,
    12248,
    12154,
    11911,
    11265,
    9195,
    12354,
    11365,
    5051,
)


def vault_cluster_hubs_enabled() -> bool:
    try:
        from config.feature_registry import is_feature_enabled

        if is_feature_enabled("vault_cluster_hubs", default=True):
            return True
    except Exception:
        pass
    from config.runtime import env_bool

    return env_bool("NI_VAULT_CLUSTER_HUBS_ENABLED", True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dedupe_bullets(bullets: list[str], *, limit: int = 16) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for b in bullets:
        key = re.sub(r"\s+", " ", b).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(b)
        if len(out) >= limit:
            break
    return out


def list_cluster_hubs(
    *,
    domain_key: str | None = None,
    limit: int = 40,
) -> list[dict[str, Any]]:
    """Active hub registry rows (cluster note_type or metadata.hub)."""
    sql = """
        SELECT id, domain_key, note_type, object_id, vault_path, title, tags,
               metadata, note_updated_at, updated_at
        FROM intelligence.vault_notes
        WHERE (
            note_type = 'cluster'
            OR COALESCE(metadata->>'hub', '') = 'true'
        )
          AND note_status IN ('note_ready', 'living', 'seeded', 'note_pending')
    """
    params: list[Any] = []
    if domain_key:
        sql += " AND domain_key = %s"
        params.append(domain_key)
    sql += " ORDER BY COALESCE(note_updated_at, updated_at) DESC NULLS LAST LIMIT %s"
    params.append(int(limit))
    out: list[dict[str, Any]] = []
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                for row in cur.fetchall() or []:
                    meta = row[7] if isinstance(row[7], dict) else {}
                    if isinstance(row[7], str):
                        try:
                            meta = json.loads(row[7])
                        except Exception:
                            meta = {}
                    out.append(
                        {
                            "id": int(row[0]),
                            "domain_key": row[1],
                            "note_type": row[2],
                            "object_id": int(row[3]),
                            "vault_path": row[4],
                            "title": row[5] or "",
                            "tags": list(row[6] or []),
                            "metadata": meta,
                            "cluster_key": (meta or {}).get("cluster_key")
                            or slugify_entity_name(row[5] or f"hub-{row[0]}"),
                            "member_storyline_ids": list(
                                (meta or {}).get("member_storyline_ids") or []
                            ),
                            "seed_entity_ids": list(
                                (meta or {}).get("seed_entity_ids") or []
                            ),
                            "current_brief": (meta or {}).get("current_brief") or None,
                            "brief_updated_at": (meta or {}).get("brief_updated_at")
                            or None,
                            "brief_fingerprint": (meta or {}).get("brief_fingerprint")
                            or None,
                            "updated_at": (row[8] or row[9]).isoformat()
                            if (row[8] or row[9])
                            else None,
                            "href": f"/hubs/{(meta or {}).get('cluster_key') or row[0]}",
                        }
                    )
    except Exception as e:
        logger.warning("list_cluster_hubs: %s", e)
    return out


def get_cluster_hub(
    *,
    domain_key: str | None = None,
    cluster_key: str | None = None,
    hub_id: int | None = None,
    slug: str | None = None,
) -> dict[str, Any] | None:
    key = (cluster_key or slug or "").strip()
    hubs = list_cluster_hubs(domain_key=domain_key, limit=200)
    if hub_id is not None:
        for h in hubs:
            if int(h["id"]) == int(hub_id):
                return h
    if key:
        key_l = key.lower()
        for h in hubs:
            if str(h.get("cluster_key") or "").lower() == key_l:
                return h
            if str(h.get("id")) == key:
                return h
            path = str(h.get("vault_path") or "")
            if path.endswith(f"/{key_l}.md") or path.endswith(f"/{key}.md"):
                return h
    return None


def _hub_storyline_rows(
    cur,
    schema: str,
    storyline_ids: list[int],
) -> list[tuple[int, str, int]]:
    if not storyline_ids:
        return []
    cur.execute(
        f"""
        SELECT id, COALESCE(title, ''), COALESCE(article_count, 0)::int
        FROM {schema}.storylines
        WHERE id = ANY(%s) AND status = 'active'
        ORDER BY COALESCE(updated_at, created_at) DESC NULLS LAST
        """,
        (list(storyline_ids),),
    )
    return [(int(r[0]), r[1] or "", int(r[2] or 0)) for r in (cur.fetchall() or [])]


def _timeline_bullets(
    cur,
    schema: str,
    storyline_ids: list[int],
    *,
    limit: int = 16,
) -> list[str]:
    if not storyline_ids:
        return []
    cur.execute(
        f"""
        SELECT DISTINCT ON (a.id)
            a.published_at::date, a.title, a.id, sa.storyline_id
        FROM {schema}.storyline_articles sa
        JOIN {schema}.articles a ON a.id = sa.article_id
        WHERE sa.storyline_id = ANY(%s)
          AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
        ORDER BY a.id, a.published_at DESC NULLS LAST
        """,
        (list(storyline_ids),),
    )
    rows = list(cur.fetchall() or [])
    rows.sort(key=lambda r: (r[0] is not None, r[0] or date.min), reverse=True)
    bullets: list[str] = []
    for pub, title, aid, sid in rows[: limit * 2]:
        day = pub.isoformat() if pub else "undated"
        bullets.append(
            f"- {day} — {(title or 'Untitled').strip()[:140]} "
            f"(article:{aid}, storyline:{sid})"
        )
    return _dedupe_bullets(bullets, limit=limit)


def _entity_wikilinks(cur, schema: str, entity_ids: list[int]) -> list[str]:
    if not entity_ids:
        return []
    cur.execute(
        f"""
        SELECT id, canonical_name
        FROM {schema}.entity_canonical
        WHERE id = ANY(%s)
        """,
        (list(entity_ids),),
    )
    names = [r[1] for r in (cur.fetchall() or []) if r[1]]
    return [f"[[{n}]]" for n in names[:12]]


def write_cluster_hub(
    *,
    domain_key: str,
    cluster_key: str,
    title: str,
    member_storyline_ids: list[int],
    seed_entity_ids: list[int] | None = None,
    significance: str | None = None,
    vault_path: str | None = None,
    tags: list[str] | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Write/refresh one Obsidian cluster hub + registry row."""
    from services.vault_bridge_service import _render_frontmatter, vault_root
    from services.vault_notes_registry_service import upsert_vault_note
    from services.vault_quality_gates import is_junk_title, sanitize_vault_prose

    title = sanitize_vault_prose(title, max_length=200)
    if is_junk_title(title):
        return {
            "ok": False,
            "skipped": True,
            "error": "junk_title",
            "title": title,
            "cluster_key": cluster_key,
        }

    key = slugify_entity_name(cluster_key)
    schema = resolve_domain_schema(domain_key)
    rel = vault_path or cluster_vault_rel_path(key)
    # Keep legacy iran path if migrating that key without explicit path
    if key == IRAN_WAR_CLUSTER_KEY and vault_path is None:
        rel = LEGACY_IRAN_WAR_PATH
    oid = cluster_object_id(key)
    members = [int(x) for x in member_storyline_ids if int(x) > 0]
    seeds = [int(x) for x in (seed_entity_ids or []) if int(x) > 0]
    hub_tags = list(
        dict.fromkeys(
            (tags or [])
            + ["cluster", f"cluster/{key}", f"domain/{domain_key}"]
        )
    )

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            sl_rows = _hub_storyline_rows(cur, schema, members)
            bullets = _timeline_bullets(cur, schema, members)
            wikilinks = _entity_wikilinks(cur, schema, seeds)

    sl_links = [
        f"- storyline `{sid}` — {title_s[:100]} ({acount} arts)"
        for sid, title_s, acount in sl_rows
    ]
    sig = (
        significance
        or f"Cluster hub for {title}: indexes related episodes by shared entities/tags/events."
    )
    related = " · ".join(wikilinks) if wikilinks else "- _Seed entities pending._"

    fm = {
        "ni_domain": domain_key,
        "note_type": "cluster",
        "cluster_key": key,
        "topic": key,
        "hub": True,
        "ni_auto": True,
        "object_id": oid,
        "preseeded_at": _now_iso(),
        "updated": _now_iso()[:10],
        "status": "ongoing",
        "lifecycle": "living",
    }
    body = f"""# {title}

## Current brief

{AUTO_BRIEF_START}
_Brief updates when the situation moves._
{AUTO_BRIEF_END}

## Basics

Situation index for related episodes. Entity and storyline pages hold detail;
this hub only lists DB-backed members (no merged membership bag).

## Related entities

{related}

## Hub storylines

{chr(10).join(sl_links) if sl_links else '- _None._'}

## Significance

{AUTO_SIGNIFICANCE_START}
{sig}
{AUTO_SIGNIFICANCE_END}

## Timeline

{AUTO_TIMELINE_START}
{chr(10).join(bullets) if bullets else '- _No articles._'}
{AUTO_TIMELINE_END}

## Sources

- cluster_key: `{key}`
- domain: `{domain_key}`
- members: {len(members)}
"""
    md = _render_frontmatter(fm) + body
    meta = {
        "hub": True,
        "cluster_key": key,
        "member_storyline_ids": members,
        "seed_entity_ids": seeds,
        "domain_key": domain_key,
        "scorer": "vault_cluster_hub_v1",
    }

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "path": rel,
            "cluster_key": key,
            "member_count": len(members),
            "timeline_n": len(bullets),
        }

    try:
        root = vault_root()
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file() and not force:
            # Patch auto fences when present
            from services.vault_note_patch import patch_auto_sections

            existing = path.read_text(encoding="utf-8")
            patched = patch_auto_sections(
                existing,
                timeline_bullets=bullets,
                significance=sig,
            )
            path.write_text(patched or md, encoding="utf-8")
        else:
            path.write_text(md, encoding="utf-8")
    except Exception as e:
        logger.warning("write_cluster_hub vault write %s: %s", rel, e)
        return {"ok": False, "error": str(e), "path": rel}

    upsert_vault_note(
        domain_key=domain_key,
        note_type="cluster",
        object_id=oid,
        vault_path=rel,
        title=title,
        note_status="note_ready",
        lifecycle="living",
        tags=hub_tags,
        metadata=meta,
        tags_source="ni_structural",
    )

    try:
        from services.vault_tag_link_sync_service import sync_vault_file

        sync_vault_file(rel)
    except Exception as e:
        logger.debug("sync_vault_file %s: %s", rel, e)

    return {
        "ok": True,
        "path": rel,
        "cluster_key": key,
        "object_id": oid,
        "member_count": len(members),
        "timeline_n": len(bullets),
        "href": f"/hubs/{key}",
    }


def refresh_hub_from_registry(hub: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    meta = hub.get("metadata") or {}
    return write_cluster_hub(
        domain_key=str(hub.get("domain_key") or "politics"),
        cluster_key=str(meta.get("cluster_key") or hub.get("cluster_key") or hub["id"]),
        title=str(hub.get("title") or meta.get("cluster_key") or "Cluster hub"),
        member_storyline_ids=list(meta.get("member_storyline_ids") or hub.get("member_storyline_ids") or []),
        seed_entity_ids=list(meta.get("seed_entity_ids") or hub.get("seed_entity_ids") or []),
        vault_path=hub.get("vault_path"),
        tags=list(hub.get("tags") or []),
        force=force,
    )


def refresh_all_cluster_hubs(
    *,
    domain_key: str | None = None,
    force: bool = False,
    limit: int = 50,
) -> dict[str, Any]:
    if not vault_cluster_hubs_enabled():
        return {"ok": False, "skipped": True, "reason": "disabled"}
    hubs = list_cluster_hubs(domain_key=domain_key, limit=limit)
    stats = {"ok": True, "refreshed": 0, "failed": 0, "hubs": []}
    for h in hubs:
        try:
            r = refresh_hub_from_registry(h, force=force)
            if r.get("ok"):
                stats["refreshed"] += 1
            else:
                stats["failed"] += 1
            stats["hubs"].append(r)
        except Exception as e:
            stats["failed"] += 1
            logger.warning("refresh hub %s: %s", h.get("id"), e)
    return stats


def bootstrap_iran_war_hub(*, force: bool = False, dry_run: bool = False) -> dict[str, Any]:
    """Migrate / seed the Iran war hub into the general cluster system."""
    return write_cluster_hub(
        domain_key="politics",
        cluster_key=IRAN_WAR_CLUSTER_KEY,
        title="Iran war (situation)",
        member_storyline_ids=list(IRAN_WAR_PRIORITY_STORYLINES),
        seed_entity_ids=list(IRAN_WAR_SEED_ENTITY_IDS),
        significance=(
            "Cluster seed from politics storylines matching Iran/Hormuz/Gaza/"
            "Netanyahu/Hezbollah/Lebanon plus curated hubs."
        ),
        vault_path=LEGACY_IRAN_WAR_PATH,
        tags=["cluster", "iran-war-cluster"],
        force=force,
        dry_run=dry_run,
    )


def storyline_ids_indexed_by_hubs(domain_key: str) -> dict[int, list[dict[str, Any]]]:
    """Map storyline_id → list of hub stubs that index it (for feed demotion)."""
    out: dict[int, list[dict[str, Any]]] = {}
    for h in list_cluster_hubs(domain_key=domain_key, limit=100):
        stub = {
            "id": h["id"],
            "cluster_key": h["cluster_key"],
            "title": h["title"],
            "href": h["href"],
        }
        for sid in h.get("member_storyline_ids") or []:
            try:
                sid_i = int(sid)
            except (TypeError, ValueError):
                continue
            out.setdefault(sid_i, []).append(stub)
    return out
