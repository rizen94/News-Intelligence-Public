"""
In-process priority queue for Newsroom Orchestrator v6.

Phase 1: no Redis required. Lower priority number = higher priority (1=critical).
"""

import heapq
import logging
import threading
import time
from typing import Optional

from .envelope import EventEnvelope

logger = logging.getLogger("orchestration")


class InProcessEventQueue:
    """Thread-safe priority queue (min-heap by priority, then timestamp)."""

    def __init__(self, maxsize: int = 0):
        self._heap: list = []
        self._lock = threading.Lock()
        self._maxsize = maxsize  # 0 = unbounded
        self._count = 0

    def put(self, envelope: EventEnvelope, block: bool = True, timeout: Optional[float] = None) -> None:
        """Add event. (priority, count, envelope) for stable ordering."""
        with self._lock:
            if self._maxsize and self._count >= self._maxsize and block:
                if timeout is not None and timeout <= 0:
                    raise ValueError("queue full")
                end = time.monotonic() + timeout if timeout else None
                while self._maxsize and self._count >= self._maxsize:
                    if end and time.monotonic() >= end:
                        raise ValueError("queue full (timeout)")
                    self._lock.release()
                    time.sleep(0.1)
                    self._lock.acquire()
            self._count += 1
            ts = time.monotonic()
            heapq.heappush(
                self._heap,
                (envelope.priority, ts, self._count, envelope),
            )
        logger.debug("Queue put: %s (priority=%s, queue_size=%s)", envelope.event_type.value, envelope.priority, self.qsize())

    def get(self, block: bool = True, timeout: Optional[float] = None) -> Optional[EventEnvelope]:
        """Remove and return next event. Returns None if non-blocking and empty."""
        with self._lock:
            if not self._heap:
                if not block:
                    return None
                if timeout is not None and timeout <= 0:
                    return None
                end = time.monotonic() + timeout if timeout else None
                while not self._heap:
                    if end and time.monotonic() >= end:
                        return None
                    self._lock.release()
                    time.sleep(0.05)
                    self._lock.acquire()
            _prio, _ts, _c, envelope = heapq.heappop(self._heap)
            self._count = max(0, self._count - 1)
            return envelope

    def qsize(self) -> int:
        with self._lock:
            return len(self._heap)
