"""
Backlog-aware cooldown for workload-driven automation phases.

When enabled (default), selected phases enqueue more often when pending work is large
relative to one batch, and less often when the queue is shallow — targeting backfill-style
work (timelines, events, discovery, PDFs) without always-on churn.

Env:
  WORKLOAD_BALANCER_ENABLED — default true (set false to restore fixed cooldown).
  WORKLOAD_BALANCER_PHASES — optional comma-separated phase names overriding the default set.
"""

from __future__ import annotations

import os

# Phases where variable cooldown helps (backfill / heavy optional paths).
_DEFAULT_BALANCER_PHASES: frozenset[str] = frozenset(
    {
        "document_processing",
        "timeline_generation",
        "event_extraction",
        "storyline_discovery",
        "rag_enhancement",
        "topic_clustering",
        "event_deduplication",
        "narrative_thread_build",
        "storyline_processing",
        "proactive_detection",
    }
)


def workload_balancer_enabled() -> bool:
    return os.environ.get("WORKLOAD_BALANCER_ENABLED", "true").lower() in (
        "1",
        "true",
        "yes",
    )


def workload_balancer_phase_names() -> frozenset[str]:
    raw = os.environ.get("WORKLOAD_BALANCER_PHASES", "").strip()
    if raw:
        return frozenset(x.strip() for x in raw.split(",") if x.strip())
    return _DEFAULT_BALANCER_PHASES


def effective_workload_cooldown_seconds(
    task_name: str,
    pending_raw: int,
    *,
    base_cooldown: int,
    batch_size: int,
) -> int:
    """
    Cooldown before the same phase may enqueue again when workload-driven and has_work.

    - Large pending vs batch → shorter cooldown (drain faster).
    - Small non-zero pending → moderately shorter.
    - Otherwise → base_cooldown.
    """
    if not workload_balancer_enabled() or task_name not in workload_balancer_phase_names():
        return base_cooldown
    pending = max(0, int(pending_raw or 0))
    batch = max(1, int(batch_size or 10))
    if pending >= batch * 4:
        return max(3, base_cooldown // 3)
    if pending >= batch * 2:
        return max(4, (2 * base_cooldown) // 3)
    if pending >= batch:
        return max(5, base_cooldown // 2)
    if pending > 0:
        return max(6, (3 * base_cooldown) // 4)
    return base_cooldown


def sample_effective_cooldowns(
    pending_counts: dict[str, int],
    *,
    base_cooldown: int,
) -> dict[str, int]:
    """For monitoring: map phase name → effective cooldown given current pending."""
    try:
        from services.backlog_metrics import BATCH_SIZE_PER_TASK
    except Exception:
        BATCH_SIZE_PER_TASK = {}
    out: dict[str, int] = {}
    for name in sorted(workload_balancer_phase_names()):
        p = int(pending_counts.get(name, 0) or 0)
        bs = int(BATCH_SIZE_PER_TASK.get(name, 30) or 30)
        out[name] = effective_workload_cooldown_seconds(
            name, p, base_cooldown=base_cooldown, batch_size=bs
        )
    return out
