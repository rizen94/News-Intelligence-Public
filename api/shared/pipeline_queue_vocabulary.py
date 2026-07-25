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
MONITOR_QUEUE_KIND = "monitor_queue_kind"

# Monitor primary-table classification (non-drainable pools stay off the main phase table).
MONITOR_KIND_DRAINABLE = "drainable"
MONITOR_KIND_ROTATING_POOL = "rotating_pool"
MONITOR_KIND_GATED = "gated"

# Phases whose queue_depth is a recurring eligibility pool, not one-shot catch-up work.
ROTATING_POOL_PHASES: frozenset[str] = frozenset(
    {
        "storyline_automation",
        # Generative samplers — queue_depth is eligibility presence, not catch-up inventory.
        "collision_sampling",
    }
)


def monitor_queue_kind(phase_name: str) -> str:
    """Classify phase backlog for Monitor primary-table filtering."""
    name = (phase_name or "").strip()
    if name in ROTATING_POOL_PHASES:
        return MONITOR_KIND_ROTATING_POOL
    return MONITOR_KIND_DRAINABLE


def apply_monitor_queue_kind(row: dict[str, Any], phase_name: str) -> dict[str, Any]:
    """Attach monitor_queue_kind; clear ETA for non-drainable pools."""
    out = dict(row)
    kind = monitor_queue_kind(phase_name)
    out[MONITOR_QUEUE_KIND] = kind
    if kind == MONITOR_KIND_ROTATING_POOL:
        out["batches_to_drain"] = None
        out["estimated_phase_runs"] = None
        out["queue_stale"] = False
    return out

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
ROWS_PER_RUN = "rows_per_run"
MEASURED_ROWS_PER_RUN_24H = "measured_rows_per_run_24h"
CONFIGURED_ROWS_PER_RUN = "configured_rows_per_run"
ROWS_PER_RUN_SOURCE = "rows_per_run_source"
ROWS_PER_RUN_SAMPLE_COUNT = "rows_per_run_sample_count"
ESTIMATED_BATCH_PER_RUN = "estimated_batch_per_run"
ESTIMATED_BATCH_PER_RUN_SOURCE = "estimated_batch_per_run_source"


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
    "monitor_queue_kind": (
        "Monitor display class: drainable (primary table), rotating_pool (hidden from primary; "
        "recurring eligibility pool), or gated (deferred until policy allows)."
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
    "rows_per_run": (
        "Rows consumed per phase run for ETA: measured_rows_per_run_24h when history samples exist, "
        "else configured_rows_per_run from backlog_metrics batch heuristics. "
        "For storyline_review_agent, rows = approve+reject decisions only (skips excluded); "
        "ETA is null (awaiting_decision_yield) until a measured decision sample exists."
    ),
    "measured_rows_per_run_24h": (
        "Average iteration throughput from automation_run_history batch rows in the last 24 hours."
    ),
    "configured_rows_per_run": (
        "Modeled rows per run from persisted adaptive batch (when tuned) or "
        "BATCH_SIZE_PER_TASK / env defaults when no measured samples."
    ),
    "rows_per_run_source": (
        "measured_24h* | adaptive_persisted | config_default | no_row_batch_model | "
        "awaiting_decision_yield — how rows_per_run was chosen."
    ),
    "estimated_batch_per_run": "Alias for rows_per_run (legacy Monitor field name).",
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


_NO_ROW_BATCH_MODEL_PHASES = frozenset(
    {
        "nightly_enrichment_context",
        "collection_cycle",
        "mention_resolution",
        "health_check",
        "rss_feed_health",
        "data_cleanup",
        "cache_cleanup",
        "pending_db_flush",
    }
)


def _configured_rows_per_run_source(phase_name: str) -> str:
    """``adaptive_persisted`` when Monitor batch comes from adaptive_batch state."""
    try:
        from shared.adaptive_batch_policy import (
            adaptive_batch_enabled,
            get_persisted_adaptive_batch,
        )

        if adaptive_batch_enabled() and get_persisted_adaptive_batch(phase_name) is not None:
            return "adaptive_persisted"
    except Exception:
        pass
    return "config_default"


def apply_rows_per_run_fields(
    row: dict[str, Any],
    phase_name: str,
    *,
    configured: int,
    measured: tuple[int, str, int] | None,
    configured_source: str | None = None,
) -> dict[str, Any]:
    """Set canonical rows/run fields on a phase_dashboard row (mutates copy)."""
    out = dict(row)
    cfg = int(configured or 0)
    out[CONFIGURED_ROWS_PER_RUN] = cfg if cfg > 0 else None

    if phase_name in _NO_ROW_BATCH_MODEL_PHASES or cfg <= 0:
        out[MEASURED_ROWS_PER_RUN_24H] = None
        out[ROWS_PER_RUN] = None
        out[ROWS_PER_RUN_SOURCE] = "no_row_batch_model"
        out[ROWS_PER_RUN_SAMPLE_COUNT] = 0
        out[ESTIMATED_BATCH_PER_RUN] = cfg
        out[ESTIMATED_BATCH_PER_RUN_SOURCE] = "no_row_batch_model"
        return out

    # Review agent: ETA must use decided throughput (approve+reject). Skips do not
    # drain the queue — never invent an ETA from configured batch size alone.
    if phase_name == "storyline_review_agent" and not measured:
        out[MEASURED_ROWS_PER_RUN_24H] = None
        out[ROWS_PER_RUN] = None
        out[ROWS_PER_RUN_SOURCE] = "awaiting_decision_yield"
        out[ROWS_PER_RUN_SAMPLE_COUNT] = 0
        out[ESTIMATED_BATCH_PER_RUN] = None
        out[ESTIMATED_BATCH_PER_RUN_SOURCE] = "awaiting_decision_yield"
        out[CONFIGURED_ROWS_PER_RUN] = cfg if cfg > 0 else None
        return out

    if measured:
        avg, source, sample_count = measured
        out[MEASURED_ROWS_PER_RUN_24H] = avg
        out[ROWS_PER_RUN] = avg
        out[ROWS_PER_RUN_SOURCE] = source
        out[ROWS_PER_RUN_SAMPLE_COUNT] = sample_count
        out[ESTIMATED_BATCH_PER_RUN] = avg
        out[ESTIMATED_BATCH_PER_RUN_SOURCE] = source
    else:
        src = (configured_source or "").strip() or _configured_rows_per_run_source(phase_name)
        if src not in ("adaptive_persisted", "config_default"):
            src = "config_default"
        out[MEASURED_ROWS_PER_RUN_24H] = None
        out[ROWS_PER_RUN] = cfg
        out[ROWS_PER_RUN_SOURCE] = src
        out[ROWS_PER_RUN_SAMPLE_COUNT] = 0
        out[ESTIMATED_BATCH_PER_RUN] = cfg
        out[ESTIMATED_BATCH_PER_RUN_SOURCE] = src
    return out
