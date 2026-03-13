"""
Event envelope for Newsroom Orchestrator v6.

Single envelope for all events: event_id, event_type, payload, priority, timestamp,
domain, correlation_id, deduplication_key.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .types import EventType


@dataclass
class EventEnvelope:
    """Event envelope for the newsroom message bus."""

    event_type: EventType
    payload: Dict[str, Any]
    priority: int = 3
    domain: Optional[str] = None
    correlation_id: Optional[str] = None
    deduplication_key: Optional[str] = None
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: Optional[str] = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "payload": self.payload,
            "priority": self.priority,
            "timestamp": self.timestamp,
            "domain": self.domain,
            "correlation_id": self.correlation_id,
            "deduplication_key": self.deduplication_key,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EventEnvelope":
        event_type = data["event_type"]
        if isinstance(event_type, str):
            event_type = EventType(event_type)
        return cls(
            event_type=event_type,
            payload=data["payload"],
            priority=data.get("priority", 3),
            domain=data.get("domain"),
            correlation_id=data.get("correlation_id"),
            deduplication_key=data.get("deduplication_key"),
            event_id=data.get("event_id", str(uuid.uuid4())),
            timestamp=data.get("timestamp"),
        )
