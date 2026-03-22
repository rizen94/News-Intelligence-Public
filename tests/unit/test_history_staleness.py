"""Unit tests for commodity history staleness helpers."""

from datetime import datetime, timedelta, timezone

from domains.finance.history_staleness import (
    bounded_refresh_start_end,
    latest_observation_date,
    observations_stale,
)


def test_latest_observation_date_empty():
    assert latest_observation_date([]) is None


def test_latest_observation_date_picks_max():
    assert latest_observation_date(
        [{"date": "2024-01-01"}, {"date": "2024-06-15"}, {"date": "2024-03-01"}]
    ).isoformat() == "2024-06-15"


def test_observations_stale_false_when_recent():
    now = datetime(2025, 3, 21, 12, 0, 0, tzinfo=timezone.utc)
    assert not observations_stale([{"date": "2025-03-21"}], now=now)


def test_observations_stale_true_when_older_than_24h():
    now = datetime(2025, 3, 22, 15, 0, 0, tzinfo=timezone.utc)
    assert observations_stale([{"date": "2025-03-21"}], max_age_hours=24, now=now)


def test_bounded_refresh_start_end():
    s, e = bounded_refresh_start_end("2020-01-01", "2025-03-21", lookback_days=14)
    assert e == "2025-03-21"
    assert s == "2025-03-07"
