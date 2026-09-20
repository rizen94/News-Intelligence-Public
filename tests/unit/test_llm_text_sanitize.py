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


def test_sanitize_reader_dek_strips_analysis_template():
    from shared.llm_text_sanitize import sanitize_reader_dek

    title = "Israeli Troops Evict Palestinian Families Amid Escalating Settler Violence in West Bank"
    raw = (
        f"**Storyline Analysis: {title}**\n\n"
        "**Main Narrative Thread:**\n"
        "The Israeli military's forced displacement of two Palestinian families "
        "from their homes in Qusra, a village in the occupied West Bank, amidst a broader campaign"
    )
    out = sanitize_reader_dek(raw, title=title, max_length=280)
    assert "**" not in out
    assert "Main Narrative Thread" not in out
    assert "Storyline Analysis" not in out
    assert out.startswith("The Israeli military's forced displacement")


def test_sanitize_reader_dek_skips_bold_title_echo():
    from shared.llm_text_sanitize import sanitize_reader_dek

    title = "US Anti-Terror Scheme Sees Record High Referrals Amid Rising Rightwing Extremism"
    raw = (
        f"**{title}**\n\n**Main Narrative Thread**\n\n"
        "The Prevent anti-terror scheme in the US has seen a record high number of referrals."
    )
    out = sanitize_reader_dek(raw, title=title, max_length=280)
    assert out.startswith("The Prevent anti-terror scheme")
    assert "**" not in out


def test_sanitize_reader_dek_inline_narrative_preamble():
    from shared.llm_text_sanitize import sanitize_reader_dek

    raw = (
        "**BAE Systems Fined $36m Amid Trump's Cyber Privateering Push**\n\n"
        "The main narrative thread of this story revolves around the UK defense "
        "contractor BAE Systems facing a $36 million penalty for violating US arms export rules."
    )
    out = sanitize_reader_dek(
        raw,
        title="BAE Systems Fined $36m Amid Trump's Cyber Privateering Push",
        max_length=280,
    )
    assert out.startswith("The UK defense contractor BAE Systems")
    assert "main narrative thread" not in out.casefold()
    assert "**" not in out


def test_sanitize_reader_dek_strips_storyline_colon_prefix():
    from shared.llm_text_sanitize import sanitize_reader_dek

    raw = "Storyline: Wasserman Schultz's Challenger Wins Progressive Support Amid Global Economic Uncertainty"
    out = sanitize_reader_dek(
        raw,
        title="Wasserman Schultz's Challenger Wins Progressive Support Amid Global Economic Uncertainty",
        max_length=280,
    )
    # Title-echo after Storyline: strip → empty or non-echo prose only
    assert not out.lower().startswith("storyline:")
    assert "**" not in out
