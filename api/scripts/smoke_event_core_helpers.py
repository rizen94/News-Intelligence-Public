#!/usr/bin/env python3
"""Unit-ish smoke tests for event-core quality-type helpers (no DB required)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_mod_path = ROOT / "api" / "services" / "event_core_membership_service.py"
spec = importlib.util.spec_from_file_location("event_core_membership_service", _mod_path)
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)

QUALITY_TYPE_SEED_EXAMPLES = m.QUALITY_TYPE_SEED_EXAMPLES
find_quality_anchors_in_text = m.find_quality_anchors_in_text
find_rare_anchors_in_text = m.find_rare_anchors_in_text


def test_cyclosporiasis_example_still_detected():
    hits = find_rare_anchors_in_text(
        "CDC investigates cyclosporiasis outbreak linked to lettuce recall",
        lexicon=list(QUALITY_TYPE_SEED_EXAMPLES),
    )
    assert "cyclosporiasis" in hits
    assert "lettuce recall" in hits


def test_instrument_and_morph_peers():
    q = find_quality_anchors_in_text(
        "Cryptosporidiosis cases; trial NCT01234567; docket 1:24-cv-00321"
    )
    values = {h["value"] for h in q}
    kinds = {h["kind"] for h in q}
    assert "cryptosporidiosis" in values
    assert "nct01234567" in values
    assert "1:24-cv-00321" in values
    assert "morph_osis" in kinds
    assert "trial_registration" in kinds
    assert "docket" in kinds


def test_common_tokens_not_quality_anchors():
    q = find_quality_anchors_in_text(
        "Trump oil prices soar amid Iran conflict and pandemic outbreak"
    )
    assert q == []
    assert "outbreak" not in QUALITY_TYPE_SEED_EXAMPLES
    assert "trump" not in {a.lower() for a in QUALITY_TYPE_SEED_EXAMPLES}


if __name__ == "__main__":
    test_cyclosporiasis_example_still_detected()
    test_instrument_and_morph_peers()
    test_common_tokens_not_quality_anchors()
    print("ok")
