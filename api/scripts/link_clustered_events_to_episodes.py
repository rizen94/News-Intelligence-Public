#!/usr/bin/env python3
"""Link clustered chronological_events to existing episodes via event_cluster_id.

  PYTHONPATH=api python3 api/scripts/link_clustered_events_to_episodes.py --all --apply --limit-clusters 500
"""

from __future__ import annotations

import argparse
import asyncio
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
from shared.episode_attach_gate import insert_event_episode_link  # noqa: E402
from services.episode_merge_service import resolve_existing_episode  # noqa: E402
from services.story_continuation_service import StoryContinuationService  # noqa: E402
from shared.chronological_event_domain import resolve_chronological_event_domain_key  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("link_clustered_events")


def link_clusters(
    *,
    domain_key: str | None,
    apply: bool,
    limit_clusters: int,
    allow_founding: bool = False,
) -> dict:
    stats = {
        "clusters_seen": 0,
        "events_linked": 0,
        "clusters_resolved": 0,
        "clusters_skipped": 0,
        "clusters_founded": 0,
    }

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ce.event_cluster_id,
                       MIN(ce.id) AS root_id,
                       array_agg(ce.id ORDER BY ce.id) AS member_ids
                FROM public.chronological_events ce
                WHERE ce.event_cluster_id IS NOT NULL
                  AND NOT EXISTS (
                    SELECT 1 FROM intelligence.event_episode_links eel
                    WHERE eel.event_id = ce.id
                      AND eel.inference_stage <> 'quarantined'
                  )
                GROUP BY ce.event_cluster_id
                HAVING COUNT(*) >= 1
                ORDER BY COUNT(*) DESC
                LIMIT %s
                """,
                (int(limit_clusters),),
            )
            clusters = cur.fetchall() or []

        for cluster_id, root_id, member_ids in clusters:
            stats["clusters_seen"] += 1
            members = [int(x) for x in (member_ids or [])]
            if not members:
                stats["clusters_skipped"] += 1
                continue

            episode_id: int | None = None
            dk: str | None = domain_key

            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT eel.episode_id, eel.domain_key
                    FROM intelligence.event_episode_links eel
                    WHERE eel.event_id = ANY(%s)
                      AND eel.inference_stage <> 'quarantined'
                    ORDER BY eel.updated_at DESC NULLS LAST
                    LIMIT 1
                    """,
                    (members,),
                )
                linked = cur.fetchone()
                if linked:
                    episode_id, dk = int(linked[0]), str(linked[1])

            if not episode_id:
                dk = dk or resolve_chronological_event_domain_key(conn, int(root_id))
                if not dk:
                    stats["clusters_skipped"] += 1
                    continue
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT title FROM public.chronological_events WHERE id = %s",
                        (int(root_id),),
                    )
                    erow = cur.fetchone()
                    event_title = (erow[0] if erow else "") or ""
                episode_id = resolve_existing_episode(
                    conn,
                    domain_key=dk,
                    event_id=int(root_id),
                    article_id=None,
                    title_hint=event_title,
                )
                if not episode_id and event_title:
                    from services.episode_merge_service import find_episodes_by_title

                    schema = resolve_domain_schema(dk)
                    title_matches = find_episodes_by_title(
                        conn, schema=schema, title=event_title
                    )
                    if title_matches:
                        from services.episode_merge_service import pick_canonical_episode

                        episode_id = pick_canonical_episode(
                            conn, schema=schema, episode_ids=title_matches
                        )

            if not episode_id and allow_founding and dk and apply:
                schema = resolve_domain_schema(dk)
                svc = StoryContinuationService(conn, schema=schema)

                async def _found():
                    return await svc.match_event_to_storyline(int(root_id))

                founded = asyncio.run(_found())
                if founded and founded.get("storyline_id"):
                    episode_id = int(founded["storyline_id"])
                    stats["clusters_founded"] += 1

            if not episode_id:
                stats["clusters_skipped"] += 1
                continue

            stats["clusters_resolved"] += 1
            linked_this = 0
            with conn.cursor() as cur:
                for eid in members:
                    if not apply:
                        linked_this += 1
                        continue
                    if insert_event_episode_link(
                        cur,
                        event_id=int(eid),
                        domain_key=dk,
                        episode_id=int(episode_id),
                        link_type="continuation",
                        matched_anchors=[],
                        inference_stage="candidate",
                        blend_rank=0.75,
                        added_by="cluster_batch_link",
                        metadata={"cluster_id": int(cluster_id), "root_event_id": int(root_id)},
                    ):
                        linked_this += 1
                        cur.execute(
                            """
                            UPDATE public.chronological_events
                            SET storyline_id = %s::text
                            WHERE id = %s
                            """,
                            (str(int(episode_id)), int(eid)),
                        )
            stats["events_linked"] += linked_this
            if apply:
                conn.commit()
            else:
                conn.rollback()
            if stats["clusters_seen"] % 50 == 0:
                logger.info("progress %s", stats)

    stats["domain"] = domain_key or "all"
    stats["apply"] = apply
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--domain")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit-clusters", type=int, default=500)
    ap.add_argument(
        "--allow-founding",
        action="store_true",
        help="Found episode via continuation when cluster has no existing match",
    )
    args = ap.parse_args()
    apply = bool(args.apply) and not args.dry_run
    if args.all:
        print(
            json.dumps(
                link_clusters(
                    domain_key=None,
                    apply=apply,
                    limit_clusters=args.limit_clusters,
                    allow_founding=bool(args.allow_founding),
                ),
                indent=2,
            )
        )
    elif args.domain:
        print(
            json.dumps(
                link_clusters(
                    domain_key=args.domain,
                    apply=apply,
                    limit_clusters=args.limit_clusters,
                    allow_founding=bool(args.allow_founding),
                ),
                indent=2,
            )
        )
    else:
        print(
            json.dumps(
                link_clusters(
                    domain_key=None,
                    apply=apply,
                    limit_clusters=args.limit_clusters,
                    allow_founding=bool(args.allow_founding),
                ),
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
