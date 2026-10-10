#!/usr/bin/env python3
"""Seed / enrich finance vault Situation hubs for market trends + resource movements.

Grounded on finance.storylines + finance.articles (+ optional politics Hormuz/oil
titles for geopolitics intersection). Does not touch brief_locked living entities.

Usage (from api/ with env loaded):
  set -a && source ../.env && set +a
  export NEWS_INTEL_VAULT_WRITE=true NI_VAULT_NOTES_ENABLED=true
  export NEWS_INTEL_VAULT_PATH=/mnt/news-intelligence-vault
  PYTHONPATH=. python scripts/seed_finance_markets_vault.py
  PYTHONPATH=. python scripts/seed_finance_markets_vault.py --force --dry-run
  PYTHONPATH=. python scripts/seed_finance_markets_vault.py --sync
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any

_API_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _API_ROOT not in sys.path:
    sys.path.insert(0, _API_ROOT)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("seed_finance_markets_vault")

DOMAIN = "finance"
SCHEMA = "finance"

# Curated Situation hubs (index-only; no membership merges).
RESOURCE_CLUSTER_KEY = "resource_movements"
RESOURCE_TITLE = "Resource movements — oil, metals, Hormuz (situation)"
RESOURCE_STORYLINES = (
    7206,  # Iran impasse / oil pressure
    9431,  # Hormuz claims / oil surge
    7637,  # Hormuz update / market jitters (has expansion)
    19719,  # OPEC+ cuts / $5 gas
    7203,  # rare earth / stockpile (has expansion)
    8663,  # Adnoc LNG / Hormuz
    5857,  # Hormuz oil supply hit
    7089,  # Source commodities
    9817,  # IEA oil shortfall
    7333,  # rare earth rally
    5195,  # commodities prices rise
    9877,  # Hormuz oil pivot / yields
)
RESOURCE_SEEDS = (
    1996,  # oil
    4939,  # Crude oil
    11034,  # Brent crude
    6856,  # OPEC+
    230,  # Strait of Hormuz
    1062,  # Hormuz
    4411,  # gold
    125740,  # Copper
    2064,  # International Energy Agency
    328,  # IEA
    10854,  # rare earths
    6134,  # rare earth elements
    228599,  # London Metal Exchange
    6491,  # Natural gas
    6443,  # Commodities
)

MARKET_CLUSTER_KEY = "market_trends"
MARKET_TITLE = "Market trends — Fed, CPI, yields, FX (situation)"
MARKET_STORYLINES = (
    9222,  # July CPI / Fed hike pace
    5229,  # Clarida K-shaped / tariffs
    5082,  # BOJ / US bond selloff
    13697,  # Fed rate-hike sentiment
    9860,  # Norway fund / CPI / cooling inflation
    9892,  # job cuts / CPI / yields
    8323,  # job cuts / inflation fears
    6365,  # US-Japan yen intervention
    9877,  # Hormuz / Treasury yields (cross-link)
    7621,  # jobs / Treasury rally / Fed bets
    5263,  # Clarida inflation target
    9903,  # BOJ hike / yen / long yields
)
MARKET_SEEDS = (
    98,  # Federal Reserve
    99,  # Inflation
    286,  # S&P 500 (subject)
    231437,  # US Treasury
    77030,  # Treasury
    4411,  # gold (safe-haven crossover)
)

# Existing hubs to refresh with tighter grounded briefs (resource/markets adjacent).
REFRESH_EXISTING = (
    {
        "cluster_key": "norges_bank_investment_management_sovereign_wealth_fund",
        "lane": "markets",
    },
    {
        "cluster_key": "caterpillar_southern_copper",
        "lane": "resources",
    },
    {
        "cluster_key": "london_metal_exchange_artificial_intelligence",
        "lane": "resources",
    },
    {
        "cluster_key": "bhp_woodside_energy",
        "lane": "resources",
    },
    {
        "cluster_key": "iran_freightwaves",
        "lane": "resources",
    },
)

PACKAGE_WIKILINKS = {
    "20_Investigations/pkg-114-ongoing-supply-disruptions-hit-four-global-fronts.md": [
        "[[resource_movements|Resource movements]]",
        "[[market_trends|Market trends]]",
        "[[inflation_iran_war|Inflation / Iran war]]",
    ],
    "20_Investigations/pkg-91-capital-one-profit-beats-estimates-as-loan-loss-pr.md": [
        "[[market_trends|Market trends]]",
        "[[resource_movements|Resource movements]]",
        "[[gold|gold]]",
    ],
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strip_nuls(text: str | None) -> str:
    """Postgres text cannot store NUL bytes; vault files occasionally have them."""
    if not text:
        return ""
    return text.replace("\x00", "")


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


def fetch_timeline_for_storylines(
    storyline_ids: list[int],
    *,
    limit: int = 18,
    title_filter: str | None = None,
) -> list[str]:
    from shared.database.connection import get_db_connection_context

    if not storyline_ids:
        return []
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            sql = f"""
                SELECT a.published_at::date, a.title, a.id, sa.storyline_id
                FROM {SCHEMA}.storyline_articles sa
                JOIN {SCHEMA}.articles a ON a.id = sa.article_id
                WHERE sa.storyline_id = ANY(%s)
                  AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
            """
            params: list[Any] = [list(storyline_ids)]
            if title_filter:
                sql += " AND a.title ~* %s"
                params.append(title_filter)
            sql += """
                ORDER BY a.published_at DESC NULLS LAST
                LIMIT %s
            """
            params.append(limit * 3)
            cur.execute(sql, tuple(params))
            rows = list(cur.fetchall() or [])
    bullets = []
    seen_aids: set[int] = set()
    for pub, title, aid, sid in rows:
        if int(aid) in seen_aids:
            continue
        seen_aids.add(int(aid))
        day = pub.isoformat() if pub else "undated"
        bullets.append(
            f"- {day} — {(title or 'Untitled').strip()[:140]} "
            f"(article:{aid}, storyline:{sid})"
        )
        if len(bullets) >= limit:
            break
    return bullets


def fetch_recent_theme_articles(
    patterns: list[str],
    *,
    days: int = 45,
    limit: int = 14,
    schema: str = SCHEMA,
) -> list[str]:
    from shared.database.connection import get_db_connection_context

    like_clause = " OR ".join(["a.title ILIKE %s"] * len(patterns))
    params: list[Any] = [int(days)] + [f"%{p}%" for p in patterns] + [int(limit)]
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT a.published_at::date, a.title, a.id
                FROM {schema}.articles a
                WHERE a.published_at >= NOW() - make_interval(days => %s)
                  AND ({like_clause})
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


def build_resource_brief(timeline: list[str], politics_x: list[str]) -> str:
    lead_bits = [re.sub(r"^- \S+ — ", "", t).split(" (article:")[0] for t in timeline[:4]]
    now_line = (
        "Oil, diesel, and Hormuz remain the choke points: corpus titles show "
        "record UK/NI diesel prices, G7 reserve-release talk, and OPEC+/sanctions "
        "pressure on crude while Strait of Hormuz risk keeps supply forecasts unstable."
    )
    if lead_bits:
        now_line = (
            "NOW: "
            + "; ".join(lead_bits[:3])
            + ". Cross-check geopolitics titles below for Hormuz/OPEC confirmation."
        )
    why = (
        "WHY IT MATTERS: Resource moves are transmitting into fuel inflation, "
        "emergency stockpile diplomacy (G7 diesel/oil releases), LNG rerouting "
        "(Adnoc/Hormuz), and critical-mineral stockpile politics (rare earths). "
        "Gold/copper titles track safe-haven and industrial-demand overlays."
    )
    watch = (
        "WATCH: Hormuz throughput vs pre-war baselines; OPEC+ November holds; "
        "diesel export-ban threats; IEA shortfall language; copper/rare-earth "
        "project headlines as industrial demand signals."
    )
    evid = "\n".join(timeline[:8])
    pol = "\n".join(politics_x[:6]) if politics_x else "- _(no recent politics oil titles)_"
    return (
        f"**CURRENT BRIEF: Resource movements**\n\n"
        f"{now_line}\n\n{why}\n\n{watch}\n\n"
        f"**Corpus timeline (finance):**\n{evid}\n\n"
        f"**Geopolitics intersection (politics titles):**\n{pol}"
    )


def build_market_brief(timeline: list[str], theme_arts: list[str]) -> str:
    lead_bits = [re.sub(r"^- \S+ — ", "", t).split(" (article:")[0] for t in timeline[:4]]
    now_line = (
        "NOW: Soft/cooling CPI prints compete with energy-driven inflation and "
        "Fed hold-vs-hike debate; Treasury yields and yen intervention episodes "
        "show the FX/rates channel reacting to the same oil shock."
    )
    if lead_bits:
        now_line = "NOW: " + "; ".join(lead_bits[:3]) + "."
    why = (
        "WHY IT MATTERS: Market trend notes should track the rate path (Fed/BOJ), "
        "inflation prints (CPI/core), and sovereign-fund risk posture — not single "
        "ticker noise. Energy pass-through into CPI and borrowing costs is the "
        "bridge to [[resource_movements]]."
    )
    watch = (
        "WATCH: next CPI vs energy components; Fed hike odds after soft core prints; "
        "US-Japan yen support; Norway oil-fund risk warnings; Treasury yield spikes "
        "when Middle East risk premia return."
    )
    evid = "\n".join((timeline or theme_arts)[:10])
    return (
        f"**CURRENT BRIEF: Market trends**\n\n"
        f"{now_line}\n\n{why}\n\n{watch}\n\n"
        f"**Corpus timeline:**\n{evid}"
    )


def persist_hub_brief(
    *,
    domain_key: str,
    cluster_key: str,
    vault_path: str,
    title: str,
    object_id: int,
    brief: str,
    member_storyline_ids: list[int],
    seed_entity_ids: list[int],
    tags: list[str],
    force: bool,
    dry_run: bool,
) -> dict[str, Any]:
    from services.vault_bridge_service import vault_root
    from services.vault_note_patch import patch_auto_sections
    from services.vault_notes_registry_service import upsert_vault_note

    brief_clean = _strip_nuls(brief or "").strip()[:3500]
    summary = _strip_nuls(
        "\n\n".join([p.strip() for p in brief_clean.split("\n\n") if p.strip()][:3])
    )[:900]
    now = _now_iso()
    meta = {
        "hub": True,
        "cluster_key": cluster_key,
        "member_storyline_ids": member_storyline_ids,
        "seed_entity_ids": seed_entity_ids,
        "domain_key": domain_key,
        "current_brief": brief_clean[:1200],
        "brief_updated_at": now,
        "brief_fingerprint": f"seed_finance_{cluster_key}_{now[:10]}",
        "brief_source": "seed_finance_markets_vault",
        "scorer": "vault_cluster_hub_v1",
    }
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "cluster_key": cluster_key,
            "brief_chars": len(brief_clean),
            "path": vault_path,
        }

    root = vault_root()
    path = root / vault_path
    body_for_pg = ""
    if path.is_file():
        existing = path.read_text(encoding="utf-8")
        # Guard brief_locked
        if re.search(r"brief_locked:\s*(true|1|yes)", existing, re.I):
            return {
                "ok": True,
                "skipped": True,
                "reason": "brief_locked",
                "path": vault_path,
            }
        patched = patch_auto_sections(existing, brief=brief_clean[:1200])
        if force or "<!-- ni:auto:brief -->" in existing:
            path.write_text(patched or existing, encoding="utf-8")
        raw_body = path.read_text(encoding="utf-8")
        body_for_pg = _strip_nuls(raw_body)
        if body_for_pg != raw_body:
            path.write_text(body_for_pg, encoding="utf-8")
    else:
        logger.warning("hub file missing for brief: %s", vault_path)

    upsert_vault_note(
        domain_key=domain_key,
        note_type="cluster",
        object_id=object_id,
        vault_path=vault_path,
        title=title,
        note_status="note_ready",
        lifecycle="living",
        tags=tags,
        metadata=meta,
        tags_source="ni_structural",
        body_md=body_for_pg or None,
        summary_md=summary or None,
    )
    return {
        "ok": True,
        "cluster_key": cluster_key,
        "path": vault_path,
        "brief_chars": len(brief_clean),
        "summary_chars": len(summary),
    }


def patch_package_wikilinks(*, force: bool, dry_run: bool) -> list[dict[str, Any]]:
    from services.vault_bridge_service import vault_root
    from services.vault_notes_registry_service import (
        get_vault_note_by_path,
        upsert_vault_note,
    )

    out: list[dict[str, Any]] = []
    root = vault_root()
    for rel, links in PACKAGE_WIKILINKS.items():
        path = root / rel
        if not path.is_file():
            out.append({"path": rel, "ok": False, "error": "missing"})
            continue
        text = path.read_text(encoding="utf-8")
        block = "## Related situations\n\n" + "\n".join(f"- {x}" for x in links) + "\n"
        if "## Related situations" in text and not force:
            out.append({"path": rel, "ok": True, "skipped": True, "reason": "exists"})
            continue
        if "## Related situations" in text:
            text = re.sub(
                r"## Related situations\n(?:.*?\n)*?(?=\n## |\Z)",
                block + "\n",
                text,
                count=1,
                flags=re.S,
            )
        else:
            # Insert after title / first heading block
            text = text.rstrip() + "\n\n" + block
        if dry_run:
            out.append({"path": rel, "ok": True, "dry_run": True})
            continue
        text = _strip_nuls(text)
        path.write_text(text, encoding="utf-8")
        note = get_vault_note_by_path(rel) or {}
        if note.get("object_id"):
            upsert_vault_note(
                domain_key=str(note.get("domain_key") or DOMAIN),
                note_type=str(note.get("note_type") or "cluster"),
                object_id=int(note["object_id"]),
                vault_path=rel,
                title=note.get("title"),
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
        out.append({"path": rel, "ok": True, "links": len(links)})
    return out


def refresh_inflation_iran_cross(*, force: bool, dry_run: bool) -> dict[str, Any]:
    """Improve politics inflation/Iran hub brief with corpus-grounded content (not locked)."""
    from services.vault_bridge_service import vault_root
    from services.vault_cluster_hub_service import get_cluster_hub
    from services.vault_note_patch import patch_auto_sections
    from services.vault_notes_registry_service import upsert_vault_note

    hub = get_cluster_hub(cluster_key="inflation_iran_war")
    if not hub:
        return {"ok": False, "error": "hub_missing"}
    meta = hub.get("metadata") or {}
    if meta.get("brief_locked"):
        return {"ok": True, "skipped": True, "reason": "brief_locked"}

    # Prefer finance oil/inflation titles + existing hub timeline members
    fin = fetch_recent_theme_articles(
        ["oil", "diesel", "Hormuz", "inflation", "CPI", "borrowing"],
        days=40,
        limit=10,
    )
    pol = fetch_recent_theme_articles(
        ["Hormuz", "oil", "OPEC", "G7", "diesel"],
        days=40,
        limit=8,
        schema="politics",
    )
    brief = (
        "**CURRENT BRIEF: Inflation / Iran war (resource geopolitics)**\n\n"
        "NOW: Middle East conflict risk and Hormuz throughput still price into "
        "fuel and borrowing costs. Finance corpus shows diesel at multi-year highs "
        "and oil-forecast uncertainty; politics corpus shows G7 reserve releases "
        "and OPEC production holds.\n\n"
        "WHY IT MATTERS: This hub bridges household inflation (gas/heating oil) "
        "to war risk — use with finance [[resource_movements]] and [[market_trends]].\n\n"
        "WATCH: Hormuz flows vs pre-war; diesel/heating-oil headlines; G7 stockpile "
        "releases; Fed/BoE rate language when energy CPI reaccelerates.\n\n"
        f"**Finance titles:**\n{chr(10).join(fin[:8])}\n\n"
        f"**Politics titles:**\n{chr(10).join(pol[:6])}"
    )
    if dry_run:
        return {"ok": True, "dry_run": True, "brief_chars": len(brief)}

    path = vault_root() / hub["vault_path"]
    if not path.is_file():
        return {"ok": False, "error": "file_missing"}
    existing = path.read_text(encoding="utf-8")
    # Skip if already seeded today and not force
    if (not force) and "seed_finance_markets_vault" in str(meta.get("brief_source") or ""):
        return {"ok": True, "skipped": True, "reason": "already_seeded"}
    brief_s = _strip_nuls(brief)
    # Some legacy hubs have brief text above YAML; normalize before patching.
    if not existing.lstrip().startswith("---"):
        fm_start = existing.find("\n---\n")
        if fm_start >= 0:
            existing = existing[fm_start + 1 :]
    if "## Current brief" not in existing and "# " in existing:
        # Insert a brief fence after the H1
        existing = re.sub(
            r"(# [^\n]+\n)",
            r"\1\n## Current brief\n\n<!-- ni:auto:brief -->\n_Brief updates when the situation moves._\n<!-- /ni:auto:brief -->\n",
            existing,
            count=1,
        )
    patched = patch_auto_sections(existing, brief=brief_s[:1200])
    body = _strip_nuls(patched or existing)
    path.write_text(body, encoding="utf-8")
    title = str(hub.get("title") or "Inflation / Iran war (situation)")
    if title.strip().lower() in {"current brief", "basics"}:
        title = "Inflation / Iran war (situation)"
    upsert_vault_note(
        domain_key=str(hub.get("domain_key") or "politics"),
        note_type="cluster",
        object_id=int(hub["object_id"]),
        vault_path=hub["vault_path"],
        title=title,
        note_status="note_ready",
        lifecycle="living",
        tags=list(
            dict.fromkeys(
                list(hub.get("tags") or [])
                + [
                    "cluster",
                    "cluster/inflation_iran_war",
                    "domain/politics",
                    "theme/resource-geopolitics",
                    "theme/inflation",
                ]
            )
        ),
        metadata={
            **meta,
            "current_brief": brief_s[:1200],
            "brief_updated_at": _now_iso(),
            "brief_source": "seed_finance_markets_vault",
            "cross_link_hubs": ["resource_movements", "market_trends"],
        },
        body_md=body,
        summary_md=_strip_nuls(
            brief_s.split("\n\n")[1][:500] if "\n\n" in brief_s else brief_s[:500]
        ),
        tags_source="obsidian",
    )
    return {"ok": True, "path": hub["vault_path"], "brief_chars": len(brief)}


def seed_hub(
    *,
    cluster_key: str,
    title: str,
    members: tuple[int, ...],
    seeds: tuple[int, ...],
    significance: str,
    tags: list[str],
    force: bool,
    dry_run: bool,
) -> dict[str, Any]:
    from services.vault_cluster_hub_service import write_cluster_hub

    return write_cluster_hub(
        domain_key=DOMAIN,
        cluster_key=cluster_key,
        title=title,
        member_storyline_ids=list(members),
        seed_entity_ids=list(seeds),
        significance=significance,
        tags=tags,
        force=force,
        dry_run=dry_run,
    )


def refresh_adjacent_hubs(*, force: bool, dry_run: bool) -> list[dict[str, Any]]:
    from services.vault_cluster_hub_service import get_cluster_hub, write_cluster_hub

    results: list[dict[str, Any]] = []
    for item in REFRESH_EXISTING:
        hub = get_cluster_hub(domain_key=DOMAIN, cluster_key=item["cluster_key"])
        if not hub:
            results.append({"cluster_key": item["cluster_key"], "ok": False, "error": "missing"})
            continue
        members = list(hub.get("member_storyline_ids") or [])
        # Cap kitchen-sink magnets
        if len(members) > 24:
            members = members[:24]
        lane = item["lane"]
        tl = fetch_timeline_for_storylines(members, limit=12)
        if lane == "resources":
            brief = (
                f"**CURRENT BRIEF: {hub.get('title')}**\n\n"
                "Resource/industrial angle from member episodes. "
                "See also [[resource_movements]].\n\n"
                + "\n".join(tl[:8] or ["- _No recent member articles._"])
            )
            sig = (
                "Indexes energy/mining/logistics episodes adjacent to resource "
                "movements. Prefer [[resource_movements]] for oil/metals spine."
            )
        else:
            brief = (
                f"**CURRENT BRIEF: {hub.get('title')}**\n\n"
                "Macro/fund posture from member episodes. "
                "See also [[market_trends]].\n\n"
                + "\n".join(tl[:8] or ["- _No recent member articles._"])
            )
            sig = (
                "Indexes sovereign-fund / asset-management episodes adjacent to "
                "market trends. Prefer [[market_trends]] for Fed/CPI/yields spine."
            )
        wr = write_cluster_hub(
            domain_key=DOMAIN,
            cluster_key=str(hub["cluster_key"]),
            title=str(hub.get("title") or hub["cluster_key"]),
            member_storyline_ids=members,
            seed_entity_ids=list(hub.get("seed_entity_ids") or []),
            significance=sig,
            vault_path=hub.get("vault_path"),
            tags=list(hub.get("tags") or [])
            + [f"theme/{'resource-movements' if lane == 'resources' else 'market-trends'}"],
            force=force,
            dry_run=dry_run,
        )
        br = persist_hub_brief(
            domain_key=DOMAIN,
            cluster_key=str(hub["cluster_key"]),
            vault_path=str(hub.get("vault_path")),
            title=str(hub.get("title") or hub["cluster_key"]),
            object_id=int(hub["object_id"]),
            brief=brief,
            member_storyline_ids=members,
            seed_entity_ids=list(hub.get("seed_entity_ids") or []),
            tags=list(hub.get("tags") or []),
            force=force,
            dry_run=dry_run,
        )
        results.append({"write": wr, "brief": br})
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Also run vault tag/link sync + quality cleanup MOCs",
    )
    parser.add_argument("--skip-adjacent", action="store_true")
    parser.add_argument("--skip-packages", action="store_true")
    parser.add_argument("--skip-cross", action="store_true")
    args = parser.parse_args()

    os.environ.setdefault("NEWS_INTEL_VAULT_PATH", "/mnt/news-intelligence-vault")
    os.environ.setdefault("NEWS_INTEL_VAULT_WRITE", "true")
    os.environ.setdefault("NI_VAULT_NOTES_ENABLED", "true")
    os.environ.setdefault("NI_VAULT_CLUSTER_HUBS_ENABLED", "true")

    stats: dict[str, Any] = {"ok": True, "started_at": _now_iso()}

    # 1) Resource movements hub
    res_write = seed_hub(
        cluster_key=RESOURCE_CLUSTER_KEY,
        title=RESOURCE_TITLE,
        members=RESOURCE_STORYLINES,
        seeds=RESOURCE_SEEDS,
        significance=(
            "Primary finance Situation for oil/diesel/Hormuz/OPEC, gold/copper/metals, "
            "and rare-earth stockpile politics. Indexes curated episodes only — "
            "no kitchen-sink membership bags. Cross-link [[market_trends]] and "
            "politics [[inflation_iran_war]]."
        ),
        tags=[
            "cluster",
            "domain/finance",
            "theme/resource-movements",
            "theme/commodities",
            "theme/oil",
            "theme/metals",
            "priority/high",
        ],
        force=args.force,
        dry_run=args.dry_run,
    )
    stats["resource_write"] = res_write

    res_tl = fetch_timeline_for_storylines(
        list(RESOURCE_STORYLINES),
        limit=16,
        title_filter=(
            "(oil|diesel|Hormuz|OPEC|crude|Brent|gold|copper|metal|"
            "rare.?earth|IEA|commodity|gas|LNG|sanction)"
        ),
    )
    if len(res_tl) < 6:
        res_tl = fetch_timeline_for_storylines(list(RESOURCE_STORYLINES), limit=16)
    # Supplement with direct article scan (storyline bags can be noisy)
    theme_res = fetch_recent_theme_articles(
        ["oil", "diesel", "Hormuz", "OPEC", "gold", "copper", "rare earth", "IEA"],
        days=45,
        limit=12,
    )
    pol_x = fetch_recent_theme_articles(
        ["Hormuz", "oil", "OPEC", "diesel", "G7"],
        days=40,
        limit=8,
        schema="politics",
    )
    # Prefer fresh theme articles over older storyline-bag titles.
    res_brief = build_resource_brief(
        _dedupe_bullets(theme_res + res_tl, limit=14), pol_x
    )
    from shared.vault_note_contract import cluster_object_id, cluster_vault_rel_path

    res_path = cluster_vault_rel_path(RESOURCE_CLUSTER_KEY)
    stats["resource_brief"] = persist_hub_brief(
        domain_key=DOMAIN,
        cluster_key=RESOURCE_CLUSTER_KEY,
        vault_path=res_path,
        title=RESOURCE_TITLE,
        object_id=int(res_write.get("object_id") or cluster_object_id(RESOURCE_CLUSTER_KEY)),
        brief=res_brief,
        member_storyline_ids=list(RESOURCE_STORYLINES),
        seed_entity_ids=list(RESOURCE_SEEDS),
        tags=[
            "cluster",
            f"cluster/{RESOURCE_CLUSTER_KEY}",
            "domain/finance",
            "theme/resource-movements",
            "theme/commodities",
            "priority/high",
        ],
        force=args.force,
        dry_run=args.dry_run,
    )

    # 2) Market trends hub
    mkt_write = seed_hub(
        cluster_key=MARKET_CLUSTER_KEY,
        title=MARKET_TITLE,
        members=MARKET_STORYLINES,
        seeds=MARKET_SEEDS,
        significance=(
            "Primary finance Situation for Fed/CPI/inflation, Treasury yields, "
            "BOJ/yen FX, and sovereign-fund risk posture. Indexes curated episodes. "
            "Energy pass-through links to [[resource_movements]]."
        ),
        tags=[
            "cluster",
            "domain/finance",
            "theme/market-trends",
            "theme/fed",
            "theme/inflation",
            "priority/high",
        ],
        force=args.force,
        dry_run=args.dry_run,
    )
    stats["market_write"] = mkt_write

    mkt_tl = fetch_timeline_for_storylines(
        list(MARKET_STORYLINES),
        limit=16,
        title_filter="(Fed|CPI|inflation|Treasury|yield|yen|BOJ|bond|rate|job)",
    )
    if len(mkt_tl) < 6:
        mkt_tl = fetch_timeline_for_storylines(list(MARKET_STORYLINES), limit=16)
    theme_mkt = fetch_recent_theme_articles(
        [
            "Fed ",
            "Federal Reserve",
            "CPI",
            "inflation",
            "Treasury",
            "yen",
            "bond sell",
            "bond market",
            "yield",
            "rate hike",
            "Jackson Hole",
        ],
        days=45,
        limit=12,
    )
    mkt_brief = build_market_brief(
        _dedupe_bullets(theme_mkt + mkt_tl, limit=14), theme_mkt
    )
    mkt_path = cluster_vault_rel_path(MARKET_CLUSTER_KEY)
    stats["market_brief"] = persist_hub_brief(
        domain_key=DOMAIN,
        cluster_key=MARKET_CLUSTER_KEY,
        vault_path=mkt_path,
        title=MARKET_TITLE,
        object_id=int(mkt_write.get("object_id") or cluster_object_id(MARKET_CLUSTER_KEY)),
        brief=mkt_brief,
        member_storyline_ids=list(MARKET_STORYLINES),
        seed_entity_ids=list(MARKET_SEEDS),
        tags=[
            "cluster",
            f"cluster/{MARKET_CLUSTER_KEY}",
            "domain/finance",
            "theme/market-trends",
            "theme/fed",
            "priority/high",
        ],
        force=args.force,
        dry_run=args.dry_run,
    )

    if not args.skip_adjacent:
        stats["adjacent"] = refresh_adjacent_hubs(force=args.force, dry_run=args.dry_run)
    if not args.skip_packages:
        stats["packages"] = patch_package_wikilinks(force=args.force, dry_run=args.dry_run)
    if not args.skip_cross:
        stats["inflation_iran_cross"] = refresh_inflation_iran_cross(
            force=args.force, dry_run=args.dry_run
        )

    if args.sync and not args.dry_run:
        # Targeted sync only — full vault walk on NFS is too slow for this seed.
        try:
            from pathlib import Path

            from services.vault_bridge_service import vault_root
            from services.vault_tag_link_sync_service import sync_vault_file

            root = vault_root()
            targets = [
                cluster_vault_rel_path(RESOURCE_CLUSTER_KEY),
                cluster_vault_rel_path(MARKET_CLUSTER_KEY),
                "40_Reference/clusters/inflation_iran_war.md",
                "40_Reference/clusters/norges_bank_investment_management_sovereign_wealth_fund.md",
                "40_Reference/clusters/caterpillar_southern_copper.md",
                "40_Reference/clusters/london_metal_exchange_artificial_intelligence.md",
                "40_Reference/clusters/bhp_woodside_energy.md",
                "40_Reference/clusters/iran_freightwaves.md",
                *PACKAGE_WIKILINKS.keys(),
            ]
            sync_stats = {"ok": True, "synced": 0, "errors": 0, "paths": []}
            for rel in targets:
                try:
                    r = sync_vault_file(Path(root / rel), root=root)
                    if r.get("ok") and not r.get("skipped"):
                        sync_stats["synced"] += 1
                        sync_stats["paths"].append(rel)
                    elif not r.get("ok"):
                        sync_stats["errors"] += 1
                except Exception as e:
                    sync_stats["errors"] += 1
                    logger.warning("sync %s: %s", rel, e)
            stats["tag_link_sync"] = sync_stats
        except Exception as e:
            stats["tag_link_sync"] = {"ok": False, "error": str(e)}
        try:
            import importlib.util

            cleanup_path = os.path.join(_API_ROOT, "scripts", "vault_quality_cleanup.py")
            spec = importlib.util.spec_from_file_location("vault_quality_cleanup", cleanup_path)
            mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            assert spec and spec.loader
            spec.loader.exec_module(mod)
            stats["mocs"] = mod.write_reading_mocs()
        except Exception as e2:
            stats["mocs"] = {"ok": False, "error": str(e2)}

    stats["finished_at"] = _now_iso()
    print(json.dumps(stats, indent=2, default=str))
    ok = bool(stats.get("resource_write", {}).get("ok")) and bool(
        stats.get("market_write", {}).get("ok")
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
