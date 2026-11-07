"""
Cross-domain entity profile sync API — manual trigger for priority flag reconciliation.
Used by operators to force-update multi_domain_priority flags on entity_profiles.
"""

import logging
from typing import Any

from fastapi import APIRouter, Body, Query

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/system_monitoring",
    tags=["System Monitoring"],
)


@router.post("/sync/cross-domain-priorities")
def post_sync_cross_domain_priorities(
    domains: list[str] | None = Body(None, embed=True),
) -> dict[str, Any]:
    """Manually trigger cross-domain priority flag reconciliation on entity_profiles.

    Without *domains*: runs a full reconciliation (unsets all flags, re-computes from
    context_entity_mentions and cross_domain_correlations across the entire corpus).

    With *domains*: runs a lightweight per-domain reconciliation for each specified domain key,
    flagging entities that appear in that domain plus at least one other.
    """
    from services.entity_profile_sync_service import (
        sync_cross_domain_priorities,
        sync_cross_domain_priorities_for_domain,
    )

    if domains:
        per_domain_results: list[dict[str, Any]] = []
        total_newly_flagged = 0
        errors: list[str] = []

        for domain_key in domains:
            try:
                count = sync_cross_domain_priorities_for_domain(domain_key)
                total_newly_flagged += count
                per_domain_results.append({"domain": domain_key, "newly_flagged": count})
            except Exception as e:
                errors.append(f"{domain_key}: {e}")
                logger.warning(
                    "sync_cross_domain_priorities_for_domain %s failed: %s", domain_key, e
                )

        return {
            "success": len(errors) == 0 or total_newly_flagged > 0,
            "mode": "per-domain",
            "domains_requested": domains,
            "newly_flagged_total": total_newly_flagged,
            "per_domain": per_domain_results,
            "errors": errors if errors else None,
        }

    # Full reconciliation
    try:
        result = sync_cross_domain_priorities()
        return {
            "success": result.get("success", False),
            "mode": "full-reconciliation",
            **{k: v for k, v in result.items()},
        }
    except Exception as e:
        logger.warning("sync_cross_domain_priorities failed: %s", e)
        return {
            "success": False,
            "mode": "full-reconciliation",
            "error": str(e),
            "multi_domain_count": 0,
        }
