#!/usr/bin/env python3
"""Merge finance storylines that share identical article sets (one-off dedup)."""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

_API = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_API))

from shared.migration_sql_runner import bootstrap_migration_env

bootstrap_migration_env()

from shared.database.connection import get_db_connection_context

GENERIC = re.compile(r"^Ongoing:\s*(Pbc|Apy|Cd|Ai|Year_2026)\s*$", re.I)


def score_title(title: str) -> int:
    t = (title or "").strip()
    if not t:
        return 0
    if GENERIC.match(t):
        return 1
    return len(t) + (
        10
        if any(k in t for k in ("Pharmaceuticals", "Planet", "Pony", "Torrid", "Nyxoah", "Earn"))
        else 0
    )


CLUSTER_SQL = """
WITH sl_articles AS (
  SELECT s.id, s.title,
         array_agg(sa.article_id ORDER BY sa.article_id) AS article_ids
  FROM finance.storylines s
  JOIN finance.storyline_articles sa ON sa.storyline_id = s.id
  WHERE (s.status IN ('active', 'ongoing', 'developing') OR s.status IS NULL)
    AND s.merged_into_id IS NULL
  GROUP BY s.id, s.title
),
clusters AS (
  SELECT article_ids,
         array_agg(id ORDER BY id) AS ids,
         array_agg(title ORDER BY id) AS titles
  FROM sl_articles
  GROUP BY article_ids
  HAVING COUNT(*) > 1
)
SELECT ids, titles FROM clusters;
"""


def merge_secondary(cur, primary_id: int, secondary_id: int) -> bool:
    cur.execute(
        """
        INSERT INTO finance.storyline_articles
        (storyline_id, article_id, relevance_score, created_at)
        SELECT %s, article_id, relevance_score, NOW()
        FROM finance.storyline_articles
        WHERE storyline_id = %s
        ON CONFLICT (storyline_id, article_id) DO NOTHING
        """,
        (primary_id, secondary_id),
    )
    from shared.storyline_article_counts import sync_counts_update_sql

    cur.execute(
        f"""
        UPDATE finance.storylines
        SET {sync_counts_update_sql("finance")},
        merge_count = COALESCE(merge_count, 0) + 1,
        updated_at = NOW()
        WHERE id = %s
        """,
        (primary_id, primary_id, primary_id),
    )
    cur.execute(
        """
        UPDATE finance.storylines
        SET merged_into_id = %s, status = 'archived', updated_at = NOW()
        WHERE id = %s AND merged_into_id IS NULL
        """,
        (primary_id, secondary_id),
    )
    return cur.rowcount == 1


def main() -> int:
    log_lines: list[str] = [
        "# Finance storyline dedup: identical article-set duplicates merged",
    ]
    merged = 0
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(CLUSTER_SQL)
            clusters = cur.fetchall()
            for ids, titles in clusters:
                ranked = sorted(zip(ids, titles), key=lambda x: (-score_title(x[1]), x[0]))
                primary_id, primary_title = ranked[0]
                for sid, stitle in ranked[1:]:
                    if merge_secondary(cur, primary_id, sid):
                        merged += 1
                        log_lines.append(
                            f"merged storyline {sid} ({stitle!r}) -> {primary_id} ({primary_title!r})"
                        )
        conn.commit()

    log_path = Path(__file__).resolve().parent / "finance_storyline_dedup_20260609.log"
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    print(f"Merged {merged} storylines; log at {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
