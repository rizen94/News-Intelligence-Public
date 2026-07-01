"""Backward-compatible shim."""

from nri_core.services.entity_claims import get_entity_claims_in_context  # noqa: F401

__all__ = ["get_entity_claims_in_context"]
