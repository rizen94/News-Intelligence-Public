"""Setup mode state in public.automation_state."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

SETUP_COMPLETE_KEY = "setup_complete"
SETUP_DRAFT_KEY = "setup_draft"
KIT_SCHEMA_VERSION_KEY = "kit_schema_version"


def _conn():
    from shared.database.connection import get_db_connection_context

    return get_db_connection_context()


def is_setup_complete() -> bool:
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT value FROM public.automation_state WHERE key = %s",
                    (SETUP_COMPLETE_KEY,),
                )
                row = cur.fetchone()
        if not row or row[0] is None:
            return False
        val = row[0]
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ("true", "1", "yes")
        if isinstance(val, dict):
            return bool(val.get("complete", val.get("value")))
        return bool(val)
    except Exception as e:
        logger.debug("is_setup_complete: %s", e)
        return False


def set_setup_complete(complete: bool = True) -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.automation_state (key, value, updated_at)
                VALUES (%s, %s::jsonb, NOW())
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                """,
                (SETUP_COMPLETE_KEY, json.dumps(complete)),
            )
        conn.commit()


def get_setup_draft() -> dict[str, Any]:
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT value FROM public.automation_state WHERE key = %s",
                    (SETUP_DRAFT_KEY,),
                )
                row = cur.fetchone()
        if not row or not row[0]:
            return {"domains": [], "interests": ""}
        raw = row[0]
        if isinstance(raw, str):
            return json.loads(raw)
        if isinstance(raw, dict):
            return raw
        return {"domains": [], "interests": ""}
    except Exception as e:
        logger.debug("get_setup_draft: %s", e)
        return {"domains": [], "interests": ""}


def save_setup_draft(draft: dict[str, Any]) -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.automation_state (key, value, updated_at)
                VALUES (%s, %s::jsonb, NOW())
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                """,
                (SETUP_DRAFT_KEY, json.dumps(draft)),
            )
        conn.commit()
