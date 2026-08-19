"""
Event coreference facade — batch entry + cluster expand helpers.

Keeps automation phase name ``event_deduplication``; delegates scoring/merge
to ``EventDeduplicationService``.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def coreference_recent(conn, limit: int = 50) -> dict[str, int]:
    """Batch coreference for recent unclustered / unmerged events."""
    from services.event_deduplication_service import EventDeduplicationService

    svc = EventDeduplicationService(conn)
    return await svc.deduplicate_recent(limit=limit)


def resolve_cluster_root(conn, event_id: int) -> int:
    """Follow canonical_event_id / event_cluster_id to the cluster root id."""
    from services.event_deduplication_service import EventDeduplicationService

    return EventDeduplicationService(conn).resolve_cluster_root(event_id)


def resolve_canonical_event_id(conn, event_id: int) -> int:
    """
    Resolve any chronological_events.id to its coreference cluster root.

    Alias of ``resolve_cluster_root`` for attach/score/timeline callers that
    should key on the canonical cluster identity rather than a member row.
    """
    return resolve_cluster_root(conn, int(event_id))


def expand_event_cluster(conn, event_id: int, *, limit: int = 25) -> list[dict[str, Any]]:
    """
    Return corroborating events in the same coreference cluster as *event_id*.

    Includes the root and soft/hard members. Used by synthesis / timeline expand.
    """
    cursor = conn.cursor()
    try:
        root = resolve_cluster_root(conn, event_id)
        cursor.execute(
            """
            SELECT id, title, actual_event_date, source_count, canonical_event_id,
                   event_cluster_id, source_article_id
            FROM public.chronological_events
            WHERE id = %s
               OR event_cluster_id = %s
               OR canonical_event_id = %s
            ORDER BY
                CASE WHEN id = %s THEN 0 ELSE 1 END,
                actual_event_date ASC NULLS LAST,
                id ASC
            LIMIT %s
            """,
            (root, root, root, root, max(1, min(int(limit), 100))),
        )
        rows = cursor.fetchall() or []
        out: list[dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "id": int(r[0]),
                    "title": r[1] or "",
                    "event_date": r[2].isoformat() if r[2] else None,
                    "source_count": int(r[3] or 1),
                    "canonical_event_id": int(r[4]) if r[4] is not None else None,
                    "event_cluster_id": int(r[5]) if r[5] is not None else None,
                    "source_article_id": int(r[6]) if r[6] is not None else None,
                    "is_cluster_root": int(r[0]) == root,
                }
            )
        return out
    except Exception as e:
        logger.debug("expand_event_cluster(%s): %s", event_id, e)
        try:
            conn.rollback()
        except Exception:
            pass
        return []
    finally:
        cursor.close()
