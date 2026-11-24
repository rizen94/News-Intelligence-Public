#!/usr/bin/env python3
"""
Archive legacy bag storylines with no EEL backing (honest-spine corpus trim).

Does not delete rows; sets status=archived and records storyline_id_lineage when
redirecting vault/reader ids is needed. Use --dry-run first.
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
for p in (ROOT, os.path.join(ROOT, "api")):
    if p not in sys.path:
        sys.path.insert(0, p)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", required=True, help="Domain key")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Max storylines to archive in one run",
    )
    parser.add_argument(
        "--min-articles",
        type=int,
        default=0,
        help="Only archive when article_count is at least this (0 = any)",
    )
    parser.add_argument(
        "--mega-only",
        action="store_true",
        help="Only touch is_mega_storyline rows",
    )
    args = parser.parse_args()

    from api.shared.database import get_db_connection_context
    from api.shared.domain_registry import resolve_domain_schema
    dk = args.domain.strip()
    schema = resolve_domain_schema(dk)
    mega_filter = "AND COALESCE(s.is_mega_storyline, FALSE) = TRUE" if args.mega_only else ""

    sql = f"""
        SELECT s.id, COALESCE(s.article_count, 0) AS ac
        FROM {schema}.storylines s
        WHERE s.merged_into_id IS NULL
          AND COALESCE(s.status, 'active') NOT IN ('merged', 'deleted', 'archived')
          AND COALESCE(s.article_count, 0) >= %s
          {mega_filter}
          AND NOT EXISTS (
              SELECT 1
              FROM intelligence.event_episode_links eel
              WHERE eel.domain_key = %s AND eel.episode_id = s.id
          )
        ORDER BY s.updated_at ASC NULLS FIRST, s.id ASC
        LIMIT %s
    """

    archived = 0
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (args.min_articles, dk, args.limit))
            rows = cur.fetchall() or []
            for sid, ac in rows:
                sid = int(sid)
                if args.dry_run:
                    print(f"[dry-run] archive {dk} storyline {sid} (articles={ac}, no EEL)")
                    archived += 1
                    continue
                cur.execute(
                    f"""
                    UPDATE {schema}.storylines
                    SET status = 'archived',
                        automation_enabled = FALSE,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (sid,),
                )
                archived += 1
        if not args.dry_run:
            conn.commit()

    print(f"{'Would archive' if args.dry_run else 'Archived'} {archived} storylines in {dk}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())