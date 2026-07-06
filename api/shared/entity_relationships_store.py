"""Shared helpers for intelligence.entity_relationships writes."""

from __future__ import annotations

from typing import Tuple

Edge = Tuple[str, int, str, int]


def normalize_edge(
    d1: str, id1: int, d2: str, id2: int
) -> tuple[str, int, str, int]:
    """Lexicographic order on (domain, entity_id) pairs — canonical edge direction."""
    if (d1, id1) <= (d2, id2):
        return d1, id1, d2, id2
    return d2, id2, d1, id1


UPSERT_ENTITY_RELATIONSHIP_SQL = """
INSERT INTO intelligence.entity_relationships
    (source_domain, source_entity_id, target_domain, target_entity_id,
     relationship_type, confidence, co_occurrence_count, last_seen_at)
VALUES (%s, %s, %s, %s, %s, %s, 1, NOW())
ON CONFLICT (source_domain, source_entity_id, target_domain, target_entity_id, relationship_type)
DO UPDATE SET
    confidence = GREATEST(
        intelligence.entity_relationships.confidence,
        EXCLUDED.confidence
    ),
    co_occurrence_count = intelligence.entity_relationships.co_occurrence_count + 1,
    last_seen_at = NOW()
RETURNING id
"""


def entity_relationships_at_cap() -> bool:
    """True when table is at ENTITY_RELATIONSHIPS_MAX_ROWS — reject new edges."""
    from config.runtime import env_int

    cap = env_int("ENTITY_RELATIONSHIPS_MAX_ROWS", 5_000_000)
    try:
        from shared.database.connection import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT reltuples::bigint AS estimate
                    FROM pg_class
                    WHERE oid = 'intelligence.entity_relationships'::regclass
                    """
                )
                row = cur.fetchone()
                if row and row[0] is not None:
                    return int(row[0]) >= cap
                cur.execute("SELECT COUNT(*) FROM intelligence.entity_relationships")
                return int(cur.fetchone()[0] or 0) >= cap
    except Exception:
        return False
