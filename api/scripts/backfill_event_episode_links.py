#!/usr/bin/env python3
"""
Backfill intelligence.event_episode_links from existing storyline_articles
+ chronological_events for signature-locked (non-container) episodes.

Dry-run by default.

  PYTHONPATH=api python3 api/scripts/backfill_event_episode_links.py --domain politics --dry-run
  PYTHONPATH=api python3 api/scripts/backfill_event_episode_links.py --all --apply --limit-episodes 200
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
from shared.episode_attach_gate import (  # noqa: E402
    allow_event_episode_attach,
    insert_event_episode_link,
    lock_episode_signature,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("backfill_event_episode_links")


def backfill_domain(
    domain_key: str,
    *,
    apply: bool,
    limit_episodes: int,
    max_articles_per_episode: int,
    bag_orphans_only: bool = False,
) -> dict:
    schema = resolve_domain_schema(domain_key)
    stats = {
        "domain": domain_key,
        "episodes": 0,
        "pairs_checked": 0,
        "linked": 0,
        "rejected": 0,
        "skipped_no_events": 0,
        "bag_orphans_only": bag_orphans_only,
    }
    with get_db_connection_context() as conn:
        orphan_filter = ""
        if bag_orphans_only:
            orphan_filter = f"""
                  AND EXISTS (
                    SELECT 1 FROM {schema}.storyline_articles sa
                    WHERE sa.storyline_id = s.id
                  )
                  AND NOT EXISTS (
                    SELECT 1 FROM intelligence.event_episode_links eel
                    WHERE eel.episode_id = s.id
                      AND eel.domain_key = %s
                      AND eel.inference_stage <> 'quarantined'
                  )
            """
        sig_filter = "" if bag_orphans_only else "AND s.signature_locked_at IS NOT NULL"
        with conn.cursor() as cur:
            params: list = [domain_key] if bag_orphans_only else []
            params.append(int(limit_episodes))
            cur.execute(
                f"""
                SELECT s.id
                FROM {schema}.storylines s
                WHERE COALESCE(s.story_kind, '') <> 'container_index'
                  AND COALESCE(s.is_mega_storyline, FALSE) = FALSE
                  AND s.merged_into_id IS NULL
                  {sig_filter}
                  {orphan_filter}
                ORDER BY s.updated_at DESC NULLS LAST
                LIMIT %s
                """,
                tuple(params),
            )
            episode_ids = [int(r[0]) for r in (cur.fetchall() or [])]

        for episode_id in episode_ids:
            stats["episodes"] += 1
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT sa.article_id
                    FROM {schema}.storyline_articles sa
                    WHERE sa.storyline_id = %s
                    ORDER BY sa.article_id
                    LIMIT %s
                    """,
                    (episode_id, int(max_articles_per_episode)),
                )
                article_ids = [int(r[0]) for r in (cur.fetchall() or [])]
                if not article_ids:
                    continue
                cur.execute(
                    """
                    SELECT id, source_article_id
                    FROM public.chronological_events
                    WHERE source_article_id = ANY(%s)
                    """,
                    (article_ids,),
                )
                events = cur.fetchall() or []
            if not events:
                stats["skipped_no_events"] += 1
                continue

            with conn.cursor() as cur:
                for eid, aid in events:
                    stats["pairs_checked"] += 1
                    ok, reason, details = allow_event_episode_attach(
                        conn,
                        domain_key=domain_key,
                        schema=schema,
                        episode_id=episode_id,
                        event_id=int(eid),
                        article_id=int(aid) if aid is not None else None,
                    )
                    if not ok:
                        stats["rejected"] += 1
                        continue
                    if not apply:
                        stats["linked"] += 1
                        continue
                    seed = details.get("seed_signature")
                    if seed:
                        lock_episode_signature(cur, schema, episode_id, seed)
                    if insert_event_episode_link(
                        cur,
                        event_id=int(eid),
                        domain_key=domain_key,
                        episode_id=episode_id,
                        link_type=str(details.get("link_type") or "continuation"),
                        matched_anchors=list(details.get("matched_anchors") or []),
                        inference_stage="candidate",
                        blend_rank=None,
                        added_by="eel_backfill",
                        metadata={"gate_reason": reason, "article_id": int(aid)},
                    ):
                        stats["linked"] += 1
                        cur.execute(
                            """
                            UPDATE public.chronological_events
                            SET storyline_id = %s::text
                            WHERE id = %s
                              AND (storyline_id IS NULL OR storyline_id = '' OR storyline_id = %s)
                            """,
                            (str(episode_id), int(eid), str(episode_id)),
                        )
                    else:
                        stats["rejected"] += 1
            if apply:
                conn.commit()
            else:
                conn.rollback()
            logger.info(
                "[%s] episode %s articles=%s linked_so_far=%s",
                domain_key,
                episode_id,
                len(article_ids),
                stats["linked"],
            )
    return stats


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--domain")
    p.add_argument("--all", action="store_true")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit-episodes", type=int, default=200)
    p.add_argument("--max-articles-per-episode", type=int, default=80)
    p.add_argument(
        "--bag-orphans-only",
        action="store_true",
        help="Only episodes with storyline_articles but zero EEL links",
    )
    args = p.parse_args()
    apply = bool(args.apply) and not args.dry_run
    domains = (
        list(get_pipeline_active_domain_keys())
        if args.all
        else ([args.domain] if args.domain else [])
    )
    if not domains:
        p.error("Pass --domain or --all")
    out = []
    for dk in domains:
        st = backfill_domain(
            dk,
            apply=apply,
            limit_episodes=args.limit_episodes,
            max_articles_per_episode=args.max_articles_per_episode,
            bag_orphans_only=bool(args.bag_orphans_only),
        )
        out.append(st)
        logger.info("stats %s", st)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
