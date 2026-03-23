"""
Optional Redis cache for idempotent LLM text results (content-hash + model + kind).

Enable with NEWS_INTEL_LLM_CACHE_REDIS=true and REDIS_HOST (or REDIS_URL).
Bust cache when prompts/models change by bumping NEWS_INTEL_LLM_CACHE_VERSION (default 1).

Used by hot paths only when explicitly wired — not a global middleware.
"""

from __future__ import annotations

import hashlib
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_CACHE_VERSION = os.environ.get("NEWS_INTEL_LLM_CACHE_VERSION", "1").strip() or "1"
_ENABLED = os.environ.get("NEWS_INTEL_LLM_CACHE_REDIS", "").lower() in ("1", "true", "yes")

_redis = None  # lazy


def _client():
    global _redis
    if not _ENABLED:
        return None
    if _redis is not None:
        return _redis if _redis is not False else None
    try:
        import redis  # type: ignore
    except ImportError:
        logger.debug("optional_llm_redis_cache: redis package not installed")
        _redis = False
        return None
    url = (os.environ.get("REDIS_URL") or "").strip()
    if url:
        try:
            _redis = redis.Redis.from_url(url, decode_responses=True, socket_timeout=2.0)
            return _redis
        except Exception as e:
            logger.debug("optional_llm_redis_cache: from_url failed: %s", e)
            _redis = False
            return None
    host = (os.environ.get("REDIS_HOST") or "").strip()
    if not host:
        _redis = False
        return None
    port = int(os.environ.get("REDIS_PORT", "6379") or "6379")
    password = os.environ.get("REDIS_PASSWORD") or None
    try:
        _redis = redis.Redis(
            host=host,
            port=port,
            password=password,
            decode_responses=True,
            socket_timeout=2.0,
        )
        return _redis
    except Exception as e:
        logger.debug("optional_llm_redis_cache: connect failed: %s", e)
        _redis = False
        return None


def cache_key(*, prompt: str, model: str, kind: str) -> str:
    h = hashlib.sha256()
    h.update(_CACHE_VERSION.encode())
    h.update(b"|")
    h.update(model.encode())
    h.update(b"|")
    h.update(kind.encode())
    h.update(b"|")
    h.update((prompt or "").encode("utf-8", errors="replace"))
    return f"ni:llm:{h.hexdigest()[:48]}"


def cache_get(*, prompt: str, model: str, kind: str) -> Optional[str]:
    r = _client()
    if not r:
        return None
    try:
        k = cache_key(prompt=prompt, model=model, kind=kind)
        v = r.get(k)
        return v if isinstance(v, str) else None
    except Exception as e:
        logger.debug("optional_llm_redis_cache get: %s", e)
        return None


def cache_set(*, prompt: str, model: str, kind: str, text: str, ttl_seconds: int = 86400) -> None:
    r = _client()
    if not r:
        return
    try:
        k = cache_key(prompt=prompt, model=model, kind=kind)
        r.setex(k, max(60, ttl_seconds), text)
    except Exception as e:
        logger.debug("optional_llm_redis_cache set: %s", e)
