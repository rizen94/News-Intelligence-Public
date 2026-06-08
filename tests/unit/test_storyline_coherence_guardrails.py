"""Storyline coherence guardrails — generic titles and finance earnings clusters."""

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_GUARDRAILS_PATH = _ROOT / "api" / "services" / "storyline_coherence_guardrails.py"


def _load_guardrails():
    name = "storyline_coherence_guardrails"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _GUARDRAILS_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


g = _load_guardrails()
_NOW = datetime.now(timezone.utc)


def _article(title: str, summary: str = "") -> dict:
    return {"title": title, "summary": summary, "content": ""}


class _Child:
    def __init__(self, title: str, entities: set[str]):
        self.title = title
        self.entities = entities


def test_generic_finance_reports_title_rejected():
    assert g.is_overly_generic_storyline_title("Reports", "finance") is True
    assert g.is_overly_generic_storyline_title("Earnings", "finance") is True
    assert g.is_overly_generic_storyline_title("Q2 Earnings Reports", "finance") is True
    assert g.is_overly_generic_storyline_title("Ongoing: Reports", "finance") is True


def test_specific_finance_title_allowed():
    assert (
        g.is_overly_generic_storyline_title(
            "Semiconductor earnings misses widen on tariff uncertainty", "finance"
        )
        is False
    )


def test_unrelated_company_reports_cluster_rejected():
    articles = [
        _article("Apple reports Q2 earnings beat expectations"),
        _article("ExxonMobil reports quarterly results"),
        _article("Walmart reports earnings for fiscal Q2"),
        _article("JPMorgan Chase reports net income rise"),
    ]
    ok, reason = g.assess_cluster_coherence(
        "finance", "Mixed Q2 corporate filings", articles
    )
    assert ok is False
    assert reason == "finance_generic_earnings_reports"


def test_sector_earnings_theme_cluster_allowed():
    articles = [
        _article("Retailers miss expectations as consumer spending slows"),
        _article("Target missed analyst expectations on same-store sales"),
        _article("Macy's lowered guidance after revenue decline"),
        _article("Kohl's profit warning adds to sector weakness"),
    ]
    ok, reason = g.assess_cluster_coherence(
        "finance", "Retail sector misses expectations", articles
    )
    assert ok is True
    assert reason in {"finance_earnings_theme", "entity_diversity", "dominant_entity:target"}


def test_mega_earnings_children_without_shared_entities_blocked():
    children = [
        _Child("Apple Q2 earnings report", {"apple"}),
        _Child("Exxon quarterly earnings", {"exxon"}),
    ]
    ok, reason = g.assess_mega_group_coherence("finance", children)
    assert ok is False
    assert reason == "finance_earnings_mega_insufficient_entities"
