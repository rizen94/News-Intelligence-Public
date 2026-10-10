"""Entity identity helpers — canonical vs profile grain."""

from __future__ import annotations

import logging
from typing import Any

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)


def canonical_entity_id_to_profile_id(
    domain_key: str,
    canonical_entity_id: int,
    *,
    conn=None,
) -> int | None:
    """
    Map domain entity_canonical.id → intelligence.entity_profiles.id.

    Note: intelligence.entity_positions.entity_id is canonical_entity_id,
    NOT entity_profiles.id — never join positions.entity_id to profiles.id.
    """
    own_conn = conn is None
    if own_conn:
        conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM intelligence.entity_profiles
                WHERE domain_key = %s AND canonical_entity_id = %s
                ORDER BY updated_at DESC NULLS LAST, id DESC
                LIMIT 1
                """,
                (domain_key, canonical_entity_id),
            )
            row = cur.fetchone()
        if own_conn:
            conn.close()
        return int(row[0]) if row else None
    except Exception as e:
        logger.warning("canonical_entity_id_to_profile_id: %s", e)
        if own_conn:
            try:
                conn.close()
            except Exception:
                pass
        return None


def profile_id_to_canonical_entity_id(
    entity_profile_id: int,
    *,
    conn=None,
) -> tuple[str | None, int | None]:
    """Return (domain_key, canonical_entity_id) for an entity profile."""
    own_conn = conn is None
    if own_conn:
        conn = get_db_connection()
    if not conn:
        return None, None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT domain_key, canonical_entity_id
                FROM intelligence.entity_profiles
                WHERE id = %s
                """,
                (entity_profile_id,),
            )
            row = cur.fetchone()
        if own_conn:
            conn.close()
        if not row:
            return None, None
        return row[0], int(row[1]) if row[1] is not None else None
    except Exception as e:
        logger.warning("profile_id_to_canonical_entity_id: %s", e)
        if own_conn:
            try:
                conn.close()
            except Exception:
                pass
        return None, None
