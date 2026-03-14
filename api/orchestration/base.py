"""
Newsroom Orchestrator v6 — base orchestrator.

Uses shared get_db_connection(), in-process queue.
Retry with backoff, dead letter on max retries. Runs Reporter poll on interval.
"""

import json
import logging
import time
import threading
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from orchestration.config import load_newsroom_config
from orchestration.events.envelope import EventEnvelope
from orchestration.events.queue import InProcessEventQueue
from orchestration.events.redis_bus import publish_event  # no-op (Redis removed)
from orchestration.events.types import EventType

logger = logging.getLogger("orchestration")


class NewsroomOrchestrator:
    """
    Event-driven newsroom orchestrator. Runs in a single thread:
    - Periodic Reporter tick (poll DB, emit ARTICLE_INGESTED / BREAKING_NEWS)
    - Consume events from in-process queue; retry with backoff; dead letter on failure
    """

    def __init__(
        self,
        get_db_connection: Callable[[], Any],
        config: Optional[Dict[str, Any]] = None,
    ):
        self.get_db_connection = get_db_connection
        self.config = config or load_newsroom_config()
        self._queue = InProcessEventQueue()
        self._handlers: Dict[EventType, List[Callable[..., None]]] = {}
        self._processed_keys: set = set()
        self._processed_max = 10000
        self.is_running = False
        self._last_event_at: Optional[float] = None
        self._lock = threading.Lock()

        eh = self.config.get("event_handling") or {}
        self._max_retries = eh.get("max_retries", 3)
        self._backoff_base = eh.get("backoff_base_seconds", 2)
        self._dead_letter_after = eh.get("dead_letter_after_retries", True)

    def emit(self, envelope: EventEnvelope) -> None:
        """Enqueue event (in-process)."""
        self._queue.put(envelope)
        with self._lock:
            self._last_event_at = time.time()
        publish_event(envelope.to_dict())

    def register_handler(self, event_type: EventType, handler: Callable[..., None]) -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def _already_processed(self, key: Optional[str]) -> bool:
        if not key:
            return False
        with self._lock:
            if key in self._processed_keys:
                return True
            return False

    def _mark_processed(self, key: Optional[str]) -> None:
        if not key:
            return
        with self._lock:
            self._processed_keys.add(key)
            while len(self._processed_keys) > self._processed_max:
                self._processed_keys.pop()

    def _persist_failed(self, envelope: EventEnvelope, error: str, retry_count: int) -> None:
        try:
            conn = self.get_db_connection()
            if not conn:
                return
            try:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO orchestration.events_failed (event_id, event_type, payload, error, retry_count)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        envelope.event_id,
                        envelope.event_type.value,
                        json.dumps(envelope.payload),
                        error[:5000] if error else None,
                        retry_count,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            logger.warning("Could not persist failed event to DB: %s", e)

    def _handle_one(self, envelope: EventEnvelope) -> bool:
        """Handle one event. Returns True if handled (or skipped idempotent), False to retry."""
        key = envelope.deduplication_key
        if self._already_processed(key):
            logger.debug("Skip already processed: %s", key)
            return True
        handlers = self._handlers.get(envelope.event_type) or []
        if not handlers:
            logger.debug("No handler for %s", envelope.event_type.value)
            self._mark_processed(key)
            return True
        try:
            for h in handlers:
                try:
                    h(envelope, self)
                except TypeError:
                    h(envelope)
            self._mark_processed(key)
            return True
        except Exception as e:
            logger.exception("Handler failed for %s: %s", envelope.event_type.value, e)
            raise

    def run_loop(self) -> None:
        """Main loop: Reporter tick on interval, then drain queue with retries."""
        from orchestration.roles.reporter import reporter_tick

        reporter_cfg = self.config.get("reporter") or {}
        poll_interval = reporter_cfg.get("poll_interval_seconds", 600)
        last_reporter = 0.0
        event_timeout = 1.0

        while self.is_running:
            now = time.time()
            if now - last_reporter >= poll_interval:
                try:
                    reporter_tick(self, self.get_db_connection, self.config)
                except Exception as e:
                    logger.exception("Reporter tick failed: %s", e)
                last_reporter = now

            envelope = self._queue.get(block=True, timeout=event_timeout)
            if not envelope:
                continue
            with self._lock:
                self._last_event_at = time.time()
            attempt = 0
            while attempt <= self._max_retries:
                try:
                    if self._handle_one(envelope):
                        break
                except Exception as e:
                    attempt += 1
                    if attempt > self._max_retries:
                        if self._dead_letter_after:
                            self._persist_failed(envelope, str(e), self._max_retries)
                        logger.error("Event failed after %s retries: %s", self._max_retries, e)
                        break
                    delay = self._backoff_base ** attempt
                    logger.warning("Retry %s/%s in %ss: %s", attempt, self._max_retries, delay, e)
                    time.sleep(delay)

    def start(self) -> None:
        """Start the main loop (blocking). Call from a dedicated thread."""
        self.is_running = True
        logger.info("Newsroom orchestrator loop starting")
        try:
            self.run_loop()
        finally:
            self.is_running = False
            logger.info("Newsroom orchestrator loop stopped")

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            last = self._last_event_at
        return {
            "enabled": True,
            "running": self.is_running,
            "last_event_at": None if last is None else datetime.utcfromtimestamp(last).isoformat() + "Z",
            "queue_depth": self._queue.qsize(),
        }
