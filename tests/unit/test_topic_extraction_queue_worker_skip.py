"""Skip topic queue worker when domain schema lacks topic_extraction_queue."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from domains.content_analysis.services.topic_extraction_queue_worker import (
    TopicExtractionQueueWorker,
)


def test_start_skips_when_queue_table_missing(monkeypatch):
    monkeypatch.setattr(
        "domains.content_analysis.services.topic_extraction_queue_worker.STARTUP_DELAY_SECONDS",
        0,
    )

    cur = MagicMock()
    cur.fetchone.return_value = None  # table missing
    cur.__enter__ = MagicMock(return_value=cur)
    cur.__exit__ = MagicMock(return_value=False)

    conn = MagicMock()
    conn.cursor.return_value = cur
    conn.close = MagicMock()

    worker = TopicExtractionQueueWorker(lambda: conn, schema="neurodiversity")
    asyncio.run(worker.start())

    assert worker.is_running is False
    assert worker._queue_table_missing is True


def test_batch_stops_on_missing_relation_error(monkeypatch):
    worker = TopicExtractionQueueWorker(lambda: None, schema="neurodiversity")
    worker.is_running = True

    async def boom(_should_yield):
        raise RuntimeError(
            'relation "neurodiversity.topic_extraction_queue" does not exist'
        )

    monkeypatch.setattr(
        "domains.content_analysis.services.topic_extraction_queue_worker._get_ollama_semaphore",
        lambda: asyncio.Semaphore(1),
    )
    monkeypatch.setattr(
        "shared.services.api_request_tracker.should_yield_to_api",
        lambda: False,
    )
    worker._process_queue_batch_inner = boom  # type: ignore[method-assign]

    had = asyncio.run(worker._process_queue_batch())
    assert had is False
    assert worker.is_running is False
    assert worker._queue_table_missing is True
