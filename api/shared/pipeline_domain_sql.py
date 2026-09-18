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
    if normalized in RETIRED_DOMAIN_KEY_ALIASES or normalized in (
        "sciencetech",
        "science tech",
    ):
        return "artificial-intelligence"
    return normalized


def pipeline_url_schema_pairs_for_phase(
    phase: str | None = None,
) -> list[tuple[str, str]]:
    """
    ``(domain_key, schema_name)`` for pipeline domains whose band runs ``phase``.

    A research-band phase stops scanning corpus-only silos, so it neither drains nor *counts* work
    that will never happen. Shared or unknown phase names fail open, as does
    ``PROCESSING_MODE_ENFORCE=0`` — both handled by ``domain_processing_mode.domain_runs_phase``.
    A processing-mode lookup failure also falls back to the full pipeline set: the band gate is an
    efficiency filter, not an authorisation boundary.
    """
    from shared.domain_registry import pipeline_url_schema_pairs

    pairs = [(str(dk), str(sch)) for dk, sch in pipeline_url_schema_pairs()]
    if not phase:
        return pairs
    try:
        from shared.domain_processing_mode import domain_runs_phase

        return [(dk, sch) for dk, sch in pairs if domain_runs_phase(dk, phase)]
    except Exception:
        return pairs


def pipeline_domain_keys_for_phase(phase: str | None = None) -> list[str]:
    """URL domain keys that may run or count ``phase``."""
    return [dk for dk, _sch in pipeline_url_schema_pairs_for_phase(phase)]


def pipeline_schema_names_for_phase(phase: str | None = None) -> list[str]:
    """Postgres schema names for domains that may run or count ``phase``."""
    return [sch for _dk, sch in pipeline_url_schema_pairs_for_phase(phase)]


def pipeline_domain_any_sql(
    column: str = "domain_key",
    phase: str | None = None,
) -> tuple[str, list[str]]:
    """
    Return (sql_fragment, keys) for ``column = ANY(%s)`` (psycopg2 needs a list).

    ``phase`` narrows the keys the same way ``pipeline_domain_keys_for_phase`` does.
    """
    keys = (
        pipeline_domain_keys_for_phase(phase) if phase else list(pipeline_domain_keys())
    )
    if not keys:
        return "FALSE", []
    return f"{column} = ANY(%s)", keys
