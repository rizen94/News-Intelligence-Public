#!/usr/bin/env python3
"""Quarantine event_episode_links that still point at container_index / mega rows."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))

from shared.database.connection import get_db_connection_context  # noqa: E402
from shared.domain_registry import (  # noqa: E402
    get_pipeline_active_domain_keys,
    resolve_domain_schema,
)


def main() -> int:
    total = 0
    demoted = []
    with get_db_connection_context() as conn:
        cur = conn.cursor()
        for dk in get_pipeline_active_domain_keys():
            schema = resolve_domain_schema(dk)
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
            n = cur.rowcount or 0
            if n:
                demoted.append({"domain": dk, "episodes": len(ids), "quarantined": n})
                total += n
        conn.commit()
    print(json.dumps({"total_quarantined": total, "by_domain": demoted}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
