"""Tests for domain-agnostic research paper classifier."""

from services.research_paper_classifier import (
    CONTENT_KIND_RESEARCH_PAPER,
    classify_research_paper,
    is_research_paper_url,
    paper_metadata_patch,
)


def test_arxiv_abs_classified():
    frag = classify_research_paper("https://arxiv.org/abs/2608.17176")
    assert frag is not None
    assert frag["content_kind"] == CONTENT_KIND_RESEARCH_PAPER
    assert frag["arxiv_id"] == "2608.17176"
    assert frag["pipeline_skip"]["event_extraction_skip"] is True


def test_biorxiv_classified():
    frag = classify_research_paper("https://www.biorxiv.org/content/10.1101/2024.01.01.123456v1")
    assert frag is not None
    assert frag["paper_host"] == "biorxiv.org"


def test_news_blog_not_paper():
    assert classify_research_paper("https://openai.com/blog/something") is None
    assert not is_research_paper_url("https://techcrunch.com/2026/01/01/ai-news")


def test_paper_metadata_patch_merge():
    patch = paper_metadata_patch(
        "https://arxiv.org/pdf/2608.17092.pdf",
        title="Some paper",
        source_domain="arXiv cs.AI",
    )
    assert patch["content_kind"] == CONTENT_KIND_RESEARCH_PAPER
    assert "arxiv_id" in patch
