"""
Cross-process DB pool pressure advisory (single-row table).

In-process waiters live in ``connection._pool_waiters``. Remote PopOS workers cannot
see them, so the API publishes a compact row (AutomationManager headroom tick,
``GET .../automation/status``, or first checkout waiter) that workers read before drain.
Uses ephemeral connections so publish/read never compete for the worker pool.

Same module on Widow and PopOS (``~/ni-popos-worker`` → this repo).
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

_LAST_PUBLISH_MONO = 0.0
_LAST_PUBLISH_SIGNATURE: Optional[tuple] = None


def _threshold() -> float:
    try:
        return float(os.getenv("AUTOMATION_DB_WORKER_UTILIZATION_SKIP_THRESHOLD", "0.82"))
    except ValueError:
        return 0.82


def _stale_sec() -> float:
    try:
        return max(15.0, float(os.getenv("DB_POOL_PRESSURE_ADVISORY_STALE_SEC", "120")))
    except ValueError:
        return 120.0


def _min_publish_interval_sec() -> float:
    try:
        return max(0.5, float(os.getenv("DB_POOL_PRESSURE_ADVISORY_PUBLISH_INTERVAL_SEC", "2")))
    except ValueError:
        return 2.0


def build_pool_pressure_signal(
    snap: Optional[dict[str, Any]] = None,
    *,
    source: str = "api",
) -> dict[str, Any]:
    """Build advisory payload from a pool snapshot (or live snapshot)."""
    if snap is None:
        from shared.database.connection import get_db_pool_snapshot

        snap = get_db_pool_snapshot()
    worker = (snap or {}).get("worker") or {}
    ui = (snap or {}).get("ui") or {}
    thr = _threshold()
    utilization = float(worker.get("utilization") or 0.0)
    pressure = float(worker.get("pressure") or utilization)
    waiters = int(worker.get("waiters") or 0)
    defer = pressure >= thr or waiters > 0
    return {
        "source": source,
        "worker_in_use": int(worker.get("in_use") or 0),
        "worker_max": int(worker.get("max") or 0),
        "worker_waiters": waiters,
        "worker_utilization": round(utilization, 3),
        "worker_pressure": round(pressure, 3),
        "defer_new_work": defer,
        "threshold": thr,
        "ui_in_use": int(ui.get("in_use") or 0),
        "ui_max": int(ui.get("max") or 0),
        "ui_waiters": int(ui.get("waiters") or 0),
        "ui_pressure": float(ui.get("pressure") or ui.get("utilization") or 0.0),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "db_pool": snap,
    }


def publish_db_pool_pressure_advisory(
    snap: Optional[dict[str, Any]] = None,
    *,
    source: str = "api",
    force: bool = False,
) -> Optional[dict[str, Any]]:
    """
    Upsert the single advisory row. Throttled unless ``force`` or defer/waiter state changes.
    """
    global _LAST_PUBLISH_MONO, _LAST_PUBLISH_SIGNATURE
    signal = build_pool_pressure_signal(snap, source=source)
    signature = (
        signal["defer_new_work"],
        signal["worker_waiters"],
        round(float(signal["worker_pressure"]), 2),
        signal["worker_in_use"],
    )
    now = time.monotonic()
    # Always publish when waiters appear so remote workers see defer promptly.
    if int(signal["worker_waiters"] or 0) > 0:
        force = True
    if (
        not force
        and signature == _LAST_PUBLISH_SIGNATURE
        and (now - _LAST_PUBLISH_MONO) < _min_publish_interval_sec()
    ):
        return signal

    try:
        from shared.database.connection import get_ephemeral_db_connection_context

        with get_ephemeral_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.db_pool_pressure_advisory AS t (
                        id, source, worker_in_use, worker_max, worker_waiters,
                        worker_utilization, worker_pressure, defer_new_work,
                        updated_at, detail
                    ) VALUES (
                        1, %s, %s, %s, %s, %s, %s, %s, NOW(), %s::jsonb
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        source = EXCLUDED.source,
                        worker_in_use = EXCLUDED.worker_in_use,
                        worker_max = EXCLUDED.worker_max,
                        worker_waiters = EXCLUDED.worker_waiters,
                        worker_utilization = EXCLUDED.worker_utilization,
                        worker_pressure = EXCLUDED.worker_pressure,
                        defer_new_work = EXCLUDED.defer_new_work,
                        updated_at = NOW(),
                        detail = EXCLUDED.detail
                    """,
                    (
                        source,
                        signal["worker_in_use"],
                        signal["worker_max"],
                        signal["worker_waiters"],
                        signal["worker_utilization"],
                        signal["worker_pressure"],
                        signal["defer_new_work"],
                        json.dumps(
                            {
                                "threshold": signal["threshold"],
                                "ui_in_use": signal["ui_in_use"],
                                "ui_max": signal["ui_max"],
                                "ui_waiters": signal["ui_waiters"],
                                "ui_pressure": signal["ui_pressure"],
                            }
                        ),
                    ),
                )
            conn.commit()
        _LAST_PUBLISH_MONO = now
        _LAST_PUBLISH_SIGNATURE = signature
        return signal
    except Exception as e:
        logger.debug("publish_db_pool_pressure_advisory failed: %s", e)
        return signal


def read_db_pool_pressure_advisory(
    *,
    max_age_sec: Optional[float] = None,
) -> dict[str, Any]:
    """
    Read advisory for remote workers. If missing/stale, returns defer_new_work=False.
    """
    stale_after = _stale_sec() if max_age_sec is None else max(1.0, float(max_age_sec))
    out: dict[str, Any] = {
        "available": False,
        "stale": True,
        "defer_new_work": False,
        "age_sec": None,
    }
    try:
        from shared.database.connection import get_ephemeral_db_connection_context

        with get_ephemeral_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT source, worker_in_use, worker_max, worker_waiters,
                           worker_utilization, worker_pressure, defer_new_work,
                           updated_at, detail,
                           EXTRACT(EPOCH FROM (NOW() - updated_at)) AS age_sec
                    FROM public.db_pool_pressure_advisory
                    WHERE id = 1
                    """
                )
                row = cur.fetchone()
        if not row:
            return out
        (
            source,
            in_use,
            maxc,
            waiters,
            util,
            pressure,
            defer,
            updated_at,
            detail,
            age_sec,
        ) = row
        age = float(age_sec) if age_sec is not None else None
        stale = age is None or age > stale_after
        out.update(
            {
                "available": True,
                "stale": stale,
                "source": source,
                "worker_in_use": int(in_use or 0),
                "worker_max": int(maxc or 0),
                "worker_waiters": int(waiters or 0),
                "worker_utilization": float(util or 0.0),
                "worker_pressure": float(pressure or 0.0),
                "defer_new_work": bool(defer) and not stale,
                "updated_at": updated_at.isoformat()
                if hasattr(updated_at, "isoformat")
                else str(updated_at),
                "age_sec": round(age, 1) if age is not None else None,
                "detail": detail if isinstance(detail, dict) else {},
            }
        )
        return out
    except Exception as e:
        logger.debug("read_db_pool_pressure_advisory failed: %s", e)
        out["error"] = str(e)[:160]
        return out


def _soft_defer_threshold() -> float:
    """Intake phases may run until this pressure when there are no waiters."""
    try:
        return float(os.getenv("AUTOMATION_DB_WORKER_UTILIZATION_SOFT_SKIP_THRESHOLD", "0.94"))
    except ValueError:
        return 0.94


def _soft_defer_phases() -> set[str]:
    """Phases that soft-defer (waiters or near-ceiling) instead of the hard 0.82 gate."""
    base = {"unified_intake_extraction", "chronological_events_catchup"}
    raw = (os.getenv("AUTOMATION_DB_POOL_SOFT_DEFER_PHASES", "") or "").strip()
    if not raw:
        return set(base)
    return {x.strip() for x in raw.split(",") if x.strip()} | base


def remote_should_defer_phase(phase_name: str) -> tuple[bool, dict[str, Any]]:
    """
    PopOS / remote workers: True if Widow advisory says defer and phase is not exempt.

    Intake soft-defer: when waiters==0 and pressure is below the soft ceiling (default 0.94),
    allow unified_intake_extraction / chronological_events_catchup even if the hard
    advisory flag is set (hard threshold default 0.82). Still defer when anyone is waiting
    on the worker pool or pressure hits the soft ceiling.
    """
    raw = (os.getenv("POPOS_DB_PRESSURE_DEFER_ENABLED", "true") or "true").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False, {"enabled": False}
    exempt_raw = os.getenv("AUTOMATION_DB_POOL_GATE_EXEMPT_PHASES", "").strip()
    exempt = {"health_check", "pending_db_flush"}
    if exempt_raw:
        exempt |= {x.strip() for x in exempt_raw.split(",") if x.strip()}
    if phase_name in exempt:
        return False, {"exempt": True, "phase": phase_name}
    adv = read_db_pool_pressure_advisory()
    if not bool(adv.get("defer_new_work")):
        return False, adv

    if phase_name in _soft_defer_phases():
        waiters = int(adv.get("worker_waiters") or 0)
        pressure = float(adv.get("worker_pressure") or 0.0)
        soft_thr = _soft_defer_threshold()
        if waiters == 0 and pressure < soft_thr:
            soft_adv = {
                **adv,
                "soft_allow": True,
                "soft_threshold": soft_thr,
                "hard_defer_bypassed": True,
            }
            return False, soft_adv
        return True, {
            **adv,
            "soft_threshold": soft_thr,
            "soft_block_reason": "waiters" if waiters > 0 else "soft_ceiling",
        }

    return True, adv
