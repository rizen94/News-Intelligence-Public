"""
Pipeline queue vocabulary — SSOT for backlog / queue-depth terminology.

Parallel to monitor_run_vocabulary (run history). See docs/monitor_alignment/CROSSWALK.md.
"""

from __future__ import annotations

from typing import Any, TypedDict

# Canonical field names (API / snapshot keys)
QUEUE_DEPTH = "queue_depth"
SCHEDULING_BACKLOG = "scheduling_backlog"
ACTIONABLE_UNIFIED_INTAKE = "actionable_unified_intake"
INVENTORY_MISSING_PASS = "inventory_missing_pass"
LEGACY_BACKFILL_ELIGIBLE = "legacy_backfill_eligible"
FIRST_PASS_DEPTH = "first_pass_depth"
RETRY_DEPTH = "retry_depth"
SPINE_QUEUE_DEPTH = "spine_queue_depth"
IN_MEMORY_QUEUE_DEPTH = "in_memory_queue_depth"

# Legacy aliases (keep during migration)
PENDING_RECORDS = "pending_records"
PENDING_COUNTS = "pending_counts"
TOTAL_MISSING_UNIFIED_PASS = "total_missing_unified_pass"
BATCHES_TO_DRAIN = "batches_to_drain"
ESTIMATED_PHASE_RUNS = "estimated_phase_runs"
PASS_RATE_24H = "pass_rate_24h"
RUN_SUCCESS_RATE_24H = "run_success_rate_24h"
PENDING_FIRST_PASS = "pending_first_pass"
PENDING_RETRY = "pending_retry"
COMBINED_QUEUE_DEPTH = "combined_queue_depth"


class UnifiedIntakeBreakdown(TypedDict):
    actionable_unified_intake: int
    inventory_missing_pass: int
    legacy_backfill_eligible: int
    spine_queue_depth: int


class PhaseQueueSnapshot(TypedDict, total=False):
    queue_depth: int
    scheduling_backlog: int
    first_pass_depth: int
    retry_depth: int
    spine_queue_depth: int


REPORTING_DEFINITIONS: dict[str, str] = {
    "queue_depth": (
        "Per-phase actionable work remaining: rows matching the same eligibility SQL "
        "automation uses for that phase (not raw table sizes or spine queue table depth)."
    ),
    "scheduling_backlog": (
        "Excess queue depth beyond one automation tick: max(queue_depth − estimated_batch_per_run, 0). "
        "Used for scheduler priority and interval shortening."
    ),
    "actionable_unified_intake": (
        "Articles still needing unified LLM extraction. Equals queue_depth for "
        "unified_intake_extraction when legacy-aware backlog is enabled."
    ),
    "inventory_missing_pass": (
        "Broader inventory: eligible articles missing a unified_intake_extraction pass marker, "
        "including legacy-complete rows that need marker-only backfill (no GPU)."
    ),
    "legacy_backfill_eligible": (
        "Subset of inventory_missing_pass: legacy per-phase outputs present; unified pass marker "
        "can be backfilled without LLM."
    ),
    "spine_queue_depth": (
        "Operational spine work-queue table depth (unified_intake_queue / content_enrichment_queue). "
        "Informational only — may exceed queue_depth when queue rows are stale or non-actionable."
    ),
    "in_memory_queue_depth": (
        "AutomationManager in-memory task queues (requested + scheduled). Not DB queue_depth."
    ),
    "first_pass_depth": (
        "Items never successfully cleared for this phase (no last_pass_at / never compiled)."
    ),
    "retry_depth": (
        "Items attempted but still needing another pass (failed or legacy false-clear outcomes)."
    ),
    "pending_records": "Alias for queue_depth (legacy Monitor field name).",
    "batches_to_drain": "Alias for estimated_phase_runs.",
    "pass_rate_24h": "Alias for run_success_rate_24h (run history success proportion, not pipeline pass).",
    "urgent_queue_depth": (
        "Realtime urgent-event in-memory queue depth (GET /api/realtime/streaming_status). "
        "Not pipeline queue_depth — unrelated to automation phase backlog."
    ),
}


def add_automation_status_aliases(payload: dict[str, Any]) -> dict[str, Any]:
    """Add canonical queue vocabulary keys to automation get_status() payload (mutates copy)."""
    out = dict(payload)
    if PENDING_COUNTS in out and "queue_depths" not in out:
        out["queue_depths"] = dict(out[PENDING_COUNTS])
    if "backlog_counts" in out and SCHEDULING_BACKLOG not in out:
        out[SCHEDULING_BACKLOG] = dict(out["backlog_counts"])
    if COMBINED_QUEUE_DEPTH in out and IN_MEMORY_QUEUE_DEPTH not in out:
        out[IN_MEMORY_QUEUE_DEPTH] = out[COMBINED_QUEUE_DEPTH]
    ctrl = out.get("controller_state")
    if isinstance(ctrl, dict) and "queue_depth" in ctrl:
        ctrl = dict(ctrl)
        if IN_MEMORY_QUEUE_DEPTH not in ctrl:
            ctrl[IN_MEMORY_QUEUE_DEPTH] = ctrl["queue_depth"]
        out["controller_state"] = ctrl
    return out


def unified_intake_breakdown_from_stats(stats: dict[str, Any], *, spine_queue: int = 0) -> UnifiedIntakeBreakdown:
    """Normalize unified intake stats dict to canonical vocabulary keys."""
    return UnifiedIntakeBreakdown(
        actionable_unified_intake=int(stats.get("actionable_unified_intake") or 0),
        inventory_missing_pass=int(stats.get("total_missing_unified_pass") or 0),
        legacy_backfill_eligible=int(stats.get("legacy_backfill_eligible") or 0),
        spine_queue_depth=int(spine_queue or 0),
    )


def add_queue_depth_aliases(row: dict[str, Any]) -> dict[str, Any]:
    """Add canonical queue_depth aliases to a phase_dashboard row (mutates copy)."""
    out = dict(row)
    if "pending_records" in out and QUEUE_DEPTH not in out:
        out[QUEUE_DEPTH] = out["pending_records"]
    if "batches_to_drain" in out and ESTIMATED_PHASE_RUNS not in out:
        out[ESTIMATED_PHASE_RUNS] = out["batches_to_drain"]
    if "pass_rate_24h" in out and RUN_SUCCESS_RATE_24H not in out:
        out[RUN_SUCCESS_RATE_24H] = out["pass_rate_24h"]
    if "pending_first_pass" in out and FIRST_PASS_DEPTH not in out:
        out[FIRST_PASS_DEPTH] = out["pending_first_pass"]
    if "pending_retry" in out and RETRY_DEPTH not in out:
        out[RETRY_DEPTH] = out["pending_retry"]
    return out
