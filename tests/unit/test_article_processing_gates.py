"""Unit tests for api/shared/article_processing_gates.py."""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# api/ on path for `shared.*`
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "api"))

import shared.article_processing_gates as gates  # noqa: E402
from shared.article_processing_gates import (  # noqa: E402
    article_eligible_for_context,
    article_eligible_for_ml,
    finalize_rss_enrichment_after_inline,
    rss_item_passes_ingest_gates,
    sql_context_sync_article_ready,
    sql_ml_ready_and_content_bounds,
)


@pytest.fixture
def no_strict_cutoff(monkeypatch):
    monkeypatch.setattr(gates, "strict_enrichment_cutoff_utc", lambda: None)


@pytest.fixture
def strict_cutoff_jan_2026(monkeypatch):
    monkeypatch.setattr(
        gates,
        "strict_enrichment_cutoff_utc",
        lambda: datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_ml_requires_enriched_or_legacy_long(no_strict_cutoff):
    assert article_eligible_for_ml("x" * 101, "enriched") is True
    assert article_eligible_for_ml("x" * 500, None) is True
    assert article_eligible_for_ml("x" * 200, None) is False
    assert article_eligible_for_ml("x" * 200, "failed") is False


def test_ml_strict_requires_enriched(strict_cutoff_jan_2026):
    new = datetime(2026, 6, 1, tzinfo=timezone.utc)
    assert article_eligible_for_ml("x" * 500, None, created_at=new) is False
    assert article_eligible_for_ml("x" * 500, "enriched", created_at=new) is True
    old = datetime(2025, 1, 1, tzinfo=timezone.utc)
    assert article_eligible_for_ml("x" * 500, None, created_at=old) is True


def test_context_allows_terminal_or_long(no_strict_cutoff):
    assert article_eligible_for_context("x" * 101, "failed") is True
    assert article_eligible_for_context("x" * 500, "pending") is True
    assert article_eligible_for_context("x" * 200, None) is False


def test_context_strict_blocks_long_without_terminal(strict_cutoff_jan_2026):
    new = datetime(2026, 6, 1, tzinfo=timezone.utc)
    assert article_eligible_for_context("x" * 500, "pending", created_at=new) is False
    assert article_eligible_for_context("x" * 500, "enriched", created_at=new) is True


def test_finalize_rss_long_body_strict_pending(strict_cutoff_jan_2026):
    ca = datetime(2026, 6, 1, tzinfo=timezone.utc)
    st, n = finalize_rss_enrichment_after_inline(
        "x" * 500,
        created_at=ca,
        url="https://a.com",
        trafilatura_attempted=False,
        trafilatura_ok=False,
    )
    assert st == "pending" and n == 0


def test_finalize_rss_long_body_legacy_enriched(no_strict_cutoff):
    ca = datetime(2026, 6, 1, tzinfo=timezone.utc)
    st, n = finalize_rss_enrichment_after_inline(
        "x" * 500,
        created_at=ca,
        url="https://a.com",
        trafilatura_attempted=False,
        trafilatura_ok=False,
    )
    assert st == "enriched" and n == 0


def test_rss_ingest_gates():
    ok, _ = rss_item_passes_ingest_gates("Title", "short but ok body text here", "https://a.com/x")
    assert ok is True
    ok, _ = rss_item_passes_ingest_gates("", "body", "https://a.com")
    assert ok is False
    ok, _ = rss_item_passes_ingest_gates("T", "x", "")
    assert ok is False


def test_sql_fragments_non_empty(no_strict_cutoff):
    assert "enrichment_status" in sql_ml_ready_and_content_bounds()
    assert "500" in sql_context_sync_article_ready("a")


def test_sql_fragments_strict_include_cutoff(strict_cutoff_jan_2026):
    ml = sql_ml_ready_and_content_bounds()
    assert "2026-01-01" in ml
    cs = sql_context_sync_article_ready("a")
    assert "timestamptz" in cs


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
