"""
Consolidation scheduler — staggered runs for storylines, entities, investigations, and events.

Runs 4 consolidation types in rotation so that roughly every N hours one type runs.
Target: 2 runs per type per day, with runs spread so consolidation happens regularly.

Default: interval = 3 hours (8 runs per day, 4 types × 2 = 2x per type per day).
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Seconds between consolidation runs (1h = ~6x per type per day; use 10800 for 2x per type per day)
CONSOLIDATION_INTERVAL_SECONDS = 3600  # 1 hour — stagger so ~every hour one type runs

# Delay before first run after startup (seconds) so we don't hammer the system
CONSOLIDATION_STARTUP_DELAY_SECONDS = 60

# Rotation: 0=storylines, 1=entities, 2=investigations, 3=events (investigation superset again)
CONSOLIDATION_TYPES = ["storylines", "entities", "investigations", "events"]


def run_consolidation_step(step_name: str) -> dict[str, Any]:
    """
    Run one consolidation step by name. Returns a result dict for logging.
    """
    result: dict[str, Any] = {"step": step_name, "success": False, "message": "", "details": {}}
    try:
        if step_name == "storylines":
            from services.storyline_consolidation_service import get_consolidation_service

            service = get_consolidation_service()
            out = service.run_all_domains()
            result["success"] = True
            result["details"] = out
            result["message"] = f"storylines: {out.get('stats', {})}"
        elif step_name == "entities":
            from services.entity_organizer_service import run_cycle

            out = run_cycle(domain_key=None)
            result["success"] = len(out.get("errors") or []) == 0
            result["details"] = out
            result["message"] = (
                f"entities: cleanup={out.get('cleanup', {})}, relationships={out.get('relationships_extracted', 0)}"
            )
        elif step_name in ("investigations", "events"):
            from services.investigation_consolidation_service import run_consolidation

            out = run_consolidation(limit_events=200)
            result["success"] = len(out.get("errors") or []) == 0
            result["details"] = out
            result["message"] = (
                f"{step_name}: clusters={out.get('clusters_found', 0)}, "
                f"supersets_created={out.get('supersets_created', 0)}"
            )
        else:
            result["message"] = f"Unknown consolidation step: {step_name}"
    except Exception as e:
        logger.exception("Consolidation step %s failed: %s", step_name, e)
        result["message"] = str(e)
    return result


def get_rotation_index(run_count: int) -> int:
    """Return 0..3 for the next step in the rotation."""
    return run_count % len(CONSOLIDATION_TYPES)


def get_next_step_name(run_count: int) -> str:
    """Name of the consolidation type for this run count."""
    return CONSOLIDATION_TYPES[get_rotation_index(run_count)]
