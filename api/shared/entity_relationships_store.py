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
     relationship_type, confidence)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (source_domain, source_entity_id, target_domain, target_entity_id, relationship_type)
DO UPDATE SET confidence = GREATEST(
    intelligence.entity_relationships.confidence,
    EXCLUDED.confidence
)
RETURNING id
"""
