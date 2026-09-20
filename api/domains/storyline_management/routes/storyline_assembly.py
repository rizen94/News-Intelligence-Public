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
    story_kind = None
    try:
        from services.domain_synthesis_config import get_domain_synthesis_config

        cfg = get_domain_synthesis_config(domain)
        threshold = cfg.storyline_development.automation.unlinked_article_threshold
        mode = cfg.storyline_development.automation.default_mode
        story_kind = cfg.story_kind
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
            "story_kind": story_kind,
        },
        "message": None,
    }


@router.get("/{domain}/storylines/story_kind")
async def get_domain_story_kind_info(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
):
    """Chemistry model: protein shape + link score profile for this domain."""
    if not is_valid_domain_key(domain):
        return {"success": False, "message": f"Unknown or inactive domain: {domain}"}
    from services.domain_synthesis_config import get_domain_synthesis_config

    cfg = get_domain_synthesis_config(domain)
    p = cfg.link_score_profile
    return {
        "success": True,
        "data": {
            "domain": domain,
            "story_kind": cfg.story_kind,
            "is_chemistry_kind": cfg.is_chemistry_kind(),
            "display_label": {
                "event_narrative": "Story",
                "market_regulatory_arc": "Market arc",
                "matter_docket": "Matter / docket",
                "evidence_thread": "Evidence thread",
                "research_topic": "Research thread",
            }.get(cfg.story_kind, "Storyline"),
            "link_score_profile": {
                "relevance_weight": p.relevance_weight,
                "semantic_weight": p.semantic_weight,
                "keyword_weight": p.keyword_weight,
                "quality_weight": p.quality_weight,
                "temporal_weight": p.temporal_weight,
                "canonical_entity_weight": p.canonical_entity_weight,
                "temporal_half_life_days": p.temporal_half_life_days,
                "auto_approve_combined": p.auto_approve_combined,
                "aggressive_membership": p.aggressive_membership,
                "allow_storyline_merge": p.allow_storyline_merge,
            },
        },
    }
