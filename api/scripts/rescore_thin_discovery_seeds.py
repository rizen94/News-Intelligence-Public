#!/usr/bin/env python3
"""
Bounded re-score of thin junk-anchor / low-coherence discovery seeds.

Dry-run by default. Unlinks members below discovery_seed_floor (or rejected by SSOT).

  PYTHONPATH=api python3 api/scripts/rescore_thin_discovery_seeds.py --domain politics
  PYTHONPATH=api python3 api/scripts/rescore_thin_discovery_seeds.py --domain politics --apply
  PYTHONPATH=api python3 api/scripts/rescore_thin_discovery_seeds.py --ids 11110 --apply
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
from shared.domain_registry import resolve_domain_schema  # noqa: E402
from shared.membership_scoring import score_article_storyline_membership  # noqa: E402
from shared.storyline_article_counts import sync_counts_update_sql  # noqa: E402
from services.domain_synthesis_config import get_domain_synthesis_config  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("rescore_thin_discovery_seeds")

_JUNK_IDENTITY = ("news", "continue", "year_2026", "rocks", "cmp", "get", "follow", "australia")


def _candidates(cur, schema: str, only_ids: list[int] | None, limit: int) -> list[tuple]:
    if only_ids:
        cur.execute(
            f"""
            SELECT id, title, COALESCE(coherence_score, 0), COALESCE(article_count, 0),
                   anchor_signature, metadata
            FROM {schema}.storylines
            WHERE id = ANY(%s)
            ORDER BY id
            """,
            (only_ids,),
        )
        return list(cur.fetchall() or [])
    cur.execute(
        f"""
        SELECT id, title, COALESCE(coherence_score, 0), COALESCE(article_count, 0),
               anchor_signature, metadata
        FROM {schema}.storylines
        WHERE status = 'active'
          AND COALESCE(article_count, 0) BETWEEN 1 AND 10
          AND (
            COALESCE(coherence_score, 0) < 0.2
            OR COALESCE(metadata->>'source', '') = 'storyline_discovery'
            OR EXISTS (
              SELECT 1
              FROM jsonb_array_elements_text(
                COALESCE(anchor_signature->'identity', '[]'::jsonb)
              ) tok
              WHERE lower(tok) = ANY(%s)
            )
          )
        ORDER BY updated_at DESC NULLS LAST
        LIMIT %s
        """,
        (list(_JUNK_IDENTITY), int(limit)),
    )
    return list(cur.fetchall() or [])


def run(*, domain_key: str, apply: bool, only_ids: list[int] | None, limit: int) -> dict:
    schema = resolve_domain_schema(domain_key)
    seed_floor = float(
        get_domain_synthesis_config(domain_key).link_score_profile.discovery_seed_floor
    )
    # Softer than seed admit: real members often land 0.30–0.55 after quality/temporal.
    floor = min(seed_floor, 0.32)
    stats = {
        "domain": domain_key,
        "apply": apply,
        "floor": floor,
        "storylines": 0,
        "scored": 0,
        "unlinked": 0,
        "kept": 0,
        "ids": [],
    }
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            rows = _candidates(cur, schema, only_ids, limit)
            for sid, title, coh, acount, sig, meta in rows:
                stats["storylines"] += 1
                sid = int(sid)
                cur.execute(
                    f"""
                    SELECT article_id FROM {schema}.storyline_articles
                    WHERE storyline_id = %s
                    """,
                    (sid,),
                )
                aids = [int(r[0]) for r in (cur.fetchall() or [])]
                removed: list[int] = []
                for aid in aids:
                    ms = score_article_storyline_membership(
                        conn,
                        domain_key=domain_key,
                        storyline_id=sid,
                        article_id=aid,
                        schema=schema,
                    )
                    stats["scored"] += 1
                    if ms.rejected or float(ms.combined) < floor:
                        removed.append(aid)
                        logger.info(
                            "unlink candidate %s/%s score=%.3f rejected=%s reason=%s title=%s",
                            sid,
                            aid,
                            ms.combined,
                            ms.rejected,
                            ms.reject_reason,
                            (title or "")[:60],
                        )
                        if apply:
                            cur.execute(
                                f"""
                                DELETE FROM {schema}.storyline_articles
                                WHERE storyline_id = %s AND article_id = %s
                                """,
                                (sid, aid),
                            )
                            if cur.rowcount:
                                stats["unlinked"] += 1
                        else:
                            stats["unlinked"] += 1
                    else:
                        stats["kept"] += 1
                        if apply:
                            cur.execute(
                                f"""
                                UPDATE {schema}.storyline_articles
                                SET relevance_score = %s,
                                    metadata = COALESCE(metadata, '{{}}'::jsonb) || %s::jsonb,
                                    updated_at = NOW()
                                WHERE storyline_id = %s AND article_id = %s
                                """,
                                (
                                    float(ms.combined),
                                    json.dumps(ms.as_metadata()),
                                    sid,
                                    aid,
                                ),
                            )
                if removed:
                    stats["ids"].append(sid)
                    if apply:
                        cur.execute(
                            f"""
                            UPDATE {schema}.storylines
                            SET {sync_counts_update_sql(schema)},
                                metadata = COALESCE(metadata, '{{}}'::jsonb) || %s::jsonb,
                                updated_at = NOW()
                            WHERE id = %s
                            """,
                            (
                                sid,
                                sid,
                                json.dumps(
                                    {
                                        "membership_rescore_at": True,
                                        "membership_rescore_removed": removed,
                                    }
                                ),
                                sid,
                            ),
                        )
            if apply:
                conn.commit()
            else:
                conn.rollback()
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--domain", default="politics")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--ids", type=int, nargs="*", default=None)
    ap.add_argument("--limit", type=int, default=50)
    args = ap.parse_args()
    stats = run(
        domain_key=args.domain,
        apply=bool(args.apply),
        only_ids=list(args.ids) if args.ids else None,
        limit=int(args.limit),
    )
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
