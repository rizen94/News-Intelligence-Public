"""Cross-host wake signal: Widow discovery bridge → PopOS editorial worker."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from shared.database.connection import get_db_connection_context

if TYPE_CHECKING:
    from shared.phase_idle_gate import PhaseIdleBackoff

logger = logging.getLogger(__name__)

WAKE_KEY = "popos_editorial_phase_wake"


def request_popos_editorial_wake(
    phases: list[str],
    *,
    reason: str = "editorial_handoff",
) -> None:
    """Persist a wake request PopOS workers consume on the next cycle."""
    names = [str(p).strip() for p in (phases or []) if str(p).strip()]
    if not names:
        return
    payload: dict[str, Any] = {
        "phases": sorted(set(names)),
        "reason": (reason or "")[:120],
        "requested_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.automation_state (key, value, updated_at)
                    VALUES (%s, %s::jsonb, NOW())
                    ON CONFLICT (key) DO UPDATE SET
                        value = EXCLUDED.value,
                        updated_at = NOW()
                    """,
                    (WAKE_KEY, json.dumps(payload)),
                )
            conn.commit()
    except Exception as exc:
        logger.debug("request_popos_editorial_wake: %s", exc)


def consume_popos_editorial_wake(backoff: PhaseIdleBackoff | None = None) -> list[str]:
    """PopOS worker: read wake request, reset idle backoff, clear flag."""
    phases: list[str] = []
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT value FROM public.automation_state WHERE key = %s",
                    (WAKE_KEY,),
                )
                row = cur.fetchone()
                if not row or not row[0]:
                    return []
                raw = row[0]
                if isinstance(raw, str):
                    data = json.loads(raw)
                elif isinstance(raw, dict):
                    data = raw
                else:
                    return []
                phases = [
                    str(p).strip()
                    for p in (data.get("phases") or [])
                    if str(p).strip()
                ]
                cur.execute(
                    "DELETE FROM public.automation_state WHERE key = %s",
                    (WAKE_KEY,),
                )
            conn.commit()
    except Exception as exc:
        logger.debug("consume_popos_editorial_wake: %s", exc)
        return []

    if backoff is not None:
        for phase in phases:
            backoff.mark_work(phase)
    return phases
