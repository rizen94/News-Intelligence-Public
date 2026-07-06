"""Unit tests for phase batch run history persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from shared.services.phase_batch_run_history import (
    batch_stats_had_work,
    record_phase_batch_completion,
)


def test_batch_stats_had_work_false_for_empty():
    assert batch_stats_had_work({}) is False
    assert batch_stats_had_work({"round_processed": 0}) is False


def test_record_phase_batch_completion_skips_empty_by_default():
    with patch(
        "shared.services.automation_run_history_writer.persist_automation_run_history"
    ) as persist:
        ok = record_phase_batch_completion(
            "unified_intake_extraction",
            datetime.now(timezone.utc),
            datetime.now(timezone.utc),
            stats={"round_processed": 0},
        )
        assert ok is False
        persist.assert_not_called()


def test_record_phase_batch_completion_allow_empty_for_monitor_runs():
    started = datetime(2026, 7, 5, 22, 0, tzinfo=timezone.utc)
    finished = datetime(2026, 7, 5, 22, 33, tzinfo=timezone.utc)
    with patch(
        "shared.services.automation_run_history_writer.persist_automation_run_history"
    ) as persist:
        ok = record_phase_batch_completion(
            "unified_intake_extraction",
            started,
            finished,
            stats={"round_processed": 0},
            allow_empty=True,
        )
        assert ok is True
        persist.assert_called_once()
        meta = persist.call_args.kwargs.get("metadata") or persist.call_args[0][4]
        assert meta["status"] == "batch_round"
        assert meta["round_processed"] == 0
