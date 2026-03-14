"""
Redis pub/sub removed for simplicity. Event queue is in-process only.

If you need Redis later (e.g. multi-node or external subscribers), restore
connection logic and call r.publish(channel, payload) here.
"""

import logging
from typing import Any

logger = logging.getLogger("orchestration")


def publish_event(envelope_dict: dict[str, Any]) -> bool:
    """No-op. Returns False (not published). In-process queue is the source of truth."""
    return False
