#!/usr/bin/env python3
"""One-shot: reconcile episodes with bag↔EEL set asymmetry (not just count drift)."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "api"))

env_file = _ROOT / ".env"
if env_file.exists():
    try:
        from dotenv import load_dotenv

        load_dotenv(env_file, override=False)
    except Exception:
        pass


def main() -> int:
    from shared.database.connection import get_db_connection_context
    from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema
    from shared.membership_store import reconcile_derived_bag_from_eel

    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    with get_db_connection_context() as conn:
        cur = conn.cursor()
        for dk in get_pipeline_active_domain_keys():
            sch = resolve_domain_schema(dk)
            cur.execute(
                f"""
                WITH eel_arts AS (
                  SELECT eel.episode_id, ce.source_article_id AS article_id
                  FROM intelligence.event_episode_links eel
                  JOIN public.chronological_events ce ON ce.id = eel.event_id
                  WHERE eel.domain_key = %s
                    AND COALESCE(eel.inference_stage, '') <> 'quarantined'
                    AND ce.source_article_id IS NOT NULL
                ),
                bag_arts AS (
                  SELECT storyline_id AS episode_id, article_id
                  FROM {sch}.storyline_articles
                ),
                bad AS (
                  SELECT episode_id FROM (
                    SELECT episode_id, article_id FROM bag_arts
                    EXCEPT
                    SELECT episode_id, article_id FROM eel_arts
                  ) x
                  UNION
                  SELECT episode_id FROM (
                    SELECT episode_id, article_id FROM eel_arts
                    EXCEPT
                    SELECT episode_id, article_id FROM bag_arts
                  ) y
                )
                SELECT DISTINCT episode_id FROM bad LIMIT %s
                """,
                (dk, limit),
            )
            ids = [int(r[0]) for r in (cur.fetchall() or [])]
            ins = rem = 0
            for eid in ids:
                st = reconcile_derived_bag_from_eel(
                    conn, domain_key=dk, schema=sch, episode_id=eid
                )
                ins += int(st.get("inserted") or 0)
                rem += int(st.get("removed") or 0)
            conn.commit()
            print(f"{dk}: asym_eps={len(ids)} inserted={ins} removed={rem}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
