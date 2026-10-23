"""
Automation schedule registry — metadata for phases (SSOT companion to automation_manager.schedules).

Full schedule dict remains in AutomationManager until incremental extraction completes.
Phase executors live in services.automation.executor.
"""

from __future__ import annotations

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


def load_schedulers_manifest() -> dict[str, Any]:
    if not _SCHEDULERS_PATH.exists():
        return {}
    with open(_SCHEDULERS_PATH) as f:
        return yaml.safe_load(f) or {}


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
