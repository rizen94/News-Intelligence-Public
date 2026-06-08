"""Tests for LLM output sanitization used in briefing titles and ledes."""

from shared.llm_text_sanitize import (
    parse_llm_json_response,
    sanitize_briefing_lede,
    sanitize_briefing_title,
    sanitize_on_persist,
    strip_llm_wrapping_artifacts,
)


def test_strip_json_object_title():
    raw = '{"title": "Fed holds rates steady amid inflation"}'
    assert strip_llm_wrapping_artifacts(raw) == "Fed holds rates steady amid inflation"


def test_strip_key_echo_prefix():
    raw = '"title": "Congress passes budget deal",'
    assert sanitize_briefing_title(raw) == "Congress passes budget deal"


def test_strip_code_fence_lede():
    raw = '```json\n{"lede": "Markets rallied on the news."}\n```'
    assert strip_llm_wrapping_artifacts(raw) == "Markets rallied on the news."


def test_sanitize_briefing_title_first_line_only():
    raw = '"summary": "Line one headline"\n"who": ["Alice"]'
    assert sanitize_briefing_title(raw) == "Line one headline"


def test_strip_professional_summary_preamble():
    raw = (
        "Here is a professional, journalistic summary of the article:\n\n"
        "**Trump Threatens to Deploy ICE Agents to Airports**"
    )
    assert sanitize_briefing_lede(raw) == "Trump Threatens to Deploy ICE Agents to Airports"


def test_strip_article_summary_meta_header():
    raw = "Here's a professional summary of the article:\n\n**ARTICLE SUMMARY**\n\n**Senate confirms nominee**"
    assert sanitize_briefing_lede(raw) == "Senate confirms nominee"


def test_bold_headline_without_preamble():
    raw = "**Senate Confirms Markwayne Mullin as Homeland Security Secretary**\n\nIn a party-line vote..."
    assert sanitize_briefing_lede(raw) == "Senate Confirms Markwayne Mullin as Homeland Security Secretary"


def test_parse_llm_json_response_valid():
    raw = '```json\n{"lede": "Markets rallied.", "analysis": "Fed held rates."}\n```'
    parsed, cleaned = parse_llm_json_response(raw)
    assert parsed is not None
    assert parsed["lede"] == "Markets rallied."
    assert "Markets" in cleaned


def test_parse_llm_json_response_invalid():
    parsed, _ = parse_llm_json_response("not json at all")
    assert parsed is None


def test_sanitize_on_persist_lede():
    raw = "Here's a professional summary of the article:\n\n**Headline Here**"
    assert sanitize_on_persist(raw, "lede") == "Headline Here"


def test_sanitize_on_persist_narrative_truncates():
    long_text = "word " * 900
    out = sanitize_on_persist(long_text, "narrative", max_length=100)
    assert len(out) <= 100
