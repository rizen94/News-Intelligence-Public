#!/usr/bin/env python3
"""
Re-narrow episode anchor_signature using current classify_event_anchors policy.

Dry-run by default. Apply with --apply.

Rewrites identity to particulars (named first, max 8); strips hub tokens;
moves bare cid-only sprawl toward supporting. Does not demote episodes.
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
    classify_event_anchors,
    parse_anchor_signature,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("renarrow_episode_signatures")


def renarrow_domain(domain_key: str, *, apply: bool, limit: int) -> dict:
    schema = resolve_domain_schema(domain_key)
    stats = {"domain": domain_key, "scanned": 0, "rewritten": 0, "skipped": 0}
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT s.id, s.anchor_signature,
                       (
                         SELECT ce.id FROM public.chronological_events ce
                         WHERE ce.storyline_id = s.id::text
                         ORDER BY ce.actual_event_date ASC NULLS LAST, ce.id ASC
                         LIMIT 1
                       ) AS seed_event_id
                FROM {schema}.storylines s
                WHERE COALESCE(s.story_kind, '') <> 'container_index'
                  AND COALESCE(s.is_mega_storyline, FALSE) = FALSE
                  AND s.anchor_signature IS NOT NULL
                ORDER BY s.updated_at DESC NULLS LAST
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall() or []
            for sid, raw_sig, seed_eid in rows:
                stats["scanned"] += 1
                old = parse_anchor_signature(raw_sig)
                if seed_eid is None:
                    stats["skipped"] += 1
                    continue
                anchors = classify_event_anchors(
                    conn,
                    domain_key=domain_key,
                    schema=schema,
                    event_id=int(seed_eid),
                )
                new_sig = {
                    "identity": list(anchors.get("identity") or [])[:8],
                    "supporting": list(anchors.get("supporting") or [])[:8],
                }
                if (
                    new_sig["identity"] == old.get("identity")
                    and new_sig["supporting"] == old.get("supporting")
                ):
                    stats["skipped"] += 1
                    continue
                logger.info(
                    "[%s] id=%s identity %s → %s",
                    domain_key,
                    sid,
                    old.get("identity")[:4],
                    new_sig["identity"][:4],
                )
                if apply:
                    cur.execute(
                        f"""
                        UPDATE {schema}.storylines
                        SET anchor_signature = %s::jsonb, updated_at = NOW()
                        WHERE id = %s
                        """,
                        (json.dumps(new_sig), int(sid)),
                    )
                stats["rewritten"] += 1
            if apply:
                conn.commit()
            else:
                conn.rollback()
    return stats


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--domain")
    p.add_argument("--all", action="store_true")
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()
    domains = (
        list(get_pipeline_active_domain_keys())
        if args.all
        else ([args.domain] if args.domain else [])
    )
    if not domains:
        p.error("Pass --domain KEY or --all")
    out = [
        renarrow_domain(dk, apply=bool(args.apply), limit=int(args.limit))
        for dk in domains
    ]
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
