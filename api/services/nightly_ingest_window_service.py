"""
Nightly off-hours pipeline (America/New_York by default).

**Unified window** ``[NIGHTLY_PIPELINE_START_HOUR, NIGHTLY_PIPELINE_END_HOUR)`` — default **01:00–07:00** local:

1. **Once per local calendar day** while the window is active: optional kickoff ``collect_rss_feeds`` (see
   ``NIGHTLY_PIPELINE_KICKOFF_RSS``; respects ``AUTOMATION_SKIP_RSS_IN_COLLECTION_CYCLE``).
2. Drain **content_enrichment** (direct batch calls; not the scheduled task).
3. Drain **context_sync** across domains.
4. For each phase in ``NIGHTLY_SEQUENTIAL_PHASES``: drain until **backlog_metrics** reports no pending
   work for that phase (see ``nightly_phase_idle.phase_has_pending_work``). Phases listed in
   ``NIGHTLY_SEQUENTIAL_SINGLE_PASS_PHASES`` run **once** per sweep (best-effort; no backlog spin).
5. Drain **content_refinement_queue** via ``process_nightly_gpu_refinement_drain`` (~70B / RAG jobs).

The outer loop repeats a full sweep until all of (enrichment, context, sequential metrics, refinement queue)
are idle, then exits so normal daytime automation resumes.

**Daytime:** ``AutomationManager`` uses ``NIGHTLY_PIPELINE_EXCLUSIVE`` (default on): only
``nightly_enrichment_context``, ``health_check``, and ``pending_db_flush`` are scheduled during the window.

Optional: ``NIGHTLY_INGEST_EXCLUSIVE_AUTOMATION`` during ``[NIGHTLY_ENRICHMENT_CONTEXT_*]`` defers other
phases — sequential sub-runs from this module bypass that gate (they are orchestrated by
``nightly_enrichment_context``).
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
_nightly_kickoff_rss_local_date: str | None = None

DEFAULT_NIGHTLY_SEQUENTIAL_PHASES: tuple[str, ...] = (
    "metadata_enrichment",
    "entity_profile_sync",
    "ml_processing",
    "entity_extraction",
    "document_processing",
    "sentiment_analysis",
    "quality_scoring",
    "claim_extraction",
    "claims_to_facts",
    "event_tracking",
    "investigation_report_refresh",
    "entity_profile_build",
    "pattern_recognition",
    "pattern_matching",
    "entity_enrichment",
    "topic_clustering",
    "proactive_detection",
    "storyline_discovery",
    "storyline_automation",
    "storyline_processing",
    "storyline_enrichment",
    "rag_enhancement",
    "timeline_generation",
    "fact_verification",
    "event_extraction",
    "event_deduplication",
    "story_continuation",
    "watchlist_alerts",
)


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
    """Unified nightly catch-up window [start, end) local time (default 01:00–07:00)."""
    zi = nightly_automation_tz()
    start_h = int(os.environ.get("NIGHTLY_PIPELINE_START_HOUR", "1"))
    end_h = int(os.environ.get("NIGHTLY_PIPELINE_END_HOUR", "7"))
    now_local = datetime.now(zi)
    start = now_local.replace(hour=start_h, minute=0, second=0, microsecond=0)
    end = now_local.replace(hour=end_h, minute=0, second=0, microsecond=0)
    return start <= now_local < end


def in_nightly_enrichment_context_window_est() -> bool:
    """
    Sub-window for ingest-focused exclusive automation (default 01:00–07:00, aligned with pipeline).
    Does not limit when enrichment runs inside the unified pipeline — only NIGHTLY_INGEST_EXCLUSIVE.
    """
    zi = nightly_automation_tz()
    start_h = int(os.environ.get("NIGHTLY_ENRICHMENT_CONTEXT_START_HOUR", "1"))
    end_h = int(os.environ.get("NIGHTLY_ENRICHMENT_CONTEXT_END_HOUR", "7"))
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
        "nightly_enrichment_context,content_enrichment,health_check,pending_db_flush,collection_cycle",
    )
    return frozenset(x.strip() for x in raw.split(",") if x.strip())


def task_allowed_during_nightly_ingest_exclusive(task_name: str) -> bool:
    return task_name in _ingest_allowlist()


def _nightly_sequential_phase_list() -> list[str]:
    raw = os.environ.get("NIGHTLY_SEQUENTIAL_PHASES", "").strip()
    if raw:
        return [x.strip() for x in raw.split(",") if x.strip()]
    return list(DEFAULT_NIGHTLY_SEQUENTIAL_PHASES)


def _pipeline_fully_idle(
    pending: dict[str, Any],
    *,
    context_sync_enabled: bool,
    sequential_phases: list[str],
) -> bool:
    from services.nightly_phase_idle import sequential_metric_backlog

    if int(pending.get("content_enrichment") or 0) > 0:
        return False
    if context_sync_enabled and int(pending.get("context_sync") or 0) > 0:
        return False
    if int(pending.get("content_refinement_queue") or 0) > 0:
        return False
    return not sequential_metric_backlog(sequential_phases, pending)


async def _maybe_nightly_kickoff_rss(
    loop: asyncio.AbstractEventLoop,
    window_active: Any,
    stats: dict[str, Any],
) -> None:
    """At most one RSS collection per local calendar day during the active window."""
    global _nightly_kickoff_rss_local_date

    if os.environ.get("NIGHTLY_PIPELINE_KICKOFF_RSS", "1").lower() not in ("1", "true", "yes"):
        return
    if os.environ.get("AUTOMATION_SKIP_RSS_IN_COLLECTION_CYCLE", "").lower() in (
        "1",
        "true",
        "yes",
    ):
        return
    zi = nightly_automation_tz()
    today = datetime.now(zi).strftime("%Y-%m-%d")
    if _nightly_kickoff_rss_local_date == today:
        return
    if not window_active():
        return
    try:
        from collectors.rss_collector import collect_rss_feeds

        activity = int(await loop.run_in_executor(None, collect_rss_feeds) or 0)
        _nightly_kickoff_rss_local_date = today
        stats["kickoff_rss_runs"] = stats.get("kickoff_rss_runs", 0) + 1
        stats["kickoff_rss_activity"] = stats.get("kickoff_rss_activity", 0) + activity
        logger.info("Nightly pipeline: kickoff RSS complete (articles touched=%s)", activity)
    except Exception as e:
        logger.warning("Nightly pipeline: kickoff RSS failed: %s", e)


async def _drain_sequential_phase(
    automation: Any,
    phase_name: str,
    window_active: Any,
    max_backlog_loops: int,
    stats: dict[str, Any],
) -> None:
    from services.backlog_metrics import invalidate_backlog_metrics_cache
    from services.nightly_phase_idle import is_single_pass_phase, phase_has_pending_work

    if is_single_pass_phase(phase_name):
        if window_active():
            r = await automation.run_nightly_sequential_phase(phase_name)
            if not r.get("skipped"):
                stats["sequential_phase_runs"] = stats.get("sequential_phase_runs", 0) + 1
                stats.setdefault("sequential_by_phase", {})
                stats["sequential_by_phase"][phase_name] = (
                    stats["sequential_by_phase"].get(phase_name, 0) + 1
                )
        return

    i = 0
    while i < max_backlog_loops and window_active():
        invalidate_backlog_metrics_cache()
        if not phase_has_pending_work(phase_name):
            logger.debug("Nightly sequential %s: no backlog — advancing to next phase", phase_name)
            break
        r = await automation.run_nightly_sequential_phase(phase_name)
        if r.get("skipped"):
            break
        i += 1
        stats["sequential_phase_runs"] = stats.get("sequential_phase_runs", 0) + 1
        stats.setdefault("sequential_by_phase", {})
        stats["sequential_by_phase"][phase_name] = stats["sequential_by_phase"].get(phase_name, 0) + 1

        invalidate_backlog_metrics_cache()
        if not phase_has_pending_work(phase_name):
            logger.debug(
                "Nightly sequential %s: backlog cleared after run — advancing to next phase",
                phase_name,
            )
            break


async def run_nightly_unified_pipeline_drain(
    *,
    automation: Any | None = None,
    force_outside_window: bool = False,
) -> dict[str, Any]:
    """
    Within ``in_nightly_pipeline_window_est`` (or ``force_outside_window``): kickoff RSS (once/day),
    drain enrichment, context_sync, sequential automation phases, then GPU refinement.

    Pass ``automation`` (the running ``AutomationManager``) so sequential phases execute with
    ``nightly_sequential_drain`` metadata. If ``automation`` is omitted, enrichment/context/GPU still run,
    but sequential steps are skipped.
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
        "sequential_phase_runs": 0,
        "sequential_by_phase": {},
        "kickoff_rss_runs": 0,
        "kickoff_rss_activity": 0,
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
    max_enrich_loops = int(os.environ.get("NIGHTLY_ENRICHMENT_MAX_LOOPS", "2000"))
    max_sync_loops = int(os.environ.get("NIGHTLY_CONTEXT_SYNC_MAX_LOOPS", "2000"))
    max_seq_backlog_loops = int(os.environ.get("NIGHTLY_SEQUENTIAL_PHASE_MAX_LOOPS", "2000"))
    sequential_phases = _nightly_sequential_phase_list()

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
            await _maybe_nightly_kickoff_rss(loop, window_active, stats)

            invalidate_backlog_metrics_cache()
            try:
                pending_pre = get_all_pending_counts()
            except Exception as e:
                logger.warning("nightly unified pipeline: pending counts: %s", e)
                stats["stopped_reason"] = "pending_counts_error"
                break

            if _pipeline_fully_idle(
                pending_pre,
                context_sync_enabled=context_sync_enabled,
                sequential_phases=sequential_phases,
            ):
                stats["stopped_reason"] = "all_idle"
                break

            stats["outer_cycles"] += 1

            # --- Enrichment ---
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
                    logger.warning(
                        "Nightly enrichment: batch processed 0 articles while backlog reported %s pending; "
                        "advancing (stale count or fetch starvation)",
                        pe,
                    )
                    break
                invalidate_backlog_metrics_cache()
                try:
                    if int(get_all_pending_counts().get("content_enrichment") or 0) == 0:
                        break
                except Exception:
                    pass

            # --- Context sync ---
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
                        logger.warning(
                            "Nightly context sync: no contexts created this round while backlog reported %s; "
                            "advancing",
                            pc,
                        )
                        break
                    invalidate_backlog_metrics_cache()
                    try:
                        if int(get_all_pending_counts().get("context_sync") or 0) == 0:
                            break
                    except Exception:
                        pass

            # --- Sequential automation phases (one phase at a time, drain backlog) ---
            if automation is not None:
                for phase_name in sequential_phases:
                    if not window_active():
                        break
                    await _drain_sequential_phase(
                        automation,
                        phase_name,
                        window_active,
                        max_seq_backlog_loops,
                        stats,
                    )
            else:
                logger.debug(
                    "Nightly unified pipeline: automation=None, skipping NIGHTLY_SEQUENTIAL_PHASES"
                )

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

            invalidate_backlog_metrics_cache()
            try:
                pending = get_all_pending_counts()
            except Exception as e:
                logger.warning("nightly unified pipeline: pending counts: %s", e)
                stats["stopped_reason"] = "pending_counts_error"
                break

            if _pipeline_fully_idle(pending, context_sync_enabled=context_sync_enabled, sequential_phases=sequential_phases):
                stats["stopped_reason"] = "all_idle"
                break

        if stats.get("stopped_reason") is None:
            stats["stopped_reason"] = (
                "manual_force_window_loop_end"
                if force_outside_window
                else "window_ended"
            )

    return stats


# Backward compatibility for imports
async def run_nightly_enrichment_context_drain(
    *,
    automation: Any | None = None,
) -> dict[str, Any]:
    """Deprecated alias; use run_nightly_unified_pipeline_drain."""
    return await run_nightly_unified_pipeline_drain(
        automation=automation,
        force_outside_window=False,
    )
