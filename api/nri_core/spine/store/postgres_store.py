"""Postgres persistence for identity_spine."""

from __future__ import annotations

import contextlib
from typing import Any, Generator, Iterable

import psycopg2
import psycopg2.extras

from nri_core.config import get_config


@contextlib.contextmanager
def spine_connection() -> Generator[Any, None, None]:
    cfg = get_config()
    conn = psycopg2.connect(cfg.identity_spine_dsn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def upsert_entity(
    entity_id: str,
    schema_name: str,
    caption: str | None,
    dataset: str,
    referents: list[str] | None = None,
) -> None:
    with spine_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO spine_entities (id, schema_name, caption, dataset, referents)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (id) DO UPDATE SET
                    caption = EXCLUDED.caption,
                    last_seen = NOW()
                """,
                (entity_id, schema_name, caption, dataset, psycopg2.extras.Json(referents or [])),
            )


def upsert_statement(
    entity_id: str,
    dataset: str,
    schema_name: str,
    prop: str,
    value: str,
    origin: str | None = None,
) -> None:
    with spine_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO spine_statements (entity_id, dataset, schema_name, prop, value, origin)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (entity_id, dataset, prop, value) DO NOTHING
                """,
                (entity_id, dataset, schema_name, prop, value, origin),
            )


def upsert_anchor(entity_id: str, anchor_type: str, anchor_value: str) -> None:
    with spine_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO spine_anchors (entity_id, anchor_type, anchor_value)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (entity_id, anchor_type, anchor_value),
            )


def lookup_by_anchor(anchor_type: str, anchor_value: str) -> list[dict[str, Any]]:
    with spine_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT e.id, e.schema_name, e.caption, e.dataset
                FROM spine_anchors a
                JOIN spine_entities e ON e.id = a.entity_id
                WHERE a.anchor_type = %s AND a.anchor_value = %s
                """,
                (anchor_type, anchor_value),
            )
            return list(cur.fetchall())


def search_name_candidates(
    name: str,
    schema_name: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    with spine_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if schema_name:
                cur.execute(
                    """
                    SELECT id, schema_name, caption, dataset
                    FROM spine_entities
                    WHERE caption ILIKE %s AND schema_name = %s
                    LIMIT %s
                    """,
                    (f"%{name}%", schema_name, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT id, schema_name, caption, dataset
                    FROM spine_entities
                    WHERE caption ILIKE %s
                    LIMIT %s
                    """,
                    (f"%{name}%", limit),
                )
            return list(cur.fetchall())


def bulk_upsert_entities(rows: Iterable[dict[str, Any]]) -> int:
    count = 0
    with spine_connection() as conn:
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(
                    """
                    INSERT INTO spine_entities (id, schema_name, caption, dataset, referents)
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (id) DO UPDATE SET caption = EXCLUDED.caption, last_seen = NOW()
                    """,
                    (
                        row["id"],
                        row["schema_name"],
                        row.get("caption"),
                        row["dataset"],
                        psycopg2.extras.Json(row.get("referents", [])),
                    ),
                )
                count += 1
    return count
