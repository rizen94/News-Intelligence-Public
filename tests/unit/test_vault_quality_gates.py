"""Unit tests for vault quality gates (import module file to avoid services.__init__)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "api/services/vault_quality_gates.py"
_SPEC = importlib.util.spec_from_file_location("vault_quality_gates", _PATH)
assert _SPEC and _SPEC.loader
vg = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(vg)


def test_is_junk_title_html():
    assert vg.is_junk_title('MBTA / class="rrssb-text">email</span></a></li><li')
    assert vg.is_junk_title("/><b>Sponsors</b>: / Artificial Intelligence")
    assert not vg.is_junk_title("TikTok to pay Alabama $100m")


def test_title_body_overlap():
    title = "Healey sets budget for late October"
    body = "Chancellor John Healey will deliver the budget in late October and spread money across the UK."
    assert vg.title_body_token_overlap(title, body) >= 0.15
    bad = "A Kemp's ridley sea turtle is thriving in Houston despite pneumonia."
    assert vg.title_body_token_overlap(title, bad) < 0.15


def test_expansion_coherence_rejects_mismatch(monkeypatch):
    monkeypatch.setattr(vg, "expansion_coherence_gate_enabled", lambda: True)
    ok, reason = vg.expansion_coherence_ok(
        title="Healey sets budget for late October",
        body=(
            "A Kemp's ridley sea turtle native to the Gulf of Mexico is thriving "
            "in Houston despite lingering pneumonia after rescue from a Welsh beach."
        ),
    )
    assert ok is False
    assert "overlap" in reason


def test_expansion_coherence_accepts_aligned(monkeypatch):
    monkeypatch.setattr(vg, "expansion_coherence_gate_enabled", lambda: True)
    body = (
        "Chancellor John Healey will deliver the UK budget in late October. "
        "He promised to spread money and power around the country while buffering "
        "against fiscal uncertainty after being appointed by Andy Burnham."
    )
    ok, reason = vg.expansion_coherence_ok(
        title="Healey sets budget for late October",
        body=body,
        member_titles=[
            "Healey to deliver Budget on October 28",
            "Healey sets budget for late October, promising to spread money",
        ],
        article_count=2,
    )
    assert ok is True
    assert reason == "ok"


def test_expansion_coherence_rejects_small_kitchen_sink(monkeypatch):
    """Discovery seeds with 3–11 unrelated members must fail (was >=12 only)."""
    monkeypatch.setattr(vg, "expansion_coherence_gate_enabled", lambda: True)
    body = (
        "SpaceX, founded by Elon Musk, reported record Q2 revenue of $7.81 billion, "
        "beating Wall Street expectations while remaining unprofitable."
    )
    ok, reason = vg.expansion_coherence_ok(
        title="Elon Musk's SpaceX Surges Past Expectations as Wall Street Hits Record Highs",
        body=body,
        member_titles=[
            "SpaceX beats expectations by posting revenue of $7.81bn in second quarter",
            "Lisa Nandy quits X over fears Musk-owned site pushes abuse and misinformation",
            "US consumer sentiment improves in June due to easing gas prices",
            "Trump says ICE will deploy to airports Monday to assist TSA amid funding standoff",
            "Trump Threatens To Deploy ICE To Airports If Democrats Won't Fund DHS",
        ],
        article_count=5,
    )
    assert ok is False
    assert "magnet_membership" in reason


def test_briefing_citations(monkeypatch):
    monkeypatch.setattr(vg, "briefing_require_citations_enabled", lambda: True)
    expansions = [
        {
            "storyline_id": 5034,
            "domain_key": "politics",
            "title": "Healey to Deliver Budget on October 28",
        }
    ]
    body = "## Ongoing\n- Update on politics/5034 Healey to Deliver Budget on October 28"
    ok, _ = vg.briefing_citations_ok(body, expansions=expansions)
    assert ok is True
    bad = "## News\n- A new coral species was found at CERN somehow."
    ok2, reason = vg.briefing_citations_ok(bad, expansions=expansions)
    assert ok2 is False


def test_daily_briefing_serve_allowed(monkeypatch):
    monkeypatch.setattr(vg, "briefing_require_citations_enabled", lambda: True)
    monkeypatch.setattr(
        vg,
        "expansions_for_briefing_day",
        lambda _day, limit=40: [
            {
                "storyline_id": 99,
                "domain_key": "politics",
                "title": "Test Arc",
            }
        ],
    )
    ok, _ = vg.daily_briefing_serve_allowed(
        "Update on politics/99 Test Arc continues.",
        briefing_day="2026-10-04",
    )
    assert ok is True
    ok2, reason = vg.daily_briefing_serve_allowed(
        "Invented CERN coral briefing with no markers.",
        briefing_day="2026-10-04",
    )
    assert ok2 is False
    assert reason
