"""In-process worker health registry for background services."""

from __future__ import annotations

import time
from typing import Any


_registry: dict[str, dict[str, Any]] = {}


def record_worker_heartbeat(name: str, *, status: str = "healthy", detail: str | None = None) -> None:
    _registry[name] = {
        "status": status,
        "detail": detail,
        "last_heartbeat": time.time(),
    }


def get_worker_health(name: str) -> dict[str, Any] | None:
    return _registry.get(name)


def list_worker_health() -> dict[str, dict[str, Any]]:
    return dict(_registry)
