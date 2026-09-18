"""Unit tests for intake catchup latency helpers."""

from __future__ import annotations


def test_catchup_sla_hours_default():
    from shared.intake_catchup_latency import catchup_sla_hours, preprocess_sla_hours

    assert catchup_sla_hours(None) >= 0.5
    assert catchup_sla_hours(6) == 6.0
    assert catchup_sla_hours(0.1) == 0.5
    assert preprocess_sla_hours(None) == 1.0
    assert preprocess_sla_hours(0.1) == 0.25
    assert preprocess_sla_hours(2) == 2.0


def test_scored_cte_has_no_bare_percent_wildcards():
    """Parameterized execute fails if SQL embeds ILIKE '%x%' without escaping."""
    import re

    from shared.intake_catchup_latency import _scored_cte_sql

    sql = _scored_cte_sql("medicine", "medicine")
    # Only %s placeholders for window_hours should remain as bare %
    bare = re.findall(r"%(?!s)", sql)
    assert bare == [], f"bare percent wildcards break psycopg2: {bare[:5]}"
    assert "preprocess_caught_up_at" in sql


def test_compute_returns_expected_keys():
    from shared.intake_catchup_latency import compute_intake_catchup_latency

    report = compute_intake_catchup_latency(window_hours=24, sla_hours=6, use_cache=False)
    assert "p50_hours" in report
    assert "p95_hours" in report
    assert "sla_hours" in report
    assert report["sla_hours"] == 6.0
    assert "stages" in report
    assert "content_enrichment" in report["stages"]
    assert "per_domain" in report
    assert "preprocess" in report
    assert report["preprocess"]["sla_hours"] == 1.0
    assert "unified_intake_extraction" in report["preprocess"]["stages"]
    assert "errors" not in report or not report.get("errors")
