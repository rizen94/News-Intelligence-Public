"""Unit tests for NI Prometheus exposition helpers (no DB required)."""

from __future__ import annotations

import os

import pytest


def test_gauge_formatting():
    from services.ni_prometheus_metrics_service import _gauge

    lines = _gauge(
        "ni_test_metric",
        "help text",
        [({}, 1.0), ({"phase": "rss"}, 2.5)],
    )
    assert lines[0].startswith("# HELP ni_test_metric")
    assert lines[1].startswith("# TYPE ni_test_metric gauge")
    assert "ni_test_metric 1.0" in lines
    assert 'ni_test_metric{phase="rss"} 2.5' in lines


def test_disabled_body(monkeypatch):
    monkeypatch.setenv("NI_PROMETHEUS_METRICS_ENABLED", "false")
    # Clear module-level cache state if previously imported
    import services.ni_prometheus_metrics_service as m

    monkeypatch.setattr(m, "_CACHE_BODY", None)
    monkeypatch.setattr(m, "_CACHE_AT", 0.0)
    body = m.build_prometheus_metrics(force=True)
    assert "disabled" in body.lower()
    assert m.is_enabled() is False


def test_scrape_token(monkeypatch):
    import services.ni_prometheus_metrics_service as m

    monkeypatch.setenv("NI_PROMETHEUS_SCRAPE_TOKEN", "secret")
    assert m.scrape_token() == "secret"
    monkeypatch.delenv("NI_PROMETHEUS_SCRAPE_TOKEN", raising=False)
    assert m.scrape_token() == ""
