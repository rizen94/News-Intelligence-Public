"""
Load context-centric pipeline config (Phase 3.3 gradual migration).
Task flags control which context-centric tasks run; set to false to fall back to old system.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TASKS = {
    "context_sync": True,
    "entity_profile_sync": True,
    "claim_extraction": True,
    "legislative_references": True,
    "event_tracking": True,
    "event_coherence_review": True,
    "investigation_report_refresh": True,
    "entity_profile_build": True,
    "pattern_recognition": True,
    "entity_dossier_compile": True,
    "entity_position_tracker": True,
}


def get_context_centric_config() -> dict[str, Any]:
    """
    Load context_centric.yaml. Returns dict with "tasks" (task_name -> bool).
    Missing file or key => task enabled (True).
    """
    try:
        from config.paths import CONFIG_DIR

        yaml_path = CONFIG_DIR / "context_centric.yaml"
    except Exception as e:
        logger.debug("Context-centric config path unavailable: %s", e)
        return {"tasks": DEFAULT_TASKS.copy()}

    if not yaml_path.exists():
        return {"tasks": DEFAULT_TASKS.copy()}

    try:
        import yaml

        with open(yaml_path) as f:
            cfg = yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning("Failed to load context_centric.yaml: %s — using defaults", e)
        return {"tasks": DEFAULT_TASKS.copy()}

    tasks = cfg.get("tasks") or {}
    out = DEFAULT_TASKS.copy()
    for k in out:
        if k in tasks and isinstance(tasks[k], bool):
            out[k] = tasks[k]
    return {"tasks": out}


def is_context_centric_task_enabled(task_name: str) -> bool:
    """Return True if the given context-centric task is enabled (default True if config missing)."""
    cfg = get_context_centric_config()
    return cfg.get("tasks", {}).get(task_name, True)
