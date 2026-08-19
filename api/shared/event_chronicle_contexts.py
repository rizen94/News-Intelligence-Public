"""Maintain intelligence.event_chronicle_contexts junction (P3 eligibility index)."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Shared anti-join fragment for discover / backlog / update paths
NOT_LINKED_SQL = """
NOT EXISTS (
    SELECT 1 FROM intelligence.event_chronicle_contexts ecc
    WHERE ecc.context_id = c.id
)
"""

NOT_LINKED_TO_EVENT_SQL = """
NOT EXISTS (
    SELECT 1 FROM intelligence.event_chronicle_contexts ecc
    WHERE ecc.context_id = c.id AND ecc.event_id = %s
)
"""


def upsert_chronicle_context_links(
    cur: Any,
    event_id: int,
    context_ids: list[int],
) -> int:
    """Insert junction rows for context_ids linked to event_id. Returns rows attempted."""
    ids = [int(x) for x in context_ids if x is not None]
    if not ids or not event_id:
        return 0
    # Drop ids that no longer exist (stale chronicle JSON must not abort the txn).
    try:
        cur.execute(
            "SELECT id FROM intelligence.contexts WHERE id = ANY(%s)",
            (ids,),
        )
        ids = [int(r[0]) for r in cur.fetchall()]
    except Exception as e:
        logger.debug("upsert_chronicle_context_links existence check: %s", e)
        return 0
    if not ids:
        return 0
    try:
        cur.execute("SAVEPOINT ecc_upsert")
        from psycopg2.extras import execute_values

        execute_values(
            cur,
            """
            INSERT INTO intelligence.event_chronicle_contexts (context_id, event_id)
            VALUES %s
            ON CONFLICT (context_id) DO NOTHING
            """,
            [(cid, int(event_id)) for cid in ids],
            page_size=200,
        )
        cur.execute("RELEASE SAVEPOINT ecc_upsert")
        return len(ids)
    except Exception as e:
        logger.debug("upsert_chronicle_context_links: %s", e)
        try:
            cur.execute("ROLLBACK TO SAVEPOINT ecc_upsert")
        except Exception:
            pass
        # Fallback row-by-row if execute_values unavailable / table missing
        n = 0
        for cid in ids:
            try:
                cur.execute("SAVEPOINT ecc_upsert_row")
                cur.execute(
                    """
                    INSERT INTO intelligence.event_chronicle_contexts (context_id, event_id)
                    VALUES (%s, %s)
                    ON CONFLICT (context_id) DO NOTHING
                    """,
                    (cid, int(event_id)),
                )
                cur.execute("RELEASE SAVEPOINT ecc_upsert_row")
                n += 1
            except Exception:
                try:
                    cur.execute("ROLLBACK TO SAVEPOINT ecc_upsert_row")
                except Exception:
                    pass
        return n
