"""UIE selection order defaults to newest-first for preprocess SLA."""

from __future__ import annotations

import os


def test_unified_intake_newest_first_default(monkeypatch):
    monkeypatch.delenv("UNIFIED_INTAKE_ARTICLE_SELECTION_ORDER", raising=False)
    monkeypatch.delenv("BULK_CATCHUP_ACTIVE", raising=False)
    monkeypatch.setenv("PIPELINE_ARTICLE_SELECTION_ORDER", "fifo")
    from shared.pipeline_article_selection import (
        sql_order_coalesce_pub_created,
        unified_intake_newest_first,
    )

    assert unified_intake_newest_first() is True
    order = sql_order_coalesce_pub_created("a", newest_first=True)
    assert "DESC" in order


def test_unified_intake_fifo_when_explicit(monkeypatch):
    monkeypatch.setenv("UNIFIED_INTAKE_ARTICLE_SELECTION_ORDER", "fifo")
    from shared.pipeline_article_selection import unified_intake_newest_first

    assert unified_intake_newest_first() is False


def test_unified_intake_follows_global_during_bulk(monkeypatch):
    monkeypatch.delenv("UNIFIED_INTAKE_ARTICLE_SELECTION_ORDER", raising=False)
    monkeypatch.setenv("BULK_CATCHUP_ACTIVE", "true")
    monkeypatch.setenv("PIPELINE_ARTICLE_SELECTION_ORDER", "fifo")
    from shared.pipeline_article_selection import unified_intake_newest_first

    assert unified_intake_newest_first() is False
