"""Tests for article body paragraph formatting."""

from services.article_content_enrichment_service import format_article_body_paragraphs


def test_single_newline_after_sentence_becomes_paragraph_break():
    raw = (
        "First paragraph ends here.\n"
        "Second paragraph starts here with more detail.\n"
        "Third line continues."
    )
    out = format_article_body_paragraphs(raw)
    assert "\n\n" in out
    assert out.startswith("First paragraph")


def test_wall_of_text_splits_into_paragraphs():
    raw = (
        "Quantum computing may not be as hot as AI right now. "
        "Useful quantum computing is projected for 2030. "
        "Companies are investing heavily today. "
        "IonQ is a major player in the space. "
        "D-Wave offers another approach. "
        "Alphabet also researches quantum systems."
    )
    out = format_article_body_paragraphs(raw)
    assert out.count("\n\n") >= 1


def test_video_player_boilerplate_sentences_removed():
    raw = (
        "Congress debated the bill Tuesday afternoon.\n\n"
        "3. One of your browser extensions seems to be blocking the video player from loading. "
        "To watch this content, you may need to disable it on this site."
    )
    out = format_article_body_paragraphs(raw)
    assert "browser extensions" not in out.lower()
    assert "disable it on this site" not in out.lower()
    assert "Congress debated" in out


def test_only_video_boilerplate_returns_empty():
    raw = (
        "One of your browser extensions seems to be blocking the video player from loading. "
        "To watch this content, you may need to disable it on this site."
    )
    out = format_article_body_paragraphs(raw)
    assert out.strip() == ""
