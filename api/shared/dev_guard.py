"""
Development environment guardrails — refuse production hosts when ENVIRONMENT=development.

Structural protection for v11 local work on PopOS: scripts and the API must not
silently write to Widow ``news_intel`` when a developer loads ``.env.dev``.
"""

from __future__ import annotations

import os
from typing import Iterable

# Authoritative Widow NI database host (see AGENTS.md / PROJECT_STATUS.md).
WIDOW_PRODUCTION_HOSTS: frozenset[str] = frozenset(
    {
        "192.168.93.101",
        "widow",
        "widow.local",
    }
)


class DevGuardError(RuntimeError):
    """Raised when development mode would target a production database host."""


def _normalize_host(host: str | None) -> str:
    return (host or "").strip().lower().rstrip(".")


def environment_name() -> str:
    return (os.environ.get("ENVIRONMENT") or os.environ.get("NI_ENVIRONMENT") or "").strip().lower()


def is_development_environment() -> bool:
    env = environment_name()
    return env in ("development", "dev", "local")


def is_production_db_host(host: str | None) -> bool:
    h = _normalize_host(host)
    if not h:
        return False
    if h in WIDOW_PRODUCTION_HOSTS:
        return True
    # Bare hostname contains widow
    if h.split(":")[0] in WIDOW_PRODUCTION_HOSTS:
        return True
    return False


def assert_dev_db_host_safe(
    host: str | None = None,
    *,
    extra_hosts: Iterable[str] | None = None,
) -> None:
    """
    Hard refusal when ENVIRONMENT is development and DB_HOST points at Widow.

    Call from ``config.runtime`` at import / config load so every script that
    imports runtime inherits the guard.
    """
    if not is_development_environment():
        return

    resolved = host if host is not None else os.environ.get("DB_HOST", "")
    hosts_to_check = [_normalize_host(resolved)]
    if extra_hosts:
        hosts_to_check.extend(_normalize_host(h) for h in extra_hosts)

    for h in hosts_to_check:
        if is_production_db_host(h):
            raise DevGuardError(
                f"ENVIRONMENT={environment_name()!r} refuses production DB host "
                f"{h!r}. Use .env.dev with DB_HOST=127.0.0.1 (local news_intel_dev). "
                "Widow writes are blocked until an explicit v11 cutover."
            )


def enforce_dev_guard_from_environ() -> None:
    """Entry point used by runtime import side-effects."""
    assert_dev_db_host_safe()
    # Also refuse identity_spine pointing at Widow under development.
    assert_dev_db_host_safe(
        os.environ.get("IDENTITY_SPINE_HOST") or None,
        extra_hosts=None,
    )
    # If IDENTITY_SPINE_HOST is unset it falls back to DB_HOST — already checked.
    spine = os.environ.get("IDENTITY_SPINE_HOST")
    if spine:
        assert_dev_db_host_safe(spine)
