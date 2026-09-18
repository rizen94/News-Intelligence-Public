"""Deterministic cross-dataset merge on shared anchors (not fuzzy nomenklatura)."""

from __future__ import annotations

from typing import Any

from nri_core.spine.store import postgres_store


def find_anchor_collisions(anchor_type: str) -> list[dict[str, Any]]:
    """Entities sharing the same anchor value across datasets."""
    with postgres_store.spine_connection() as conn:
        import psycopg2.extras

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT a.anchor_value, array_agg(DISTINCT a.entity_id) AS entity_ids,
                       array_agg(DISTINCT e.dataset) AS datasets
                FROM spine_anchors a
                JOIN spine_entities e ON e.id = a.entity_id
                WHERE a.anchor_type = %s
                GROUP BY a.anchor_value
                HAVING COUNT(DISTINCT a.entity_id) > 1
                ORDER BY COUNT(DISTINCT a.entity_id) DESC
                LIMIT 100
                """,
                (anchor_type,),
            )
            return list(cur.fetchall())


def record_anchor_judgement(
    left_id: str,
    right_id: str,
    anchor_type: str,
    anchor_value: str,
    judgement: str = "same_as",
) -> None:
    from nri_core.spine.resolver.git_resolver import add_judgement

    add_judgement(left_id, right_id, score=1.0, judgement=judgement)
    with postgres_store.spine_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO resolver_judgements (left_id, right_id, score, judgement, source)
                VALUES (%s, %s, 1.0, %s, %s)
                ON CONFLICT (left_id, right_id) DO NOTHING
                """,
                (left_id, right_id, judgement, f"anchor_join:{anchor_type}:{anchor_value}"),
            )


def run_anchor_join_audit() -> dict[str, int]:
    """Audit cross-dataset collisions on high-value anchors; record judgements."""
    stats = {"cik": 0, "lei": 0, "qid": 0, "fec_id": 0}
    for anchor_type in stats:
        collisions = find_anchor_collisions(anchor_type)
        for row in collisions:
            ids = row["entity_ids"]
            if len(ids) >= 2:
                record_anchor_judgement(ids[0], ids[1], anchor_type, row["anchor_value"])
                stats[anchor_type] += 1
    return stats
