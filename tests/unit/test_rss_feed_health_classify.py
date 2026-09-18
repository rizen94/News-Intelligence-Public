"""Unit tests for RSS feed health yield classification + weekly cull picks."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "api"))

from services.rss_feed_health_service import (  # noqa: E402
    FeedQualityScore,
    classify_feed_yield_reason,
    pick_lowest_failing_feed,
    weekly_cull_status,
)


def _base(**overrides):
    kw = dict(
        last_err="",
        consec_empty=0,
        fail_consec=5,
        articles_zero_window=100,
        feed_age_days=60,
        zero_days=14,
        articles_low_window=100,
        above_threshold=50,
        low_min=10,
        articles_blocked_window=100,
        blocked_or_failed=10,
        fulltext_count=80,
        blocked_min=20,
        blocked_rate_threshold=0.70,
        fulltext_rate_max=0.05,
    )
    kw.update(overrides)
    return classify_feed_yield_reason(**kw)


def test_healthy_open_feed():
    assert _base() == ""


def test_bloomberg_style_blocked_yield():
    assert (
        _base(
            articles_blocked_window=500,
            blocked_or_failed=420,
            fulltext_count=3,
            above_threshold=200,
        )
        == "blocked_yield"
    )


def test_low_signal_when_not_blocked():
    assert (
        _base(
            articles_low_window=40,
            above_threshold=0,
            articles_blocked_window=40,
            blocked_or_failed=5,
            fulltext_count=30,
        )
        == "low_signal_yield"
    )


def test_fetch_failure_wins():
    assert _base(last_err="timeout", blocked_or_failed=90, fulltext_count=0) == "fetch_failure"


def test_zero_yield():
    assert _base(articles_zero_window=0, feed_age_days=30) == "zero_yield"


def _score(**kw):
    base = dict(
        domain_key="finance",
        schema="finance",
        feed_id=1,
        feed_name="x",
        article_count=20,
        avg_quality=0.5,
        fulltext_count=10,
        blocked_or_failed=2,
        feed_age_days=60,
    )
    base.update(kw)
    return FeedQualityScore(**base)


def test_weekly_cull_picks_lowest_avg():
    scores = [
        _score(feed_id=1, feed_name="ok", avg_quality=0.72),
        _score(feed_id=2, feed_name="bad", avg_quality=0.31, blocked_or_failed=15),
        _score(feed_id=3, feed_name="worse", avg_quality=0.22, blocked_or_failed=18),
    ]
    victim = pick_lowest_failing_feed(
        scores, target_avg=0.60, min_articles=5, grace_days=21
    )
    assert victim is not None
    assert victim.feed_id == 3


def test_weekly_cull_all_passing_returns_none():
    scores = [
        _score(feed_id=1, avg_quality=0.70),
        _score(feed_id=2, avg_quality=0.65),
    ]
    assert (
        pick_lowest_failing_feed(scores, target_avg=0.60, min_articles=5, grace_days=21)
        is None
    )
    status = weekly_cull_status(scores, target_avg=0.60, min_articles=5, grace_days=21)
    assert status["all_scored_passing"] is True
    assert len(status["failing"]) == 0


def test_weekly_cull_skips_insufficient_and_grace():
    scores = [
        _score(feed_id=1, avg_quality=0.10, article_count=2),  # insufficient
        _score(feed_id=2, avg_quality=0.10, feed_age_days=3),  # grace
        _score(feed_id=3, avg_quality=0.40, article_count=20, feed_age_days=60),
    ]
    victim = pick_lowest_failing_feed(
        scores, target_avg=0.60, min_articles=5, grace_days=21
    )
    assert victim is not None and victim.feed_id == 3
    status = weekly_cull_status(scores, target_avg=0.60, min_articles=5, grace_days=21)
    assert len(status["insufficient"]) == 2
    assert len(status["failing"]) == 1
