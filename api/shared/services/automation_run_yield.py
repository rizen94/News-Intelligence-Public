"""Normalize per-phase yield fields for infrastructure.automation_run_history.metadata."""

from __future__ import annotations

from typing import Any

_YIELD_KEYS: tuple[str, ...] = (
    "articles_enriched",
    "contexts_created",
    "claims_inserted",
    "rows_processed",
    "contexts_processed",
    "profiles_updated",
    "profiles_attempted",
    "profiles_skipped_unchanged",
    "batch_updated",
    "batch_attempted",
    "unlinked_before",
    "unlinked_after",
    "linkage_rate_before",
    "refinement_processed",
    "refinement_failed",
    "storylines_saved",
    "consolidation_merges",
    "discovery_deferred_sprawl",
)


def build_automation_run_yield_metadata(task_metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    """Collect yield counters from task.metadata for history rows and Grafana readers."""
    meta = task_metadata or {}
    out: dict[str, Any] = {}
    for key in _YIELD_KEYS:
        if key not in meta:
            continue
        val = meta[key]
        if val is None:
            continue
        out[key] = val
    nested = meta.get("run_yield")
    if isinstance(nested, dict):
        for key, val in nested.items():
            if val is not None:
                out[key] = val
    if meta.get("batch") is True:
        out["batch"] = True
    if meta.get("status"):
        out["status"] = meta.get("status")
    return out or None