"""Record and query pipeline phase last-run heartbeats."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from shared.database.connection import get_db_connection_context, get_ui_db_connection_context

logger = logging.getLogger(__name__)

# Expected interval seconds for stall detection (2× triggers alert).
PHASE_EXPECTED_INTERVAL_SEC: dict[str, int] = {
    "context_sync": 900,
    "entity_profile_sync": 21600,
    "nightly_enrichment_context": 86400,
    "collection_cycle": 7200,
    "entity_extraction": 3600,
    "claim_extraction": 3600,
    "embeddings_worker": 3600,
}


def record_phase_heartbeat(
    phase_name: str,
    *,
    scheduler_path: str = "automation",
    success: bool = True,
    items_processed: int = 0,
    detail: dict[str, Any] | None = None,
) -> None:
    """Upsert heartbeat row (best-effort if migration not applied)."""
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.pipeline_phase_heartbeats
                        (phase_name, scheduler_path, last_run_at, last_success,
                         items_processed, detail, updated_at)
                    VALUES (%s, %s, NOW(), %s, %s, %s::jsonb, NOW())
                    ON CONFLICT (phase_name) DO UPDATE SET
                        scheduler_path = EXCLUDED.scheduler_path,
                        last_run_at = EXCLUDED.last_run_at,
                        last_success = EXCLUDED.last_success,
                        items_processed = EXCLUDED.items_processed,
                        detail = EXCLUDED.detail,
                        updated_at = NOW()
                    """,
                    (
                        phase_name,
                        scheduler_path,
                        success,
                        items_processed,
                        json.dumps(detail or {}),
                    ),
                )
            conn.commit()
    except Exception as e:
        logger.debug("record_phase_heartbeat(%s): %s", phase_name, e)


def list_phase_heartbeats() -> list[dict[str, Any]]:
    """All heartbeats with lag hours for backlog_status."""
    now = datetime.now(timezone.utc)
    out: list[dict[str, Any]] = []
    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT phase_name, scheduler_path, last_run_at, last_success,
                           items_processed, detail
                    FROM public.pipeline_phase_heartbeats
                    ORDER BY phase_name
                    """
                )
                cols = [d[0] for d in cur.description]
                for row in cur.fetchall():
                    d = dict(zip(cols, row))
                    lr = d.get("last_run_at")
                    lag_h = None
                    stalled = False
                    if lr is not None:
                        if lr.tzinfo is None:
                            lr = lr.replace(tzinfo=timezone.utc)
                        lag_h = round((now - lr).total_seconds() / 3600.0, 2)
                        expected = PHASE_EXPECTED_INTERVAL_SEC.get(d["phase_name"], 86400)
                        stalled = (now - lr).total_seconds() > expected * 2
                    d["last_run_at"] = lr.isoformat() if lr else None
                    d["lag_hours"] = lag_h
                    d["stalled"] = stalled
                    out.append(d)
    except Exception as e:
        logger.debug("list_phase_heartbeats: %s", e)
    return out


def stalled_phases() -> list[str]:
    return [h["phase_name"] for h in list_phase_heartbeats() if h.get("stalled")]
