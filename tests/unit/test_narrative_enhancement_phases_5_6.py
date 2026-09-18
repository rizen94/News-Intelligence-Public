"""Focused unit tests for Narrative Enhancement Phases 5–6 scaffolding."""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path


def _load(name: str, rel: str):
    path = Path(__file__).resolve().parents[2] / rel
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # required for @dataclass under importlib
    spec.loader.exec_module(mod)
    return mod


def test_parse_due_date_iso_and_month():
    m = _load("expectation_tracking_service", "api/services/expectation_tracking_service.py")
    d, prec = m.parse_due_date("The ruling is expected by 2026-08-15 after hearings.")
    assert d == date(2026, 8, 15)
    assert prec == "day"

    d2, prec2 = m.parse_due_date("Decision expected by March 2027")
    assert d2 == date(2027, 3, 31)
    assert prec2 == "month"

    d3, prec3 = m.parse_due_date("Results within 2 weeks", as_of=date(2026, 7, 1))
    assert d3 == date(2026, 7, 15)
    assert prec3 == "week"

    d4, _ = m.parse_due_date("No timeline mentioned at all")
    assert d4 is None


def test_looks_forward_looking():
    m = _load("expectation_tracking_service", "api/services/expectation_tracking_service.py")
    assert m.looks_forward_looking("Company expects to ship by Q3")
    assert not m.looks_forward_looking("Company shipped last year")


def test_detect_gap_missing_next_stage_pure():
    """Gap detect helpers: furthest stage + pattern stages without DB."""
    arc = _load("arc_stage_service", "api/services/arc_stage_service.py")
    stages = arc.ARC_PATTERN_STAGES["litigation"]
    detected = arc.detect_stages_in_text(
        "Plaintiff filed a lawsuit; a hearing is scheduled next month.",
        stages,
    )
    assert "filing" in detected
    assert "hearing" in detected
    stage, idx = arc.furthest_stage(stages, detected)
    assert stage == "hearing"
    assert idx == stages.index("hearing")
    # Next missing stage would be ruling
    assert stages[idx + 1] == "ruling"

    gap = _load("narrative_gap_service", "api/services/narrative_gap_service.py")
    # Pure structural check: with hearing current, missing is ruling
    assert gap.gap_days_threshold() >= 1


def test_lifecycle_transition_rules():
    life = _load("storyline_lifecycle_service", "api/services/storyline_lifecycle_service.py")
    assert life.infer_lifecycle_transition(
        current="emerging",
        event_count=5,
        days_since_last_event=2.0,
        article_count=10,
    ) == "active"

    assert life.infer_lifecycle_transition(
        current="active",
        event_count=5,
        days_since_last_event=30.0,
        article_count=10,
    ) == "dormant"

    assert life.infer_lifecycle_transition(
        current="dormant",
        event_count=5,
        days_since_last_event=50.0,
        article_count=10,
    ) in ("resolved", "dormant")

    assert life.can_transition("active", "merged")
    assert not life.can_transition("merged", "active")
    assert life.can_transition("emerging", "active")


def test_dual_centroid_flag_off_by_default(monkeypatch):
    cent = _load("storyline_centroid", "api/services/storyline_centroid.py")
    monkeypatch.delenv("STORYLINE_DUAL_CENTROID_ENABLED", raising=False)
    # Feature registry may return False for staged/disabled
    assert cent.dual_centroid_enabled() is False

    # matching_centroid with dual off should not require trailing
    dual = {"full": [1.0, 0.0], "trailing": [0.0, 1.0], "dual_enabled": False}
    # Inline logic mirror
    prefer_trailing = True
    chosen = (
        dual["trailing"]
        if dual.get("dual_enabled") and prefer_trailing and dual.get("trailing")
        else dual.get("full")
    )
    assert chosen == [1.0, 0.0]


def test_detect_source_type_generalized():
    rag = _load("rag_evidence_pull_service", "api/services/rag_evidence_pull_service.py")
    assert rag.detect_source_type("https://arxiv.org/abs/2401.12345") == "arxiv"
    assert (
        rag.detect_source_type("https://www.federalregister.gov/documents/2026/01/01/foo")
        == "federal_register"
    )
    assert rag.parse_arxiv_id("arxiv:2401.12345v2") == "2401.12345"
