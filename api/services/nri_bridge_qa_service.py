"""Backward-compatible shim."""

from nri_core.services.bridge_qa import (  # noqa: F401
    assess_bridge_qa,
    enrich_bridge_with_qa,
    pg_trgm_similarity,
)

__all__ = ["assess_bridge_qa", "enrich_bridge_with_qa", "pg_trgm_similarity"]
