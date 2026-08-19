#!/usr/bin/env python3
"""One-shot: create Cyclospora canonical + backfill politics.article_entities."""

from __future__ import annotations

import sys

from services.entity_resolution_service import _add_alias, resolve_to_canonical
from shared.database.connection import get_db_connection

ARTICLE_IDS = (351991, 352661, 352646, 352911, 353210, 353674)
ALIASES = (
    "cyclospora",
    "cyclosporiasis",
    "cyclospora outbreak",
    "cyclosporiasis outbreak",
    "Cyclospora outbreak",
    "Cyclosporiasis outbreak",
)
STORYLINE_ID = 3716


def main() -> int:
    cid = resolve_to_canonical("politics", "Cyclospora", "subject", create_if_missing=True)
    if not cid:
        print("failed to resolve/create Cyclospora canonical", file=sys.stderr)
        return 1
    print(f"canonical_id={cid}")

    conn = get_db_connection()
    if not conn:
        print("no db", file=sys.stderr)
        return 1
    try:
        with conn.cursor() as cur:
            for a in ALIASES:
                _add_alias(cur, "politics", cid, a)
            cur.execute(
                """
                UPDATE politics.article_entities
                SET canonical_entity_id = %s
                WHERE canonical_entity_id IS DISTINCT FROM %s
                  AND (
                    LOWER(entity_name) = ANY(%s)
                    OR LOWER(entity_name) LIKE %s
                    OR LOWER(entity_name) LIKE %s
                  )
                """,
                (
                    cid,
                    cid,
                    [a.lower() for a in ALIASES],
                    "cyclospora%",
                    "cyclosporiasis%",
                ),
            )
            print(f"updated_article_entities={cur.rowcount}")

            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'politics' AND table_name = 'story_entity_index'
                """
            )
            cols = {r[0] for r in cur.fetchall()}
            if "canonical_entity_id" in cols:
                cur.execute(
                    """
                    INSERT INTO politics.story_entity_index
                      (storyline_id, entity_name, entity_type, mention_count, canonical_entity_id)
                    VALUES (%s, 'Cyclospora', 'other', %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (STORYLINE_ID, len(ARTICLE_IDS), cid),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO politics.story_entity_index
                      (storyline_id, entity_name, entity_type, mention_count)
                    VALUES (%s, 'Cyclospora', 'other', %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (STORYLINE_ID, len(ARTICLE_IDS)),
                )
            print(f"story_entity_index_rows={cur.rowcount}")

            cur.execute(
                """
                SELECT article_id, entity_name, canonical_entity_id
                FROM politics.article_entities
                WHERE article_id = ANY(%s)
                  AND entity_name ILIKE %s
                ORDER BY article_id, entity_name
                """,
                (list(ARTICLE_IDS), "%cyclo%"),
            )
            for row in cur.fetchall():
                print(f"  ae={row}")
        conn.commit()
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
