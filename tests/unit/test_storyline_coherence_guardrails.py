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
    assert reason in {
        "insufficient_shared_entities",
        "finance_earnings_mega_insufficient_entities",
    }


def test_placeholder_mega_title_detected():
    assert g.is_placeholder_mega_title("Ongoing: WHAT") is True
    assert g.is_placeholder_mega_title("Ongoing: Who") is True
    assert g.is_overly_generic_storyline_title("Ongoing: WHAT", "legal") is True
    assert g.is_placeholder_mega_title("Ongoing: Gaza") is False


def test_leaked_storyline_title_detected():
    assert g.is_leaked_storyline_title("{: The Next Stage in Enforcement") is True
    assert g.is_leaked_storyline_title('lede: Something happened') is True
    assert g.is_leaked_storyline_title("Apple sues OpenAI over trade secrets") is False


def test_sanitize_storyline_title_for_display():
    assert (
        g.sanitize_storyline_title_for_display(
            "{: The Next Stage in Enforcement Escalation: DOJ’s First DEI-Related FCA Settlement"
        )
        == "The Next Stage in Enforcement Escalation: DOJ’s First DEI-Related FCA Settlement"
    )
    assert (
        g.sanitize_storyline_title_for_display(
            "Year_2026: California spars with expert witness over safety of abortion reversals"
        )
        == "California spars with expert witness over safety of abortion reversals"
    )
    assert (
        g.sanitize_storyline_title_for_display("Ongoing: WHAT", fallback="Storyline #9")
        == "Storyline #9"
    )
    assert (
        g.sanitize_storyline_title_for_display("Normal Legal Storyline Title")
        == "Normal Legal Storyline Title"
    )
    # Mid-word truncation → soft ellipsis at last full word
    assert (
        g.sanitize_storyline_title_for_display(
            "California spars with expert witness ove"
        )
        == "California spars with expert witness…"
    )


def test_mega_group_requires_shared_entity_all_domains():
    children = [
        _Child("DOJ enforcement escalation", {"doj"}),
        _Child("Cyclospora outbreak insurance cases", {"cyclospora"}),
    ]
    ok, reason = g.assess_mega_group_coherence("legal", children)
    assert ok is False
    assert reason == "insufficient_shared_entities"


def test_mega_group_shared_entity_passes_legal():
    children = [
        _Child("DOJ probes OpenAI trade secrets", {"openai", "doj"}),
        _Child("Apple sues OpenAI over model weights", {"openai", "apple"}),
    ]
    ok, reason = g.assess_mega_group_coherence("legal", children)
    assert ok is True
    assert reason == "ok"


def test_mega_group_rejects_leaked_child_title():
    children = [
        _Child("{: Enforcement Escalation", {"doj"}),
        _Child("DOJ files second brief", {"doj"}),
    ]
    ok, reason = g.assess_mega_group_coherence("legal", children)
    assert ok is False
    assert reason == "leaked_child_title"


def test_pairwise_merge_unrelated_entities_blocked():
    s1 = _Child("Apple Q2 earnings report", {"apple"})
    s2 = _Child("Exxon quarterly earnings", {"exxon"})
    ok, reason = g.assess_storyline_pair_merge_coherence("finance", s1, s2)
    assert ok is False
    assert reason == "insufficient_shared_entities"


def test_pairwise_merge_shared_entity_allowed():
    s1 = _Child("Apple Q2 earnings report", {"apple", "tim cook"})
    s2 = _Child("Apple supply chain earnings impact", {"apple", "foxconn"})
    ok, reason = g.assess_storyline_pair_merge_coherence("finance", s1, s2)
    assert ok is True
    assert reason == "ok"


def test_kitchen_sink_amid_title():
    articles = [
        {"title": "Apple sues OpenAI", "summary": "", "content": ""},
        {"title": "Cyclospora outbreak spreads", "summary": "", "content": ""},
    ]
    sink, reason = g.assess_kitchen_sink_risk(
        "Apple Sues OpenAI Amid Cyclospora Outbreak and Insurance Cases",
        articles,
    )
    assert sink is True
    assert reason == "title_amid_join"
