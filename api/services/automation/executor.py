"""
Phase executors extracted from AutomationManager.

New investigation-related phases live here; legacy phases remain in automation_manager
until incremental extraction completes.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from services.automation.registry import MENTION_RESOLUTION_PHASE

logger = logging.getLogger(__name__)

PhaseExecutor = Callable[[Any], Awaitable[None]]

VAULT_TAG_LINK_SYNC_PHASE = "vault_tag_link_sync"
VAULT_NOTES_WRITER_PHASE = "vault_notes_writer"
VAULT_CLUSTER_HUB_REFRESH_PHASE = "vault_cluster_hub_refresh"
VAULT_MORNING_PRIME_PHASE = "vault_morning_prime"
STORYLINE_HYGIENE_PHASE = "storyline_hygiene"


async def execute_mention_resolution(task: Any) -> None:
    """Drain CEM mention resolver (replaces nri-mention-resolver.timer)."""
    from nri_core.resolver_runner import run_mention_resolution_drain
    from shared.pipeline_batch_drain import phase_run_budget_seconds

    budget = phase_run_budget_seconds(MENTION_RESOLUTION_PHASE, 900)
    loop = asyncio.get_event_loop()
    try:
        stats = await loop.run_in_executor(
            None,
            lambda: run_mention_resolution_drain(budget_seconds=float(budget)),
        )
        logger.info("%s drain: %s", MENTION_RESOLUTION_PHASE, stats)
    except Exception as e:
        logger.warning("%s failed: %s", MENTION_RESOLUTION_PHASE, e)


async def execute_vault_tag_link_sync(task: Any) -> None:
    """Mirror Obsidian tags/wikilinks into Postgres (Obsidian wins)."""
    from services.vault_tag_link_sync_service import sync_vault_tags_and_links

    loop = asyncio.get_event_loop()
    try:
        stats = await loop.run_in_executor(None, sync_vault_tags_and_links)
        logger.info("%s: %s", VAULT_TAG_LINK_SYNC_PHASE, stats)
    except Exception as e:
        logger.warning("%s failed: %s", VAULT_TAG_LINK_SYNC_PHASE, e)


async def execute_vault_notes_writer(task: Any) -> None:
    """Drain vault_update_queue — fence-safe note patches."""
    from services.vault_note_writer_service import run_vault_notes_writer_cycle

    try:
        stats = await run_vault_notes_writer_cycle()
        logger.info("%s: %s", VAULT_NOTES_WRITER_PHASE, stats)
    except Exception as e:
        logger.warning("%s failed: %s", VAULT_NOTES_WRITER_PHASE, e)


async def execute_vault_cluster_hub_refresh(task: Any) -> None:
    """Discover + refresh Obsidian cluster hubs (index only; no bag merge)."""
    from services.vault_cluster_discovery_service import run_cluster_hub_discovery_cycle

    loop = asyncio.get_event_loop()
    try:
        stats = await loop.run_in_executor(None, run_cluster_hub_discovery_cycle)
        logger.info("%s: %s", VAULT_CLUSTER_HUB_REFRESH_PHASE, stats)
    except Exception as e:
        logger.warning("%s failed: %s", VAULT_CLUSTER_HUB_REFRESH_PHASE, e)


async def execute_vault_morning_prime(task: Any) -> None:
    """Batch expansions + daily briefing for reader (cache-only web path)."""
    from services.vault_morning_prime_service import run_vault_morning_prime

    loop = asyncio.get_event_loop()
    try:
        stats = await loop.run_in_executor(None, run_vault_morning_prime)
        logger.info("%s: %s", VAULT_MORNING_PRIME_PHASE, stats)
    except Exception as e:
        logger.warning("%s failed: %s", VAULT_MORNING_PRIME_PHASE, e)


async def execute_storyline_hygiene(task: Any) -> None:
    """Tight bags: core prune + near-dup merge across pipeline domains."""
    from services.storyline_hygiene_service import run_storyline_hygiene_all_domains

    loop = asyncio.get_event_loop()
    try:
        stats = await loop.run_in_executor(None, run_storyline_hygiene_all_domains)
        logger.info("%s: %s", STORYLINE_HYGIENE_PHASE, stats)
    except Exception as e:
        logger.warning("%s failed: %s", STORYLINE_HYGIENE_PHASE, e)


PHASE_EXECUTORS: dict[str, PhaseExecutor] = {
    MENTION_RESOLUTION_PHASE: execute_mention_resolution,
    VAULT_TAG_LINK_SYNC_PHASE: execute_vault_tag_link_sync,
    VAULT_NOTES_WRITER_PHASE: execute_vault_notes_writer,
    VAULT_CLUSTER_HUB_REFRESH_PHASE: execute_vault_cluster_hub_refresh,
    VAULT_MORNING_PRIME_PHASE: execute_vault_morning_prime,
    STORYLINE_HYGIENE_PHASE: execute_storyline_hygiene,
}


async def dispatch_phase(task: Any) -> bool:
    """Run a registered phase executor. Returns True if handled."""
    handler = PHASE_EXECUTORS.get(task.name)
    if handler is None:
        return False
    await handler(task)
    return True
