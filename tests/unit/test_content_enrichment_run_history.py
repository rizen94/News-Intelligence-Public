"""Content enrichment Monitor runs_1h alignment (batch_round vs nightly no-op)."""

from __future__ import annotations

import asyncio
import importlib
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch


def _load_am_module():
    for key in list(sys.modules):
        if key in (
            "services.automation_manager",
            "services",
            "shared.domain_registry",
        ) or key.startswith("services."):
            # Keep other services; only drop automation_manager + domain_registry if present.
            pass
    for key in ("services.automation_manager", "shared.domain_registry"):
        sys.modules.pop(key, None)

    with (
        patch("shared.database.connection.get_ui_db_connection", return_value=None),
        patch("shared.database.connection.get_db_connection", return_value=None),
    ):
        if "shared.domain_registry" in sys.modules:
            import shared.domain_registry as dr

            importlib.reload(dr)
        import services.automation_manager as am

        return am


def _make_task(am_mod, **meta):
    return am_mod.Task(
        id="t1",
        name="content_enrichment",
        priority=1,
        status=am_mod.TaskStatus.PENDING,
        created_at=datetime.now(timezone.utc),
        metadata=dict(meta),
    )


def test_content_enrichment_nightly_noop_skips_history():
    am_mod = _load_am_module()
    am = object.__new__(am_mod.AutomationManager)
    am._content_enrichment_lock = asyncio.Lock()
    am._record_phase_batch_loop = AsyncMock()
    am._activity_feed_activity_id = lambda task: f"phase:{task.name}"
    task = _make_task(am_mod)

    with (
        patch(
            "services.nightly_ingest_window_service.in_nightly_pipeline_window_est",
            return_value=True,
        ),
        patch("services.activity_feed_service.get_activity_feed") as feed_mod,
    ):
        feed = MagicMock()
        feed_mod.return_value = feed
        asyncio.run(am._execute_content_enrichment(task))

    assert task.metadata.get("skip_automation_run_history") is True
    am._record_phase_batch_loop.assert_not_called()
    feed.update_current_progress.assert_called_once()
    msg = feed.update_current_progress.call_args.kwargs.get("message") or ""
    assert "nightly" in msg.lower()


def test_content_enrichment_always_records_batch_round_even_when_zero():
    am_mod = _load_am_module()
    am = object.__new__(am_mod.AutomationManager)
    am._content_enrichment_lock = asyncio.Lock()
    am._record_phase_batch_loop = AsyncMock()
    am._activity_feed_activity_id = lambda task: f"phase:{task.name}"
    task = _make_task(am_mod)

    with (
        patch(
            "services.nightly_ingest_window_service.in_nightly_pipeline_window_est",
            return_value=False,
        ),
        patch(
            "shared.content_enrichment_drain.run_content_enrichment_batch",
            return_value=0,
        ),
    ):
        asyncio.run(am._execute_content_enrichment(task))

    assert task.metadata.get("skip_automation_run_history") is True
    am._record_phase_batch_loop.assert_awaited_once()
    kwargs = am._record_phase_batch_loop.await_args.kwargs
    assert kwargs["loops_processed"] == 1
    assert kwargs["round_processed"] == 0
    assert kwargs["processed"] == 0


def test_empty_outer_history_row_not_measurable():
    """Reproduce the Monitor mismatch: Recent activity can show a run while runs_1h ignores it."""
    from shared.monitor_run_vocabulary import is_measurable_run_history_row

    started = datetime(2026, 7, 17, 4, 34, 11, 405095, tzinfo=timezone.utc)
    finished = datetime(2026, 7, 17, 4, 34, 11, 405518, tzinfo=timezone.utc)
    assert not is_measurable_run_history_row(
        {},
        started_at=started,
        finished_at=finished,
    )
    assert is_measurable_run_history_row(
        {"status": "batch_round", "round_processed": 0},
        started_at=started,
        finished_at=finished,
    )
