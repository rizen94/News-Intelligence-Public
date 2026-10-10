#!/usr/bin/env python3
"""Seed priority politics/finance Situation hubs (reader spine).

Order:
  1) US institutions (politics)
  2) China–trade–tech (finance — corpus lives in markets/tariffs/rare earths)
  3) Ukraine hub promotion (politics russia_ukraine)
  4) Climate–resource policy (politics + cross-link finance resource_movements)

Usage:
  set -a && source ../.env && set +a
  export NEWS_INTEL_VAULT_WRITE=true NI_VAULT_NOTES_ENABLED=true
  export NEWS_INTEL_VAULT_PATH=/mnt/news-intelligence-vault
  PYTHONPATH=. python scripts/seed_priority_situations_vault.py --force --sync
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
logger = logging.getLogger("seed_priority_situations_vault")

# 1) US executive / institutions
US_KEY = "us_institutions"
US_TITLE = "US institutions — White House, DOJ, Congress, courts (situation)"
US_MEMBERS = (
    7709,  # Blanche AG confirm
    5505,  # Blanche scraps anti-weaponization fund
    7697,  # Senate confirms Blanche
    12409,  # SCOTUS E Jean Carroll
    13950,  # SCOTUS Prop 50
    9653,  # WH press secretary exit (one Leavitt arc)
    11950,  # Pentagon / ROK exercises
    5343,  # Senate scrutiny / slush fund
    7426,  # Fed governor / SCOTUS
    5103,  # Cabinet Camp David
    11029,  # WH / Senate campaign
)
US_SEEDS = (
    23063,  # White House (subject)
    592281,  # Department of Justice
    983,  # Congress
    35465,  # Donald J. Trump
    38795,  # Todd Blanche (if missing, write_cluster_hub skips wikilink)
)

# 2) China–trade–tech (finance corpus)
CHINA_KEY = "china_trade_tech"
CHINA_TITLE = "China–trade–tech — tariffs, rare earths, chips (situation)"
CHINA_MEMBERS = (
    19736,  # oil / geopolitics / tariffs
    19746,  # oil / tariff uncertainty
    5229,  # Clarida K-shaped / tariffs
    7333,  # rare earth rally
    7203,  # rare earth stockpile
    5879,  # war + tariffs / fuel costs
    5714,  # China gold buying / US-China tensions
    5577,  # Fed agenda / tariff uncertainty
)
CHINA_SEEDS = (
    1058,  # China
    3286,  # Taiwan
    25135,  # Heavy rare earths
    2555,  # Lynas Rare Earths
    10854,  # rare earths
    6134,  # rare earth elements
)

# 3) Ukraine — promote russia_ukraine
UKRAINE_KEY = "russia_ukraine"
UKRAINE_TITLE = "Russia / Ukraine (situation)"
UKRAINE_MEMBERS = (
    12444,  # Trump 2026 / Ukraine
    5272,  # Ukraine missile / Iran overlap
    3983,  # Zelenskyy domestic / global
    3995,  # Zelenskyy influence
    11028,  # Zelenskyy European integration
    7043,  # NATO Ukraine defenses
    8481,  # Ukraine conflict context
)
UKRAINE_SEEDS = (
    5224,  # Ukraine
    4287,  # Russia
    5556,  # Putin
    25248,  # Zelenskyy
    3374,  # Nato
    35465,  # Trump
)

# 4) Climate–resource policy
CLIMATE_KEY = "climate_resource_policy"
CLIMATE_TITLE = "Climate–resource policy — adaptation, energy, critical minerals (situation)"
CLIMATE_MEMBERS = (
    11030,  # UK climate adaptation
    12380,  # Hurricane / climate infrastructure
    8044,  # Wildfires / policy
    6735,  # Extreme heat / services
    12228,  # Europe wildfires
)
CLIMATE_SEEDS = (
    877,  # climate change
    659283,  # EPA
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strip_nuls(text: str | None) -> str:
    if not text:
        return ""
    return text.replace("\x00", "")


def _dedupe_bullets(bullets: list[str], *, limit: int = 14) -> list[str]:
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


def existing_storyline_ids(schema: str, ids: tuple[int, ...]) -> list[int]:
    from shared.database.connection import get_db_connection_context

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT id FROM {schema}.storylines WHERE id = ANY(%s)",
                (list(ids),),
            )
            found = {int(r[0]) for r in (cur.fetchall() or [])}
    return [i for i in ids if i in found]


def existing_entity_ids(schema: str, ids: tuple[int, ...]) -> list[int]:
    from shared.database.connection import get_db_connection_context

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT id FROM {schema}.entity_canonical WHERE id = ANY(%s)",
                (list(ids),),
            )
            found = {int(r[0]) for r in (cur.fetchall() or [])}
    return [i for i in ids if i in found]


def fetch_theme_articles(
    schema: str,
    patterns: list[str],
    *,
    days: int = 60,
    limit: int = 12,
) -> list[str]:
    from shared.database.connection import get_db_connection_context

    like = " OR ".join(["a.title ILIKE %s"] * len(patterns))
    params: list[Any] = [int(days)] + [f"%{p}%" for p in patterns] + [int(limit)]
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


def fetch_member_timeline(
    schema: str, storyline_ids: list[int], *, limit: int = 14
) -> list[str]:
    from shared.database.connection import get_db_connection_context

    if not storyline_ids:
        return []
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT a.published_at::date, a.title, a.id, sa.storyline_id
                FROM {schema}.storyline_articles sa
                JOIN {schema}.articles a ON a.id = sa.article_id
                WHERE sa.storyline_id = ANY(%s)
                  AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                ORDER BY a.published_at DESC NULLS LAST
                LIMIT %s
                """,
                (list(storyline_ids), limit * 3),
            )
            rows = cur.fetchall() or []
    out: list[str] = []
    seen: set[int] = set()
    for pub, title, aid, sid in rows:
        if int(aid) in seen:
            continue
        seen.add(int(aid))
        day = pub.isoformat() if pub else "undated"
        out.append(
            f"- {day} — {(title or 'Untitled').strip()[:140]} "
            f"(article:{aid}, storyline:{sid})"
        )
        if len(out) >= limit:
            break
    return out


def build_brief(
    *,
    label: str,
    now: str,
    why: str,
    watch: str,
    timeline: list[str],
    also: str | None = None,
) -> str:
    evid = "\n".join(timeline[:10]) if timeline else "- _(no recent corpus titles)_"
    parts = [
        f"**CURRENT BRIEF: {label}**",
        "",
        now,
        "",
        why,
        "",
        watch,
        "",
        "**Corpus timeline:**",
        evid,
    ]
    if also:
        parts.extend(["", also])
    return "\n".join(parts)


def persist_brief(
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
        "brief_fingerprint": f"seed_priority_{cluster_key}_{now[:10]}",
        "brief_source": "seed_priority_situations_vault",
        "scorer": "vault_cluster_hub_v1",
    }
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "cluster_key": cluster_key,
            "brief_chars": len(brief_clean),
        }

    root = vault_root()
    path = root / vault_path
    body_for_pg = ""
    if path.is_file():
        existing = path.read_text(encoding="utf-8")
        if re.search(r"brief_locked:\s*(true|1|yes)", existing, re.I):
            return {"ok": True, "skipped": True, "reason": "brief_locked", "path": vault_path}
        patched = patch_auto_sections(existing, brief=brief_clean[:1200])
        if force or "<!-- ni:auto:brief -->" in existing:
            path.write_text(_strip_nuls(patched or existing), encoding="utf-8")
        body_for_pg = _strip_nuls(path.read_text(encoding="utf-8"))
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
        "members": len(member_storyline_ids),
    }


def seed_one(
    *,
    domain_key: str,
    cluster_key: str,
    title: str,
    members: list[int],
    seeds: list[int],
    significance: str,
    tags: list[str],
    brief: str,
    force: bool,
    dry_run: bool,
) -> dict[str, Any]:
    from services.vault_cluster_hub_service import write_cluster_hub
    from shared.vault_note_contract import cluster_object_id, cluster_vault_rel_path

    wr = write_cluster_hub(
        domain_key=domain_key,
        cluster_key=cluster_key,
        title=title,
        member_storyline_ids=members,
        seed_entity_ids=seeds,
        significance=significance,
        tags=tags,
        force=force,
        dry_run=dry_run,
    )
    path = str(wr.get("vault_path") or cluster_vault_rel_path(cluster_key))
    oid = int(wr.get("object_id") or cluster_object_id(cluster_key))
    br = persist_brief(
        domain_key=domain_key,
        cluster_key=cluster_key,
        vault_path=path,
        title=title,
        object_id=oid,
        brief=brief,
        member_storyline_ids=members,
        seed_entity_ids=seeds,
        tags=tags,
        force=force,
        dry_run=dry_run,
    )
    return {"write": wr, "brief": br, "path": path, "members": members}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sync", action="store_true")
    args = parser.parse_args()

    os.environ.setdefault("NEWS_INTEL_VAULT_PATH", "/mnt/news-intelligence-vault")
    os.environ.setdefault("NEWS_INTEL_VAULT_WRITE", "true")
    os.environ.setdefault("NI_VAULT_NOTES_ENABLED", "true")
    os.environ.setdefault("NI_VAULT_CLUSTER_HUBS_ENABLED", "true")

    stats: dict[str, Any] = {"ok": True, "started_at": _now_iso(), "hubs": {}}

    # --- 1 US institutions ---
    us_m = existing_storyline_ids("politics", US_MEMBERS)
    us_s = existing_entity_ids("politics", US_SEEDS)
    us_tl = _dedupe_bullets(
        fetch_theme_articles(
            "politics",
            [
                "White House",
                "Attorney General",
                "Supreme Court",
                "Pentagon",
                "State Department",
                "Senate confirm",
            ],
            days=75,
            limit=12,
        )
        + fetch_member_timeline("politics", us_m, limit=10),
        limit=14,
    )
    stats["hubs"][US_KEY] = seed_one(
        domain_key="politics",
        cluster_key=US_KEY,
        title=US_TITLE,
        members=us_m,
        seeds=us_s,
        significance=(
            "US executive and institutional track: White House, DOJ/AG, Congress, "
            "courts, Pentagon. Indexes curated episodes only. Cross-link "
            "[[donald_j_trump]] living entity and Just Security / State Dept feeds."
        ),
        tags=[
            "cluster",
            "domain/politics",
            "theme/us-institutions",
            "theme/executive",
            "priority/high",
        ],
        brief=build_brief(
            label="US institutions",
            now=(
                "NOW: Corpus centers on AG confirmation/fund fights, White House "
                "personnel churn, Supreme Court emergency petitions, and Pentagon "
                "posture orders — institutional capacity under a second Trump term."
                if not us_tl
                else "NOW: " + "; ".join(
                    re.sub(r"^- \S+ — ", "", t).split(" (article:")[0] for t in us_tl[:3]
                )
                + "."
            ),
            why=(
                "WHY IT MATTERS: Reader Situations should track durable institutions "
                "(WH/State/DOJ/courts), not single personnel headlines. This hub is "
                "the shelf for executive-branch continuity and legal conflict."
            ),
            watch=(
                "WATCH: AG/DOJ directives; SCOTUS emergency docket vs Trump; "
                "State Department diplomatic lines; Pentagon exercise posture; "
                "Senate confirmation fights."
            ),
            timeline=us_tl,
            also="See also [[donald_j_trump]] · [[iran_war]] · [[russia_ukraine]].",
        ),
        force=args.force,
        dry_run=args.dry_run,
    )

    # --- 2 China–trade–tech ---
    ch_m = existing_storyline_ids("finance", CHINA_MEMBERS)
    ch_s = existing_entity_ids("finance", CHINA_SEEDS)
    ch_tl = _dedupe_bullets(
        fetch_theme_articles(
            "finance",
            ["China", "Taiwan", "tariff", "rare earth", "semiconductor", "export"],
            days=75,
            limit=12,
        )
        + fetch_theme_articles(
            "politics",
            ["China", "Taiwan", "tariff", "rare earth", "Xi "],
            days=75,
            limit=8,
        )
        + fetch_member_timeline("finance", ch_m, limit=10),
        limit=14,
    )
    stats["hubs"][CHINA_KEY] = seed_one(
        domain_key="finance",
        cluster_key=CHINA_KEY,
        title=CHINA_TITLE,
        members=ch_m,
        seeds=ch_s,
        significance=(
            "Multipolar trade/tech Situation: tariffs, rare-earth stockpiles, "
            "chip/semiconductor exposure, China gold/FX overlays. Finance-hosted "
            "because politics China storylines are thin; cross-link "
            "[[resource_movements]] and politics think-tank intake."
        ),
        tags=[
            "cluster",
            "domain/finance",
            "theme/china-trade-tech",
            "theme/tariffs",
            "theme/rare-earths",
            "priority/high",
        ],
        brief=build_brief(
            label="China–trade–tech",
            now=(
                "NOW: Tariff uncertainty and rare-earth/defense-stockpile headlines "
                "sit beside oil and gold moves as the US–China risk channel."
                if not ch_tl
                else "NOW: " + "; ".join(
                    re.sub(r"^- \S+ — ", "", t).split(" (article:")[0] for t in ch_tl[:3]
                )
                + "."
            ),
            why=(
                "WHY IT MATTERS: Trade/tech controls and critical minerals are the "
                "industrial half of resource geopolitics — distinct from Hormuz oil "
                "but often co-moving with [[resource_movements]] and [[market_trends]]."
            ),
            watch=(
                "WATCH: new tariff tranches; rare-earth export/stockpile language; "
                "chip/semiconductor partnership risk; China gold/central-bank buying; "
                "Taiwan strait headlines in politics wires."
            ),
            timeline=ch_tl,
            also="See also [[resource_movements]] · [[market_trends]] · [[us_institutions]].",
        ),
        force=args.force,
        dry_run=args.dry_run,
    )

    # --- 3 Ukraine promotion ---
    uk_m = existing_storyline_ids("politics", UKRAINE_MEMBERS)
    uk_s = existing_entity_ids("politics", UKRAINE_SEEDS)
    uk_tl = _dedupe_bullets(
        fetch_theme_articles(
            "politics",
            ["Ukraine", "Zelensky", "Zelenskyy", "Kyiv", "NATO"],
            days=90,
            limit=12,
        )
        + fetch_member_timeline("politics", uk_m, limit=10),
        limit=14,
    )
    stats["hubs"][UKRAINE_KEY] = seed_one(
        domain_key="politics",
        cluster_key=UKRAINE_KEY,
        title=UKRAINE_TITLE,
        members=uk_m,
        seeds=uk_s,
        significance=(
            "Promoted Russia/Ukraine Situation: replaces thin auto members with "
            "curated Zelenskyy/Trump/NATO episodes. Long-track multipolar conflict "
            "alongside [[iran_war]]."
        ),
        tags=[
            "cluster",
            "domain/politics",
            "theme/ukraine",
            "theme/multipolar",
            "priority/high",
        ],
        brief=build_brief(
            label="Russia / Ukraine",
            now=(
                "NOW: Ukraine remains a US agenda and European-integration pressure "
                "point; missile/aid language co-occurs with other war theaters."
                if not uk_tl
                else "NOW: " + "; ".join(
                    re.sub(r"^- \S+ — ", "", t).split(" (article:")[0] for t in uk_tl[:3]
                )
                + "."
            ),
            why=(
                "WHY IT MATTERS: Distinct from Iran/Hormuz but shares US presidential "
                "bandwidth and NATO posture. Keep this Situation as the Ukraine shelf "
                "so morning prime does not bury it inside kitchen-sink magnets."
            ),
            watch=(
                "WATCH: US aid/agenda language; Zelenskyy domestic vs diplomatic track; "
                "NATO defense boosts; spillover titles that only name-check Ukraine "
                "(exclude from hub)."
            ),
            timeline=uk_tl,
            also="See also [[iran_war]] · [[us_institutions]] · [[inflation_iran_war]].",
        ),
        force=args.force,
        dry_run=args.dry_run,
    )

    # --- 4 Climate–resource policy ---
    cl_m = existing_storyline_ids("politics", CLIMATE_MEMBERS)
    cl_s = existing_entity_ids("politics", CLIMATE_SEEDS)
    cl_tl = _dedupe_bullets(
        fetch_theme_articles(
            "politics",
            [
                "climate",
                "carbon",
                "EPA",
                "emissions",
                "wildfire",
                "critical mineral",
                "net zero",
            ],
            days=90,
            limit=12,
        )
        + fetch_theme_articles(
            "finance",
            ["climate", "carbon", "critical mineral", "renewable", "LNG"],
            days=75,
            limit=8,
        )
        + fetch_member_timeline("politics", cl_m, limit=8),
        limit=14,
    )
    stats["hubs"][CLIMATE_KEY] = seed_one(
        domain_key="politics",
        cluster_key=CLIMATE_KEY,
        title=CLIMATE_TITLE,
        members=cl_m,
        seeds=cl_s,
        significance=(
            "Climate and resource-policy Situation for adaptation, extreme weather "
            "governance, and critical-minerals framing. Cross-link finance "
            "[[resource_movements]] (oil/metals) — politics holds policy; finance "
            "holds price/supply."
        ),
        tags=[
            "cluster",
            "domain/politics",
            "theme/climate",
            "theme/resource-geopolitics",
            "priority/high",
        ],
        brief=build_brief(
            label="Climate–resource policy",
            now=(
                "NOW: Extreme-weather and adaptation governance titles dominate the "
                "thin politics climate shelf; industrial minerals stay on finance."
                if not cl_tl
                else "NOW: " + "; ".join(
                    re.sub(r"^- \S+ — ", "", t).split(" (article:")[0] for t in cl_tl[:3]
                )
                + "."
            ),
            why=(
                "WHY IT MATTERS: New Carbon Brief / E&E / Climate.gov feeds need a "
                "Situation home. Policy and adaptation belong here; oil/metals price "
                "action belongs on [[resource_movements]]."
            ),
            watch=(
                "WATCH: EPA/regulatory fights; adaptation funding language; "
                "critical-mineral policy; LNG/export climate framing; avoid UK "
                "party-climate spat duplicates."
            ),
            timeline=cl_tl,
            also="See also [[resource_movements]] · [[china_trade_tech]] · [[guardian_environment]].",
        ),
        force=args.force,
        dry_run=args.dry_run,
    )

    if args.sync and not args.dry_run:
        try:
            from pathlib import Path

            from scripts.vault_quality_cleanup import write_reading_mocs
            from services.vault_bridge_service import vault_root
            from services.vault_tag_link_sync_service import sync_vault_file

            root = vault_root()
            paths = [
                str(h.get("path") or "")
                for h in stats["hubs"].values()
                if h.get("path")
            ]
            sync_results = []
            for p in paths:
                if not p:
                    continue
                sync_results.append(sync_vault_file(root / p))
            write_reading_mocs()
            stats["sync"] = {"paths": paths, "results": sync_results, "mocs": True}
        except Exception as e:
            logger.exception("sync failed")
            stats["sync_error"] = str(e)

    print(json.dumps(stats, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
