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
from shared.pipeline_batch_drain import DrainStallTracker, RunBudget
from shared.services.conductor_run_history import run_conductor_phase_with_history

logger = logging.getLogger(__name__)

_ASSEMBLY_SCHEDULER_PATH = "assembly_conductor"
_assembly_phase_lock = asyncio.Lock()

# Narrative / storyline phases defer when spine-adjacent GPU queues are deep.
_ASSEMBLY_DEFER_WHEN_HEAVY: frozenset[str] = frozenset(
    {
        "event_tracking",
        "story_continuation",
        "storyline_assembly",
        "storyline_automation",
        "editorial_room_loop",
    }
)


def _intake_heavy_threshold() -> int:
    try:
        return max(500, int(env_str("ASSEMBLY_DEFER_INTAKE_BACKLOG", "3000")))
    except (TypeError, ValueError):
        return 3000


def _profile_heavy_threshold() -> int:
    try:
        return max(1000, int(env_str("ASSEMBLY_DEFER_PROFILE_BACKLOG", "8000")))
    except (TypeError, ValueError):
        return 8000


def _defer_dossier_profile_first_pass_threshold() -> int:
    try:
        return max(
            500,
            int(env_str("ASSEMBLY_DEFER_DOSSIER_PROFILE_FIRST_PASS", "8000")),
        )
    except (TypeError, ValueError):
        return 8000


def _assembly_phases_eligible() -> tuple[str, ...]:
    phases: list[str] = []
    for p in POST_SPINE_PHASE_ORDER:
        if p == "editorial_room_loop" and not editorial_room_loop_enabled():
            continue
        phases.append(p)
    return tuple(phases)


def _pick_assembly_phase(backlog: dict[str, int]) -> tuple[str | None, dict[str, Any]]:
    """
    Backlog-weighted pick (harmony-style). Skips idle phases; defers narrative work when
    intake/profile queues are deep so GPU time goes to drain, not churn.
    """
    from services.backlog_metrics import get_per_run_batch_size_for_phase

    intake = int(backlog.get("unified_intake_extraction") or 0)
    profile = int(backlog.get("entity_profile_build") or 0)
    heavy = intake >= _intake_heavy_threshold() or profile >= _profile_heavy_threshold()

    meta: dict[str, Any] = {
        "intake_backlog": intake,
        "profile_backlog": profile,
        "heavy_defer": heavy,
        "candidates": [],
    }
    scored: list[tuple[str, float]] = []

    profile_first_pass = profile
    dossier_retry = 0
    try:
        from services.phase_work_queue_metrics import get_phase_work_queue

        profile_first_pass = int(
            get_phase_work_queue("entity_profile_build", pending_total=profile).get(
                "first_pass", profile
            )
            or profile
        )
        dossier_wq = get_phase_work_queue("entity_dossier_compile")
        dossier_retry = int(dossier_wq.get("retry_pending", 0) or 0)
        meta["profile_first_pass"] = profile_first_pass
        meta["dossier_retry_pending"] = dossier_retry
    except Exception:
        pass

    defer_dossier_fp = _defer_dossier_profile_first_pass_threshold()

    for phase in _assembly_phases_eligible():
        work = int(backlog.get(phase) or 0)
        if work <= 0:
            continue
        batch = max(1, int(get_per_run_batch_size_for_phase(phase) or 25))
        score = work / batch
        scored.append((phase, score))
        meta["candidates"].append({"phase": phase, "work": work, "score": round(score, 2)})

    if not scored:
        return None, meta

    scored.sort(key=lambda x: (-x[1], x[0]))
    meta["picked"] = scored[0][0]
    meta["picked_score"] = round(scored[0][1], 2)
    return scored[0][0], meta


def _conductor_idle_seconds() -> float:
    try:
        return max(5.0, float(env_str("ASSEMBLY_CONDUCTOR_IDLE_SECONDS", "5")))
    except (TypeError, ValueError):
        return 5.0


def _assembly_phase_cycle_budget_seconds(phase: str) -> int:
    """
    Wall-clock cap per assembly phase within one conductor cycle.

    Without caps, event_tracking / storyline_assembly can monopolize the loop and
    starve downstream phases (entity_profile_build, dossier compile).
    """
    p = (phase or "").strip().lower().replace("-", "_")
    defaults: dict[str, int] = {
        "graph_connection_distillation": 60,
        "event_tracking": 120,
        "story_continuation": 120,
        "storyline_assembly": 240,
        "storyline_automation": 180,
        "entity_organizer": 120,
        "entity_profile_build": 600,
        "editorial_room_loop": 90,
        "entity_dossier_compile": 600,
    }
    default = defaults.get(p, 120)
    key = f"ASSEMBLY_{p.upper()}_CYCLE_BUDGET_SECONDS"
    try:
        raw = env_str(key, "")
        if raw is not None and str(raw).strip() != "":
            return max(0, int(raw))
    except (TypeError, ValueError):
        pass
    return default


def _event_tracking_batch_limit() -> int:
    batch_max = max(25, min(300, int(env_str("EVENT_TRACKING_ASSEMBLY_BATCH_MAX", "300"))))
    return max(1, min(batch_max, int(env_str("EVENT_TRACKING_ASSEMBLY_BATCH_LIMIT", "25"))))


def _event_tracking_batch_timeout_seconds(batch_limit: int) -> float:
    return max(90.0, float(batch_limit) * 1.5)


def _entity_dossier_compile_limit() -> int:
    default = max(1, min(100, int(env_str("ENTITY_DOSSIER_COMPILE_MAX", "20"))))
    try:
        from shared.adaptive_batch_policy import resolve_adaptive_batch

        tuned, _meta = resolve_adaptive_batch("entity_dossier_compile", default)
        return tuned
    except Exception:
        return default


async def run_assembly_conductor_cycle(
    automation: Any | None = None,
    *,
    budget_seconds: int | None = None,
) -> dict[str, Any]:
    mode = assembly_pipeline_mode()
    stats: dict[str, Any] = {"mode": mode, "steps": {}}

    if mode == "shadow":
        try:
            from services.backlog_metrics import get_all_backlog_counts

            backlog = get_all_backlog_counts()
        except Exception:
            backlog = {}
        phase, pick_meta = _pick_assembly_phase(backlog)
        stats["pick"] = pick_meta
        if phase is None:
            stats["skipped"] = "no_pending_work"
            return stats
        stats["phase"] = phase
        step_stats = await _drain_assembly_phase(
            phase, automation=automation, shadow=True
        )
        stats["steps"][phase] = step_stats
        logger.info("assembly conductor shadow would run %s: %s", phase, step_stats)
        return stats

    if not _assembly_phase_lock.locked():
        async with _assembly_phase_lock:
            return await _run_one_assembly_phase(automation, stats)
    stats["skipped"] = "phase_in_flight"
    logger.debug("assembly conductor skipping cycle — prior phase still running")
    return stats


async def _run_one_assembly_phase(
    automation: Any | None,
    stats: dict[str, Any],
) -> dict[str, Any]:
    try:
        from services.backlog_metrics import get_all_backlog_counts

        backlog = get_all_backlog_counts()
    except Exception:
        backlog = {}

    phase, pick_meta = _pick_assembly_phase(backlog)
    stats["pick"] = pick_meta

    if phase is None:
        stats["skipped"] = "no_pending_work"
        logger.debug("assembly conductor idle — no assembly phase with pending work")
        return stats

    stats["phase"] = phase
    step_stats = await _drain_assembly_phase(phase, automation=automation, shadow=False)
    stats["steps"][phase] = step_stats
    logger.info("assembly conductor finished %s: %s", phase, step_stats)

    try:
        from services.assembly_throughput_metrics import record_assembly_cycle

        record_assembly_cycle(stats)
    except Exception:
        pass
    return stats


async def _drain_assembly_phase(
    phase: str,
    *,
    automation: Any | None,
    shadow: bool,
) -> dict[str, Any]:
    if shadow:
        try:
            from services.backlog_metrics import get_all_backlog_counts
            from shared.pipeline_queue_counts import get_phase_queue_depth

            queue_depth = int(get_phase_queue_depth(phase))
            scheduling_backlog = int(get_all_backlog_counts().get(phase, 0) or 0)
        except Exception:
            queue_depth = -1
            scheduling_backlog = -1
        return {
            "shadow": True,
            "queue_depth": queue_depth,
            "pending": queue_depth,
            "scheduling_backlog": scheduling_backlog,
        }

    runners: dict[str, Any] = {
        "graph_connection_distillation": lambda: _drain_graph_distillation(automation),
        "event_tracking": lambda: _drain_event_tracking(automation),
        "story_continuation": lambda: _run_story_continuation(automation),
        "storyline_assembly": lambda: _run_storyline_assembly(automation),
        "storyline_automation": lambda: _run_storyline_automation(automation),
        "entity_organizer": lambda: _run_entity_resolution_ambiguous(automation),
        "entity_profile_build": lambda: _drain_entity_profile_build(automation),
        "editorial_room_loop": _run_editorial_room_loop,
        "entity_dossier_compile": lambda: _drain_entity_dossier_compile(automation),
    }
    runner = runners.get(phase)
    if runner is None:
        return {"skipped": phase}

    budget_sec = _assembly_phase_cycle_budget_seconds(phase)
    logger.info(
        "assembly conductor draining %s (cycle_budget_seconds=%s)",
        phase,
        budget_sec,
    )

    return await run_conductor_phase_with_history(
        phase,
        runner,
        scheduler_path=_ASSEMBLY_SCHEDULER_PATH,
    )


async def _drain_graph_distillation(automation: Any | None) -> dict[str, Any]:
    from services.graph_connection_processor_service import (
        process_graph_connection_proposals_batch,
    )

    budget_sec = _assembly_phase_cycle_budget_seconds("graph_connection_distillation")
    budget = RunBudget(budget_sec)
    stall = DrainStallTracker()
    total_processed = 0
    rounds = 0
    loop = asyncio.get_event_loop()
    executor = getattr(automation, "executor", None) if automation else None

    while not budget.expired():
        rounds += 1
        try:
            if executor:
                stats = await loop.run_in_executor(
                    executor, process_graph_connection_proposals_batch, None
                )
            else:
                stats = await loop.run_in_executor(
                    None, process_graph_connection_proposals_batch, None
                )
            n = int((stats or {}).get("processed") or (stats or {}).get("distilled") or 0)
        except Exception as e:
            logger.warning("assembly graph_distillation batch: %s", e)
            n = 0
        total_processed += n
        had_pending = n > 0
        if stall.record_round(processed=n, had_pending=had_pending):
            break
        if n == 0:
            break

    return {
        "processed": total_processed,
        "rounds": rounds,
        "round_processed": total_processed,
        "budget_seconds": budget_sec,
    }


async def _drain_event_tracking(automation: Any | None) -> dict[str, Any]:
    from services.event_tracking_service import run_event_tracking_batch

    budget_sec = _assembly_phase_cycle_budget_seconds("event_tracking")
    budget = RunBudget(budget_sec)
    stall = DrainStallTracker()
    total_entries = 0
    rounds = 0
    batch_limit = _event_tracking_batch_limit()
    timeout = _event_tracking_batch_timeout_seconds(batch_limit)

    try:
        from shared.adaptive_batch_policy import resolve_adaptive_batch

        batch_limit, _meta = resolve_adaptive_batch("event_tracking", batch_limit)
        timeout = _event_tracking_batch_timeout_seconds(batch_limit)
    except Exception:
        pass

    while not budget.expired():
        rounds += 1
        n = 0
        try:
            n = int(
                await asyncio.wait_for(
                    run_event_tracking_batch(limit=batch_limit),
                    timeout=timeout,
                )
                or 0
            )
        except asyncio.TimeoutError:
            logger.warning(
                "assembly event_tracking batch timed out (limit=%s, timeout=%s)",
                batch_limit,
                timeout,
            )
        except Exception as e:
            logger.warning("assembly event_tracking batch: %s", e)
        total_entries += n
        had_pending = n > 0
        if stall.record_round(processed=n, had_pending=had_pending):
            break
        if n == 0:
            break

    return {
        "chronicle_entries": total_entries,
        "round_processed": total_entries,
        "processed": total_entries,
        "rounds": rounds,
        "batch_limit": batch_limit,
        "budget_seconds": budget_sec,
    }


async def _drain_entity_profile_build(automation: Any | None) -> dict[str, Any]:
    try:
        from config.context_centric_config import is_context_centric_task_enabled

        if not is_context_centric_task_enabled("entity_profile_build"):
            return {"skipped": "disabled"}
    except Exception:
        pass
    from services.entity_profile_builder_service import (
        drain_entity_profile_build,
        entity_profile_build_batch_limit,
    )

    budget_sec = _assembly_phase_cycle_budget_seconds("entity_profile_build")
    return await drain_entity_profile_build(
        budget_seconds=budget_sec,
        batch_limit=entity_profile_build_batch_limit(),
    )


async def _drain_entity_dossier_compile(automation: Any | None) -> dict[str, Any]:
    try:
        from config.context_centric_config import is_context_centric_task_enabled

        if not is_context_centric_task_enabled("entity_dossier_compile"):
            return {"skipped": "disabled"}
    except Exception:
        pass
    from services.dossier_compiler_service import _run_scheduled_dossier_compiles

    budget_sec = _assembly_phase_cycle_budget_seconds("entity_dossier_compile")
    budget = RunBudget(budget_sec)
    stall = DrainStallTracker()
    total_compiled = 0
    rounds = 0
    limit = _entity_dossier_compile_limit()
    loop = asyncio.get_event_loop()
    executor = getattr(automation, "executor", None) if automation else None

    while not budget.expired():
        rounds += 1
        compiled = int(
            await loop.run_in_executor(
                executor,
                _run_scheduled_dossier_compiles,
                limit,
                None,
            )
            or 0
        )
        total_compiled += compiled
        had_pending = compiled > 0
        if stall.record_round(processed=compiled, had_pending=had_pending):
            break
        if compiled == 0:
            break

    return {
        "compiled": total_compiled,
        "round_processed": total_compiled,
        "processed": total_compiled,
        "rounds": rounds,
        "batch_limit": limit,
        "budget_seconds": budget_sec,
    }


async def _run_story_continuation(automation: Any | None) -> dict[str, Any]:
    if automation and hasattr(automation, "_execute_story_continuation_v5"):
        task = type("Task", (), {"name": "story_continuation", "metadata": {}})()
        await automation._execute_story_continuation_v5(task)
        return {"delegated": True}
    return {"skipped": "no_automation"}


async def _run_storyline_assembly(automation: Any | None) -> dict[str, Any]:
    if automation and hasattr(automation, "_execute_storyline_assembly"):
        task = type("Task", (), {"name": "storyline_assembly", "metadata": {}})()
        await automation._execute_storyline_assembly(task)
        return {"delegated": True}
    if env_str("STORYLINE_ASSEMBLY_RUN_PROACTIVE", "false").lower() in ("0", "false", "no"):
        return {"skipped": "proactive_disabled"}
    from services.storyline_assembly_service import run_storyline_assembly_all_domains

    batch = await run_storyline_assembly_all_domains()
    return {"batch": batch}


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


async def _run_editorial_room_loop() -> dict[str, Any]:
    from services.editorial_room_loop_service import run_editorial_room_loop

    return await run_editorial_room_loop(shadow=False)


def assembly_phase_should_suppress_scheduler(phase_name: str) -> bool:
    """Retired — PipelineController owns assembly phase scheduling."""
    return False
