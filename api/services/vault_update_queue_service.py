"""
vault_update_queue — claim/lease, idempotency, dead-letter for unattended notetaking.
"""

from __future__ import annotations

import json
import logging
import os
import socket
from datetime import datetime, timedelta, timezone
from typing import Any

from shared.database.connection import get_db_connection_context
from shared.vault_note_contract import DEFAULT_MAX_JOBS_PER_CYCLE

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = int(os.environ.get("NI_VAULT_UPDATE_MAX_ATTEMPTS", "5"))
_LEASE_SECONDS = int(os.environ.get("NI_VAULT_UPDATE_LEASE_SECONDS", "300"))


def enqueue_vault_update(
    *,
    domain_key: str,
    note_type: str,
    object_id: int,
    vault_path: str,
    action: str,
    idempotency_key: str,
    priority: str = "medium",
    object_id_secondary: int | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Enqueue create/update; dedupe on idempotency_key while pending/processing."""
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.vault_update_queue (
                    domain_key, note_type, object_id, object_id_secondary,
                    vault_path, action, priority, idempotency_key, payload
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (idempotency_key) DO NOTHING
                RETURNING id
                """,
                (
                    domain_key,
                    note_type,
                    int(object_id),
                    object_id_secondary,
                    vault_path,
                    action,
                    priority,
                    idempotency_key,
                    json.dumps(payload or {}),
                ),
            )
            row = cur.fetchone()
        conn.commit()
    if row:
        return {"ok": True, "queue_id": row[0], "already_queued": False}
    return {"ok": True, "queue_id": None, "already_queued": True}


def claim_vault_update_jobs(
    *,
    limit: int | None = None,
    worker_id: str | None = None,
) -> list[dict[str, Any]]:
    """Claim pending jobs; skip paths that already have a processing lease."""
    lim = limit if limit is not None else DEFAULT_MAX_JOBS_PER_CYCLE
    lim = max(1, min(int(os.environ.get("NI_VAULT_MAX_JOBS_PER_CYCLE", str(lim))), 32))
    worker = worker_id or f"{socket.gethostname()}:{os.getpid()}"
    lease_until = datetime.now(timezone.utc) + timedelta(seconds=_LEASE_SECONDS)
    claimed: list[dict[str, Any]] = []

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            # Release expired leases
            cur.execute(
                """
                UPDATE intelligence.vault_update_queue
                SET status = 'pending', locked_by = NULL, locked_until = NULL
                WHERE status = 'processing'
                  AND locked_until IS NOT NULL
                  AND locked_until < NOW()
                """
            )
            cur.execute(
                """
                SELECT id FROM intelligence.vault_update_queue
                WHERE status = 'pending'
                  AND vault_path NOT IN (
                      SELECT vault_path FROM intelligence.vault_update_queue
                      WHERE status = 'processing'
                        AND locked_until IS NOT NULL
                        AND locked_until >= NOW()
                  )
                ORDER BY
                    CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                    created_at ASC
                LIMIT %s
                FOR UPDATE SKIP LOCKED
                """,
                (lim,),
            )
            ids = [r[0] for r in cur.fetchall()]
            for jid in ids:
                cur.execute(
                    """
                    UPDATE intelligence.vault_update_queue
                    SET status = 'processing',
                        locked_by = %s,
                        locked_until = %s,
                        started_at = NOW(),
                        attempts = attempts + 1
                    WHERE id = %s AND status = 'pending'
                    RETURNING id, domain_key, note_type, object_id, object_id_secondary,
                              vault_path, action, priority, idempotency_key,
                              attempts, payload
                    """,
                    (worker, lease_until, jid),
                )
                row = cur.fetchone()
                if not row:
                    continue
                payload = row[10]
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except json.JSONDecodeError:
                        payload = {}
                claimed.append(
                    {
                        "id": row[0],
                        "domain_key": row[1],
                        "note_type": row[2],
                        "object_id": row[3],
                        "object_id_secondary": row[4],
                        "vault_path": row[5],
                        "action": row[6],
                        "priority": row[7],
                        "idempotency_key": row[8],
                        "attempts": row[9],
                        "payload": payload if isinstance(payload, dict) else {},
                    }
                )
        conn.commit()
    return claimed


def complete_vault_update_job(job_id: int, *, success: bool, error: str | None = None) -> None:
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            if success:
                cur.execute(
                    """
                    UPDATE intelligence.vault_update_queue
                    SET status = 'completed',
                        completed_at = NOW(),
                        locked_by = NULL,
                        locked_until = NULL,
                        error_message = NULL
                    WHERE id = %s
                    """,
                    (job_id,),
                )
            else:
                cur.execute(
                    """
                    UPDATE intelligence.vault_update_queue
                    SET status = CASE
                            WHEN attempts >= %s THEN 'dead'
                            ELSE 'pending'
                        END,
                        error_message = %s,
                        locked_by = NULL,
                        locked_until = NULL,
                        completed_at = CASE WHEN attempts >= %s THEN NOW() ELSE NULL END
                    WHERE id = %s
                    """,
                    (_MAX_ATTEMPTS, (error or "")[:2000], _MAX_ATTEMPTS, job_id),
                )
        conn.commit()


def count_vault_update_pending() -> dict[str, int]:
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT status, COUNT(*)
                FROM intelligence.vault_update_queue
                GROUP BY status
                """
            )
            rows = cur.fetchall()
    out = {str(s): int(n) for s, n in rows}
    return out
