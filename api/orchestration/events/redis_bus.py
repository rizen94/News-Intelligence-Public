"""
Optional Redis pub/sub for Newsroom Orchestrator v6.

If REDIS_URL is set and connection succeeds, publish events to a channel.
Main consumer queue stays in-process; this is for optional subscribers (e.g. dashboard).
"""

import json
import logging
from typing import Optional

logger = logging.getLogger("orchestration")

_redis_client = None
_redis_available = False
_channel = "newsroom:events"


def _get_redis():
    global _redis_client, _redis_available
    if _redis_client is not None:
        return _redis_client if _redis_available else None
    try:
        import os
        import redis
        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = redis.Redis.from_url(url, decode_responses=True, socket_timeout=2)
        r.ping()
        _redis_client = r
        _redis_available = True
        logger.info("Redis pub/sub available for newsroom events")
        return r
    except Exception as e:
        logger.debug("Redis unavailable for pub/sub: %s", e)
        _redis_available = False
        return None


def publish_event(envelope_dict: dict) -> bool:
    """Publish event dict to Redis channel. Returns True if published."""
    r = _get_redis()
    if not r:
        return False
    try:
        r.publish(_channel, json.dumps(envelope_dict))
        return True
    except Exception as e:
        logger.warning("Redis publish failed: %s", e)
        return False
