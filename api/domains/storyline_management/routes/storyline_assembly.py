"""
Storyline assembly API — run proactive detection + discovery + automation for one domain.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Path, Query
from services.storyline_assembly_service import (
    count_unlinked_articles,
    run_storyline_assembly_for_domain,
)
from shared.domain_registry import DOMAIN_PATH_PATTERN, is_valid_domain_key

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Storyline Assembly"])


@router.post("/{domain}/storylines/assemble")
async def assemble_domain_storylines(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    run_proactive: bool = Query(True, description="Run proactive emerging-storyline detection"),
    run_discovery: bool = Query(True, description="Run AI storyline discovery and save clusters"),
    run_automation: bool = Query(
        True, description="Match new articles to automation-enabled storylines"
    ),
    discovery_hours: Annotated[
        int | None,
        Query(description="Optional discovery window in hours; omit for full capped backlog"),
    ] = None,
    max_automation_storylines: Annotated[
        int | None,
        Query(ge=1, le=100, description="Max storylines to scan in automation step"),
    ] = None,
):
    """
    Tie together storyline assembly for a domain: detect new clusters, discover storylines,
    and attach incoming articles to existing automation-enabled storylines.
    """
    if not is_valid_domain_key(domain):
        return {"success": False, "message": f"Unknown or inactive domain: {domain}"}
    logger.info("Storyline assembly requested for %s", domain)
    result = await run_storyline_assembly_for_domain(
        domain,
        run_proactive=run_proactive,
        run_discovery=run_discovery,
        run_automation=run_automation,
        discovery_hours=discovery_hours,
        max_automation_storylines=max_automation_storylines,
    )
    return {"success": True, "data": result, "message": None}


@router.get("/{domain}/storylines/assembly_status")
def storyline_assembly_status(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
):
    """Unlinked-article count and whether assembly is recommended for this domain."""
    if not is_valid_domain_key(domain):
        return {"success": False, "message": f"Unknown or inactive domain: {domain}"}
    unlinked = count_unlinked_articles(domain)
    try:
        from services.domain_synthesis_config import get_domain_synthesis_config

        cfg = get_domain_synthesis_config(domain)
        threshold = cfg.storyline_development.automation.unlinked_article_threshold
        mode = cfg.storyline_development.automation.default_mode
    except Exception:
        threshold = 25
        mode = "auto_approve"
    return {
        "success": True,
        "data": {
            "domain": domain,
            "unlinked_articles": unlinked,
            "assembly_recommended": unlinked >= threshold,
            "threshold": threshold,
            "automation_mode": mode,
        },
        "message": None,
    }
