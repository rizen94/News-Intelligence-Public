#!/usr/bin/env python3
"""One-shot magnet scrub + legal mega demote (ops)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))

from shared.database.connection import get_db_connection_context  # noqa: E402


def main() -> int:
    with get_db_connection_context() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO intelligence.entity_anchor_class
                (domain_key, entity_name, anchor_class, source, metadata)
            VALUES
                (%s, %s, %s, %s, %s::jsonb),
                (%s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (domain_key, entity_name) DO UPDATE SET
                anchor_class = EXCLUDED.anchor_class,
                updated_at = NOW()
            """,
            (
                "politics",
                "cid:2423",
                "hub",
                "magnet_scrub",
                json.dumps({"canonical_hint": "Iran"}),
                "politics",
                "iran",
                "hub",
                "magnet_scrub",
                "{}",
            ),
        )
        # Also store canonical id column when available
        try:
            cur.execute(
                """
                UPDATE intelligence.entity_anchor_class
                SET canonical_entity_id = 2423, updated_at = NOW()
                WHERE domain_key = 'politics' AND entity_name IN ('cid:2423', 'iran')
                """
            )
        except Exception:
            conn.rollback()
            # re-seed without cid column update path
            cur.execute(
                """
                INSERT INTO intelligence.entity_anchor_class
                    (domain_key, entity_name, anchor_class, source, metadata)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (domain_key, entity_name) DO UPDATE SET
                    anchor_class = 'hub', updated_at = NOW()
                """,
                ("politics", "cid:2423", "hub", "magnet_scrub", "{}"),
            )

        cur.execute(
            """
            UPDATE intelligence.event_episode_links
            SET inference_stage = 'quarantined',
                updated_at = NOW(),
                metadata = COALESCE(metadata, '{}'::jsonb)
                    || '{"quarantine_reason":"iran_cid_magnet"}'::jsonb
            WHERE domain_key = 'politics'
              AND episode_id = 3938
              AND inference_stage <> 'quarantined'
              AND (
                matched_anchors = '["cid:2423"]'::jsonb
                OR matched_anchors = '["iran"]'::jsonb
              )
            """
        )
        quarantined = cur.rowcount or 0

        cur.execute(
            """
            UPDATE legal.storylines
            SET story_kind = 'container_index',
                is_mega_storyline = TRUE,
                automation_enabled = FALSE,
                episode_state = COALESCE(episode_state, 'concluded'),
                metadata = COALESCE(metadata, '{}'::jsonb)
                    || '{"assembly_role":"container_index"}'::jsonb,
                updated_at = NOW()
            WHERE id = 4132
            """
        )
        cur.execute("DELETE FROM legal.storyline_articles WHERE storyline_id = 4132")
        stripped = cur.rowcount or 0
        cur.execute(
            "UPDATE legal.storylines SET article_count = 0, total_articles = 0 WHERE id = 4132"
        )

        hubs = {"cid:2423", "iran", "labour", "the labour party"}
        for sid in (3938, 3887, 3884, 3905):
            cur.execute(
                "SELECT anchor_signature FROM politics.storylines WHERE id = %s", (sid,)
            )
            row = cur.fetchone()
            if not row or not row[0]:
                continue
            raw = row[0]
            sig = raw if isinstance(raw, dict) else json.loads(raw)
            ident = [
                t
                for t in list(sig.get("identity") or [])
                if str(t).lower() not in hubs
            ][:8]
            sig["identity"] = ident
            sig["supporting"] = list(sig.get("supporting") or [])[:8]
            cur.execute(
                """
                UPDATE politics.storylines
                SET anchor_signature = %s::jsonb, updated_at = NOW()
                WHERE id = %s
                """,
                (json.dumps(sig), sid),
            )

        conn.commit()
        print(json.dumps({"quarantined_3938": quarantined, "legal_4132_stripped": stripped}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
