"""Regression tests for ActivityFeedService.reconcile_stale_current.

Guards the fix that prevents phantom "running" rows from lingering on the Monitor
page when a task's finally never ran (leaked stable-phase refcount) but
AutomationManager authoritatively reports zero active workers for that phase.
"""

from datetime import datetime, timedelta, timezone

from services.activity_feed_service import ActivityFeedService


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def test_leaked_stable_phase_refcount_is_reconciled_when_no_workers():
    """A stable phase:* row with a leaked refcount must still be cleaned up
    once AutomationManager reports zero active workers and it exceeds grace."""
    feed = ActivityFeedService()
    # Simulate an orphaned start: add_current bumped the refcount but the matching
    # complete() never ran (task cancelled before its finally).
    feed.add_current(
        "phase:storyline_assembly",
        "Storyline Assembly",
        task_name="storyline_assembly",
    )
    # Force the row to look old (started 2 hours ago).
    feed._current["phase:storyline_assembly"]["started_at"] = _iso(
        datetime.now(timezone.utc) - timedelta(hours=2)
    )
    assert feed._stable_phase_refs.get("phase:storyline_assembly") == 1

    removed = feed.reconcile_stale_current(
        {"storyline_assembly": 0}, grace_seconds=180.0
    )

    assert removed == 1
    snap = feed.get_snapshot()
    assert snap["current"] == []
    # Leaked refcount must be reset so the row cannot resurrect/veto again.
    assert "phase:storyline_assembly" not in feed._stable_phase_refs
    assert snap["recent"][0]["task_name"] == "storyline_assembly"
    assert snap["recent"][0]["success"] is False
    assert snap["recent"][0]["error_message"] == "stale_activity_reconciled"


def test_active_worker_keeps_stable_row_even_when_old():
    """If AutomationManager reports a live worker for the phase, the row stays."""
    feed = ActivityFeedService()
    feed.add_current(
        "phase:storyline_assembly",
        "Storyline Assembly",
        task_name="storyline_assembly",
    )
    feed._current["phase:storyline_assembly"]["started_at"] = _iso(
        datetime.now(timezone.utc) - timedelta(hours=2)
    )

    removed = feed.reconcile_stale_current(
        {"storyline_assembly": 1}, grace_seconds=180.0
    )

    assert removed == 0
    assert len(feed.get_snapshot()["current"]) == 1


def test_recent_row_within_grace_is_not_reconciled():
    """A freshly started row (within grace) is preserved even with zero workers,
    covering the brief race between add_current and the worker counter."""
    feed = ActivityFeedService()
    feed.add_current(
        "phase:storyline_assembly",
        "Storyline Assembly",
        task_name="storyline_assembly",
    )
    # started_at defaults to now → within grace.

    removed = feed.reconcile_stale_current(
        {"storyline_assembly": 0}, grace_seconds=180.0
    )

    assert removed == 0
    assert len(feed.get_snapshot()["current"]) == 1
