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


PHASE_EXECUTORS: dict[str, PhaseExecutor] = {
    MENTION_RESOLUTION_PHASE: execute_mention_resolution,
}


async def dispatch_phase(task: Any) -> bool:
    """Run a registered phase executor. Returns True if handled."""
    handler = PHASE_EXECUTORS.get(task.name)
    if handler is None:
        return False
    await handler(task)
    return True
