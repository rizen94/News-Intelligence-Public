"""
Enhancement orchestrator — Phase 3 RAG. Runs iterative enhancement stages on a schedule:
(1) Process fact_change_log and story_update_queue (story state refresh),
(2) Entity enrichment batch (Wikipedia → entity_profiles + versioned_facts),
(3) Entity profile builder batch (contexts → sections).
Can be invoked by AutomationManager (story_enhancement task) or API.
See docs/RAG_ENHANCEMENT_ROADMAP.md.
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def run_enhancement_cycle(
    fact_batch: int = 100,
    queue_batch: int = 10,
    enrich_limit: int = 10,
    build_limit: int = 10,
) -> dict[str, Any]:
    """
    Run one enhancement cycle: story state triggers, then entity enrichment, then profile build.
    Production: 100 fact changes, max 10 stories/run (queue_batch), 60s budget; enrich/build 10 each.
    Returns counts for each stage.
    """
    loop = asyncio.get_event_loop()
    result: dict[str, Any] = {
        "fact_change_log_processed": 0,
        "story_update_queue_processed": 0,
        "entity_profiles_enriched": 0,
        "entity_profiles_built": 0,
        "errors": [],
    }
    try:
        from services.story_state_trigger_service import (
            process_fact_change_log,
            process_story_update_queue,
        )

        result["fact_change_log_processed"] = await loop.run_in_executor(
            None, lambda: process_fact_change_log(batch_size=fact_batch)
        )
        result["story_update_queue_processed"] = await loop.run_in_executor(
            None, lambda: process_story_update_queue(batch_size=queue_batch)
        )
    except Exception as e:
        logger.warning("Enhancement cycle (triggers): %s", e)
        result["errors"].append(f"triggers: {e!s}")
    try:
        from services.entity_enrichment_service import run_enrichment_batch

        result["entity_profiles_enriched"] = await loop.run_in_executor(
            None, lambda: run_enrichment_batch(limit=enrich_limit)
        )
    except Exception as e:
        logger.warning("Enhancement cycle (enrichment): %s", e)
        result["errors"].append(f"enrichment: {e!s}")
    try:
        from services.entity_profile_builder_service import run_profile_builder_batch

        result["entity_profiles_built"] = await run_profile_builder_batch(limit=build_limit)
    except Exception as e:
        logger.warning("Enhancement cycle (profile build): %s", e)
        result["errors"].append(f"profile_build: {e!s}")
    return result
