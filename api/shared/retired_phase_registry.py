"""Registry of automation phases that must not run on default schedules (features.yaml enabled: false)."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# phases with features.yaml enabled: false and a phase_name (excluding non-scheduled entries)
RETIRED_AUTOMATION_SCHEDULE_PHASES: frozenset[str] = frozenset(
    {
        "entity_extraction",
        "event_extraction",
        "sentiment_analysis",
        "quality_scoring",
        "ml_processing",
        "metadata_enrichment",
        "pattern_recognition",
        "arc_report_generation",
        "longitudinal_matview_refresh",
        "relationship_extraction",
    }
)


def retired_automation_phases() -> frozenset[str]:
    """Phases that must not run on default schedules (hard-retired list)."""
    return RETIRED_AUTOMATION_SCHEDULE_PHASES


def apply_retired_schedule_suppression(schedules: dict[str, Any]) -> None:
    """Disable retired phase schedules and strip them from depends_on lists."""
    for name in RETIRED_AUTOMATION_SCHEDULE_PHASES:
        sched = schedules.get(name)
        if sched is not None:
            sched["enabled"] = False
            logger.debug("Automation schedule %s disabled (retired_phase_registry)", name)
    for sched_name, sched in schedules.items():
        deps = list(sched.get("depends_on") or [])
        new_deps = [d for d in deps if d not in RETIRED_AUTOMATION_SCHEDULE_PHASES]
        if new_deps != deps:
            sched["depends_on"] = new_deps
            logger.debug(
                "Automation: %s depends_on stripped retired phases: %s",
                sched_name,
                new_deps,
            )
