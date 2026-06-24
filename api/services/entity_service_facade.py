"""
Entity service facade — common entity operations for routes, automation, and scripts.

Delegates to specialized services; keeps callers decoupled from individual modules.
"""

from __future__ import annotations

from typing import Any


def resolve_with_candidates(
    domain_key: str,
    entity_name: str,
    entity_type: str = "person",
    *,
    limit: int = 10,
) -> dict[str, Any]:
    from services.entity_resolution_service import resolve_with_candidates as _resolve

    return _resolve(domain_key, entity_name, entity_type, limit=limit)


def populate_aliases(domain_key: str, *, min_mentions: int = 2) -> dict[str, Any]:
    from services.entity_resolution_service import populate_aliases_from_mentions

    return populate_aliases_from_mentions(domain_key, min_mentions=min_mentions)


def find_merge_candidates(
    domain_key: str,
    *,
    min_confidence: float = 0.5,
    limit: int = 50,
) -> dict[str, Any]:
    from services.entity_resolution_service import find_merge_candidates as _find

    return _find(domain_key, min_confidence=min_confidence, limit=limit)


def merge_canonical(
    domain_key: str,
    *,
    keep_id: int,
    merge_id: int,
) -> dict[str, Any]:
    from services.entity_resolution_service import merge_canonical_entities

    return merge_canonical_entities(domain_key, keep_id=keep_id, merge_id=merge_id)


def run_resolution_batch(
    *,
    auto_merge_confidence: float = 0.9,
    cross_domain_confidence: float = 0.8,
) -> dict[str, Any]:
    from services.entity_resolution_service import run_resolution_batch as _batch

    return _batch(
        auto_merge_confidence=auto_merge_confidence,
        cross_domain_confidence=cross_domain_confidence,
    )


def sync_entity_profiles(domain_key: str) -> dict[str, Any]:
    from services.entity_profile_sync_service import (
        backfill_entity_canonical,
        sync_domain_entity_profiles,
    )

    backfilled = backfill_entity_canonical(domain_key)
    created = sync_domain_entity_profiles(domain_key)
    return {
        "success": True,
        "domain_key": domain_key,
        "canonical_backfilled": backfilled,
        "profiles_created": created,
    }


def get_entity_positions(domain_key: str, entity_id: int, *, limit: int = 50) -> dict[str, Any]:
    from services.entity_position_tracker_service import get_entity_positions as _get

    return _get(domain_key, entity_id, limit=limit)
