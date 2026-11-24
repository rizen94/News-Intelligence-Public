"""Research subject index helpers."""
import importlib.util
from pathlib import Path

_path = (
    Path(__file__).resolve().parents[2]
    / "api"
    / "domains"
    / "reader"
    / "routes"
    / "research_subjects.py"
)
_spec = importlib.util.spec_from_file_location("research_subjects", _path)
_mod = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)
_prefer_subject_card = _mod._prefer_subject_card


def test_prefer_subject_card_more_assertions_wins():
    existing = {
        "assertion_counts": {"is": 0, "is_not": 0, "open": 0},
        "status": "published",
        "profile_id": 1,
        "canonical_entity_id": 100,
    }
    candidate = {
        "assertion_counts": {"is": 2, "is_not": 0, "open": 1},
        "status": "draft",
        "profile_id": 2,
        "canonical_entity_id": 200,
    }
    assert _prefer_subject_card(existing, candidate)


def test_prefer_subject_card_keeps_richer_when_candidate_empty():
    existing = {
        "assertion_counts": {"is": 1, "is_not": 0, "open": 0},
        "status": "published",
        "profile_id": 1,
        "canonical_entity_id": 100,
    }
    candidate = {
        "assertion_counts": {"is": 0, "is_not": 0, "open": 0},
        "status": "published",
        "profile_id": None,
        "canonical_entity_id": 200,
    }
    assert not _prefer_subject_card(existing, candidate)