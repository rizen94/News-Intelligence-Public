"""Unit tests for measured vs configured rows/run (Monitor phase_dashboard)."""

from __future__ import annotations

from shared.pipeline_queue_vocabulary import (
    CONFIGURED_ROWS_PER_RUN,
    MEASURED_ROWS_PER_RUN_24H,
    ROWS_PER_RUN,
    ROWS_PER_RUN_SAMPLE_COUNT,
    ROWS_PER_RUN_SOURCE,
    apply_rows_per_run_fields,
)


def test_apply_rows_per_run_measured():
    row = apply_rows_per_run_fields(
        {},
        "content_enrichment",
        configured=60,
        measured=(42, "measured_24h", 8),
    )
    assert row[MEASURED_ROWS_PER_RUN_24H] == 42
    assert row[ROWS_PER_RUN] == 42
    assert row[ROWS_PER_RUN_SOURCE] == "measured_24h"
    assert row[ROWS_PER_RUN_SAMPLE_COUNT] == 8
    assert row[CONFIGURED_ROWS_PER_RUN] == 60


def test_apply_rows_per_run_config_fallback():
    row = apply_rows_per_run_fields(
        {},
        "claim_extraction",
        configured=25,
        measured=None,
    )
    assert row[MEASURED_ROWS_PER_RUN_24H] is None
    assert row[ROWS_PER_RUN] == 25
    assert row[ROWS_PER_RUN_SOURCE] == "config_default"
    assert row[ROWS_PER_RUN_SAMPLE_COUNT] == 0


def test_apply_rows_per_run_no_row_batch_model():
    row = apply_rows_per_run_fields(
        {},
        "collection_cycle",
        configured=0,
        measured=None,
    )
    assert row[ROWS_PER_RUN] is None
    assert row[ROWS_PER_RUN_SOURCE] == "no_row_batch_model"


def test_processing_progress_uses_sql_measured_rows_per_run():
    path = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "api"
        / "domains"
        / "system_monitoring"
        / "routes"
        / "processing_progress.py"
    )
    text = path.read_text(encoding="utf-8")
    assert "query_measured_rows_per_run_by_phase" in text
    assert "apply_rows_per_run_fields" in text


def test_claims_to_facts_batch_history_uses_record_phase_batch_completion():
    path = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "api"
        / "services"
        / "claim_extraction_service.py"
    )
    text = path.read_text(encoding="utf-8")
    assert "record_phase_batch_completion" in text
    assert 'persist_automation_run_history("claims_to_facts"' not in text
