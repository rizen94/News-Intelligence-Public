"""Daily report helpers (no DB)."""

from datetime import datetime

from shared.daily_framing import time_of_day


def test_time_of_day_weekend():
    assert time_of_day(datetime(2026, 8, 16, 10, 0)) == "weekend"


def test_time_of_day_morning():
    assert time_of_day(datetime(2026, 8, 17, 9, 0)) == "morning"


def test_time_of_day_evening():
    assert time_of_day(datetime(2026, 8, 17, 19, 0)) == "evening"
