"""NIGHTLY_PIPELINE_EXCLUSIVE allowlist helpers (schedule + dispatch)."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clear_all_day_log_flag(monkeypatch):
    import services.nightly_ingest_window_service as niw

    monkeypatch.setattr(niw, "_logged_nightly_all_day", False)
    yield
    monkeypatch.setattr(niw, "_logged_nightly_all_day", False)


def test_pipeline_exclusive_blocks_non_allowlisted_during_all_day(monkeypatch):
    monkeypatch.setenv("NIGHTLY_UNIFIED_PIPELINE_ENABLED", "true")
    monkeypatch.setenv("NIGHTLY_PIPELINE_ALL_DAY", "true")
    monkeypatch.setenv("NIGHTLY_PIPELINE_EXCLUSIVE", "true")
    monkeypatch.setenv(
        "NIGHTLY_PIPELINE_ALLOWED_SCHEDULED_PHASES",
        "content_enrichment,context_sync,health_check,pending_db_flush,nightly_enrichment_context",
    )

    from services.nightly_ingest_window_service import (
        should_block_phase_for_nightly_pipeline_exclusive,
        task_allowed_during_nightly_pipeline_exclusive,
    )

    assert task_allowed_during_nightly_pipeline_exclusive("content_enrichment")
    assert not task_allowed_during_nightly_pipeline_exclusive("event_tracking")
    assert should_block_phase_for_nightly_pipeline_exclusive("event_tracking")
    assert should_block_phase_for_nightly_pipeline_exclusive("event_coherence_review")
    assert should_block_phase_for_nightly_pipeline_exclusive("investigation_report_refresh")
    assert not should_block_phase_for_nightly_pipeline_exclusive("content_enrichment")
    assert not should_block_phase_for_nightly_pipeline_exclusive("context_sync")


def test_pipeline_exclusive_disabled_allows_all(monkeypatch):
    monkeypatch.setenv("NIGHTLY_UNIFIED_PIPELINE_ENABLED", "true")
    monkeypatch.setenv("NIGHTLY_PIPELINE_ALL_DAY", "true")
    monkeypatch.setenv("NIGHTLY_PIPELINE_EXCLUSIVE", "false")

    from services.nightly_ingest_window_service import (
        should_block_phase_for_nightly_pipeline_exclusive,
    )

    assert not should_block_phase_for_nightly_pipeline_exclusive("event_tracking")
