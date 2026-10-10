#!/usr/bin/env python3
"""Quarantine thin single-anchor event_episode_links on known magnet episodes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))

from shared.database.connection import get_db_connection_context  # noqa: E402

# High-link politics magnets from overnight drain
DEFAULT_EPISODES = (3905, 3884, 3887, 3822, 3856, 3938)


def main() -> int:
    episodes = [int(x) for x in (sys.argv[1:] or DEFAULT_EPISODES)]
    with get_db_connection_context() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE intelligence.event_episode_links
            SET inference_stage = 'quarantined',
                updated_at = NOW(),
                metadata = COALESCE(metadata, '{}'::jsonb)
                    || '{"quarantine_reason":"single_anchor_magnet"}'::jsonb
            WHERE domain_key = 'politics'
              AND episode_id = ANY(%s)
              AND inference_stage <> 'quarantined'
              AND jsonb_typeof(matched_anchors) = 'array'
              AND jsonb_array_length(matched_anchors) <= 1
            """,
            (list(episodes),),
        )
        n = cur.rowcount or 0
        # Cap remaining magnet signatures
        hubs = {
            "cid:2423",
            "iran",
            "labour",
            "the labour party",
            "cid:513558",  # climate magnet single-cid if still present
        }
        capped = 0
        for sid in episodes:
            cur.execute(
                "SELECT anchor_signature FROM politics.storylines WHERE id = %s",
                (sid,),
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
            ][:6]
            sig["identity"] = ident
            sig["supporting"] = list(sig.get("supporting") or [])[:6]
            cur.execute(
                """
                UPDATE politics.storylines
                SET anchor_signature = %s::jsonb, updated_at = NOW()
                WHERE id = %s
                """,
                (json.dumps(sig), sid),
            )
            capped += 1
        conn.commit()
        print(json.dumps({"quarantined_single_anchor": n, "signatures_capped": capped}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
