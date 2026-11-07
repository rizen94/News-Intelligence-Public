"""Constants for domain registry / onboarding (no DB access at import)."""

from __future__ import annotations

import re

# Retired URL keys (schema science_tech dropped in migration 212).
RETIRED_DOMAIN_KEY_ALIQUES: frozenset[str] = frozenset({"science-tech"})

# Schemas that must never be targeted by provision_domain as a *new* YAML silo (system + legacy dumps).
RESERVED_SCHEMA_NAMES: frozenset[str] = frozenset(
    {
        "public",
        "information_schema",
        "pg_catalog",
        "pg_toast",
        "intelligence",
        "artificial_intelligence",
    }
)

# Permitted schema names (whitelist for dynamic SQL targets).
# These are active domain schemas that can safely be interpolated into f-strings.
PERMITTED_SCHEMA_NAMES: frozenset[str] = frozenset(
    {
        "politics",
        "finance",
        "intelligence",
        "artificial_intelligence",
        "legal",
        "medicine",
        "neurodiversity",
            }
)

# Reserved-but-invalid: schemas that should never be used (excludes PERMITTED ones).
PROHIBITED_SCHEMA_NAMES: frozenset[str] = RESERVED_SCHEMA_NAMES - PERMITTED_SCHEMA_NAMES

# Regex for valid PostgreSQL schema names (identifier pattern).
_SCHEMA_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


def validate_schema_name(name: str) -> str:
    """Validate a Postgres schema name.

    Enforces three invariants:

    1. Must match PostgreSQL identifier syntax (lowercase alphanumeric + underscore).
    2. Must be in ``PERMITTED_SCHEMA_NAMES`` (whitelist of active domain schemas).
    3. Must not be in prohibited system/legacy namespaces.

    Returns the validated name on success; raises ValueError otherwise.
    """
    if not isinstance(name, str):
        raise ValueError(f"schema_name must be a string, got {type(name).__name__!r}")
    stripped = name.strip()
    if not stripped:
        raise ValueError("schema_name must not be empty")
    if not _SCHEMA_NAME_RE.match(stripped):
        raise ValueError(
            f"Invalid schema name {stripped!r}: must match pattern "
            r"^[a-z_][a-z0-9_]*$"
        )
    if stripped in PROHIBITED_SCHEMA_NAMES:
        raise ValueError(
            f"Schema name {stripped!r} is prohibited (system/legacy namespace); use a permitted domain schema instead"
        )
    if stripped not in PERMITTED_SCHEMA_NAMES:
        raise ValueError(
            f"Schema name {stripped!r} is not in the permitted whitelist; "
            f"approved schemas: {sorted(PERMITTED_SCHEMA_NAMES)}"
        )
    return stripped


def validate_schema_names(names: list[str]) -> list[str]:
    """Validate a list of schema names. Returns cleaned list on success."""
    return [validate_schema_name(n) for n in names]
