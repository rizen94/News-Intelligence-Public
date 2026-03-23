"""Unit tests for api/shared/article_processing_gates.py."""

import sys
from pathlib import Path

import pytest

# api/ on path for `shared.*`
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "api"))

from shared.article_processing_gates import (  # noqa: E402
    article_eligible_for_context,
    article_eligible_for_ml,
    rss_item_passes_ingest_gates,
    sql_context_sync_article_ready,
    sql_ml_ready_and_content_bounds,
)


def test_ml_requires_enriched_or_legacy_long():
    assert article_eligible_for_ml("x" * 101, "enriched") is True
    assert article_eligible_for_ml("x" * 500, None) is True
    assert article_eligible_for_ml("x" * 200, None) is False
    assert article_eligible_for_ml("x" * 200, "failed") is False


def test_context_allows_terminal_or_long():
    assert article_eligible_for_context("x" * 101, "failed") is True
    assert article_eligible_for_context("x" * 500, "pending") is True
    assert article_eligible_for_context("x" * 200, None) is False


def test_rss_ingest_gates():
    ok, _ = rss_item_passes_ingest_gates("Title", "short but ok body text here", "https://a.com/x")
    assert ok is True
    ok, _ = rss_item_passes_ingest_gates("", "body", "https://a.com")
    assert ok is False
    ok, _ = rss_item_passes_ingest_gates("T", "x", "")
    assert ok is False


def test_sql_fragments_non_empty():
    assert "enrichment_status" in sql_ml_ready_and_content_bounds()
    assert "500" in sql_context_sync_article_ready("a")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
