"""Unit tests for NRI bridge QA heuristics."""

import importlib.util
import sys
from pathlib import Path

_API = Path(__file__).resolve().parents[2] / "api"
_QA_PATH = _API / "_archived" / "services" / "nri_bridge_qa_service.py"
_spec = importlib.util.spec_from_file_location("nri_bridge_qa_service", _QA_PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["nri_bridge_qa_service"] = _mod
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
assess_bridge_qa = _mod.assess_bridge_qa


def test_exact_name_match_ok():
    qa = assess_bridge_qa(
        ni_canonical_name="GitHub",
        ftm_caption="GitHub",
        ni_entity_type="organization",
        ftm_schema_name="LegalEntity",
    )
    assert qa["qa_status"] == "ok"
    assert qa["name_similarity"] == 1.0


def test_wrong_person_mismatch():
    qa = assess_bridge_qa(
        ni_canonical_name="Rand Paul",
        ftm_caption="Taylor Frankie Paul",
        ni_entity_type="person",
        ftm_schema_name="Person",
        ftm_dataset="wikidata_lazy",
    )
    assert qa["qa_status"] == "mismatch"
    assert "name_mismatch" in qa["qa_flags"]


def test_schema_type_swap_suspect():
    qa = assess_bridge_qa(
        ni_canonical_name="Democratic party",
        ftm_caption="Democratic Party",
        ni_entity_type="organization",
        ftm_schema_name="Person",
    )
    assert qa["qa_status"] == "suspect"
    assert "person_org_schema_swap" in qa["qa_flags"]


def test_generic_caption_suspect():
    qa = assess_bridge_qa(
        ni_canonical_name="hearing",
        ftm_caption="hearing",
        ni_entity_type="organization",
        ftm_schema_name="LegalEntity",
    )
    assert qa["qa_status"] == "suspect"
    assert "generic_caption" in qa["qa_flags"]


def test_short_mention_flag():
    qa = assess_bridge_qa(
        ni_canonical_name="EU",
        ftm_caption="European Union",
        mention_text="EU",
        ni_entity_type="organization",
        ftm_schema_name="LegalEntity",
    )
    assert "wikidata_lazy_short_name" in qa["qa_flags"]
