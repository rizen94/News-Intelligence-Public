#!/usr/bin/env python3
"""Seed Trump/hub cid anchors + demote legal/politics signature sprawl magnets."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))

from shared.database.connection import get_db_connection_context  # noqa: E402

HUB_SEEDS = [
    ("politics", "cid:2", 2, "Donald Trump"),
    ("politics", "donald trump", 2, "Donald Trump"),
    ("politics", "president donald trump", 2, "Donald Trump"),
    ("legal", "cid:2", 2, "Donald Trump"),
    ("legal", "donald trump", 2, "Donald Trump"),
    ("legal", "president donald trump", 2, "Donald Trump"),
    ("politics", "emergency services", None, "generic hub"),
]

# Over-broad signature bags (legal Trump magnets + politics emergency/global)
DEMOTE = {
    "legal": {
        3856: "trump_cid_sprawl",
        3871: "tariff_cid_sprawl",
        3817: "trump_nimby_sprawl",
    },
    "politics": {
        3942: "emergency_services_magnet",
        3992: "global_tensions_sprawl",
    },
}


def main() -> int:
    with get_db_connection_context() as conn:
        cur = conn.cursor()
        seeded = 0
        for dk, name, cid, hint in HUB_SEEDS:
            cur.execute(
                """
                INSERT INTO intelligence.entity_anchor_class
                    (domain_key, entity_name, canonical_entity_id, anchor_class, source, metadata)
                VALUES (%s, %s, %s, 'hub', 'magnet_scrub', %s::jsonb)
                ON CONFLICT (domain_key, entity_name) DO UPDATE SET
                    anchor_class = 'hub',
                    canonical_entity_id = COALESCE(EXCLUDED.canonical_entity_id, intelligence.entity_anchor_class.canonical_entity_id),
                    updated_at = NOW()
                """,
                (dk, name, cid, json.dumps({"hint": hint})),
            )
            seeded += 1

        demoted = {}
        for dk, mapping in DEMOTE.items():
            schema = {
                "politics": "politics",
                "legal": "legal",
                "finance": "finance",
                "medicine": "medicine",
            }.get(dk, dk.replace("-", "_"))
            for sid, reason in mapping.items():
                cur.execute(
                    f"""
                    UPDATE {schema}.storylines
                    SET story_kind = 'container_index',
                        is_mega_storyline = TRUE,
                        automation_enabled = FALSE,
                        episode_state = COALESCE(episode_state, 'concluded'),
                        metadata = COALESCE(metadata, '{{}}'::jsonb)
                            || %s::jsonb,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (
                        json.dumps(
                            {"assembly_role": "container_index", "demote_reason": reason}
                        ),
                        sid,
                    ),
                )
                cur.execute(
                    f"DELETE FROM {schema}.storyline_articles WHERE storyline_id = %s",
                    (sid,),
                )
                cur.execute(
                    f"""
                    UPDATE {schema}.storylines
                    SET article_count = 0, total_articles = 0 WHERE id = %s
                    """,
                    (sid,),
                )
                cur.execute(
                    """
                    UPDATE intelligence.event_episode_links
                    SET inference_stage = 'quarantined',
                        updated_at = NOW(),
                        metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                    WHERE domain_key = %s
                      AND episode_id = %s
                      AND inference_stage <> 'quarantined'
                    """,
                    (json.dumps({"quarantine_reason": reason}), dk, sid),
                )
                demoted[f"{dk}:{sid}"] = cur.rowcount or 0

        # Cap remaining legal signatures: strip cid:2 / trump hubs, max 6 identity
        hubs = {
            "cid:2",
            "donald trump",
            "president donald trump",
            "emergency services",
        }
        capped = 0
        for schema, dk in (("legal", "legal"), ("politics", "politics")):
            cur.execute(
                f"""
                SELECT id, anchor_signature FROM {schema}.storylines
                WHERE COALESCE(story_kind, '') <> 'container_index'
                  AND anchor_signature IS NOT NULL
                  AND jsonb_array_length(COALESCE(anchor_signature->'identity', '[]'::jsonb)) > 6
                ORDER BY id DESC
                LIMIT 40
                """
            )
            for sid, raw in cur.fetchall() or []:
                sig = raw if isinstance(raw, dict) else json.loads(raw)
                ident = [
                    t
                    for t in list(sig.get("identity") or [])
                    if str(t).lower() not in hubs
                ][:6]
                sig["identity"] = ident
                sig["supporting"] = list(sig.get("supporting") or [])[:6]
                cur.execute(
                    f"""
                    UPDATE {schema}.storylines
                    SET anchor_signature = %s::jsonb, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (json.dumps(sig), int(sid)),
                )
                capped += 1

        conn.commit()
        print(
            json.dumps(
                {"hubs_seeded": seeded, "demoted_links": demoted, "signatures_capped": capped},
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
