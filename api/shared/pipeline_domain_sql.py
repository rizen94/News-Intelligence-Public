"""SQL helpers: limit intelligence work to pipeline-active domain keys."""

from __future__ import annotations

from shared.domain_registry import get_pipeline_active_domain_keys
from shared.domain_registry_constants import RETIRED_DOMAIN_KEY_ALIASES


def pipeline_domain_keys() -> tuple[str, ...]:
    return get_pipeline_active_domain_keys()


def is_retired_domain_key(domain_key: str | None) -> bool:
    if not domain_key:
        return False
    normalized = str(domain_key).strip().lower().replace("_", "-")
    return normalized in RETIRED_DOMAIN_KEY_ALIASES


def normalize_legacy_domain_key(domain_key: str) -> str:
    """Map retired science-tech tokens to artificial-intelligence for legacy rows/URLs."""
    normalized = str(domain_key or "").strip().lower().replace("_", "-")
    if normalized in RETIRED_DOMAIN_KEY_ALIASES or normalized in ("sciencetech", "science tech"):
        return "artificial-intelligence"
    return normalized


def pipeline_domain_any_sql(column: str = "domain_key") -> tuple[str, list[str]]:
    """Return (sql_fragment, keys) for ``column = ANY(%s)`` (psycopg2 needs a list)."""
    keys = list(pipeline_domain_keys())
    if not keys:
        return "FALSE", []
    return f"{column} = ANY(%s)", keys
