#!/usr/bin/env python3
"""Seed distinct vault arcs outside the Iran/Gaza cluster.

Package:
  - Ukraine #12444 (+ Putin / Zelenskyy enrichment)
  - Farage + Reform small boats #5473 (+ Clacton gifts #10605)
  - Venezuela BoE gold #10523
  - AI rogue models #6649 (+ OpenAI)
  - Todd Blanche AG #7709 (+ anti-weaponization fund #5505)
"""

from __future__ import annotations

import json
import logging
import os
import sys

_API_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _API_ROOT not in sys.path:
    sys.path.insert(0, _API_ROOT)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("seed_distinct_arcs")

STORYLINE_IDS = (
    12444,  # Ukraine / Trump 2026 agenda
    5473,  # Reform navy / small boats
    10605,  # Farage Clacton gifts
    5703,  # Farage £5m gift
    10523,  # Venezuela BoE gold
    6649,  # OpenAI/Anthropic rogue UK watchdog
    6697,  # OpenAI/Anthropic rogue follow-on
    7709,  # Todd Blanche AG confirmation
    5505,  # Blanche scraps anti-weaponization fund
)

# Prefer clean display names for vault paths
ENTITY_SPECS = (
    (28441, "Nigel Farage"),
    (3633, "OpenAI"),
    (5503, "Venezuela"),
    (3899, "Xi Jinping"),
    (38795, "Todd Blanche"),
    (572647, "Department of Homeland Security"),
    (5556, "Vladimir Putin"),
    (25248, "Volodymyr Zelenskyy"),
    (1884, "Gavin Newsom"),
)

CONNECTION_SEEDS = (
    (28441, 35465, "Nigel Farage", "Donald J. Trump"),  # Farage ↔ Trump
    (5556, 25248, "Vladimir Putin", "Volodymyr Zelenskyy"),
    (3633, 35465, "OpenAI", "Donald J. Trump"),  # weak but useful shelf; skip if Trump missing
)


def main() -> int:
    os.environ.setdefault("NEWS_INTEL_VAULT_PATH", "/mnt/news-intelligence-vault")
    os.environ.setdefault("NEWS_INTEL_VAULT_WRITE", "true")
    os.environ.setdefault("DB_PORT", os.environ.get("DB_PORT", "6432"))

    from services.vault_bridge_service import (
        _render_frontmatter,
        vault_root,
        vault_write_enabled,
    )
    from services.vault_notes_preseed_service import (
        build_connection_note,
        build_entity_note_markdown,
        build_storyline_event_note,
        fetch_entity_profile_basics,
        fetch_recent_article_bullets,
        _write_file,
    )
    from services.vault_notes_registry_service import upsert_vault_note
    from shared.database.connection import get_db_connection_context
    from shared.vault_note_contract import (
        connection_vault_rel_path,
        entity_vault_rel_path,
        storyline_vault_rel_path,
    )

    if not vault_write_enabled():
        logger.error("vault write disabled")
        return 1

    domain = "politics"
    stats = {
        "entities": 0,
        "storylines": 0,
        "connections": 0,
        "paths": [],
        "vault_root": str(vault_root()),
    }

    # --- Entities ---
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for eid, display in ENTITY_SPECS:
                cur.execute(
                    """
                    SELECT ec.id, ec.canonical_name, ec.entity_type,
                           COALESCE((
                             SELECT COUNT(*)::int FROM politics.article_entities ae
                             WHERE ae.canonical_entity_id = ec.id
                           ), 0),
                           LEFT(COALESCE(ec.description, ''), 800)
                    FROM politics.entity_canonical ec
                    WHERE ec.id = %s
                    """,
                    (eid,),
                )
                row = cur.fetchone()
                if not row:
                    logger.warning("entity %s missing", eid)
                    continue
                ent = {
                    "id": int(row[0]),
                    "name": display,
                    "entity_type": row[2],
                    "mentions": int(row[3] or 0),
                    "description": (row[4] or "").strip(),
                }
                basics = fetch_entity_profile_basics(domain, ent["id"])
                bullets = fetch_recent_article_bullets(domain, ent["id"], limit=10)
                md = build_entity_note_markdown(
                    domain_key=domain,
                    entity=ent,
                    basics=basics,
                    timeline_bullets=bullets,
                )
                path = entity_vault_rel_path(display)
                result = _write_file(path, md, force=True)
                if result.get("ok"):
                    stats["entities"] += 1
                    stats["paths"].append(path)
                upsert_vault_note(
                    domain_key=domain,
                    note_type="entity",
                    object_id=ent["id"],
                    vault_path=path,
                    title=display,
                    note_status="note_ready",
                    lifecycle="living" if ent["mentions"] >= 100 else "seeded",
                    mention_count=ent["mentions"],
                    tags=[str(ent.get("entity_type") or "entity"), "distinct_arc_seed"],
                    metadata={"seed_package": "distinct_arcs_v1"},
                )

            # --- Storylines ---
            cur.execute(
                """
                SELECT id, title, COALESCE(article_count, 0), status,
                       LEFT(COALESCE(description, analysis_summary, ''), 1200),
                       LEFT(COALESCE(canonical_narrative, ''), 2000)
                FROM politics.storylines
                WHERE id = ANY(%s)
                """,
                (list(STORYLINE_IDS),),
            )
            for r in cur.fetchall():
                sl = {
                    "id": int(r[0]),
                    "title": r[1] or f"Storyline {r[0]}",
                    "article_count": int(r[2] or 0),
                    "status": r[3],
                    "description": (r[4] or "").strip(),
                    "canonical_narrative": (r[5] or "").strip(),
                }
                path = storyline_vault_rel_path(domain, sl["id"], sl["title"])
                md = build_storyline_event_note(domain, sl)
                result = _write_file(path, md, force=True)
                if result.get("ok"):
                    stats["storylines"] += 1
                    stats["paths"].append(path)
                upsert_vault_note(
                    domain_key=domain,
                    note_type="storyline",
                    object_id=sl["id"],
                    vault_path=path,
                    title=sl["title"],
                    note_status="note_ready",
                    lifecycle="seeded",
                    mention_count=sl["article_count"],
                    tags=["storyline", "distinct_arc_seed"],
                    metadata={"seed_package": "distinct_arcs_v1", "status": sl.get("status")},
                )

    # --- Connections (skip OpenAI↔Trump if too forced — keep Farage↔Trump + Putin↔Zelenskyy) ---
    for id_a, id_b, name_a, name_b in (
        (28441, 35465, "Nigel Farage", "Donald J. Trump"),
        (5556, 25248, "Vladimir Putin", "Volodymyr Zelenskyy"),
        (3633, 2990, "OpenAI", "Anthropic"),  # pair the AI labs note
    ):
        # Anthropic id from prior seed was profiled; look up
        if name_b == "Anthropic":
            from shared.database.connection import get_db_connection_context as _ctx

            with _ctx() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id FROM politics.entity_canonical
                        WHERE canonical_name ILIKE 'Anthropic' ORDER BY id LIMIT 1
                        """
                    )
                    row = cur.fetchone()
                    if not row:
                        continue
                    id_b = int(row[0])
        path = connection_vault_rel_path(name_a, name_b)
        md = build_connection_note(
            domain, id_a=id_a, id_b=id_b, name_a=name_a, name_b=name_b
        )
        result = _write_file(path, md, force=True)
        if result.get("ok") and not result.get("skipped"):
            stats["connections"] += 1
            stats["paths"].append(path)
        upsert_vault_note(
            domain_key=domain,
            note_type="connection",
            object_id=min(id_a, id_b),
            object_id_secondary=max(id_a, id_b),
            vault_path=path,
            title=f"{name_a} ↔ {name_b}",
            note_status="note_ready",
            lifecycle="seeded",
            tags=["connection", "distinct_arc_seed"],
            metadata={"seed_package": "distinct_arcs_v1"},
        )

    # Index blurb
    index_rel = "40_Reference/entities/_distinct_arcs_index.md"
    lines = [
        "# Distinct arc seeds (non–Iran/Gaza)",
        "",
        "Ukraine · Reform/Farage boats · Venezuela gold · AI rogue models · Blanche AG",
        "",
        "## Paths",
        "",
    ]
    for p in stats["paths"]:
        lines.append(f"- `{p}`")
    (vault_root() / index_rel).write_text("\n".join(lines) + "\n", encoding="utf-8")
    stats["paths"].append(index_rel)

    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
