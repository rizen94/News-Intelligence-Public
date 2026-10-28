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


def list_popos_worker_heartbeats() -> list[dict[str, Any]]:
    """Heartbeats written by scripts/run_popos_phase_worker (scheduler_path=popos_worker)."""
    return [h for h in list_phase_heartbeats() if h.get("scheduler_path") == "popos_worker"]


def _heartbeat_age_seconds(row: dict[str, Any] | None) -> float | None:
    if not row or not row.get("last_run_at"):
        return None
    try:
        lr = datetime.fromisoformat(str(row["last_run_at"]).replace("Z", "+00:00"))
        if lr.tzinfo is None:
            lr = lr.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - lr).total_seconds()
    except Exception:
        return None


def _heartbeat_detail(row: dict[str, Any]) -> dict[str, Any]:
    detail = row.get("detail")
    if isinstance(detail, dict):
        return detail
    if isinstance(detail, str) and detail.strip():
        try:
            parsed = json.loads(detail)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


# Drop crashed mid-drain "running" rows after this (assembly can exceed one budget).
POPOS_RUNNING_ACTIVITY_MAX_AGE_SEC = 3600


def popos_current_activities_from_heartbeats(
    *,
    max_running_age_sec: float = POPOS_RUNNING_ACTIVITY_MAX_AGE_SEC,
) -> list[dict[str, Any]]:
    """
    Monitor Current activity rows for in-flight PopOS phase drains.

    Workers write detail.status=running at drain start and complete/failed at end.
    """
    return current_activities_from_heartbeats(
        scheduler_paths=("popos_worker",),
        max_running_age_sec=max_running_age_sec,
        execution_host="popos",
        id_prefix="popos-active",
    )


def widow_current_activities_from_heartbeats(
    *,
    max_running_age_sec: float = POPOS_RUNNING_ACTIVITY_MAX_AGE_SEC,
) -> list[dict[str, Any]]:
    """Widow/conductor drains with detail.status=running (Phase E heartbeat honesty)."""
    return current_activities_from_heartbeats(
        scheduler_paths=("widow", "automation", "conductor"),
        max_running_age_sec=max_running_age_sec,
        execution_host="widow",
        id_prefix="widow-active",
    )


def current_activities_from_heartbeats(
    *,
    scheduler_paths: tuple[str, ...] = ("popos_worker",),
    max_running_age_sec: float = POPOS_RUNNING_ACTIVITY_MAX_AGE_SEC,
    execution_host: str = "popos",
    id_prefix: str = "hb-active",
) -> list[dict[str, Any]]:
    paths = set(scheduler_paths)
    out: list[dict[str, Any]] = []
    for row in list_phase_heartbeats():
        if row.get("scheduler_path") not in paths:
            continue
        phase = str(row.get("phase_name") or "")
        if not phase or phase.startswith("__"):
            continue
        detail = _heartbeat_detail(row)
        if detail.get("status") != "running":
            continue
        age = _heartbeat_age_seconds(row)
        if age is None or age > max_running_age_sec:
            continue
        worker_id = detail.get("worker_id") or "default"
        label = phase.replace("_", " ")
        out.append(
            {
                "id": f"{id_prefix}:{phase}:{worker_id}",
                "message": f"Running {label}",
                "task_name": phase,
                "running_instances": 1,
                "started_at": row.get("last_run_at"),
                "execution_host": execution_host,
                "worker_id": worker_id,
            }
        )
    out.sort(key=lambda x: x.get("started_at") or "", reverse=True)
    return out


def popos_worker_status_summary() -> dict[str, Any]:
    """Compact Monitor payload: cycle rows (incl. split workers) + recent phase drains."""
    rows = list_popos_worker_heartbeats()
    cycles = [
        h
        for h in rows
        if str(h.get("phase_name") or "").startswith("__popos_worker__")
    ]
    phases = [
        h
        for h in rows
        if not str(h.get("phase_name") or "").startswith("__popos_worker__")
    ]
    alive = False
    age_sec = None

    def _sort_key(row: dict[str, Any]) -> float:
        a = _heartbeat_age_seconds(row)
        # Newest first; missing age sorts last.
        return a if a is not None else 1e18

    cycles = sorted(cycles, key=_sort_key)
    # Cycle start writes status=running; treat those as fresh even for long drains.
    fresh_cycles: list[dict[str, Any]] = []
    for c in cycles:
        a = _heartbeat_age_seconds(c)
        if a is None:
            continue
        status = _heartbeat_detail(c).get("status")
        if status == "running" and a <= POPOS_RUNNING_ACTIVITY_MAX_AGE_SEC:
            fresh_cycles.append(c)
        elif a <= 600:
            fresh_cycles.append(c)
    cycle = fresh_cycles[0] if fresh_cycles else (cycles[0] if cycles else None)
    candidates = list(fresh_cycles) + list(phases)
    ages = [a for a in (_heartbeat_age_seconds(r) for r in candidates) if a is not None]
    if ages:
        age_sec = round(min(ages), 1)
        alive = age_sec <= 600 or any(
            _heartbeat_detail(c).get("status") == "running" for c in fresh_cycles
        )
    return {
        "alive": alive,
        "age_sec": age_sec,
        "cycle": cycle,
        "cycles": fresh_cycles or cycles,
        "workers": len(fresh_cycles) if fresh_cycles else (1 if alive else 0),
        "phases": phases,
    }
