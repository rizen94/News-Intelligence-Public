"""Unit tests for research assemble mention extraction (no DB)."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

_ROOT = Path(__file__).resolve().parents[2]
_API = _ROOT / "api"
_PATH = _API / "services" / "research_assemble_service.py"

sys.path.insert(0, str(_API))

# Avoid services/__init__.py pulling live DB via automation_manager.
sys.modules.setdefault("shared.database.connection", MagicMock())
sys.modules.setdefault("shared.domain_registry", MagicMock())
sys.modules.setdefault("config.runtime", MagicMock())
sys.modules.setdefault("config.settings", MagicMock())

if "services" not in sys.modules:
    pkg = types.ModuleType("services")
    pkg.__path__ = [str(_API / "services")]  # type: ignore[attr-defined]
    sys.modules["services"] = pkg

# Lightweight stubs for assemble imports that are not under test.
sys.modules.setdefault("services.pattern_entity_extractor", MagicMock())
sys.modules.setdefault(
    "shared.post_processing_modals",
    MagicMock(modals_for_domain=lambda _dk: ("research", "narrative")),
)

_spec = importlib.util.spec_from_file_location(
    "services.research_assemble_service", _PATH
)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
sys.modules["services.research_assemble_service"] = _mod
_spec.loader.exec_module(_mod)

_HEADLINE_BAIT = _mod._HEADLINE_BAIT
_draft_sections = _mod._draft_sections
_extract_mention_candidates = _mod._extract_mention_candidates
_normalize_interpret_brief = _mod._normalize_interpret_brief


def test_extract_china_bonds_mentions():
    idea = "I saw a news story about china dropping US bonds and moving to gold"
    mentions = _extract_mention_candidates(idea)
    names = {m["name"].lower() for m in mentions}
    assert "china" in names or any("china" in n for n in names)
    assert any(n in names for n in ("gold", "us", "u.s.", "bonds", "united states"))


def test_headline_bait_not_extracted_as_entities():
    idea = "Revealed: How undercover agents spied on anti-ICE protesters in Minnesota"
    mentions = _extract_mention_candidates(idea)
    names = {m["name"].lower() for m in mentions}
    assert "revealed" not in names
    assert "how" not in names
    assert "revealed" in _HEADLINE_BAIT
    assert "ice" in names or any("ice" in n for n in names)
    assert "minnesota" in names


def test_draft_sections_structure():
    pkg = {
        "members": [
            {
                "status": "active",
                "member_type": "extracted_claim",
                "provenance": {"label": "China reduced Treasury holdings"},
            },
            {
                "status": "active",
                "member_type": "chronological_event",
                "provenance": {"label": "2024 holdings report released"},
            },
        ]
    }
    sections = _draft_sections(pkg, idea="China bonds to gold")
    assert sections["whats_new"]
    assert "## What's new" in sections["brief_md"]
    assert "## Timeline" in sections["brief_md"]


def test_normalize_interpret_brief_keeps_assumptions():
    brief = _normalize_interpret_brief(
        {
            "working_title": "China Treasuries vs gold",
            "research_question": "Did official China reduce US Treasuries while raising gold?",
            "domain_key": "finance",
            "entities": [{"name": "PBOC", "entity_type": "organization", "role": "actor"}],
            "key_assumptions": ["Means official holdings"],
            "facts_to_verify": ["Treasury holdings trend"],
            "search_queries": ["China US Treasury holdings", "PBOC gold reserves"],
            "time_scope": "last decade",
            "exclusions": ["jewelry retail"],
            "open_questions": ["Private vs official?"],
        },
        idea="china bonds gold",
        domain_key=None,
    )
    assert brief["domain_key"] == "finance"
    assert brief["entities"][0]["name"] == "PBOC"
    assert "China US Treasury holdings" in brief["search_queries"]
    assert brief["source"] == "llm"
