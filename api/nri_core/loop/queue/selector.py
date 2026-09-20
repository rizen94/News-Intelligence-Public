"""Entity selection with fixed prune slots."""

from __future__ import annotations

from dataclasses import dataclass

from nri_core.config import get_config


@dataclass
class SelectionBatch:
    entity_ids: list[str]
    prune_slots: int


def select_entities(limit: int = 5, prune_slots: int = 2) -> SelectionBatch:
    cfg = get_config()
    entity_ids: list[str] = []
    try:
        from nri_core.evidence import ni_reader
        import psycopg2.extras

        with ni_reader.news_intel_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    f"""
                    SELECT ftm_id, COUNT(*) AS mention_count
                    FROM {cfg.nri_schema}.resolved_mentions
                    WHERE ftm_id IS NOT NULL AND status = 'auto_linked'
                    GROUP BY ftm_id
                    ORDER BY mention_count DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                entity_ids = [row["ftm_id"] for row in cur.fetchall()]
    except Exception:
        entity_ids = []

    return SelectionBatch(entity_ids=entity_ids, prune_slots=prune_slots)
