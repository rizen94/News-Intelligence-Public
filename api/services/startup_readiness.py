"""Startup readiness checks for systemd and monitoring."""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import Request

logger = logging.getLogger(__name__)


def _ollama_local_status() -> str:
    """Return ok, degraded, or unavailable for local Ollama."""
    try:
        import urllib.request

        host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        req = urllib.request.Request(f"{host}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                return "ok"
    except Exception as exc:
        logger.debug("ollama local readiness: %s", exc)
    return "degraded"


def _disabled_schedules() -> list[str]:
    raw = os.getenv("AUTOMATION_DISABLED_SCHEDULES", "").strip()
    if not raw:
        return []
    return sorted({x.strip() for x in raw.split(",") if x.strip()})


def _is_phase_disabled(phase: str) -> bool:
    return phase.strip() in _disabled_schedules()


def build_startup_readiness(request: Request) -> dict[str, Any]:
    """Build readiness payload; ready=true only when core pipeline subsystems are live."""
    from shared.database.db_availability import is_automation_db_ready

    automation = getattr(request.app.state, "automation", None)
    automation_thread = getattr(request.app.state, "automation_thread", None)
    coordinator_thread = getattr(request.app.state, "coordinator_thread", None)

    db_ok = is_automation_db_ready()
    thread_alive = bool(automation_thread and automation_thread.is_alive())
    automation_running = bool(automation and getattr(automation, "is_running", False))
    coordinator_alive = bool(coordinator_thread and coordinator_thread.is_alive())

    try:
        from services.pipeline_schedule_service import pipeline_schedule_info

        schedule_info = pipeline_schedule_info()
        pipeline_window = schedule_info.get("active_window", "unknown")
    except Exception:
        schedule_info = {}
        pipeline_window = "unknown"

    checks = {
        "database": "ok" if db_ok else "unavailable",
        "automation_thread_alive": thread_alive,
        "automation_running": automation_running,
        "coordinator_thread_alive": coordinator_alive,
        "ollama_local": _ollama_local_status(),
        "pipeline_window": pipeline_window,
        "disabled_schedules": _disabled_schedules(),
    }

    ready = db_ok and thread_alive and automation_running

    return {
        "ready": ready,
        "checks": checks,
        "pipeline_schedule": schedule_info,
    }
