"""
Enhancement orchestrator — Phase 3 RAG. Runs iterative enhancement stages on a schedule:
(1) Process fact_change_log and story_update_queue (story state refresh),
(2) Entity enrichment batch (Wikipedia → entity_profiles + versioned_facts),
(3) Entity profile builder batch (contexts → sections).

Enrichment (Widow HTTP) and profile build (GPU LLM) run concurrently by default so both
hosts can work in parallel during catch-up. Set ENHANCEMENT_PARALLEL_ENRICH_BUILD=false to
restore sequential enrich-then-build.

Can be invoked by AutomationManager (story_enhancement task) or API.
See docs/RAG_ENHANCEMENT_ROADMAP.md.
"""

import asyncio
import logging
from typing import Any

from config.runtime import env_bool

logger = logging.getLogger(__name__)


async def _run_enrichment_batch(limit: int) -> int:
    from services.entity_enrichment_service import run_enrichment_batch

    loop = asyncio.get_event_loop()
    return int(await loop.run_in_executor(None, lambda: run_enrichment_batch(limit=limit)) or 0)


async def _run_profile_build_batch(limit: int) -> int:
    from services.entity_profile_builder_service import run_profile_builder_batch

    result = await run_profile_builder_batch(limit=limit)
    return int(result.updated or 0)


async def run_enhancement_cycle(
    fact_batch: int = 100,
    queue_batch: int = 10,
    enrich_limit: int = 10,
    build_limit: int = 10,
) -> dict[str, Any]:
    """
    Run one enhancement cycle: story state triggers, then entity enrichment + profile build.
    When ENHANCEMENT_PARALLEL_ENRICH_BUILD is true (default), enrichment and profile build
    overlap — Wikipedia I/O on the orchestrator host while LLM profile build uses the GPU lane.
    """
    loop = asyncio.get_event_loop()
    result: dict[str, Any] = {
        "fact_change_log_processed": 0,
        "story_update_queue_processed": 0,
        "entity_profiles_enriched": 0,
        "entity_profiles_built": 0,
        "parallel_enrich_build": False,
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

    parallel = env_bool("ENHANCEMENT_PARALLEL_ENRICH_BUILD", True)
    run_enrich = enrich_limit > 0
    run_build = build_limit > 0

    if parallel and run_enrich and run_build:
        result["parallel_enrich_build"] = True
        logger.info(
            "Enhancement cycle: parallel enrich (limit=%s) + profile build (limit=%s)",
            enrich_limit,
            build_limit,
        )
        enrich_out, build_out = await asyncio.gather(
            _run_enrichment_batch(enrich_limit),
            _run_profile_build_batch(build_limit),
            return_exceptions=True,
        )
        if isinstance(enrich_out, Exception):
            logger.warning("Enhancement cycle (enrichment): %s", enrich_out)
            result["errors"].append(f"enrichment: {enrich_out!s}")
        else:
            result["entity_profiles_enriched"] = enrich_out
        if isinstance(build_out, Exception):
            logger.warning("Enhancement cycle (profile build): %s", build_out)
            result["errors"].append(f"profile_build: {build_out!s}")
        else:
            result["entity_profiles_built"] = build_out
    else:
        if run_enrich:
            try:
                result["entity_profiles_enriched"] = await _run_enrichment_batch(enrich_limit)
            except Exception as e:
                logger.warning("Enhancement cycle (enrichment): %s", e)
                result["errors"].append(f"enrichment: {e!s}")
        if run_build:
            try:
                result["entity_profiles_built"] = await _run_profile_build_batch(build_limit)
            except Exception as e:
                logger.warning("Enhancement cycle (profile build): %s", e)
                result["errors"].append(f"profile_build: {e!s}")

    return result
