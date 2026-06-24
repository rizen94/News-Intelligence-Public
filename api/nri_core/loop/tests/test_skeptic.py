from nri_core.loop.reason.ach_synthesizer import lint_causal_language
from nri_core.loop.skeptic.agent import review_note


def test_causal_language_linter():
    flags = lint_causal_language("This caused the merger because of timing")
    assert flags


def test_skeptic_review_offline():
    finding = review_note("Hypothesis: Company A caused Company B to fail")
    assert finding.findings or finding.causal_language_flags or finding.raw.get("_fallback")
