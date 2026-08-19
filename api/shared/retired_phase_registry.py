"""Registry of automation phases that must not run on default schedules.

Hard-retired = no schedule entry in AutomationManager, and any accidental
enqueue / Monitor force-run is refused at execute time. Archived runners may
still load under LEGACY_INTAKE_EXTRACTION_ENABLED for emergency rollback scripts,
but they are never re-enabled via schedules.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Phases with features.yaml enabled:false / archived — must not appear in schedules.
RETIRED_AUTOMATION_SCHEDULE_PHASES: frozenset[str] = frozenset(
    {
        # Superseded by unified_intake_extraction
        "entity_extraction",
        "event_extraction",
        "sentiment_analysis",
        "quality_scoring",
        "ml_processing",
        "metadata_enrichment",
        # Fully retired briefing / digest batch synthesizers
        "editorial_document_generation",
        "editorial_briefing_generation",
        "daily_briefing_synthesis",
        "digest_generation",
        # Under-developed / empty data — scheduler off permanently until re-designed
        "pattern_recognition",
        "arc_report_generation",
        "longitudinal_matview_refresh",
        # Archived service (on-demand loader only; never scheduled)
        "relationship_extraction",
    }
)


def retired_automation_phases() -> frozenset[str]:
    """Phases that must not run on default schedules (hard-retired list)."""
    return RETIRED_AUTOMATION_SCHEDULE_PHASES


def is_hard_retired_schedule_phase(phase_name: str) -> bool:
    return (phase_name or "").strip() in RETIRED_AUTOMATION_SCHEDULE_PHASES


def apply_retired_schedule_suppression(schedules: dict[str, Any]) -> None:
    """
    Safety net: if a hard-retired phase is re-added to schedules by mistake,
    force it disabled and strip from depends_on. Prefer deleting the schedule
    entry entirely — this only catches accidental reintroductions.
    """
    for name in RETIRED_AUTOMATION_SCHEDULE_PHASES:
        sched = schedules.get(name)
        if sched is not None:
            sched["enabled"] = False
            logger.warning(
                "Automation schedule %s present but hard-retired — forced disabled "
                "(remove the schedule entry; do not re-enable)",
                name,
            )
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
