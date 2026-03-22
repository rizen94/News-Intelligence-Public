"""
Nightly off-hours pipeline (America/New_York by default).

Unified window [NIGHTLY_PIPELINE_START_HOUR, NIGHTLY_PIPELINE_END_HOUR) default 02:00–05:00:
  1) Drain content_enrichment
  2) Drain context_sync
  3) Drain content_refinement_queue (~70B) with nightly caps — starts as soon as (1) and (2) are
     idle; no fixed 03:00 wait.
When enrichment, context_sync, and refinement queue are all idle, the run exits immediately so
normal automation can proceed (no busy-wait until window end).

Optional: NIGHTLY_INGEST_EXCLUSIVE_AUTOMATION during [NIGHTLY_ENRICHMENT_CONTEXT_*] only (default
02:00–03:00) defers other phases — see NIGHTLY_INGEST_ALLOW.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from shared.domain_registry import get_active_domain_keys

logger = logging.getLogger(__name__)

_nightly_ingest_lock = asyncio.Lock()


def nightly_automation_tz() -> ZoneInfo:
    tz_name = (
        os.environ.get("NIGHTLY_PIPELINE_TZ")
        or os.environ.get("NIGHTLY_INGEST_TZ")
        or os.environ.get("NIGHTLY_GPU_REFINEMENT_TZ")
        or "America/New_York"
    ).strip() or "America/New_York"
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("America/New_York")


def in_nightly_pipeline_window_est() -> bool:
    """Unified nightly catch-up window [start, end) local time (default 02:00–05:00)."""
    zi = nightly_automation_tz()
    start_h = int(os.environ.get("NIGHTLY_PIPELINE_START_HOUR", "2"))
    end_h = int(os.environ.get("NIGHTLY_PIPELINE_END_HOUR", "5"))
    now_local = datetime.now(zi)
    start = now_local.replace(hour=start_h, minute=0, second=0, microsecond=0)
    end = now_local.replace(hour=end_h, minute=0, second=0, microsecond=0)
    return start <= now_local < end


def in_nightly_enrichment_context_window_est() -> bool:
    """
    Sub-window for ingest-focused exclusive automation (default 02:00–03:00).
    Does not limit when enrichment runs inside the unified pipeline — only NIGHTLY_INGEST_EXCLUSIVE.
    """
    zi = nightly_automation_tz()
    start_h = int(os.environ.get("NIGHTLY_ENRICHMENT_CONTEXT_START_HOUR", "2"))
    end_h = int(os.environ.get("NIGHTLY_ENRICHMENT_CONTEXT_END_HOUR", "3"))
    now_local = datetime.now(zi)
    start = now_local.replace(hour=start_h, minute=0, second=0, microsecond=0)
    end = now_local.replace(hour=end_h, minute=0, second=0, microsecond=0)
    return start <= now_local < end


def nightly_ingest_exclusive_automation_enabled() -> bool:
    return os.environ.get("NIGHTLY_INGEST_EXCLUSIVE_AUTOMATION", "0").lower() in (
        "1",
        "true",
        "yes",
    )


def _ingest_allowlist() -> frozenset[str]:
    raw = os.environ.get(
        "NIGHTLY_INGEST_ALLOW",
        "nightly_enrichment_context,health_check,pending_db_flush,collection_cycle",
    )
    return frozenset(x.strip() for x in raw.split(",") if x.strip())


def task_allowed_during_nightly_ingest_exclusive(task_name: str) -> bool:
    return task_name in _ingest_allowlist()


async def run_nightly_unified_pipeline_drain(
    *,
    force_outside_window: bool = False,
) -> dict[str, Any]:
    """
    Within in_nightly_pipeline_window_est: drain enrichment, then context_sync, then GPU refinement.
    Repeats the outer cycle if new work appears (e.g. RSS). Exits immediately when all three idle.

    force_outside_window: set True when AutomationManager runs this phase from a manual Monitor
    request outside local night hours — same drain logic, no clock gate.
    """

    def window_active() -> bool:
        if force_outside_window:
            return True
        return in_nightly_pipeline_window_est()

    stats: dict[str, Any] = {
        "enrichment_batches": 0,
        "enrichment_articles": 0,
        "context_sync_rounds": 0,
        "contexts_created": 0,
        "gpu_batches": 0,
        "gpu_processed": 0,
        "gpu_failed": 0,
        "gpu_by_type": {},
        "gpu_stopped_reason": None,
        "stopped_reason": None,
        "outer_cycles": 0,
        "manual_force": bool(force_outside_window),
    }
    if not window_active():
        stats["stopped_reason"] = "outside_pipeline_window"
        return stats

    try:
        from config.context_centric_config import is_context_centric_task_enabled

        context_sync_enabled = is_context_centric_task_enabled("context_sync")
    except Exception:
        context_sync_enabled = True

    enrich_bs = int(os.environ.get("NIGHTLY_ENRICHMENT_BATCH_SIZE", "80"))
    sync_limit = int(os.environ.get("NIGHTLY_CONTEXT_SYNC_LIMIT_PER_DOMAIN", "200"))
    max_enrich_loops = int(os.environ.get("NIGHTLY_ENRICHMENT_MAX_LOOPS", "800"))
    max_sync_loops = int(os.environ.get("NIGHTLY_CONTEXT_SYNC_MAX_LOOPS", "800"))

    async with _nightly_ingest_lock:
        if not window_active():
            stats["stopped_reason"] = "outside_window_after_lock"
            return stats

        from services.article_content_enrichment_service import enrich_articles_batch
        from services.backlog_metrics import get_all_pending_counts, invalidate_backlog_metrics_cache
        from services.context_processor_service import sync_domain_articles_to_contexts
        from services.content_refinement_queue_service import process_nightly_gpu_refinement_drain

        loop = asyncio.get_event_loop()

        while window_active():
            invalidate_backlog_metrics_cache()
            try:
                pending = get_all_pending_counts()
                pe = int(pending.get("content_enrichment") or 0)
                pc = int(pending.get("context_sync") or 0)
                pr = int(pending.get("content_refinement_queue") or 0)
            except Exception as e:
                logger.warning("nightly unified pipeline: pending counts: %s", e)
                stats["stopped_reason"] = "pending_counts_error"
                break

            if pe == 0 and pc == 0 and pr == 0:
                stats["stopped_reason"] = "all_idle"
                break

            stats["outer_cycles"] += 1

            # --- Enrichment (must complete before sync / GPU in this cycle) ---
            enrich_i = 0
            while enrich_i < max_enrich_loops and window_active():
                invalidate_backlog_metrics_cache()
                try:
                    pe = int(get_all_pending_counts().get("content_enrichment") or 0)
                except Exception:
                    break
                if pe == 0:
                    break
                n = int(
                    await loop.run_in_executor(
                        None, lambda bs=enrich_bs: enrich_articles_batch(batch_size=bs)
                    )
                )
                enrich_i += 1
                stats["enrichment_batches"] += 1
                stats["enrichment_articles"] += n
                if n == 0:
                    break

            if context_sync_enabled:
                sync_i = 0
                while sync_i < max_sync_loops and window_active():
                    invalidate_backlog_metrics_cache()
                    try:
                        pc = int(get_all_pending_counts().get("context_sync") or 0)
                    except Exception:
                        break
                    if pc == 0:
                        break

                    round_total = 0
                    for domain_key in get_active_domain_keys():
                        if not window_active():
                            break
                        lim = sync_limit
                        created = await loop.run_in_executor(
                            None,
                            lambda d=domain_key, l=lim: sync_domain_articles_to_contexts(d, l),
                        )
                        round_total += int(created or 0)

                    sync_i += 1
                    stats["context_sync_rounds"] += 1
                    stats["contexts_created"] += round_total
                    if round_total == 0:
                        break

            if not window_active():
                stats["stopped_reason"] = "window_ended_before_gpu"
                break

            invalidate_backlog_metrics_cache()
            try:
                pr = int(get_all_pending_counts().get("content_refinement_queue") or 0)
            except Exception:
                pr = 0

            if pr > 0:
                gpu_stats = await process_nightly_gpu_refinement_drain(
                    window_active=window_active,
                    use_drain_lock=False,
                )
                stats["gpu_batches"] += int(gpu_stats.get("batches") or 0)
                stats["gpu_processed"] += int(gpu_stats.get("processed") or 0)
                stats["gpu_failed"] += int(gpu_stats.get("failed") or 0)
                stats["gpu_stopped_reason"] = gpu_stats.get("stopped_reason")
                for k, v in (gpu_stats.get("by_type") or {}).items():
                    stats["gpu_by_type"][k] = stats["gpu_by_type"].get(k, 0) + int(v)

        if stats.get("stopped_reason") is None:
            stats["stopped_reason"] = (
                "manual_force_window_loop_end"
                if force_outside_window
                else "window_ended"
            )

    return stats


# Backward compatibility for imports
async def run_nightly_enrichment_context_drain() -> dict[str, Any]:
    """Deprecated alias; use run_nightly_unified_pipeline_drain."""
    return await run_nightly_unified_pipeline_drain()
