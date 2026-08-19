#!/usr/bin/env python3
"""Diagnose why story_continuation finds no episode candidates."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))

from shared.database.connection import get_db_connection_context  # noqa: E402
from shared.domain_registry import resolve_domain_schema  # noqa: E402


def main() -> int:
    out: dict = {"domains": {}, "samples": []}
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for dk in ["politics", "legal", "finance", "medicine"]:
                sch = resolve_domain_schema(dk)
                cur.execute(
                    f"""
                    SELECT
                      count(*) FILTER (
                        WHERE COALESCE(story_kind, '') <> 'container_index'
                          AND COALESCE(is_mega_storyline, false) = false
                          AND status IN ('active', 'dormant', 'emerging')
                      ),
                      count(*) FILTER (
                        WHERE COALESCE(story_kind, '') <> 'container_index'
                          AND COALESCE(is_mega_storyline, false) = false
                          AND anchor_signature IS NOT NULL
                          AND status IN ('active', 'dormant', 'emerging')
                      ),
                      count(*) FILTER (
                        WHERE COALESCE(story_kind, '') <> 'container_index'
                          AND COALESCE(is_mega_storyline, false) = false
                          AND status IN ('active', 'dormant', 'emerging')
                          AND EXISTS (
                            SELECT 1 FROM {sch}.story_entity_index sei
                            WHERE sei.storyline_id = s.id
                          )
                      )
                    FROM {sch}.storylines s
                    """
                )
                ep, signed, sei = cur.fetchone()
                out["domains"][dk] = {
                    "episodes": int(ep),
                    "signed": int(signed),
                    "with_sei": int(sei),
                }

            cur.execute(
                """
                SELECT ce.id, ce.title, ce.source_article_id
                FROM public.chronological_events ce
                WHERE (ce.storyline_id = '' OR ce.storyline_id IS NULL)
                  AND ce.canonical_event_id IS NULL
                  AND ce.source_article_id IS NOT NULL
                  AND EXISTS (
                        SELECT 1 FROM politics.articles a
                        WHERE a.id = ce.source_article_id
                  )
                ORDER BY ce.continuation_checked_at ASC NULLS FIRST, ce.id DESC
                LIMIT 12
                """
            )
            for eid, title, aid in cur.fetchall() or []:
                cur.execute(
                    """
                    SELECT count(DISTINCT sei.storyline_id)
                    FROM politics.article_entities ae
                    JOIN politics.story_entity_index sei
                      ON (
                        lower(sei.entity_name) = lower(ae.entity_name)
                        OR (
                          ae.canonical_entity_id IS NOT NULL
                          AND sei.canonical_entity_id = ae.canonical_entity_id
                        )
                      )
                    JOIN politics.storylines s ON s.id = sei.storyline_id
                    WHERE ae.article_id = %s
                      AND COALESCE(s.story_kind, '') <> 'container_index'
                      AND COALESCE(s.is_mega_storyline, false) = false
                      AND s.status NOT IN ('archived', 'concluded')
                      AND lower(COALESCE(sei.entity_type, 'other')) NOT IN
                          ('subject', 'other', 'location', 'recurring_event')
                    """,
                    (int(aid),),
                )
                n = int((cur.fetchone() or (0,))[0])
                out["samples"].append(
                    {
                        "event_id": int(eid),
                        "article_id": int(aid),
                        "cand_eps": n,
                        "title": (title or "")[:60],
                    }
                )
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
