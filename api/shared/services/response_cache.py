"""
Simple response caching for frequently accessed endpoints
Uses in-memory cache with TTL (Time To Live)
"""

import hashlib
import inspect
import json
import logging
import time
from collections.abc import Callable
from functools import wraps

logger = logging.getLogger(__name__)

# In-memory cache (thread-safe with simple dict)
_cache: dict = {}
_cache_lock = None

try:
    import threading

    _cache_lock = threading.Lock()
except ImportError:
    pass


def _get_cache_key(*args, **kwargs) -> str:
    """Generate cache key from function arguments"""
    key_data = {"args": args, "kwargs": sorted(kwargs.items())}
    key_str = json.dumps(key_data, sort_keys=True, default=str)
    return hashlib.md5(key_str.encode()).hexdigest()


def cached_response(ttl: int = 60, max_size: int = 1000):
    """
    Decorator to cache function responses

    Args:
        ttl: Time to live in seconds (default: 60)
        max_size: Maximum number of cached items (default: 1000)

    Usage:
        @cached_response(ttl=300)  # Cache for 5 minutes
        async def get_dashboard_stats():
            ...
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            async def _call_underlying():
                if inspect.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                return func(*args, **kwargs)

            # Skip caching if lock not available
            if _cache_lock is None:
                return await _call_underlying()

            # Generate cache key
            cache_key = f"{func.__name__}:{_get_cache_key(*args, **kwargs)}"

            # Check cache
            with _cache_lock:
                if cache_key in _cache:
                    cached_item = _cache[cache_key]
                    # Check if expired
                    if time.time() - cached_item["timestamp"] < ttl:
                        logger.debug(f"Cache HIT: {func.__name__}")
                        return cached_item["value"]
                    else:
                        # Expired, remove it
                        del _cache[cache_key]
                        logger.debug(f"Cache EXPIRED: {func.__name__}")

            # Cache miss - call function (sync or async)
            result = await _call_underlying()

            # Store in cache
            with _cache_lock:
                # Clean up old entries if cache is full
                if len(_cache) >= max_size:
                    # Remove oldest 10% of entries
                    sorted_items = sorted(_cache.items(), key=lambda x: x[1]["timestamp"])
                    to_remove = len(sorted_items) // 10
                    for key, _ in sorted_items[:to_remove]:
                        del _cache[key]

                _cache[cache_key] = {"value": result, "timestamp": time.time()}
                logger.debug(f"Cache STORE: {func.__name__}")

            return result

        return wrapper

    return decorator


def cached_response_sync(ttl: int = 60, max_size: int = 1000):
    """
    Same TTL cache as ``cached_response`` but keeps the handler **synchronous**.

    Use for **sync** ``def`` FastAPI routes that do blocking I/O (psycopg2).  The async
    ``cached_response`` wrapper would make Starlette treat the endpoint as async and run
    blocking work on the event loop — freezing all other requests on that worker.
    """

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if _cache_lock is None:
                return func(*args, **kwargs)

            cache_key = f"{func.__name__}:{_get_cache_key(*args, **kwargs)}"

            with _cache_lock:
                if cache_key in _cache:
                    cached_item = _cache[cache_key]
                    if time.time() - cached_item["timestamp"] < ttl:
                        logger.debug("Cache HIT (sync): %s", func.__name__)
                        return cached_item["value"]
                    del _cache[cache_key]
                    logger.debug("Cache EXPIRED (sync): %s", func.__name__)

            result = func(*args, **kwargs)

            with _cache_lock:
                if len(_cache) >= max_size:
                    sorted_items = sorted(_cache.items(), key=lambda x: x[1]["timestamp"])
                    to_remove = len(sorted_items) // 10
                    for key, _ in sorted_items[:to_remove]:
                        del _cache[key]
                _cache[cache_key] = {"value": result, "timestamp": time.time()}
                logger.debug("Cache STORE (sync): %s", func.__name__)

            return result

        return wrapper

    return decorator


def clear_cache(pattern: str | None = None):
    """
    Clear cache entries

    Args:
        pattern: Optional pattern to match cache keys (e.g., "get_dashboard")
                 If None, clears all cache
    """
    global _cache
    if _cache_lock is None:
        return

    with _cache_lock:
        if pattern is None:
            _cache.clear()
            logger.info("Cache cleared (all entries)")
        else:
            keys_to_remove = [k for k in _cache.keys() if pattern in k]
            for key in keys_to_remove:
                del _cache[key]
            logger.info(f"Cache cleared ({len(keys_to_remove)} entries matching '{pattern}')")


def get_cache_stats() -> dict:
    """Get cache statistics"""
    if _cache_lock is None:
        return {"enabled": False}

    with _cache_lock:
        return {
            "enabled": True,
            "size": len(_cache),
            "entries": list(_cache.keys())[:10],  # First 10 keys
        }
