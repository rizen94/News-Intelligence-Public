"""Unit tests for pipeline queue depth vocabulary and alignment helpers."""

from __future__ import annotations

from unittest.mock import patch

from shared.pipeline_queue_counts import verify_unified_intake_alignment
from shared.pipeline_queue_vocabulary import (
    add_automation_status_aliases,
    add_queue_depth_aliases,
    unified_intake_breakdown_from_stats,
)
from shared.queue_audit import build_queue_audit


def test_unified_intake_breakdown_from_stats_maps_inventory():
    stats = {
        "actionable_unified_intake": 100,
        "total_missing_unified_pass": 150,
        "legacy_backfill_eligible": 50,
    }
    b = unified_intake_breakdown_from_stats(stats, spine_queue=9170)
    assert b["actionable_unified_intake"] == 100
    assert b["inventory_missing_pass"] == 150
    assert b["legacy_backfill_eligible"] == 50
    assert b["spine_queue_depth"] == 9170


def test_add_queue_depth_aliases():
    row = {
        "pending_records": 42,
        "batches_to_drain": 3,
        "pass_rate_24h": 95.0,
        "pending_first_pass": 40,
        "pending_retry": 2,
    }
    out = add_queue_depth_aliases(row)
    assert out["queue_depth"] == 42
    assert out["estimated_phase_runs"] == 3
    assert out["run_success_rate_24h"] == 95.0
    assert out["first_pass_depth"] == 40
    assert out["retry_depth"] == 2


@patch("shared.pipeline_queue_counts.get_unified_intake_breakdown")
def test_verify_unified_intake_alignment_matches(mock_breakdown):
    mock_breakdown.return_value = {
        "actionable_unified_intake": 2770,
        "inventory_missing_pass": 2770,
        "legacy_backfill_eligible": 0,
        "spine_queue_depth": 9170,
    }
    result = verify_unified_intake_alignment({"unified_intake_extraction": 2770})
    assert result["matches_actionable_sql"] is True
    assert result["queue_depth"] == 2770
    assert result["spine_queue_depth"] == 9170


@patch("shared.pipeline_queue_counts.get_unified_intake_breakdown")
def test_verify_unified_intake_alignment_detects_spine_inflation(mock_breakdown):
    mock_breakdown.return_value = {
        "actionable_unified_intake": 2770,
        "inventory_missing_pass": 2770,
        "legacy_backfill_eligible": 0,
        "spine_queue_depth": 9170,
    }
    result = verify_unified_intake_alignment({"unified_intake_extraction": 9170})
    assert result["matches_actionable_sql"] is False


@patch("shared.pipeline_queue_counts.verify_unified_intake_alignment")
@patch("shared.pipeline_queue_counts.get_unified_intake_breakdown")
def test_queue_audit_unified_includes_spine_queue_depth(mock_breakdown, mock_verify):
    mock_breakdown.return_value = {
        "actionable_unified_intake": 100,
        "inventory_missing_pass": 100,
        "legacy_backfill_eligible": 0,
        "spine_queue_depth": 500,
    }
    mock_verify.return_value = {
        "queue_depth": 100,
        "actionable_unified_intake": 100,
        "inventory_missing_pass": 100,
        "legacy_backfill_eligible": 0,
        "spine_queue_depth": 500,
        "matches_actionable_sql": True,
    }
    audit = build_queue_audit({"unified_intake_extraction": 100})
    phase = audit["phases"]["unified_intake_extraction"]
    assert phase["spine_queue_depth"] == 500
    assert phase["matches_actionable_sql"] is True
    assert phase["queue_depth"] == 100


def test_backlog_metrics_unified_count_does_not_prefer_spine_queue():
    """Regression: spine queue table depth must not override actionable SQL."""
    from pathlib import Path

    text = (Path(__file__).resolve().parents[2] / "api" / "services" / "backlog_metrics.py").read_text(
        encoding="utf-8"
    )
    fn_start = text.index("def _count_unified_intake_extraction_pending")
    fn_end = text.index("\ndef _count_sentiment_analysis_pending", fn_start)
    body = text[fn_start:fn_end]
    assert "count_all_pending" not in body
    assert "spine_work_queues_enabled" not in body


def test_backlog_metrics_content_enrichment_does_not_prefer_spine_queue():
    from pathlib import Path

    text = (Path(__file__).resolve().parents[2] / "api" / "services" / "backlog_metrics.py").read_text(
        encoding="utf-8"
    )
    fn_start = text.index("def _count_content_enrichment_backlog")
    fn_end = text.index("\ndef _count_context_sync_backlog", fn_start)
    body = text[fn_start:fn_end]
    assert "count_all_pending" not in body
    assert "spine_work_queues_enabled" not in body


def test_add_automation_status_aliases():
    payload = {
        "pending_counts": {"unified_intake_extraction": 100},
        "backlog_counts": {"unified_intake_extraction": 50},
        "combined_queue_depth": 3,
        "controller_state": {"queue_depth": 3, "active": True},
    }
    out = add_automation_status_aliases(payload)
    assert out["queue_depths"]["unified_intake_extraction"] == 100
    assert out["scheduling_backlog"]["unified_intake_extraction"] == 50
    assert out["in_memory_queue_depth"] == 3
    assert out["controller_state"]["in_memory_queue_depth"] == 3


def test_sql_claim_extraction_eligible_includes_gap_fill_ssot():
    from pathlib import Path

    ces = (Path(__file__).resolve().parents[2] / "api" / "services" / "claim_extraction_service.py").read_text(
        encoding="utf-8"
    )
    start = ces.index("def sql_claim_extraction_eligible")
    end = ces.find("\ndef ", start + 1)
    body = ces[start:end if end != -1 else None]
    assert "claim_extraction_gap_fill_sql" in body
    assert "extracted_claims" in body


def test_sql_claim_extraction_eligible_shared_by_backlog_and_stats():
    from pathlib import Path

    ces = (Path(__file__).resolve().parents[2] / "api" / "services" / "claim_extraction_service.py").read_text(
        encoding="utf-8"
    )
    assert "sql_claim_extraction_eligible" in ces
    for fn in (
        "get_context_ids_without_claims",
        "get_context_claim_backlog_stats",
    ):
        start = ces.index(f"def {fn}")
        end = ces.find("\ndef ", start + 1)
        body = ces[start:end if end != -1 else None]
        assert "sql_claim_extraction_eligible" in body, f"{fn} must use SSOT SQL"
