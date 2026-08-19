"""
Duration-aware scheduling helpers for AutomationManager.

Aligns enqueue cadence with measured run times and recommends gap-fill work when
workers have idle capacity. Complements workload-driven order (backlog-first) with
harmony between interval metadata, cooldown, and observed duration.

Env:
  AUTOMATION_GAP_FILL_ENABLED — default true
  AUTOMATION_HARMONY_COOLDOWN_FRACTION — fraction of measured avg duration used as
      minimum cooldown when a phase has pending work (default 0.35)
  AUTOMATION_HARMONY_USE_MEASURED_DURATION — default true
"""

from __future__ import annotations

import os
from typing import Any
from config.runtime import env_bool, env_float, env_int, env_pop, env_set, env_setdefault, env_str


def harmony_enabled() -> bool:
    raw = env_str("AUTOMATION_HARMONY_USE_MEASURED_DURATION", "")
    if raw.strip():
        return raw.lower() in ("1", "true", "yes")
    gov = _governance_harmony().get("use_measured_duration")
    if gov is not None:
        return bool(gov)
    return True


def gap_fill_enabled() -> bool:
    raw = env_str("AUTOMATION_GAP_FILL_ENABLED", "")
    if raw.strip():
        return raw.lower() in ("1", "true", "yes")
    gov = _governance_harmony().get("gap_fill_enabled")
    if gov is not None:
        return bool(gov)
    return True


def _governance_harmony() -> dict:
    try:
        from config.orchestrator_governance import get_orchestrator_governance_config

        raw = get_orchestrator_governance_config().get("pipeline_orchestration_harmony") or {}
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _harmony_cooldown_fraction() -> float:
    try:
        raw = env_str("AUTOMATION_HARMONY_COOLDOWN_FRACTION", "")
        if raw.strip():
            return max(0.05, min(1.0, float(raw)))
    except (TypeError, ValueError):
        pass
    try:
        gov = _governance_harmony().get("cooldown_fraction")
        if gov is not None:
            return max(0.05, min(1.0, float(gov)))
    except (TypeError, ValueError):
        pass
    return 0.35


def measured_phase_duration_seconds(
    processing_history: dict[str, list[float]],
    phase_name: str,
    *,
    fallback_estimated: float,
    min_samples: int = 2,
) -> float:
    """Recent average wall time for a phase, or schedule estimate when unknown."""
    history = processing_history.get(phase_name) or []
    if len(history) >= min_samples:
        recent = history[-5:]
        return max(30.0, sum(recent) / len(recent))
    return max(30.0, float(fallback_estimated or 60))


def harmonized_workload_cooldown_seconds(
    phase_name: str,
    *,
    base_cooldown: int,
    processing_history: dict[str, list[float]],
    estimated_duration: float,
    pending: int,
    running_same_phase: int,
    per_phase_cap: int,
) -> int:
    """
    Cooldown before re-enqueueing a phase that still has pending work.

    When a phase typically runs for hours, a 10s cooldown is meaningless and causes
    noisy scheduler ticks. Use a fraction of measured duration, capped so backlog
    phases can still drain via continuous re-queue after completion.
    """
    if not harmony_enabled():
        return base_cooldown

    avg = measured_phase_duration_seconds(
        processing_history,
        phase_name,
        fallback_estimated=estimated_duration,
    )

    # While at concurrent cap, outer gate blocks enqueue; keep cooldown low for after completion.
    if per_phase_cap > 0 and running_same_phase >= per_phase_cap:
        return base_cooldown

    duration_based = int(max(base_cooldown, avg * _harmony_cooldown_fraction()))

    # Large backlog: allow somewhat faster re-enqueue after a run finishes.
    try:
        from services.backlog_metrics import BATCH_SIZE_PER_TASK

        batch = max(1, int(BATCH_SIZE_PER_TASK.get(phase_name, 30) or 30))
    except Exception:
        batch = 30
    if pending >= batch * 4:
        duration_based = max(base_cooldown, int(duration_based * 0.5))
    elif pending >= batch * 2:
        duration_based = max(base_cooldown, int(duration_based * 0.7))

    return max(base_cooldown, duration_based)


def gap_fill_phase_candidates(
    *,
    schedules: dict[str, dict[str, Any]],
    pending_counts: dict[str, int],
    backlog_counts: dict[str, int],
    running_by_phase: dict[str, int],
    queued_by_phase: dict[str, int],
    per_phase_cap_fn: Any,
    batch_phases_continuous: frozenset[str],
) -> list[tuple[str, float]]:
    """
    Rank phases that have work, are not saturated (running+queued), for idle-worker fill.

    Returns list of (phase_name, score) descending by urgency.
    """
    if not gap_fill_enabled():
        return []

    out: list[tuple[str, float]] = []
    for phase_name, schedule in schedules.items():
        if not schedule.get("enabled", True):
            continue
        pending = int(pending_counts.get(phase_name, 0) or 0)
        backlog = int(backlog_counts.get(phase_name, 0) or 0)
        work = max(pending, backlog)
        if work <= 0 and phase_name not in batch_phases_continuous:
            continue
        if work <= 0:
            continue

        cap = int(per_phase_cap_fn(phase_name) or 0)
        running = int(running_by_phase.get(phase_name, 0) or 0)
        queued = int(queued_by_phase.get(phase_name, 0) or 0)
        if cap > 0 and (running + queued) >= cap:
            continue

        try:
            from services.backlog_metrics import BATCH_SIZE_PER_TASK

            batch = max(1, int(BATCH_SIZE_PER_TASK.get(phase_name, 30) or 30))
        except Exception:
            batch = 30

        batches = work / batch
        # Prefer phases with more batches waiting and not currently executing.
        idle_bonus = 2.0 if running == 0 else 0.5
        score = batches * idle_bonus
        out.append((phase_name, score))

    out.sort(key=lambda x: (-x[1], x[0]))
    return out


def effective_schedule_interval_seconds(
    phase_name: str,
    base_interval: int,
    *,
    processing_history: dict[str, list[float]],
    estimated_duration: float,
) -> int:
    """
    Display/planning helper: interval should not be shorter than typical run duration.
    """
    if not harmony_enabled():
        return base_interval
    avg = measured_phase_duration_seconds(
        processing_history,
        phase_name,
        fallback_estimated=estimated_duration,
    )
    return max(int(base_interval), int(avg * 0.9))
