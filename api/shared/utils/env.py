"""Cached environment variable helpers for News Intelligence services.

Extracted from ``config.runtime`` to serve as a thin, cache-friendly layer
for services that read configuration values but don't need runtime config
merging.  Files that only use ``env_str / env_bool / env_int`` should import
from this module **instead of** ``config.runtime`` — it avoids pulling in the
large runtime-config dict and any ``@lru_cache`` overhead on unrelated symbols.

All helpers cache their result keyed by environment variable name so that
hot paths avoid repeated ``os.environ.get`` calls.  Cache is cleared on import
of this module only (i.e. no automatic invalidation — callers should call
``reset_env_cache()`` when env vars change at runtime).
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any


# ── Internal ----------------------------------------------------------------

def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


# ── Cached helpers ----------------------------------------------------------

@lru_cache(maxsize=512)
def env_str(name: str, default: str = "") -> str:
    """Return the stripped environment variable *name*, falling back to *default*."""
    return _env(name, default)


@lru_cache(maxsize=512)
def env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name)
    if not raw:
        return default
    return raw.lower() in ("1", "true", "yes", "on")


@lru_cache(maxsize=512)
def env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except (TypeError, ValueError):
        return default


@lru_cache(maxsize=512)
def env_float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)))
    except (TypeError, ValueError):
        return default


# ── Non-cached helpers (for mutable / set-pop operations) -------------------

def env_pop(name: str, default: str | None = None) -> str | None:
    """Pop an environment variable and return its value (or *default*)."""
    return os.environ.pop(name, default)


def env_setdefault(name: str, value: str) -> str:
    return os.environ.setdefault(name, value)


def env_set(name: str, value: str) -> None:
    os.environ[name] = value


# ── Cache management --------------------------------------------------------

def reset_env_cache() -> None:
    """Clear the LRU cache for all cached env helpers.

    Call this when environment variables change at runtime (e.g., after a
    dynamic reload, config update, or during tests).
    """
    env_str.cache_clear()  # type: ignore[attr-defined]
    env_bool.cache_clear()  # type: ignore[attr-defined]
    env_int.cache_clear()  # type: ignore[attr-defined]
    env_float.cache_clear()  # type: ignore[attr-defined]
