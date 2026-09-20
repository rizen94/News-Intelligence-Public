"""Unit tests for package evidence briefs + expand helpers."""

from __future__ import annotations

from services.package_evidence_brief_service import REQUIRED_SECTIONS, compute_density


def test_compute_density_passes_with_sections_and_cites():
    # Need >=800 chars for the publish density gate.
    md = """## What We Know
- The Court held that occasional marijuana use alone cannot disarm under the Second Amendment in United States v. Hemani. [@m11]
- Wolford v. Lopez rejected a presumptive public-carry ban on private property open to the public. [@m12]

## Timeline
- 2025-10-01 — oral argument and subsequent decision sequence for Hemani. [@m13]
- Prior precedents Heller and Bruen frame the analysis and are cited throughout the opinions. [@m11]

## Supporting Evidence
- Reporting and event extracts corroborate the 9-0 Hemani outcome and the Wolford holding. [@m11]
- Additional contemporaneous coverage tracks the same case captions and holdings. [@m12]

## Contested / Uncertain
- Scope questions remain about how lower courts will apply the marijuana-use holding beyond Hemani's facts.

## Open Questions
- How will federal prosecutors revise charging guidance after Hemani?
- What follow-on Second Amendment dockets cite Wolford next term?
"""
    d = compute_density(md, {"m11": {}, "m12": {}, "m13": {}})
    assert d["unique_members_cited"] == 3
    assert d["sections_missing"] == []
    assert d["passes_gate"] is True


def test_compute_density_fails_when_thin():
    d = compute_density("Short stub [@m1]", {})
    assert d["passes_gate"] is False
    assert "## What We Know" in d["sections_missing"]


def test_required_sections_contract():
    assert "## What We Know" in REQUIRED_SECTIONS
    assert "## Open Questions" in REQUIRED_SECTIONS


def test_deterministic_gaps_via_importlib():
    import importlib.util
    import sys
    import types
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[1]
        / "api"
        / "services"
        / "editorial_package_evidence_expand_service.py"
    )
    spec = importlib.util.spec_from_file_location("evidence_expand_mod", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    stub_names = [
        "config.runtime",
        "shared.database.connection",
        "shared.editorial_package_theme",
    ]
    saved = {name: sys.modules.get(name) for name in stub_names}
    rt = types.ModuleType("config.runtime")
    rt.env_bool = lambda *a, **k: True
    rt.env_int = lambda *a, **k: 3
    sys.modules["config.runtime"] = rt
    db = types.ModuleType("shared.database.connection")
    db.get_ui_db_connection_context = lambda: None
    sys.modules["shared.database.connection"] = db
    theme = types.ModuleType("shared.editorial_package_theme")
    theme.is_theme_mismatch = lambda *a, **k: False
    theme.package_spine_tokens = lambda *a, **k: set()
    sys.modules["shared.editorial_package_theme"] = theme
    try:
        spec.loader.exec_module(mod)
        gaps = mod._deterministic_gaps(
            {
                "working_title": "United States v. Hemani",
                "summary_stub": "Second Amendment case",
                "members": [],
            }
        )
        ids = {g["id"] for g in gaps}
        assert "parties" in ids
        assert "holding" in ids
    finally:
        for name in stub_names:
            if saved[name] is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = saved[name]
