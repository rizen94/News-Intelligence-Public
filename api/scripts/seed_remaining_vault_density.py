#!/usr/bin/env python3
"""Remaining vault density: promote distinct-arc Situations, living entities,
package Related-situations backfill, finance clipping body sync.

Usage:
  set -a && source ../.env && set +a
  export NEWS_INTEL_VAULT_WRITE=true NI_VAULT_NOTES_ENABLED=true
  export NEWS_INTEL_VAULT_PATH=/mnt/news-intelligence-vault
  PYTHONPATH=. python scripts/seed_remaining_vault_density.py --force --sync
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_API_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _API_ROOT not in sys.path:
    sys.path.insert(0, _API_ROOT)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("seed_remaining_vault_density")

# --- Situation hubs (promote distinct arcs) ---
HUBS: list[dict[str, Any]] = [
    {
        "domain_key": "politics",
        "cluster_key": "farage_reform_boats",
        "title": "Farage / Reform — small boats & gifts (situation)",
        "members": (5473, 10605, 5703),
        "seeds": (28441, 35465),  # Farage, Trump
        "themes": ["Farage", "Reform", "small boat", "Clacton", "Channel"],
        "significance": (
            "UK Reform / Farage track: small-boats navy pledge and gift scrutiny. "
            "Cross-link [[donald_j_trump]] and [[us_institutions]] for transatlantic "
            "populist shelf — not a kitchen-sink UK politics bag."
        ),
        "tags": ["theme/farage", "theme/uk-politics", "priority/high"],
        "also": "See also [[donald_j_trump]] · [[us_institutions]].",
        "why": (
            "WHY IT MATTERS: Distinct UK arc already storyline-seeded; needs a "
            "Situation home so morning prime can track boats/gifts without Iran magnets."
        ),
        "watch": "WATCH: navy/boats language; gift/donation probes; Farage–Trump proximity.",
    },
    {
        "domain_key": "politics",
        "cluster_key": "venezuela_boe_gold",
        "title": "Venezuela / BoE gold (situation)",
        "members": (10523,),
        "seeds": (5503, 5504),  # Venezuela org/subject — filtered later
        "themes": ["Venezuela", "Bank of England", "gold reserve", "BoE gold"],
        "significance": (
            "Sovereign gold / BoE custody dispute. Bridges politics Venezuela "
            "titles to finance [[resource_movements]] / gold."
        ),
        "tags": ["theme/venezuela", "theme/gold", "priority/high"],
        "also": "See also [[resource_movements]] · [[market_trends]] · [[gold]].",
        "why": (
            "WHY IT MATTERS: Rare sovereign-asset custody story linking geopolitics "
            "to gold — keep separate from generic Latin America bags."
        ),
        "watch": "WATCH: BoE court/custody language; Venezuela recognition fights; gold price overlays.",
    },
    {
        "domain_key": "politics",
        "cluster_key": "ai_governance",
        "title": "AI governance — rogue models & labs (situation)",
        "members": (6649, 6697),
        "seeds": (3633,),  # OpenAI; Anthropic resolved at runtime
        "themes": ["OpenAI", "Anthropic", "rogue", "AI model", "cybersecurity test", "watchdog"],
        "significance": (
            "AI lab governance / UK watchdog rogue-model tests. Politics-hosted "
            "until AI RSS is dense; cross-link research lane and [[china_trade_tech]] "
            "for chips only when evidence overlaps."
        ),
        "tags": ["theme/ai-governance", "theme/openai", "priority/high"],
        "also": "See also [[china_trade_tech]] · OpenAI entity note.",
        "why": (
            "WHY IT MATTERS: Distinct-arc storylines already exist; Situation shelf "
            "keeps AI safety/governance out of news kitchen-sink clusters."
        ),
        "watch": "WATCH: watchdog/regulator language; lab safety evals; UK/US policy bills.",
    },
]

# High-hit entities → living notes (domain, id, display_name)
ENTITY_LIVING: list[tuple[str, int, str]] = [
    ("finance", 98, "Federal Reserve"),
    ("finance", 1996, "oil"),
    ("finance", 4411, "gold"),
    ("finance", 6856, "OPEC+"),
    ("finance", 230, "Strait of Hormuz"),
    ("finance", 2064, "International Energy Agency"),
    ("politics", 654591, "State Department"),
    ("politics", 3752, "Pentagon"),
    ("politics", 584200, "Supreme Court"),
    ("politics", 573976, "White House"),
    ("politics", 28441, "Nigel Farage"),
    ("politics", 3633, "OpenAI"),
    ("politics", 5503, "Venezuela"),
]

MIN_HITS_LIVING = 20

PACKAGE_RULES: list[tuple[re.Pattern[str], list[str]]] = [
    (
        re.compile(r"supply|oil|hormuz|diesel|gold|metal|commodity|energy|tariff", re.I),
        [
            "[[resource_movements|Resource movements]]",
            "[[market_trends|Market trends]]",
            "[[china_trade_tech|China–trade–tech]]",
        ],
    ),
    (
        re.compile(r"fed|cpi|inflation|yield|treasury|bond", re.I),
        [
            "[[market_trends|Market trends]]",
            "[[resource_movements|Resource movements]]",
        ],
    ),
    (
        re.compile(r"ukraine|zelensk|putin|nato", re.I),
        ["[[russia_ukraine|Russia / Ukraine]]", "[[us_institutions|US institutions]]"],
    ),
    (
        re.compile(r"iran|gaza|netanyahu|hezbollah", re.I),
        ["[[iran_war|Iran war]]", "[[inflation_iran_war|Inflation / Iran war]]"],
    ),
    (
        re.compile(r"openai|anthropic|ai model|rogue", re.I),
        ["[[ai_governance|AI governance]]"],
    ),
    (
        re.compile(r"farage|reform uk|small boat", re.I),
        ["[[farage_reform_boats|Farage / Reform]]"],
    ),
    (
        re.compile(r"white house|attorney general|supreme court|pentagon", re.I),
        ["[[us_institutions|US institutions]]"],
    ),
    (
        re.compile(r"climate|carbon|wildfire|epa", re.I),
        ["[[climate_resource_policy|Climate–resource policy]]"],
    ),
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strip_nuls(text: str | None) -> str:
    return (text or "").replace("\x00", "")


def _dedupe(bullets: list[str], *, limit: int = 12) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for b in bullets:
        k = re.sub(r"\s+", " ", b).strip().lower()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(b)
        if len(out) >= limit:
            break
    return out


def existing_ids(schema: str, table: str, ids: list[int]) -> list[int]:
    from shared.database.connection import get_db_connection_context

    if not ids:
        return []
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT id FROM {schema}.{table} WHERE id = ANY(%s)",
                (list(ids),),
            )
            found = {int(r[0]) for r in (cur.fetchall() or [])}
    return [i for i in ids if i in found]


def fetch_theme(schema: str, patterns: list[str], *, days: int = 90, limit: int = 10) -> list[str]:
    from shared.database.connection import get_db_connection_context

    like = " OR ".join(["a.title ILIKE %s"] * len(patterns))
    params: list[Any] = [days] + [f"%{p}%" for p in patterns] + [limit]
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT a.published_at::date, a.title, a.id
                FROM {schema}.articles a
                WHERE a.published_at >= NOW() - make_interval(days => %s)
                  AND ({like})
                  AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                ORDER BY a.published_at DESC NULLS LAST
                LIMIT %s
                """,
                tuple(params),
            )
            rows = cur.fetchall() or []
    return [
        f"- {pub.isoformat() if pub else 'undated'} — "
        f"{(title or 'Untitled').strip()[:150]} (article:{aid})"
        for pub, title, aid in rows
    ]


def resolve_anthropic_id() -> int | None:
    from shared.database.connection import get_db_connection_context

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM politics.entity_canonical
                WHERE canonical_name ILIKE 'Anthropic' ORDER BY id LIMIT 1
                """
            )
            row = cur.fetchone()
    return int(row[0]) if row else None


def persist_hub_brief(
    *,
    domain_key: str,
    cluster_key: str,
    path: str,
    title: str,
    object_id: int,
    brief: str,
    members: list[int],
    seeds: list[int],
    tags: list[str],
    force: bool,
    dry_run: bool,
) -> dict[str, Any]:
    from services.vault_bridge_service import vault_root
    from services.vault_note_patch import patch_auto_sections
    from services.vault_notes_registry_service import upsert_vault_note

    brief_clean = _strip_nuls(brief)[:3500]
    parts = [p.strip() for p in brief_clean.split("\n\n") if p.strip()]
    summary = _strip_nuls("\n\n".join(parts[:3]))[:900]
    meta = {
        "hub": True,
        "cluster_key": cluster_key,
        "member_storyline_ids": members,
        "seed_entity_ids": seeds,
        "domain_key": domain_key,
        "current_brief": brief_clean[:1200],
        "brief_updated_at": _now_iso(),
        "brief_fingerprint": f"seed_density_{cluster_key}_{_now_iso()[:10]}",
        "brief_source": "seed_remaining_vault_density",
        "scorer": "vault_cluster_hub_v1",
    }
    if dry_run:
        return {"ok": True, "dry_run": True, "cluster_key": cluster_key}

    root = vault_root()
    fp = root / path
    body = ""
    if fp.is_file():
        existing = fp.read_text(encoding="utf-8")
        if re.search(r"brief_locked:\s*(true|1|yes)", existing, re.I):
            return {"ok": True, "skipped": True, "reason": "brief_locked"}
        patched = patch_auto_sections(existing, brief=brief_clean[:1200])
        if force or "<!-- ni:auto:brief -->" in existing:
            fp.write_text(_strip_nuls(patched or existing), encoding="utf-8")
        body = _strip_nuls(fp.read_text(encoding="utf-8"))

    upsert_vault_note(
        domain_key=domain_key,
        note_type="cluster",
        object_id=object_id,
        vault_path=path,
        title=title,
        note_status="note_ready",
        lifecycle="living",
        tags=tags,
        metadata=meta,
        tags_source="ni_structural",
        body_md=body or None,
        summary_md=summary or None,
    )
    return {"ok": True, "cluster_key": cluster_key, "path": path, "members": len(members)}


def seed_hubs(*, force: bool, dry_run: bool) -> dict[str, Any]:
    from services.vault_cluster_hub_service import write_cluster_hub
    from shared.vault_note_contract import cluster_object_id, cluster_vault_rel_path

    out: dict[str, Any] = {}
    for hub in HUBS:
        domain = hub["domain_key"]
        members = existing_ids(domain, "storylines", list(hub["members"]))
        seeds = existing_ids(domain, "entity_canonical", list(hub["seeds"]))
        if hub["cluster_key"] == "ai_governance":
            aid = resolve_anthropic_id()
            if aid and aid not in seeds:
                seeds.append(aid)
        tl = _dedupe(fetch_theme(domain, list(hub["themes"]), days=120, limit=12))
        now = (
            "NOW: " + "; ".join(
                re.sub(r"^- \S+ — ", "", t).split(" (article:")[0] for t in tl[:3]
            )
            + "."
            if tl
            else f"NOW: Situation seeded from curated storylines {members}."
        )
        brief = (
            f"**CURRENT BRIEF: {hub['title'].split('(')[0].strip()}**\n\n"
            f"{now}\n\n{hub['why']}\n\n{hub['watch']}\n\n"
            f"**Corpus timeline:**\n"
            + ("\n".join(tl[:10]) if tl else "- _(thin corpus — members indexed)_")
            + f"\n\n{hub['also']}"
        )
        tags = ["cluster", f"domain/{domain}", "priority/high"] + list(hub["tags"])
        wr = write_cluster_hub(
            domain_key=domain,
            cluster_key=hub["cluster_key"],
            title=hub["title"],
            member_storyline_ids=members,
            seed_entity_ids=seeds,
            significance=hub["significance"],
            tags=tags,
            force=force,
            dry_run=dry_run,
        )
        path = str(wr.get("vault_path") or cluster_vault_rel_path(hub["cluster_key"]))
        oid = int(wr.get("object_id") or cluster_object_id(hub["cluster_key"]))
        br = persist_hub_brief(
            domain_key=domain,
            cluster_key=hub["cluster_key"],
            path=path,
            title=hub["title"],
            object_id=oid,
            brief=brief,
            members=members,
            seeds=seeds,
            tags=tags,
            force=force,
            dry_run=dry_run,
        )
        out[hub["cluster_key"]] = {"write": wr, "brief": br, "path": path}
    return out


def entity_hits(domain: str, eid: int) -> int:
    from shared.database.connection import get_db_connection_context
    from shared.domain_registry import resolve_domain_schema

    schema = resolve_domain_schema(domain)
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT COUNT(*)::int FROM {schema}.article_entities
                WHERE canonical_entity_id = %s
                """,
                (eid,),
            )
            return int((cur.fetchone() or [0])[0] or 0)


def seed_entities(*, force: bool, dry_run: bool) -> list[dict[str, Any]]:
    from services.vault_bridge_service import vault_root
    from services.vault_notes_preseed_service import (
        _write_file,
        build_entity_note_markdown,
        fetch_entity_profile_basics,
        fetch_recent_article_bullets,
    )
    from services.vault_notes_registry_service import upsert_vault_note
    from shared.database.connection import get_db_connection_context
    from shared.domain_registry import resolve_domain_schema
    from shared.vault_note_contract import entity_vault_rel_path

    results: list[dict[str, Any]] = []
    root = vault_root()
    for domain, eid, display in ENTITY_LIVING:
        hits = entity_hits(domain, eid)
        if hits < MIN_HITS_LIVING:
            results.append(
                {"id": eid, "name": display, "ok": False, "skipped": True, "reason": f"hits={hits}"}
            )
            continue
        schema = resolve_domain_schema(domain)
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, canonical_name, entity_type,
                           LEFT(COALESCE(description, ''), 800)
                    FROM {schema}.entity_canonical WHERE id = %s
                    """,
                    (eid,),
                )
                row = cur.fetchone()
        if not row:
            results.append({"id": eid, "name": display, "ok": False, "error": "missing"})
            continue
        ent = {
            "id": int(row[0]),
            "name": display,
            "entity_type": row[2],
            "mentions": hits,
            "description": (row[3] or "").strip(),
        }
        path = entity_vault_rel_path(display)
        fp = root / path
        if fp.is_file():
            existing = fp.read_text(encoding="utf-8")
            if re.search(r"brief_locked:\s*(true|1|yes)", existing, re.I):
                results.append({"id": eid, "path": path, "ok": True, "skipped": True, "reason": "brief_locked"})
                continue
            if not force and "canonical_entity_id:" in existing and hits < 100:
                results.append({"id": eid, "path": path, "ok": True, "skipped": True, "reason": "exists"})
                continue
        basics = fetch_entity_profile_basics(domain, eid)
        bullets = fetch_recent_article_bullets(domain, eid, limit=12)
        # Cross-link Situations in posture area via significance later — keep builder default
        md = build_entity_note_markdown(
            domain_key=domain,
            entity=ent,
            basics=basics,
            timeline_bullets=bullets,
        )
        # Inject See also into Relationships section
        see = {
            "finance": "[[resource_movements]] · [[market_trends]] · [[china_trade_tech]]",
            "politics": "[[us_institutions]] · [[iran_war]] · [[russia_ukraine]]",
        }.get(domain, "")
        if display in ("Nigel Farage",):
            see = "[[farage_reform_boats]] · [[donald_j_trump]]"
        elif display in ("OpenAI",):
            see = "[[ai_governance]] · [[china_trade_tech]]"
        elif display in ("Venezuela",):
            see = "[[venezuela_boe_gold]] · [[resource_movements]]"
        elif display in ("oil", "gold", "OPEC+", "Strait of Hormuz", "International Energy Agency"):
            see = "[[resource_movements]] · [[market_trends]] · [[inflation_iran_war]]"
        elif display in ("Federal Reserve",):
            see = "[[market_trends]] · [[resource_movements]]"
        elif display in ("State Department", "Pentagon", "Supreme Court", "White House"):
            see = "[[us_institutions]] · [[donald_j_trump]]"
        if see:
            md = md.replace(
                "- _Wikilinks and pair threads fill in as the vault writer runs._",
                f"- Related Situations: {see}\n- _More wikilinks fill in as the vault writer runs._",
            )
        if dry_run:
            results.append({"id": eid, "path": path, "ok": True, "dry_run": True, "hits": hits})
            continue
        wr = _write_file(path, md, force=True)
        upsert_vault_note(
            domain_key=domain,
            note_type="entity",
            object_id=eid,
            vault_path=path,
            title=display,
            note_status="note_ready",
            lifecycle="living" if hits >= 100 else "seeded",
            mention_count=hits,
            tags=[str(ent.get("entity_type") or "entity"), "density_seed"],
            metadata={"seed_package": "remaining_vault_density", "hits": hits},
            body_md=_strip_nuls(md),
            summary_md=_strip_nuls("\n".join(bullets[:3]))[:900] or None,
        )
        results.append({"id": eid, "path": path, "ok": True, "write": wr, "hits": hits})
    return results


def patch_packages(*, force: bool, dry_run: bool) -> list[dict[str, Any]]:
    from services.vault_bridge_service import vault_root
    from services.vault_notes_registry_service import (
        get_vault_note_by_path,
        upsert_vault_note,
    )

    root = vault_root()
    inv = root / "20_Investigations"
    out: list[dict[str, Any]] = []
    if not inv.is_dir():
        return [{"ok": False, "error": "no_investigations_dir"}]
    for fp in sorted(inv.glob("pkg-*.md")):
        rel = str(fp.relative_to(root)).replace("\\", "/")
        text = fp.read_text(encoding="utf-8")
        title = ""
        for line in text.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        blob = f"{fp.name} {title}"
        links: list[str] = []
        for pat, ls in PACKAGE_RULES:
            if pat.search(blob):
                for x in ls:
                    if x not in links:
                        links.append(x)
        if not links:
            out.append({"path": rel, "ok": True, "skipped": True, "reason": "no_rule"})
            continue
        if "## Related situations" in text and not force:
            out.append({"path": rel, "ok": True, "skipped": True, "reason": "exists"})
            continue
        block = "## Related situations\n\n" + "\n".join(f"- {x}" for x in links) + "\n"
        if "## Related situations" in text:
            text = re.sub(
                r"## Related situations\n(?:.*?\n)*?(?=\n## |\Z)",
                block + "\n",
                text,
                count=1,
                flags=re.S,
            )
        else:
            text = text.rstrip() + "\n\n" + block
        if dry_run:
            out.append({"path": rel, "ok": True, "dry_run": True, "links": links})
            continue
        text = _strip_nuls(text)
        fp.write_text(text, encoding="utf-8")
        note = get_vault_note_by_path(rel) or {}
        if note.get("object_id"):
            upsert_vault_note(
                domain_key=str(note.get("domain_key") or "politics"),
                note_type=str(note.get("note_type") or "cluster"),
                object_id=int(note["object_id"]),
                vault_path=rel,
                title=note.get("title") or title,
                note_status="note_ready",
                lifecycle=str(note.get("lifecycle") or "living"),
                body_md=text,
                summary_md=_strip_nuls((note.get("summary_md") or "")[:900]) or None,
                metadata={
                    **(note.get("metadata") or {}),
                    "related_situations_seeded": True,
                    "related_seeded_at": _now_iso(),
                },
                tags_source="ni_structural",
            )
        out.append({"path": rel, "ok": True, "links": links})
    return out


def sync_finance_clipping_bodies(*, dry_run: bool, limit: int = 40) -> dict[str, Any]:
    """Mirror disk clipping markdown into empty PG body_md rows."""
    from services.vault_bridge_service import vault_root
    from services.vault_notes_registry_service import upsert_vault_note
    from shared.database.connection import get_db_connection_context

    root = vault_root()
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, object_id, vault_path, title, domain_key, lifecycle, metadata
                FROM intelligence.vault_notes
                WHERE note_type = 'clipping'
                  AND domain_key = 'finance'
                  AND COALESCE(length(body_md), 0) < 40
                ORDER BY id
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall() or []
    filled = 0
    missing = 0
    for _id, oid, vpath, title, domain, lifecycle, meta in rows:
        fp = root / str(vpath)
        if not fp.is_file():
            missing += 1
            continue
        text = _strip_nuls(fp.read_text(encoding="utf-8"))
        if len(text) < 40:
            missing += 1
            continue
        if dry_run:
            filled += 1
            continue
        upsert_vault_note(
            domain_key=str(domain or "finance"),
            note_type="clipping",
            object_id=int(oid) if oid is not None else int(_id),
            vault_path=str(vpath),
            title=title,
            note_status="note_ready",
            lifecycle=str(lifecycle or "living"),
            body_md=text,
            summary_md=text[:500],
            metadata={**(meta or {}), "body_synced_from_disk": True, "synced_at": _now_iso()},
        )
        filled += 1
    return {"candidates": len(rows), "filled": filled, "missing_or_thin": missing}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sync", action="store_true")
    parser.add_argument("--skip-hubs", action="store_true")
    parser.add_argument("--skip-entities", action="store_true")
    parser.add_argument("--skip-packages", action="store_true")
    parser.add_argument("--skip-clippings", action="store_true")
    args = parser.parse_args()

    os.environ.setdefault("NEWS_INTEL_VAULT_PATH", "/mnt/news-intelligence-vault")
    os.environ.setdefault("NEWS_INTEL_VAULT_WRITE", "true")
    os.environ.setdefault("NI_VAULT_NOTES_ENABLED", "true")
    os.environ.setdefault("NI_VAULT_CLUSTER_HUBS_ENABLED", "true")

    stats: dict[str, Any] = {"ok": True, "started_at": _now_iso()}

    if not args.skip_hubs:
        stats["hubs"] = seed_hubs(force=args.force, dry_run=args.dry_run)
    if not args.skip_entities:
        stats["entities"] = seed_entities(force=args.force, dry_run=args.dry_run)
    if not args.skip_packages:
        stats["packages"] = patch_packages(force=args.force, dry_run=args.dry_run)
    if not args.skip_clippings:
        stats["clippings"] = sync_finance_clipping_bodies(dry_run=args.dry_run)

    if args.sync and not args.dry_run:
        try:
            from scripts.vault_quality_cleanup import write_reading_mocs
            from services.vault_bridge_service import vault_root
            from services.vault_tag_link_sync_service import sync_vault_file

            root = vault_root()
            paths: list[str] = []
            for h in (stats.get("hubs") or {}).values():
                if h.get("path"):
                    paths.append(str(h["path"]))
            for e in stats.get("entities") or []:
                if e.get("ok") and e.get("path") and not e.get("skipped"):
                    paths.append(str(e["path"]))
            sync_res = []
            for p in paths:
                sync_res.append(sync_vault_file(root / p))
            write_reading_mocs()
            stats["sync"] = {"n": len(paths), "mocs": True}
        except Exception as e:
            logger.exception("sync failed")
            stats["sync_error"] = str(e)

    # Compact package stats
    if isinstance(stats.get("packages"), list):
        pkgs = stats["packages"]
        stats["packages_summary"] = {
            "total": len(pkgs),
            "linked": sum(1 for p in pkgs if p.get("ok") and p.get("links")),
            "skipped": sum(1 for p in pkgs if p.get("skipped")),
        }

    print(json.dumps(stats, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
