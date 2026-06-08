"""Constants for domain registry / onboarding (no DB access at import)."""

from __future__ import annotations

# Schemas that must never be targeted by provision_domain as a *new* YAML silo (system + legacy dumps).
RESERVED_SCHEMA_NAMES: frozenset[str] = frozenset(
    {
        "public",
        "information_schema",
        "pg_catalog",
        "pg_toast",
        "politics",
        "finance",
        "science_tech",
        "intelligence",
        "artificial_intelligence",
    }
)
