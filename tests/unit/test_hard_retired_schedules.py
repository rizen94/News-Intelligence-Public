"""Hard-retired phases must not reappear in AutomationManager schedules."""

from __future__ import annotations

from shared.retired_phase_registry import RETIRED_AUTOMATION_SCHEDULE_PHASES


def test_hard_retired_phases_are_named():
    assert "entity_extraction" in RETIRED_AUTOMATION_SCHEDULE_PHASES
    assert "digest_generation" in RETIRED_AUTOMATION_SCHEDULE_PHASES
    assert "pattern_recognition" in RETIRED_AUTOMATION_SCHEDULE_PHASES


def test_apply_retired_suppression_forces_disabled_if_reintroduced():
    from shared.retired_phase_registry import apply_retired_schedule_suppression

    schedules = {
        "entity_extraction": {
            "enabled": True,
            "depends_on": [],
        },
        "mention_resolution": {
            "enabled": True,
            "depends_on": ["entity_extraction", "unified_intake_extraction"],
        },
    }
    apply_retired_schedule_suppression(schedules)
    assert schedules["entity_extraction"]["enabled"] is False
    assert schedules["mention_resolution"]["depends_on"] == ["unified_intake_extraction"]


def test_schedule_source_has_no_hard_retired_keys():
    """Parse automation_manager schedule dict keys without importing the heavy module."""
    from pathlib import Path
    import re

    path = Path(__file__).resolve().parents[2] / "api" / "services" / "automation_manager.py"
    text = path.read_text(encoding="utf-8")
    # Locate self.schedules = { ... } block roughly via the collection_cycle key start
    # through the closing of that dict (pending_db_flush is last known schedule).
    m = re.search(
        r'self\.schedules\s*=\s*\{(.*?)"pending_db_flush"\s*:\s*\{.*?\},?\s*\n\s*\}',
        text,
        re.DOTALL,
    )
    assert m, "could not locate self.schedules dict in automation_manager.py"
    block = m.group(0)
    for phase in sorted(RETIRED_AUTOMATION_SCHEDULE_PHASES):
        # Schedule keys look like: "phase_name": {
        assert f'"{phase}":' not in block, (
            f"hard-retired phase {phase!r} still has a schedule entry — "
            "remove it; do not re-enable via enabled=True"
        )
