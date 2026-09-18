"""Constants for domain registry / onboarding (no DB access at import)."""

from __future__ import annotations

# Retired URL keys (schema science_tech dropped in migration 212).
RETIRED_DOMAIN_KEY_ALIASES: frozenset[str] = frozenset({"science-tech"})

# Schemas that must never be targeted by provision_domain as a *new* YAML silo (system + legacy dumps).
RESERVED_SCHEMA_NAMES: frozenset[str] = frozenset(
    {
        "public",
        "information_schema",
        "pg_catalog",
        "pg_toast",
        "politics",
        "finance",
        "science_tech",  # dropped — reserved so provision_domain cannot recreate it
        "intelligence",
        "artificial_intelligence",
    }
)
