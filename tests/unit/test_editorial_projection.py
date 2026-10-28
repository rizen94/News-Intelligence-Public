"""Tests for editorial projection + retired schedule suppression."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from shared.retired_phase_registry import (
    RETIRED_AUTOMATION_SCHEDULE_PHASES,
    apply_retired_schedule_suppression,
    is_hard_retired_schedule_phase,
)

_API = Path(__file__).resolve().parents[2] / "api"
_PROJ = _API / "services" / "editorial_projection_service.py"
_DESK = _API / "services" / "desk_promotion_service.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_editorial_phases_are_hard_retired():
    assert is_hard_retired_schedule_phase("editorial_document_generation")
    assert is_hard_retired_schedule_phase("editorial_briefing_generation")
    assert "editorial_document_generation" in RETIRED_AUTOMATION_SCHEDULE_PHASES


def test_apply_retired_schedule_suppression_disables_and_strips_deps():
    schedules = {
        "editorial_document_generation": {
            "enabled": True,
            "depends_on": [],
            "interval": 1800,
        },
        "digest_generation": {
            "enabled": True,
            "depends_on": ["editorial_document_generation"],
            "interval": 3600,
        },
        "story_enhancement": {
            "enabled": True,
            "depends_on": [],
            "interval": 300,
        },
    }
    apply_retired_schedule_suppression(schedules)
    assert schedules["editorial_document_generation"]["enabled"] is False
    assert schedules["digest_generation"]["enabled"] is False
    assert schedules["digest_generation"]["depends_on"] == []
    assert schedules["story_enhancement"]["enabled"] is True


def test_prose_to_editorial_patch_maps_lede_and_bullets():
    mod = _load("editorial_projection_service_ut", _PROJ)
    patch = mod.prose_to_editorial_patch(
        title="Test arc",
        lede="One-sentence lede about the story.",
        body_md=(
            "One-sentence lede about the story.\n\n"
            "Longer analysis paragraph that explains significance for readers "
            "and gives enough length to count as analysis text.\n\n"
            "- First concrete development landed today\n"
            "- Second concrete development with more detail\n\n"
            "## Outlook\n\nWatch the next hearing for updates."
        ),
    )
    assert patch["lede"].startswith("One-sentence")
    assert isinstance(patch.get("what"), list) and len(patch["what"]) >= 1
    assert "analysis" in patch
    assert "outlook" in patch
    assert patch.get("generated_at")


def test_prose_to_editorial_patch_prefers_brief_md():
    mod = _load("editorial_projection_service_ut2", _PROJ)
    patch = mod.prose_to_editorial_patch(
        lede="",
        body_md="Short body only.",
        brief_md=(
            "Evidence brief lede with enough characters to win over the short body.\n\n"
            "Second paragraph of brief analysis for projection into editorial_document.\n\n"
            "- Brief bullet one with substance\n"
            "- Brief bullet two with substance"
        ),
    )
    assert "Evidence brief lede" in patch["lede"]
    assert patch.get("what")


def test_merge_preserves_desk_provenance():
    desk = _load("desk_promotion_service_ut", _DESK)
    existing = {
        "lede": "Desk lede",
        "desk_provenance": {"source": "desk_agent", "vault_path": "x.md"},
    }
    merged = desk.merge_editorial_document(
        existing,
        {"lede": "Package lede", "analysis": "New analysis"},
        provenance={"source": "package_publish", "package_id": 9},
    )
    assert merged["lede"] == "Package lede"
    assert merged["analysis"] == "New analysis"
    assert merged["desk_provenance"]["source"] == "package_publish"
    assert merged["desk_provenance"]["package_id"] == 9
    assert merged["desk_provenance"]["vault_path"] == "x.md"


def test_parse_storyline_legacy_seed():
    mod = _load("editorial_projection_service_ut3", _PROJ)
    assert mod.parse_storyline_legacy_seed("storyline:politics:12094") == ("politics", 12094)
    assert mod.parse_storyline_legacy_seed("entity:medicine:3") is None
    assert mod.parse_storyline_legacy_seed("") is None
