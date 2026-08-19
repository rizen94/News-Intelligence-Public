#!/usr/bin/env python3
"""Demote overnight cid-pair magnets; quarantine thin-anchor EELs on hot episodes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))

from shared.database.connection import get_db_connection_context  # noqa: E402

# episode_id -> (domain_key, schema, reason)
DEMOTE = {
    4584: ("politics", "politics", "cid_pair_magnet_1518_1848"),
    3852: ("legal", "legal", "scotus_cid_sprawl"),
    3802: ("legal", "legal", "high_eel_legal_magnet"),
}


def _demote(cur, schema: str, dk: str, sid: int, reason: str) -> int:
    cur.execute(
        f"""
        UPDATE {schema}.storylines
        SET story_kind = 'container_index',
            is_mega_storyline = TRUE,
            automation_enabled = FALSE,
            episode_state = COALESCE(episode_state, 'concluded'),
            metadata = COALESCE(metadata, '{{}}'::jsonb) || %s::jsonb,
            updated_at = NOW()
        WHERE id = %s
        """,
        (json.dumps({"assembly_role": "container_index", "demote_reason": reason}), sid),
    )
    cur.execute(f"DELETE FROM {schema}.storyline_articles WHERE storyline_id = %s", (sid,))
    cur.execute(
        f"UPDATE {schema}.storylines SET article_count = 0, total_articles = 0 WHERE id = %s",
        (sid,),
    )
    cur.execute(
        """
        UPDATE intelligence.event_episode_links
        SET inference_stage = 'quarantined',
            updated_at = NOW(),
            metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
        WHERE domain_key = %s AND episode_id = %s AND inference_stage <> 'quarantined'
        """,
        (json.dumps({"quarantine_reason": reason}), dk, sid),
    )
    return cur.rowcount or 0


def main() -> int:
    with get_db_connection_context() as conn:
        cur = conn.cursor()
        out = {}
        for sid, (dk, schema, reason) in DEMOTE.items():
            out[f"{dk}:{sid}"] = _demote(cur, schema, dk, sid, reason)

        # Quarantine ≤2-anchor EELs on any episode with ≥8 active links (magnet smell)
        cur.execute(
            """
            WITH hot AS (
                SELECT episode_id, domain_key
                FROM intelligence.event_episode_links
                WHERE inference_stage <> 'quarantined'
                GROUP BY episode_id, domain_key
                HAVING COUNT(*) >= 8
            )
            UPDATE intelligence.event_episode_links e
            SET inference_stage = 'quarantined',
                updated_at = NOW(),
                metadata = COALESCE(e.metadata, '{}'::jsonb)
                    || '{"quarantine_reason":"thin_anchor_on_hot_episode"}'::jsonb
            FROM hot h
            WHERE e.episode_id = h.episode_id
              AND e.domain_key = h.domain_key
              AND e.inference_stage <> 'quarantined'
              AND jsonb_typeof(e.matched_anchors) = 'array'
              AND jsonb_array_length(e.matched_anchors) <= 2
              AND NOT EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements_text(e.matched_anchors) t(tok)
                    WHERE tok !~ '^cid:'
                )
            """
        )
        out["thin_cid_only_quarantined"] = cur.rowcount or 0

        # Re-run container EEL quarantine
        for dk, schema in (
            ("politics", "politics"),
            ("legal", "legal"),
            ("finance", "finance"),
            ("medicine", "medicine"),
            ("artificial-intelligence", "artificial_intelligence"),
        ):
            cur.execute(
                f"""
                SELECT id FROM {schema}.storylines
                WHERE COALESCE(story_kind, '') = 'container_index'
                   OR COALESCE(is_mega_storyline, FALSE) = TRUE
                """
            )
            ids = [int(r[0]) for r in (cur.fetchall() or [])]
            if not ids:
                continue
            cur.execute(
                """
                UPDATE intelligence.event_episode_links
                SET inference_stage = 'quarantined',
                    updated_at = NOW(),
                    metadata = COALESCE(metadata, '{}'::jsonb)
                        || '{"quarantine_reason":"target_is_container"}'::jsonb
                WHERE domain_key = %s
                  AND episode_id = ANY(%s)
                  AND inference_stage <> 'quarantined'
                """,
                (dk, ids),
            )
            out[f"container_eel_{dk}"] = cur.rowcount or 0

        conn.commit()
        print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
