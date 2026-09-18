"""
Automation schedule registry — metadata for phases (SSOT companion to automation_manager.schedules).

Full schedule dict remains in AutomationManager until incremental extraction completes.
Phase executors live in services.automation.executor.
"""

from __future__ import annotations

import copy
import threading
from pathlib import Path
from typing import Any

import yaml

from config.paths import CONFIG_DIR

_SCHEDULERS_PATH = CONFIG_DIR / "schedulers.yaml"

MENTION_RESOLUTION_PHASE = "mention_resolution"

# Phases gated when longitudinal tables empty (orchestrator_governance.yaml)
LONGITUDINAL_GATED_PHASES = frozenset(
    {
        "arc_report_generation",
        "longitudinal_matview_refresh",
    }
)


_MANIFEST_LOCK = threading.Lock()
_manifest_cache_key: tuple[Any, ...] | None = None
_manifest_cache: dict[str, Any] | None = None


def invalidate_schedulers_manifest_cache() -> None:
    """Drop the parsed manifest — the file stat check makes this rarely necessary."""
    global _manifest_cache_key, _manifest_cache
    with _MANIFEST_LOCK:
        _manifest_cache_key = None
        _manifest_cache = None


def load_schedulers_manifest() -> dict[str, Any]:
    """
    Parsed ``schedulers.yaml``, cached on the file's ``(mtime_ns, size)``.

    ``scheduler_entry`` / ``is_scheduler_enabled`` look up one key at a time, so each call used to
    re-parse the whole manifest (~3.6 ms). Same shape as
    ``config.orchestrator_governance.get_orchestrator_governance_config``. Callers get their own copy.
    """
    global _manifest_cache_key, _manifest_cache

    try:
        stat = _SCHEDULERS_PATH.stat()
    except OSError:
        return {}
    key = (str(_SCHEDULERS_PATH), stat.st_mtime_ns, stat.st_size)

    with _MANIFEST_LOCK:
        if _manifest_cache_key == key and _manifest_cache is not None:
            return copy.deepcopy(_manifest_cache)

    with open(_SCHEDULERS_PATH) as f:
        parsed = yaml.safe_load(f) or {}
    if not isinstance(parsed, dict):
        parsed = {}

    with _MANIFEST_LOCK:
        _manifest_cache_key = key
        _manifest_cache = parsed
    return copy.deepcopy(parsed)


def list_scheduler_owners() -> list[str]:
    """Return scheduler keys from schedulers.yaml manifest."""
    manifest = load_schedulers_manifest()
    schedulers = manifest.get("schedulers") or {}
    return sorted(schedulers.keys())


def scheduler_entry(name: str) -> dict[str, Any] | None:
    manifest = load_schedulers_manifest()
    schedulers = manifest.get("schedulers") or {}
    entry = schedulers.get(name)
    return dict(entry) if isinstance(entry, dict) else None


def is_scheduler_enabled(name: str, *, default: bool = True) -> bool:
    entry = scheduler_entry(name)
    if entry is None:
        return default
    return bool(entry.get("enabled", default))


def retired_systemd_units() -> list[str]:
    """Systemd units disabled after unification (see schedulers.yaml)."""
    units: list[str] = []
    for key in list_scheduler_owners():
        entry = scheduler_entry(key)
        if not entry or entry.get("enabled", True):
            continue
        unit = entry.get("unit")
        if unit:
            units.append(str(unit))
    return units
