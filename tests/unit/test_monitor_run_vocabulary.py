"""Invariant tests for monitor run vocabulary SSOT."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from shared.monitor_run_vocabulary import (
    RunHistoryStatus,
    batch_stats_had_work,
    is_measurable_run_history_row,
    normalize_phase_run_event,
    throughput_from_payload,
)


def test_throughput_from_payload_matches_batch_stats_had_work():
    stats = {"round_processed": 0, "profiles_updated": 3}
    assert throughput_from_payload(stats) == 3
    assert batch_stats_had_work(stats) is True
    assert batch_stats_had_work({"round_processed": 0}) is False


def test_empty_batch_round_measurable_when_allow_empty():
    started = datetime(2026, 7, 5, 22, 0, tzinfo=timezone.utc)
    finished = started + timedelta(minutes=33)
    event = normalize_phase_run_event(
        "unified_intake_extraction",
        1,
        started_at=started,
        finished_at=finished,
        allow_empty=True,
        round_processed=0,
    )
    assert event.rows_processed == 0
    assert event.iteration_index == 1
    meta = event.to_metadata()
    assert meta["status"] == RunHistoryStatus.BATCH_ROUND
    assert is_measurable_run_history_row(meta, started_at=started, finished_at=finished)


def test_drain_started_not_measurable():
    meta = {"status": RunHistoryStatus.DRAIN_STARTED, "batch": True}
    started = datetime(2026, 7, 5, 22, 0, tzinfo=timezone.utc)
    assert is_measurable_run_history_row(meta, started_at=started, finished_at=started) is False


def test_activity_and_history_share_rows_processed():
    raw = {"round_processed": 12, "total_processed": 400, "wave": 2}
    event = normalize_phase_run_event(
        "entity_profile_build",
        2,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        **raw,
    )
    assert event.rows_processed == throughput_from_payload(raw)
    assert event.to_metadata()["rows_processed"] == 12


def test_format_activity_message_includes_fast_full_tiers():
    from shared.monitor_run_vocabulary import format_activity_message

    event = normalize_phase_run_event(
        "entity_profile_build",
        3,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        profiles_updated=9,
        round_processed=9,
        fast_updated=6,
        full_updated=3,
    )
    msg = format_activity_message("Building entity profiles from contexts", event)
    assert "round 3" in msg
    assert "9 processed" in msg
    assert "6 fast / 3 full" in msg
