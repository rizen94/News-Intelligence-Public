#!/usr/bin/env python3
"""
Demote never-grew story_continuation_founding orphans → container_index.

A founder "never grew" when it still has ≤1 article membership (and usually
≤1 event_episode_link). These were minted by the founding escape hatch and
should not stay in Mode B candidacy.

Dry-run by default. Apply with --apply.

  PYTHONPATH=api python3 api/scripts/cleanup_never_grew_founders.py --all
  PYTHONPATH=api python3 api/scripts/cleanup_never_grew_founders.py --all --apply
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))

from shared.database.connection import get_db_connection_context  # noqa: E402
from shared.domain_registry import (  # noqa: E402
    get_pipeline_active_domain_keys,
    resolve_domain_schema,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("cleanup_never_grew_founders")


def cleanup_domain(
    domain_key: str,
    *,
    apply: bool,
    max_articles: int,
    min_age_hours: int,
    max_eels: int,
) -> dict:
    schema = resolve_domain_schema(domain_key)
    stats = {
        "domain": domain_key,
        "candidates": 0,
        "demoted": 0,
        "membership_stripped": 0,
        "eels_quarantined": 0,
        "ce_cleared": 0,
    }
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT s.id, s.title, COALESCE(s.article_count, 0)::int,
                       (
                         SELECT COUNT(*)::int
                         FROM intelligence.event_episode_links e
                         WHERE e.domain_key = %s
                           AND e.episode_id = s.id
                           AND e.inference_stage <> 'quarantined'
                       ) AS eel_n
                FROM {schema}.storylines s
                WHERE COALESCE(s.story_kind, '') <> 'container_index'
                  AND COALESCE(s.is_mega_storyline, FALSE) = FALSE
                  AND COALESCE(s.metadata->>'source', '') = 'story_continuation_founding'
                  AND COALESCE(s.article_count, 0) <= %s
                  AND s.created_at < NOW() - (%s || ' hours')::interval
                ORDER BY s.id
                """,
                (domain_key, int(max_articles), str(int(min_age_hours))),
            )
            rows = cur.fetchall() or []
            for sid, title, acount, eel_n in rows:
                if int(eel_n or 0) > int(max_eels):
                    continue
                stats["candidates"] += 1
                logger.info(
                    "[%s] never-grew id=%s arts=%s eels=%s title=%s",
                    domain_key,
                    sid,
                    acount,
                    eel_n,
                    (title or "")[:70],
                )
                if not apply:
                    continue
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
                            {
                                "assembly_role": "container_index",
                                "demote_reason": "never_grew_founding",
                            }
                        ),
                        int(sid),
                    ),
                )
                cur.execute(
                    f"""
                    DELETE FROM {schema}.storyline_articles
                    WHERE storyline_id = %s
                    """,
                    (int(sid),),
                )
                stats["membership_stripped"] += cur.rowcount or 0
                cur.execute(
                    f"""
                    UPDATE {schema}.storylines
                    SET article_count = 0, total_articles = 0, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (int(sid),),
                )
                cur.execute(
                    """
                    UPDATE intelligence.event_episode_links
                    SET inference_stage = 'quarantined',
                        updated_at = NOW(),
                        metadata = COALESCE(metadata, '{}'::jsonb)
                            || '{"quarantine_reason":"never_grew_founding"}'::jsonb
                    WHERE domain_key = %s
                      AND episode_id = %s
                      AND inference_stage <> 'quarantined'
                    """,
                    (domain_key, int(sid)),
                )
                stats["eels_quarantined"] += cur.rowcount or 0
                cur.execute(
                    """
                    UPDATE public.chronological_events
                    SET storyline_id = ''
                    WHERE storyline_id = %s
                    """,
                    (str(int(sid)),),
                )
                stats["ce_cleared"] += cur.rowcount or 0
                stats["demoted"] += 1

            if apply:
                conn.commit()
            else:
                conn.rollback()
    return stats


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--domain")
    p.add_argument("--all", action="store_true")
    p.add_argument("--apply", action="store_true")
    p.add_argument(
        "--max-articles",
        type=int,
        default=1,
        help="Max article_count to treat as never-grew (default 1)",
    )
    p.add_argument(
        "--max-eels",
        type=int,
        default=1,
        help="Max non-quarantined event_episode_links (default 1)",
    )
    p.add_argument(
        "--min-age-hours",
        type=int,
        default=1,
        help="Only demote founders older than this (default 1h)",
    )
    args = p.parse_args()
    domains = (
        list(get_pipeline_active_domain_keys())
        if args.all
        else ([args.domain] if args.domain else [])
    )
    if not domains:
        p.error("Pass --domain KEY or --all")
    out = []
    for dk in domains:
        st = cleanup_domain(
            dk,
            apply=bool(args.apply),
            max_articles=int(args.max_articles),
            min_age_hours=int(args.min_age_hours),
            max_eels=int(args.max_eels),
        )
        out.append(st)
        logger.info("stats %s", st)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
