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


def pipeline_domain_any_sql(
    column: str = "domain_key",
    phase: str | None = None,
) -> tuple[str, list[str]]:
    """
    Return (sql_fragment, keys) for ``column = ANY(%s)`` (psycopg2 needs a list).

    ``phase`` narrows the keys to domains whose ``processing_mode`` band runs that phase, so a
    research-band phase stops scanning corpus-only silos. Shared or unknown phase names fail open,
    and ``PROCESSING_MODE_ENFORCE=0`` disables the gate — both handled by
    ``domain_processing_mode.domain_runs_phase``.
    """
    keys = list(pipeline_domain_keys())
    if phase:
        try:
            from shared.domain_processing_mode import filter_domains_for_phase

            keys = filter_domains_for_phase(keys, phase)
        except Exception:
            # Fail open on the whole pipeline set rather than narrowing to nothing: the band gate is
            # an efficiency filter, not an authorisation boundary.
            pass
    if not keys:
        return "FALSE", []
    return f"{column} = ANY(%s)", keys
