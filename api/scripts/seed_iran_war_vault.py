#!/usr/bin/env python3
"""Enrich Obsidian vault notes for the Iran-war politics cluster from Postgres.

Grounded only on DB: entity_profiles, article titles+ids, storyline
description/canonical_narrative, public.chronological_events, co-anchored pairs.

Usage (from api/ with .env loaded):
  set -a && source ../.env && set +a
  export NEWS_INTEL_VAULT_WRITE=true NI_VAULT_NOTES_ENABLED=true
  export NEWS_INTEL_VAULT_PATH=/mnt/news-intelligence-vault
  PYTHONPATH=. python scripts/seed_iran_war_vault.py
  PYTHONPATH=. python scripts/seed_iran_war_vault.py --force --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import date, datetime, timezone
from typing import Any

_API_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _API_ROOT not in sys.path:
    sys.path.insert(0, _API_ROOT)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("seed_iran_war_vault")

DOMAIN = "politics"
SCHEMA = "politics"

# Core Iran-war cluster entities (preferred display names for vault paths)
CORE_ENTITIES: list[tuple[int, str]] = [
    (35465, "Donald J. Trump"),
    (490, "Benjamin Netanyahu"),
    (2423, "Iran"),
    (2571, "Israel"),
    (31932, "Ali Khamenei"),
    (18607, "Pete Hegseth"),
    (2110, "Hezbollah"),
    (3752, "Pentagon"),
    (2054, "Hamas"),
]

# Living co-occur entities to branch outward (skip noisy aliases)
BRANCH_ENTITIES: list[tuple[int, str]] = [
    (2646, "JD Vance"),
    (26, "Abbas Araghchi"),
    (2563, "Islamic Revolutionary Guard Corps"),
    (2631, "Jared Kushner"),
    (3024, "Masoud Pezeshkian"),
    (2990, "Marco Rubio"),
    (7559, "Steve Witkoff"),
    (33048, "Joseph Aoun"),
    (5254, "United Nations"),
    (719, "Centcom"),
    (47674, "Mohammad Bagher Ghalibaf"),
]

PRIORITY_STORYLINES = (
    3845,  # Trump war on Iran
    11146,  # Hormuz
    8267,  # Netanyahu Gaza disarmament
    8261,  # Netanyahu Gaza plan
    12248,  # Oman / Iran
    12154,  # Gaza peace plan balance
    11911,  # Kushner Hamas
    11265,  # Hezbollah Lebanon strikes
    9195,  # Lebanon aggression
    12354,  # Oman bomb threat / Ossoff
    11365,  # Houthis / Iran
    5051,  # US borrowing / Iran conflict
)

CONNECTION_PAIRS: list[tuple[int, int, str, str]] = [
    (35465, 490, "Donald J. Trump", "Benjamin Netanyahu"),
    (35465, 2423, "Donald J. Trump", "Iran"),
    (2571, 490, "Israel", "Benjamin Netanyahu"),
    (35465, 18607, "Donald J. Trump", "Pete Hegseth"),
    (2423, 31932, "Iran", "Ali Khamenei"),
    (2571, 2110, "Israel", "Hezbollah"),
    (35465, 3752, "Donald J. Trump", "Pentagon"),
    (490, 2054, "Benjamin Netanyahu", "Hamas"),
    (2423, 2110, "Iran", "Hezbollah"),
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dedupe_bullets(bullets: list[str], *, limit: int = 14) -> list[str]:
    seen_arts: set[str] = set()
    seen_lines: set[str] = set()
    out: list[str] = []
    for b in bullets:
        line = b.strip()
        if not line.startswith("-"):
            line = f"- {line}"
        if line in seen_lines:
            continue
        m = re.search(r"\(article:(\d+)\)", line)
        if m:
            if m.group(1) in seen_arts:
                continue
            seen_arts.add(m.group(1))
        seen_lines.add(line)
        out.append(line)
        if len(out) >= limit:
            break
    return out


def fetch_entity_row(entity_id: int) -> dict[str, Any] | None:
    from shared.database.connection import get_db_connection_context

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT ec.id, ec.canonical_name, ec.entity_type,
                       LEFT(COALESCE(ec.description, ''), 800),
                       COALESCE((
                         SELECT COUNT(*)::int FROM {SCHEMA}.article_entities ae
                         WHERE ae.canonical_entity_id = ec.id
                       ), 0)
                FROM {SCHEMA}.entity_canonical ec
                WHERE ec.id = %s
                """,
                (entity_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    return {
        "id": int(row[0]),
        "canonical_name": row[1],
        "entity_type": row[2],
        "description": (row[3] or "").strip(),
        "mentions": int(row[4] or 0),
    }


def fetch_storyline(sid: int) -> dict[str, Any] | None:
    from shared.database.connection import get_db_connection_context

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, title, COALESCE(article_count, 0), status,
                       LEFT(COALESCE(description, analysis_summary, ''), 1600),
                       LEFT(COALESCE(canonical_narrative, ''), 2500)
                FROM {SCHEMA}.storylines
                WHERE id = %s AND merged_into_id IS NULL
                """,
                (sid,),
            )
            row = cur.fetchone()
    if not row:
        return None
    return {
        "id": int(row[0]),
        "title": row[1] or f"Storyline {row[0]}",
        "article_count": int(row[2] or 0),
        "status": row[3],
        "description": (row[4] or "").strip(),
        "canonical_narrative": (row[5] or "").strip(),
    }


def fetch_storyline_article_bullets(sid: int, *, limit: int = 12) -> list[str]:
    from shared.database.connection import get_db_connection_context

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT a.published_at::date, a.title, a.id
                FROM {SCHEMA}.storyline_articles sa
                JOIN {SCHEMA}.articles a ON a.id = sa.article_id
                WHERE sa.storyline_id = %s
                  AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                ORDER BY a.published_at DESC NULLS LAST
                LIMIT %s
                """,
                (sid, limit),
            )
            rows = cur.fetchall()
    return [
        f"- {pub.isoformat() if pub else 'undated'} — "
        f"{(title or 'Untitled').strip()[:160]} (article:{aid})"
        for pub, title, aid in rows
    ]


def fetch_chrono_bullets_for_storyline(sid: int, *, limit: int = 10) -> list[str]:
    from shared.database.connection import get_db_connection_context

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT event_date::date, title, description, source_article_id, id
                FROM public.chronological_events
                WHERE storyline_id::text = %s
                ORDER BY event_date DESC NULLS LAST, id DESC
                LIMIT %s
                """,
                (str(sid), limit),
            )
            rows = cur.fetchall()
    bullets: list[str] = []
    for pub, title, desc, aid, ce_id in rows:
        day = pub.isoformat() if pub else "undated"
        text = (title or desc or "Event").strip()[:140]
        cite = f" (article:{aid})" if aid else f" (chrono:{ce_id})"
        bullets.append(f"- {day} — {text}{cite}")
    return bullets


def fetch_coanchor_bullets(
    id_a: int, id_b: int, *, limit: int = 10, iran_cluster: bool = True
) -> tuple[int, list[str]]:
    """Return (co_article_count, recent co-mention bullets). Prefer Iran/Gaza/Hormuz titles."""
    from shared.database.connection import get_db_connection_context

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT COUNT(DISTINCT a.id)
                FROM {SCHEMA}.articles a
                JOIN {SCHEMA}.article_entities ae1
                  ON ae1.article_id = a.id AND ae1.canonical_entity_id = %s
                JOIN {SCHEMA}.article_entities ae2
                  ON ae2.article_id = a.id AND ae2.canonical_entity_id = %s
                WHERE (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                """,
                (id_a, id_b),
            )
            total = int(cur.fetchone()[0] or 0)

            if iran_cluster:
                cur.execute(
                    f"""
                    SELECT DISTINCT ON (a.id)
                           a.published_at::date, a.title, a.id
                    FROM {SCHEMA}.articles a
                    JOIN {SCHEMA}.article_entities ae1
                      ON ae1.article_id = a.id AND ae1.canonical_entity_id = %s
                    JOIN {SCHEMA}.article_entities ae2
                      ON ae2.article_id = a.id AND ae2.canonical_entity_id = %s
                    WHERE (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                      AND (
                        a.title ILIKE '%%Iran%%' OR a.title ILIKE '%%Hormuz%%'
                        OR a.title ILIKE '%%Gaza%%' OR a.title ILIKE '%%Hezbollah%%'
                        OR a.title ILIKE '%%Lebanon%%' OR a.title ILIKE '%%Netanyahu%%'
                        OR a.title ILIKE '%%Khamenei%%' OR a.title ILIKE '%%Oman%%'
                        OR a.title ILIKE '%%Hamas%%'
                      )
                    ORDER BY a.id, a.published_at DESC NULLS LAST
                    """,
                    (id_a, id_b),
                )
                cluster_rows = cur.fetchall()
                cluster_rows = sorted(
                    cluster_rows,
                    key=lambda r: (r[0] is not None, r[0] or date.min),
                    reverse=True,
                )[:limit]
            else:
                cluster_rows = []

            if len(cluster_rows) < limit:
                cur.execute(
                    f"""
                    SELECT a.published_at::date, a.title, a.id
                    FROM {SCHEMA}.articles a
                    JOIN {SCHEMA}.article_entities ae1
                      ON ae1.article_id = a.id AND ae1.canonical_entity_id = %s
                    JOIN {SCHEMA}.article_entities ae2
                      ON ae2.article_id = a.id AND ae2.canonical_entity_id = %s
                    WHERE (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                    ORDER BY a.published_at DESC NULLS LAST
                    LIMIT %s
                    """,
                    (id_a, id_b, limit * 2),
                )
                extra = cur.fetchall()
            else:
                extra = []

    bullets = [
        f"- {pub.isoformat() if pub else 'undated'} — "
        f"{(title or 'Untitled').strip()[:160]} (article:{aid})"
        for pub, title, aid in list(cluster_rows) + list(extra)
    ]
    return total, _dedupe_bullets(bullets, limit=limit)


def fetch_related_wikilinks(entity_id: int, names: dict[int, str]) -> list[str]:
    """Wikilinks to other cluster entities that co-occur in priority storylines."""
    from shared.database.connection import get_db_connection_context

    others = [i for i in names if i != entity_id]
    if not others:
        return []
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT ae2.canonical_entity_id, COUNT(DISTINCT ae1.article_id)::int AS n
                FROM {SCHEMA}.storyline_articles sa
                JOIN {SCHEMA}.article_entities ae1
                  ON ae1.article_id = sa.article_id AND ae1.canonical_entity_id = %s
                JOIN {SCHEMA}.article_entities ae2
                  ON ae2.article_id = sa.article_id
                 AND ae2.canonical_entity_id = ANY(%s)
                WHERE sa.storyline_id = ANY(%s)
                GROUP BY ae2.canonical_entity_id
                ORDER BY n DESC
                LIMIT 8
                """,
                (entity_id, others, list(PRIORITY_STORYLINES)),
            )
            rows = cur.fetchall()
    links = []
    for eid, n in rows:
        name = names.get(int(eid))
        if name:
            links.append(f"- [[{name}]] — co-anchored in Iran-war cluster ({n} articles)")
    return links


def _patch_or_write(
    rel: str,
    *,
    new_md: str | None,
    timeline_bullets: list[str],
    significance: str | None,
    posture: str | None,
    force: bool,
    dry_run: bool,
) -> dict[str, Any]:
    """Create note or patch auto fences on existing note (human text sacred)."""
    from services.vault_bridge_service import vault_root, vault_write_enabled
    from services.vault_note_patch import (
        append_timeline_bullet,
        ensure_fences,
        replace_auto_section,
    )

    if not vault_write_enabled() and not dry_run:
        return {"ok": False, "error": "vault write disabled", "path": rel}

    path = vault_root() / rel
    exists = path.is_file()

    if dry_run:
        return {
            "ok": True,
            "path": rel,
            "created": not exists,
            "updated": exists,
            "dry_run": True,
        }

    if not exists or (force and new_md):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_md or "", encoding="utf-8")
        return {"ok": True, "path": rel, "created": not exists, "updated": exists, "mode": "write"}

    # Patch fences only
    body = path.read_text(encoding="utf-8")
    body = ensure_fences(body)
    for bullet in timeline_bullets:
        body = append_timeline_bullet(body, bullet)
    if significance and significance.strip():
        body = replace_auto_section(body, "significance", significance.strip())
    if posture and posture.strip():
        body = replace_auto_section(body, "posture", posture.strip())
    # Fill empty Relationships placeholder with cluster wikilinks if present in new_md
    if new_md and "_Wikilinks and pair threads" in body:
        m = re.search(
            r"## Relationships\n\n(.*?)(?=\n## |\Z)",
            new_md,
            re.DOTALL,
        )
        if m and m.group(1).strip() and "[[" in m.group(1):
            body = re.sub(
                r"## Relationships\n\n.*?(?=\n## |\Z)",
                f"## Relationships\n\n{m.group(1).strip()}\n\n",
                body,
                count=1,
                flags=re.DOTALL,
            )
    path.write_text(body, encoding="utf-8")
    return {"ok": True, "path": rel, "created": False, "updated": True, "mode": "patch"}


def enrich_entity(
    *,
    entity_id: int,
    display_name: str,
    name_by_id: dict[int, str],
    force: bool,
    dry_run: bool,
) -> dict[str, Any]:
    from services.vault_notes_preseed_service import (
        build_entity_note_markdown,
        fetch_entity_profile_basics,
        fetch_recent_article_bullets,
    )
    from services.vault_notes_registry_service import upsert_vault_note
    from shared.vault_note_contract import entity_vault_rel_path

    row = fetch_entity_row(entity_id)
    if not row:
        return {"ok": False, "error": "entity missing", "id": entity_id}

    entity = {
        "id": entity_id,
        "name": display_name,
        "entity_type": row["entity_type"],
        "mentions": row["mentions"],
        "description": row["description"],
    }
    basics = fetch_entity_profile_basics(DOMAIN, entity_id) or row["description"]
    bullets = fetch_recent_article_bullets(DOMAIN, entity_id, limit=10)
    # Prefer cluster-titled articles when available
    cluster_bullets = []
    from shared.database.connection import get_db_connection_context

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT a.published_at::date, a.title, a.id
                FROM {SCHEMA}.article_entities ae
                JOIN {SCHEMA}.articles a ON a.id = ae.article_id
                WHERE ae.canonical_entity_id = %s
                  AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                  AND (
                    a.title ILIKE '%%Iran%%' OR a.title ILIKE '%%Hormuz%%'
                    OR a.title ILIKE '%%Gaza%%' OR a.title ILIKE '%%Hezbollah%%'
                    OR a.title ILIKE '%%Lebanon%%' OR a.title ILIKE '%%Netanyahu%%'
                    OR a.title ILIKE '%%Khamenei%%' OR a.title ILIKE '%%Oman%%'
                    OR a.title ILIKE '%%Hamas%%' OR a.title ILIKE '%%Hegseth%%'
                  )
                ORDER BY a.published_at DESC NULLS LAST
                LIMIT 10
                """,
                (entity_id,),
            )
            for pub, title, aid in cur.fetchall():
                day = pub.isoformat() if pub else "undated"
                cluster_bullets.append(
                    f"- {day} — {(title or 'Untitled').strip()[:160]} (article:{aid})"
                )
    timeline = _dedupe_bullets(cluster_bullets + bullets, limit=12)
    links = fetch_related_wikilinks(entity_id, name_by_id)

    md = build_entity_note_markdown(
        domain_key=DOMAIN,
        entity=entity,
        basics=basics,
        timeline_bullets=timeline,
    )
    if links:
        md = md.replace(
            "- _Wikilinks and pair threads fill in as the vault writer runs._",
            "\n".join(links),
            1,
        )

    mentions = entity["mentions"]
    posture = (
        f"Living entity in Iran-war vault cluster "
        f"({mentions} politics mentions). Timeline prioritises Iran/Gaza/Hormuz-titled articles."
    )
    # Significance: first profile section snippet or description — no invention
    sig_parts = []
    if basics:
        # first bold section line only
        first = basics.split("\n\n")[0].strip()
        if first and not first.startswith("_No profile"):
            sig_parts.append(first[:900])
    if not sig_parts and row["description"]:
        sig_parts.append(row["description"][:900])
    significance = "\n\n".join(sig_parts) if sig_parts else (
        f"_Profile thin in DB; {mentions} mentions tracked._"
    )

    # Inject posture/significance into built md before write
    from services.vault_note_patch import replace_auto_section

    md = replace_auto_section(md, "posture", posture)
    md = replace_auto_section(md, "significance", significance)

    path = entity_vault_rel_path(display_name)
    result = _patch_or_write(
        path,
        new_md=md,
        timeline_bullets=timeline,
        significance=significance,
        posture=posture,
        force=force,
        dry_run=dry_run,
    )
    if not dry_run and result.get("ok"):
        upsert_vault_note(
            domain_key=DOMAIN,
            note_type="entity",
            object_id=entity_id,
            vault_path=path,
            title=display_name,
            note_status="note_ready",
            lifecycle="living" if mentions >= 100 else "seeded",
            mention_count=mentions,
            tags=[str(row["entity_type"] or "entity"), "iran-war-cluster"],
            metadata={"seed": "iran_war", "seeded_at": _now_iso()},
        )
        result["registry"] = True
    result["title"] = display_name
    return result


def enrich_storyline(*, sid: int, force: bool, dry_run: bool) -> dict[str, Any]:
    from services.vault_notes_preseed_service import build_storyline_event_note
    from services.vault_notes_registry_service import upsert_vault_note
    from services.vault_note_patch import replace_auto_section
    from shared.vault_note_contract import storyline_vault_rel_path

    sl = fetch_storyline(sid)
    if not sl:
        return {"ok": False, "error": "storyline missing", "id": sid}

    art_bullets = fetch_storyline_article_bullets(sid, limit=12)
    chrono_bullets = fetch_chrono_bullets_for_storyline(sid, limit=10)
    timeline = _dedupe_bullets(chrono_bullets + art_bullets, limit=14)

    narrative = sl["canonical_narrative"] or ""
    desc = sl["description"] or ""
    significance = (narrative[:1800] if narrative else desc[:1400]) or (
        f"_Thin in DB for storyline {sid}._"
    )

    md = build_storyline_event_note(DOMAIN, sl)
    md = replace_auto_section(md, "significance", significance)
    md = replace_auto_section(md, "timeline", "\n".join(timeline) if timeline else "- _No articles._")

    path = storyline_vault_rel_path(DOMAIN, sid, sl["title"])
    result = _patch_or_write(
        path,
        new_md=md,
        timeline_bullets=timeline,
        significance=significance,
        posture=None,
        force=force,
        dry_run=dry_run,
    )
    if not dry_run and result.get("ok"):
        upsert_vault_note(
            domain_key=DOMAIN,
            note_type="storyline",
            object_id=sid,
            vault_path=path,
            title=sl["title"],
            note_status="note_ready",
            lifecycle="seeded",
            mention_count=int(sl["article_count"] or 0),
            tags=["storyline", "iran-war-cluster"],
            metadata={"seed": "iran_war", "status": sl.get("status"), "seeded_at": _now_iso()},
        )
        result["registry"] = True
    result["title"] = sl["title"]
    return result


def enrich_connection(
    *,
    id_a: int,
    id_b: int,
    name_a: str,
    name_b: str,
    force: bool,
    dry_run: bool,
) -> dict[str, Any]:
    from services.vault_notes_preseed_service import build_connection_note
    from services.vault_notes_registry_service import upsert_vault_note
    from services.vault_note_patch import replace_auto_section
    from shared.vault_note_contract import connection_vault_rel_path

    total, bullets = fetch_coanchor_bullets(id_a, id_b, limit=10)
    significance = (
        f"Co-anchored in {total} politics articles (DB count). "
        f"Timeline below prefers Iran/Gaza/Hormuz/Lebanon-titled co-mentions when available."
    )
    md = build_connection_note(
        DOMAIN, id_a=id_a, id_b=id_b, name_a=name_a, name_b=name_b
    )
    md = replace_auto_section(md, "significance", significance)
    md = replace_auto_section(
        md, "timeline", "\n".join(bullets) if bullets else "- _No co-mention articles pulled._"
    )

    path = connection_vault_rel_path(name_a, name_b)
    result = _patch_or_write(
        path,
        new_md=md,
        timeline_bullets=bullets,
        significance=significance,
        posture=None,
        force=force,
        dry_run=dry_run,
    )
    if not dry_run and result.get("ok"):
        upsert_vault_note(
            domain_key=DOMAIN,
            note_type="connection",
            object_id=min(id_a, id_b),
            object_id_secondary=max(id_a, id_b),
            vault_path=path,
            title=f"{name_a} ↔ {name_b}",
            note_status="note_ready",
            lifecycle="seeded",
            mention_count=total,
            tags=["connection", "iran-war-cluster"],
            metadata={
                "seed": "iran_war",
                "entity_ids": [id_a, id_b],
                "co_articles": total,
                "seeded_at": _now_iso(),
            },
        )
        result["registry"] = True
    result["title"] = f"{name_a} ↔ {name_b}"
    result["co_articles"] = total
    return result


def write_cluster_hub(*, force: bool, dry_run: bool, paths: list[str]) -> dict[str, Any]:
    """Thin CLI wrapper — general vault cluster hub service owns the hub."""
    from services.vault_cluster_hub_service import bootstrap_iran_war_hub

    result = bootstrap_iran_war_hub(force=force, dry_run=dry_run)
    if result.get("ok") and result.get("path") and result["path"] not in paths:
        paths.append(result["path"])
    result["registry"] = bool(result.get("ok") and not dry_run)
    return result


def run(*, force: bool, dry_run: bool, skip_branch: bool) -> dict[str, Any]:
    os.environ.setdefault("NEWS_INTEL_VAULT_PATH", "/mnt/news-intelligence-vault")
    os.environ["NEWS_INTEL_VAULT_WRITE"] = "true"
    os.environ["NI_VAULT_NOTES_ENABLED"] = "true"

    entities = list(CORE_ENTITIES)
    if not skip_branch:
        entities.extend(BRANCH_ENTITIES)

    name_by_id = {eid: name for eid, name in entities}
    # Ensure core names present for wikilinks even if branch skipped
    for eid, name in CORE_ENTITIES:
        name_by_id[eid] = name

    stats: dict[str, Any] = {
        "entities_written": 0,
        "entities_updated": 0,
        "entities_failed": 0,
        "storylines_written": 0,
        "storylines_updated": 0,
        "connections_written": 0,
        "connections_updated": 0,
        "registry_upserts": 0,
        "paths": [],
        "dry_run": dry_run,
        "force": force,
    }

    for eid, name in entities:
        try:
            r = enrich_entity(
                entity_id=eid,
                display_name=name,
                name_by_id=name_by_id,
                force=force,
                dry_run=dry_run,
            )
            if not r.get("ok"):
                stats["entities_failed"] += 1
                logger.warning("entity %s failed: %s", eid, r)
                continue
            if r.get("created"):
                stats["entities_written"] += 1
            else:
                stats["entities_updated"] += 1
            if r.get("registry"):
                stats["registry_upserts"] += 1
            stats["paths"].append(r["path"])
            logger.info("entity %s → %s (%s)", name, r["path"], r.get("mode") or "dry")
        except Exception as e:
            stats["entities_failed"] += 1
            logger.exception("entity %s error: %s", eid, e)

    for sid in PRIORITY_STORYLINES:
        try:
            r = enrich_storyline(sid=sid, force=force, dry_run=dry_run)
            if not r.get("ok"):
                logger.warning("storyline %s failed: %s", sid, r)
                continue
            if r.get("created"):
                stats["storylines_written"] += 1
            else:
                stats["storylines_updated"] += 1
            if r.get("registry"):
                stats["registry_upserts"] += 1
            stats["paths"].append(r["path"])
            logger.info("storyline %s → %s", sid, r["path"])
        except Exception as e:
            logger.exception("storyline %s error: %s", sid, e)

    for id_a, id_b, na, nb in CONNECTION_PAIRS:
        try:
            r = enrich_connection(
                id_a=id_a, id_b=id_b, name_a=na, name_b=nb, force=force, dry_run=dry_run
            )
            if not r.get("ok"):
                logger.warning("connection %s↔%s failed: %s", na, nb, r)
                continue
            if r.get("created"):
                stats["connections_written"] += 1
            else:
                stats["connections_updated"] += 1
            if r.get("registry"):
                stats["registry_upserts"] += 1
            stats["paths"].append(r["path"])
            logger.info("connection %s ↔ %s (co=%s) → %s", na, nb, r.get("co_articles"), r["path"])
        except Exception as e:
            logger.exception("connection error: %s", e)

    try:
        hub = write_cluster_hub(force=force, dry_run=dry_run, paths=stats["paths"])
        if hub.get("ok") and hub.get("path") and hub["path"] not in stats["paths"]:
            stats["paths"].append(hub["path"])
        if hub.get("registry") or (hub.get("ok") and not dry_run):
            stats["registry_upserts"] += 1
    except Exception as e:
        logger.exception("hub error: %s", e)

    stats["paths_unique"] = len(set(stats["paths"]))
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rewrite thin auto notes fully (still DB-grounded)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--skip-branch",
        action="store_true",
        help="Only core entities (no Vance/Kushner/IRGC/…)",
    )
    args = parser.parse_args()
    stats = run(force=args.force, dry_run=args.dry_run, skip_branch=args.skip_branch)
    print(json.dumps(stats, indent=2, default=str))
    return 0 if stats.get("paths") else 1


if __name__ == "__main__":
    raise SystemExit(main())
