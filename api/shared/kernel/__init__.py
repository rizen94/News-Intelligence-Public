"""Shared kernel — cross-domain infrastructure primitives."""

from api.shared.kernel.domain_events import (
    DomainEvent,
    DomainEventBus,
    get_domain_event_bus,
    publish_domain_event,
)
from api.shared.services.article_query_service import (
    get_domain_articles,
    get_recent_domain_articles,
)

__all__ = [
    "DomainEvent",
    "DomainEventBus",
    "get_domain_articles",
    "get_domain_event_bus",
    "get_recent_domain_articles",
    "publish_domain_event",
]
