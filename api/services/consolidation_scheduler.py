"""
Consolidation scheduler — staggered runs for storylines, entities, investigations, and events.

Runs 4 consolidation types in rotation so that roughly every N hours one type runs.
Target: 2 runs per type per day, with runs spread so consolidation happens regularly.

Default: interval = 3 hours (8 runs per day, 4 types × 2 = 2x per type per day).
"""

import logging
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_INTERVAL = 3600
_DEFAULT_STARTUP_DELAY = 60
_DEFAULT_TYPES = ["storylines", "entities", "investigations", "events"]


@lru_cache(maxsize=1)
def _consolidation_config() -> dict[str, Any]:
    try:
        from services.automation.registry import load_schedulers_manifest

        raw = load_schedulers_manifest().get("consolidation") or {}
        if not isinstance(raw, dict):
            return {}
        return raw
    except Exception as exc:
        logger.debug("consolidation config load skipped: %s", exc)
        return {}


def _consolidation_interval_seconds() -> int:
    raw = _consolidation_config().get("interval_seconds", _DEFAULT_INTERVAL)
    try:
        return max(60, int(raw))
    except (TypeError, ValueError):
        return _DEFAULT_INTERVAL


def _consolidation_startup_delay_seconds() -> int:
    raw = _consolidation_config().get("startup_delay_seconds", _DEFAULT_STARTUP_DELAY)
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return _DEFAULT_STARTUP_DELAY


def _consolidation_types() -> list[str]:
    raw = _consolidation_config().get("rotation")
    if isinstance(raw, list) and raw:
        return [str(x) for x in raw]
    return list(_DEFAULT_TYPES)


CONSOLIDATION_INTERVAL_SECONDS = _consolidation_interval_seconds()
CONSOLIDATION_STARTUP_DELAY_SECONDS = _consolidation_startup_delay_seconds()
CONSOLIDATION_TYPES = _consolidation_types()


def run_consolidation_step(step_name: str) -> dict[str, Any]:
    """
    Run one consolidation step by name. Returns a result dict for logging.
    """
    result: dict[str, Any] = {"step": step_name, "success": False, "message": "", "details": {}}
    try:
        from shared.services.worker_health import record_worker_heartbeat

        record_worker_heartbeat(f"consolidation:{step_name}", status="running")
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
        record_worker_heartbeat(
            f"consolidation:{step_name}",
            status="healthy" if result["success"] else "degraded",
            detail=result.get("message"),
        )
    except Exception as e:
        logger.exception("Consolidation step %s failed: %s", step_name, e)
        result["message"] = str(e)
        try:
            from shared.services.worker_health import record_worker_heartbeat

            record_worker_heartbeat(
                f"consolidation:{step_name}",
                status="unhealthy",
                detail=str(e),
            )
        except Exception:
            pass
    return result


def get_rotation_index(run_count: int) -> int:
    """Return 0..3 for the next step in the rotation."""
    return run_count % len(CONSOLIDATION_TYPES)


def get_next_step_name(run_count: int) -> str:
    """Name of the consolidation type for this run count."""
    return CONSOLIDATION_TYPES[get_rotation_index(run_count)]
