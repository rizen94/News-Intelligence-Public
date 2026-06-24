"""Read-only spine lookup API for loop and evidence adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nri_core.spine.resolution.matcher import MatchResult, resolve_mention
from nri_core.spine.store import postgres_store


@dataclass
class EntityRecord:
    ftm_id: str
    schema_name: str
    caption: str | None
    dataset: str
    anchors: dict[str, str]


def get_entity(ftm_id: str) -> EntityRecord | None:
    with postgres_store.spine_connection() as conn:
        import psycopg2.extras

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, schema_name, caption, dataset FROM spine_entities WHERE id = %s",
                (ftm_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            cur.execute(
                "SELECT anchor_type, anchor_value FROM spine_anchors WHERE entity_id = %s",
                (ftm_id,),
            )
            anchors = {r["anchor_type"]: r["anchor_value"] for r in cur.fetchall()}
    return EntityRecord(
        ftm_id=row["id"],
        schema_name=row["schema_name"],
        caption=row["caption"],
        dataset=row["dataset"],
        anchors=anchors,
    )


def match_mention(
    text: str,
    anchors: dict[str, str] | None = None,
    schema_name: str | None = None,
) -> MatchResult:
    return resolve_mention(text=text, anchors=anchors, schema_name=schema_name)


def list_entities(dataset: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    with postgres_store.spine_connection() as conn:
        import psycopg2.extras

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if dataset:
                cur.execute(
                    """
                    SELECT id, schema_name, caption, dataset
                    FROM spine_entities WHERE dataset = %s LIMIT %s
                    """,
                    (dataset, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT id, schema_name, caption, dataset
                    FROM spine_entities LIMIT %s
                    """,
                    (limit,),
                )
            return list(cur.fetchall())
