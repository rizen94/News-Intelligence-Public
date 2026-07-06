from __future__ import annotations
from config.runtime import env_bool, env_float, env_int, env_pop, env_set, env_setdefault, env_str
"""Detect operator pause while bulk_catchup.py runs (NI + NRI competition avoidance)."""


import json
import os
from datetime import datetime, timezone
from pathlib import Path

_PAUSE_ENV = "AUTOMATION_BULK_CATCHUP_PAUSE"
_PAUSE_FILE = Path(__file__).resolve().parents[2] / "data" / "bulk_catchup_competition_pause.json"

# Phases that may still run during bulk catch-up (pool safety / spill replay only).
BULK_PAUSE_ALLOW_PHASES: frozenset[str] = frozenset(
    {"health_check", "pending_db_flush"}
)

# GPU extraction phases deferred while bulk catch-up holds the competition pause.
BULK_PAUSE_DEFER_GPU_PHASES: frozenset[str] = frozenset(
    {
        "unified_intake_extraction",
        "entity_extraction",
        "event_extraction",
        "entity_profile_sync",
    }
)


def bulk_catchup_competition_pause_active() -> bool:
    if env_str(_PAUSE_ENV, "").strip().lower() in ("1", "true", "yes"):
        return True
    return _PAUSE_FILE.is_file()


def bulk_catchup_pause_allows_phase(phase_name: str) -> bool:
    return (phase_name or "").strip() in BULK_PAUSE_ALLOW_PHASES


def bulk_catchup_pause_defers_phase(phase_name: str) -> bool:
    """True when automation should not enqueue/run this phase during bulk catch-up."""
    if not bulk_catchup_competition_pause_active():
        return False
    if bulk_catchup_pause_allows_phase(phase_name):
        return False
    return (phase_name or "").strip() in BULK_PAUSE_DEFER_GPU_PHASES


def write_pause_marker(*, reason: str = "bulk_catchup", by: str = "operator") -> Path:
    _PAUSE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "paused_at": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "by": by,
    }
    _PAUSE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return _PAUSE_FILE


def clear_pause_marker() -> None:
    try:
        _PAUSE_FILE.unlink(missing_ok=True)
    except OSError:
        pass
