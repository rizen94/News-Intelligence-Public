"""Read-only adapter to news_intel.intelligence.* with watermark support."""

from __future__ import annotations

import contextlib
from typing import Any, Generator

import psycopg2
import psycopg2.extras

from config.investigation_tables import T_ENTITY_BRIDGE, T_FTM_ENTITY_CACHE, T_WATERMARKS
from nri_core.config import get_config, require_prod_safety


@contextlib.contextmanager
def news_intel_connection() -> Generator[Any, None, None]:
    cfg = get_config()
    conn = psycopg2.connect(cfg.news_intel_dsn)
    try:
        yield conn
    finally:
        conn.close()


def get_watermark(name: str) -> int:
    with news_intel_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT last_value FROM {T_WATERMARKS} WHERE name = %s",
                (name,),
            )
            row = cur.fetchone()
            return int(row[0]) if row else 0


def set_watermark(name: str, value: int) -> None:
    with news_intel_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {T_WATERMARKS} (name, last_value)
                VALUES (%s, %s)
                ON CONFLICT (name) DO UPDATE SET
                    last_value = EXCLUDED.last_value,
                    updated_at = NOW()
                """,
                (name, value),
            )
        conn.commit()


def fetch_new_mentions(since_id: int = 0, limit: int = 500) -> list[dict[str, Any]]:
    require_prod_safety()
    with news_intel_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    m.id,
                    m.context_id,
                    COALESCE(
                        NULLIF(TRIM(m.source_snippet), ''),
                        ep.metadata->>'canonical_name',
                        'entity:' || m.entity_profile_id::text
                    ) AS mention_text,
                    m.entity_profile_id,
                    ep.domain_key,
                    ep.canonical_entity_id,
                    ep.metadata->>'entity_type' AS entity_type
                FROM intelligence.context_entity_mentions m
                JOIN intelligence.entity_profiles ep ON ep.id = m.entity_profile_id
                WHERE m.id > %s
                ORDER BY m.id ASC
                LIMIT %s
                """,
                (since_id, limit),
            )
            return list(cur.fetchall())


def fetch_context(context_id: int) -> dict[str, Any] | None:
    with news_intel_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, context_type, title, body, created_at
                FROM intelligence.contexts
                WHERE id = %s
                """,
                (context_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def context_exists(context_id: int) -> bool:
    with news_intel_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM intelligence.contexts WHERE id = %s", (context_id,))
            return cur.fetchone() is not None


def fetch_claims_for_context(context_id: int) -> list[dict[str, Any]]:
    with news_intel_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, claim_text, confidence, created_at
                FROM intelligence.extracted_claims
                WHERE context_id = %s
                ORDER BY id
                """,
                (context_id,),
            )
            return list(cur.fetchall())


def fetch_entity_profiles(limit: int = 100) -> list[dict[str, Any]]:
    with news_intel_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    id,
                    domain_key,
                    canonical_entity_id,
                    metadata->>'canonical_name' AS canonical_name,
                    metadata->>'entity_type' AS entity_type,
                    created_at
                FROM intelligence.entity_profiles
                ORDER BY id
                LIMIT %s
                """,
                (limit,),
            )
            return list(cur.fetchall())
