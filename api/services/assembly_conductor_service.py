"""
Ordered post-spine assembly conductor — programmatic graph → editorial room loop.

Mirrors spine_pipeline_conductor pattern. ``ASSEMBLY_PIPELINE_MODE=shadow`` logs only.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from config.runtime import env_str
from shared.assembly_phase_order import (
    POST_SPINE_PHASE_ORDER,
    assembly_pipeline_mode,
    assembly_pipeline_ordered_active,
    assembly_pipeline_shadow_active,
    editorial_room_loop_enabled,
)
from shared.pipeline_batch_drain import RunBudget, phase_run_budget_seconds

logger = logging.getLogger(__name__)


def _conductor_idle_seconds() -> float:
    try:
        return max(10.0, float(env_str("ASSEMBLY_CONDUCTOR_IDLE_SECONDS", "45")))
    except (TypeError, ValueError):
        return 45.0


async def run_assembly_conductor_cycle(
    automation: Any | None = None,
    *,
    budget_seconds: int | None = None,
) -> dict[str, Any]:
    mode = assembly_pipeline_mode()
    budget = RunBudget(
        budget_seconds
        if budget_seconds is not None
        else phase_run_budget_seconds("assembly_conductor", 0)
    )
    stats: dict[str, Any] = {"mode": mode, "steps": {}}

    for phase in POST_SPINE_PHASE_ORDER:
        if budget.expired():
            break
        if phase == "editorial_room_loop" and not editorial_room_loop_enabled():
            stats["steps"][phase] = {"skipped": "disabled"}
            continue
        step_stats = await _drain_assembly_phase(
            phase, automation=automation, shadow=mode == "shadow"
        )
        stats["steps"][phase] = step_stats
        if mode == "shadow":
            logger.info("assembly conductor shadow would run %s: %s", phase, step_stats)

    try:
        from services.assembly_throughput_metrics import record_assembly_cycle

        record_assembly_cycle(stats)
    except Exception:
        pass
    return stats


async def assembly_conductor_loop(automation: Any) -> None:
    logger.info("assembly conductor loop started (mode=%s)", assembly_pipeline_mode())
    while getattr(automation, "is_running", False):
        try:
            if assembly_pipeline_ordered_active() or assembly_pipeline_shadow_active():
                await run_assembly_conductor_cycle(automation)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("assembly conductor cycle failed: %s", e)
        await asyncio.sleep(_conductor_idle_seconds())


async def _drain_assembly_phase(
    phase: str,
    *,
    automation: Any | None,
    shadow: bool,
) -> dict[str, Any]:
    if shadow:
        try:
            from services.backlog_metrics import get_all_backlog_counts

            pending = int(get_all_backlog_counts().get(phase, 0) or 0)
        except Exception:
            pending = -1
        return {"shadow": True, "pending": pending}

    if phase == "graph_connection_distillation":
        return await _run_graph_distillation(automation)
    if phase == "event_tracking":
        return await _run_event_tracking_tail(automation)
    if phase == "story_continuation":
        return await _run_story_continuation(automation)
    if phase == "storyline_assembly":
        return await _run_storyline_assembly(automation)
    if phase == "storyline_automation":
        return await _run_storyline_automation(automation)
    if phase == "entity_organizer":
        return await _run_entity_resolution_ambiguous(automation)
    if phase == "editorial_room_loop":
        from services.editorial_room_loop_service import run_editorial_room_loop

        return await run_editorial_room_loop(shadow=False)
    if phase == "entity_dossier_compile":
        return await _run_entity_dossier_compile(automation)
    return {"skipped": phase}


async def _run_graph_distillation(automation: Any | None) -> dict[str, Any]:
    from services.graph_connection_processor_service import (
        process_graph_connection_proposals_batch,
    )

    loop = asyncio.get_event_loop()
    executor = getattr(automation, "executor", None) if automation else None
    if executor:
        stats = await loop.run_in_executor(
            executor, process_graph_connection_proposals_batch, None
        )
    else:
        stats = await loop.run_in_executor(
            None, process_graph_connection_proposals_batch, None
        )
    return dict(stats or {})


async def _run_event_tracking_tail(automation: Any | None) -> dict[str, Any]:
    from services.spine_sql_tail_service import _mark_event_tracking_for_unified_contexts

    loop = asyncio.get_event_loop()
    n = await loop.run_in_executor(None, _mark_event_tracking_for_unified_contexts)
    return {"event_context_markers": n}


async def _run_story_continuation(automation: Any | None) -> dict[str, Any]:
    if automation and hasattr(automation, "_execute_story_continuation_v5"):
        task = type("Task", (), {"name": "story_continuation", "metadata": {}})()
        await automation._execute_story_continuation_v5(task)
        return {"delegated": True}
    return {"skipped": "no_automation"}


async def _run_storyline_assembly(automation: Any | None) -> dict[str, Any]:
    if env_str("STORYLINE_ASSEMBLY_RUN_PROACTIVE", "false").lower() in ("0", "false", "no"):
        from services.storyline_assembly_service import run_storyline_assembly_all_domains

        batch = await run_storyline_assembly_all_domains()
        return {"batch": batch}
    if automation and hasattr(automation, "_execute_storyline_assembly"):
        task = type("Task", (), {"name": "storyline_assembly", "metadata": {}})()
        await automation._execute_storyline_assembly(task)
        return {"delegated": True}
    return {"skipped": "no_automation"}


async def _run_storyline_automation(automation: Any | None) -> dict[str, Any]:
    if automation and hasattr(automation, "_execute_storyline_automation"):
        task = type("Task", (), {"name": "storyline_automation", "metadata": {}})()
        await automation._execute_storyline_automation(task)
        return {"delegated": True}
    return {"skipped": "no_automation"}


async def _run_entity_resolution_ambiguous(automation: Any | None) -> dict[str, Any]:
    from services.entity_resolution_service import run_resolution_ambiguous_batch

    loop = asyncio.get_event_loop()
    executor = getattr(automation, "executor", None) if automation else None
    if executor:
        result = await loop.run_in_executor(executor, run_resolution_ambiguous_batch)
    else:
        result = await loop.run_in_executor(None, run_resolution_ambiguous_batch)
    return dict(result or {})


async def _run_entity_dossier_compile(automation: Any | None) -> dict[str, Any]:
    if automation and hasattr(automation, "_execute_entity_dossier_compile"):
        task = type("Task", (), {"name": "entity_dossier_compile", "metadata": {}})()
        await automation._execute_entity_dossier_compile(task)
        return {"delegated": True}
    return {"skipped": "no_automation"}


def assembly_phase_should_suppress_scheduler(phase_name: str) -> bool:
    """When ordered mode active, individual assembly phases are conductor-owned."""
    if not assembly_pipeline_ordered_active():
        return False
    p = (phase_name or "").strip().lower().replace("-", "_")
    if p in POST_SPINE_PHASE_ORDER:
        return True
    try:
        from shared.assembly_phase_order import post_spine_scheduling_suppressed

        return post_spine_scheduling_suppressed(p)
    except Exception:
        return False
