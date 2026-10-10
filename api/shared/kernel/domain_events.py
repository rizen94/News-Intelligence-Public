"""
Lightweight in-process domain event bus for cross-domain decoupling.

Handlers run synchronously in the publishing thread; keep handlers fast and delegate
heavy work to background services/queues.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)

DomainEventHandler = Callable[["DomainEvent"], None]


@dataclass(frozen=True)
class DomainEvent:
    """A domain-scoped notification payload."""

    event_type: str
    domain_key: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    occurred_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class DomainEventBus:
    """Simple pub/sub registry (process-local singleton)."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[DomainEventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: DomainEventHandler) -> None:
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)

    def publish(self, event: DomainEvent) -> int:
        handlers = list(self._handlers.get(event.event_type, []))
        handlers.extend(self._handlers.get("*", []))
        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:
                logger.warning(
                    "Domain event handler failed type=%s: %s",
                    event.event_type,
                    exc,
                    exc_info=True,
                )
        return len(handlers)


_bus: DomainEventBus | None = None


def get_domain_event_bus() -> DomainEventBus:
    global _bus
    if _bus is None:
        _bus = DomainEventBus()
    return _bus


def publish_domain_event(
    event_type: str,
    *,
    domain_key: str | None = None,
    payload: dict[str, Any] | None = None,
) -> int:
    """Publish a domain event and return handler count."""
    event = DomainEvent(
        event_type=event_type,
        domain_key=domain_key,
        payload=payload or {},
    )
    return get_domain_event_bus().publish(event)
