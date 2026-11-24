#!/usr/bin/env python3
"""
Batch-clean storyline bags: core-prune dissimilar members + title-misaligned links.

Clears excerpt-mash master_summary/analysis_summary so the reader uses grounded
member prose. Run with --dry-run first.
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
for p in (ROOT, os.path.join(ROOT, "api")):
    if p not in sys.path:
        sys.path.insert(0, p)

DEFAULT_DOMAINS = (
    "politics",
    "finance",
    "artificial-intelligence",
    "legal",
    "medicine",
    "neurodiversity",
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--domain", action="append", dest="domains")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--min-articles", type=int, default=2)
    p.add_argument("--limit", type=int, default=0, help="Max storylines per domain (0=all)")
    p.add_argument("--title-unlink", action="store_true", default=True)
    p.add_argument("--no-title-unlink", action="store_false", dest="title_unlink")
    args = p.parse_args()

    domains = args.domains or list(DEFAULT_DOMAINS)
    from api.shared.database import get_db_connection_context
    from api.shared.domain_registry import resolve_domain_schema
    from api.shared.llm_text_sanitize import is_multi_topic_excerpt_mash
    from api.shared.storyline_article_counts import sync_counts_update_sql
    from api.shared.storyline_bag_hygiene import article_title_aligns_with_story
    from services.storyline_core_prune_service import prune_dissimilar_parts

    totals = {
        "storylines": 0,
        "core_unlinked": 0,
        "title_unlinked": 0,
        "mash_cleared": 0,
    }

    with get_db_connection_context() as conn:
        for dk in domains:
            try:
                schema = resolve_domain_schema(dk)
            except Exception as e:
                print(f"skip domain {dk}: {e}")
                continue
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, title, COALESCE(article_count, 0)
                    FROM {schema}.storylines
                    WHERE merged_into_id IS NULL
                      AND COALESCE(status, 'active') NOT IN ('merged', 'deleted', 'archived')
                      AND COALESCE(article_count, 0) >= %s
                    ORDER BY article_count DESC, id ASC
                    """,
                    (args.min_articles,),
                )
                rows = cur.fetchall() or []
            if args.limit:
                rows = rows[: args.limit]

            for sid, title, ac in rows:
                sid = int(sid)
                totals["storylines"] += 1
                pr = prune_dissimilar_parts(
                    dk, sid, dry_run=args.dry_run, count_only=False
                )
                un = int(pr.get("unlinked") or pr.get("would_unlink") or 0)
                totals["core_unlinked"] += un

                title_removed = 0
                if args.title_unlink:
                    with conn.cursor() as cur:
                        cur.execute(
                            f"""
                            SELECT sa.article_id, a.title
                            FROM {schema}.storyline_articles sa
                            JOIN {schema}.articles a ON a.id = sa.article_id
                            WHERE sa.storyline_id = %s
                            """,
                            (sid,),
                        )
                        members = cur.fetchall() or []
                    misaligned = [
                        int(aid)
                        for aid, atitle in members
                        if not article_title_aligns_with_story(str(title), str(atitle or ""))
                    ]
                    if misaligned and not args.dry_run:
                        with conn.cursor() as cur:
                            cur.execute(
                                f"""
                                DELETE FROM {schema}.storyline_articles
                                WHERE storyline_id = %s AND article_id = ANY(%s)
                                """,
                                (sid, misaligned),
                            )
                            title_removed = int(cur.rowcount or 0)
                            cur.execute(
                                f"""
                                UPDATE {schema}.storylines
                                SET {sync_counts_update_sql(schema)}, updated_at = NOW()
                                WHERE id = %s
                                """,
                                (sid, sid, sid),
                            )
                    elif misaligned and args.dry_run:
                        title_removed = len(misaligned)
                    totals["title_unlinked"] += title_removed

                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT master_summary, analysis_summary, description
                        FROM {schema}.storylines WHERE id = %s
                        """,
                        (sid,),
                    )
                    row = cur.fetchone()
                if row:
                    master, analysis, desc = row[0], row[1], row[2]
                    mash = any(
                        is_multi_topic_excerpt_mash(x)
                        for x in (master, analysis)
                        if x
                    )
                    if mash and not args.dry_run:
                        with conn.cursor() as cur:
                            cur.execute(
                                f"""
                                UPDATE {schema}.storylines
                                SET master_summary = NULL,
                                    analysis_summary = NULL,
                                    description = CASE
                                        WHEN char_length(COALESCE(description, '')) < 400
                                        THEN NULL
                                        ELSE description
                                    END,
                                    updated_at = NOW()
                                WHERE id = %s
                                """,
                                (sid,),
                            )
                        totals["mash_cleared"] += 1
                    elif mash:
                        totals["mash_cleared"] += 1

                if un or title_removed:
                    print(
                        f"{'[dry-run] ' if args.dry_run else ''}{dk}/{sid} "
                        f"ac~{ac} core_unlink={un} title_unlink={title_removed} mash={mash}"
                    )

        if not args.dry_run:
            conn.commit()

    print(
        f"Done {'(dry-run) ' if args.dry_run else ''}"
        f"storylines={totals['storylines']} "
        f"core_unlinked={totals['core_unlinked']} "
        f"title_unlinked={totals['title_unlinked']} "
        f"mash_cleared={totals['mash_cleared']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())