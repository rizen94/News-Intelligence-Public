"""
Nightly off-hours pipeline (America/New_York by default).

**Unified window** ``[NIGHTLY_PIPELINE_START_HOUR, NIGHTLY_PIPELINE_END_HOUR)`` — default **00:00–07:00** local
(see ``pipeline_schedule_service``; ``PIPELINE_NIGHTLY_*`` aliases the same hours):

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

Optional: ``NIGHTLY_INGEST_EXCLUSIVE_AUTOMATION`` during ``[NIGHTLY_ENRICHMENT_CONTEXT_*]`` defers phases
not listed in ``NIGHTLY_INGEST_ALLOW`` (default includes core ingest plus extraction pipeline phases such as
``claim_extraction``, ``entity_extraction``, ``event_extraction``). Sequential sub-runs from this module
bypass that gate (``nightly_sequential_drain`` metadata).

Temporary catch-up: set ``NIGHTLY_PIPELINE_ALL_DAY=true`` to treat the unified pipeline as **always**
inside the local window (24/7) until unset — same behavior as 02:00–07:00 extended all day
(``nightly_enrichment_context`` every 60s, ``NIGHTLY_PIPELINE_EXCLUSIVE`` applies around the clock).

**Disable unified nightly:** set ``NIGHTLY_UNIFIED_PIPELINE_ENABLED=false`` — the local time window is
never active, ``nightly_enrichment_context`` does not schedule, and the main AutomationManager interval
schedule runs all phases (no exclusive overnight backlog drain). Restart API after changing env.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from shared.domain_registry import get_active_domain_keys
from config.runtime import env_bool, env_float, env_int, env_pop, env_set, env_setdefault, env_str

logger = logging.getLogger(__name__)

_nightly_ingest_lock = asyncio.Lock()
_nightly_kickoff_rss_local_date: str | None = None
_logged_nightly_all_day: bool = False

# Default allowlist when ``NIGHTLY_INGEST_ALLOW`` is unset: ingest + extraction + ML/entity paths that feed them.
_DEFAULT_NIGHTLY_INGEST_ALLOW = (
    "nightly_enrichment_context,content_enrichment,health_check,pending_db_flush,collection_cycle,"
    "claim_extraction,legislative_references,claims_to_facts,claim_subject_gap_refresh,extracted_claims_dedupe,"
    "event_tracking,topic_clustering,quality_scoring,sentiment_analysis,"
    "entity_profile_sync,entity_extraction,ml_processing,metadata_enrichment,"
    "event_extraction,event_deduplication"
)


def nightly_unified_pipeline_enabled() -> bool:
    """When false, the 02:00–07:00 (or ALL_DAY) unified drain never runs; daytime automation handles work."""
    return env_str("NIGHTLY_UNIFIED_PIPELINE_ENABLED", "true").lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _nightly_pipeline_all_day_enabled() -> bool:
    """When true, unified nightly pipeline window is treated as 24h (temporary backlog catch-up)."""
    return env_str("NIGHTLY_PIPELINE_ALL_DAY", "").lower() in (
        "1",
        "true",
        "yes",
    )

DEFAULT_NIGHTLY_SEQUENTIAL_PHASES: tuple[str, ...] = (
    "claim_extraction",
    "claims_to_facts",
    "extracted_claims_dedupe",
    "claim_subject_gap_refresh",
    "entity_profile_sync",
    "entity_extraction",
    "event_tracking",
    "topic_clustering",
    "metadata_enrichment",
    "ml_processing",
    "document_processing",
    "sentiment_analysis",
    "quality_scoring",
    "entity_profile_build",
    "entity_enrichment",
    "storyline_assembly",
    "storyline_automation",
    "fact_verification",
    "event_extraction",
    "event_deduplication",
    "cross_domain_synthesis",
    "entity_dossier_compile",
    "entity_organizer",
    "graph_connection_distillation",
    "story_continuation",
    "watchlist_alerts",
    "mention_resolution",
)


def nightly_automation_tz() -> ZoneInfo:
    tz_name = (
        env_str("NIGHTLY_PIPELINE_TZ")
        or env_str("NIGHTLY_INGEST_TZ")
        or env_str("NIGHTLY_GPU_REFINEMENT_TZ")
        or "America/New_York"
    ).strip() or "America/New_York"
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("America/New_York")


def nightly_sequential_phases() -> list[str]:
    """Phases drained in order during the unified nightly pipeline (env ``NIGHTLY_SEQUENTIAL_PHASES``)."""
    return list(_nightly_sequential_phase_list())


def nightly_pipeline_window_info() -> dict[str, Any]:
    """
    Snapshot for monitoring: schedule, env flags, and next window boundary in nightly automation TZ.
    Assumes ``NIGHTLY_PIPELINE_START_HOUR`` < ``NIGHTLY_PIPELINE_END_HOUR`` (same calendar day).
    """
    from services.pipeline_schedule_service import (
        nightly_end_hour,
        nightly_start_hour,
        pipeline_schedule_info,
        pipeline_schedule_tz,
    )

    zi = pipeline_schedule_tz()
    start_h = nightly_start_hour()
    end_h = nightly_end_hour()
    all_day = _nightly_pipeline_all_day_enabled()
    exclusive = env_str("NIGHTLY_PIPELINE_EXCLUSIVE", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    ingest_exclusive = nightly_ingest_exclusive_automation_enabled()
    enrich_start = int(
        env_str(
            "NIGHTLY_ENRICHMENT_CONTEXT_START_HOUR",
            str(nightly_start_hour()),
        )
    )
    enrich_end = int(
        env_str(
            "NIGHTLY_ENRICHMENT_CONTEXT_END_HOUR",
            str(nightly_end_hour()),
        )
    )
    now_local = datetime.now(zi)
    in_window = in_nightly_pipeline_window_est()
    window_label = f"{start_h:02d}:00–{end_h:02d}:00 ({zi})"

    start_dt = now_local.replace(hour=start_h, minute=0, second=0, microsecond=0)
    end_dt = now_local.replace(hour=end_h, minute=0, second=0, microsecond=0)

    window_ends_local: str | None = None
    next_window_starts_local: str | None = None
    if not all_day:
        if in_window:
            window_ends_local = end_dt.isoformat()
        elif now_local < start_dt:
            next_window_starts_local = start_dt.isoformat()
        else:
            next_window_starts_local = (
                (now_local + timedelta(days=1))
                .replace(hour=start_h, minute=0, second=0, microsecond=0)
                .isoformat()
            )

    schedule = pipeline_schedule_info(now_local=now_local)
    return {
        "timezone": str(zi),
        "unified_pipeline_enabled": nightly_unified_pipeline_enabled(),
        "pipeline_start_hour_local": start_h,
        "pipeline_end_hour_local": end_h,
        "window_label": window_label,
        "all_day_catchup": all_day,
        "exclusive_other_phases": exclusive,
        "nightly_ingest_exclusive_automation": ingest_exclusive,
        "enrichment_context_subwindow_local": f"{enrich_start:02d}:00–{enrich_end:02d}:00",
        "in_unified_window": in_window,
        "window_ends_local": window_ends_local,
        "next_window_starts_local": next_window_starts_local,
        "pipeline_schedule": schedule,
    }


def in_nightly_pipeline_window_est() -> bool:
    """Unified nightly catch-up window [start, end) local time (default 00:00–07:00)."""
    global _logged_nightly_all_day
    if not nightly_unified_pipeline_enabled():
        return False
    if _nightly_pipeline_all_day_enabled():
        if not _logged_nightly_all_day:
            logger.info(
                "NIGHTLY_PIPELINE_ALL_DAY enabled — unified nightly pipeline active 24/7 "
                "(disable after backlog catch-up; restart API/workers after changing .env)"
            )
            _logged_nightly_all_day = True
        return True
    from services.pipeline_schedule_service import in_nightly_heavy_window

    return in_nightly_heavy_window()


def in_nightly_enrichment_context_window_est() -> bool:
    """
    Sub-window for ingest-focused exclusive automation (default 00:00–07:00, aligned with pipeline).
    Does not limit when enrichment runs inside the unified pipeline — only NIGHTLY_INGEST_EXCLUSIVE.
    """
    if not nightly_unified_pipeline_enabled():
        return False
    if _nightly_pipeline_all_day_enabled():
        return True
    from services.pipeline_schedule_service import nightly_end_hour, nightly_start_hour, pipeline_schedule_tz

    zi = pipeline_schedule_tz()
    start_h = int(env_str("NIGHTLY_ENRICHMENT_CONTEXT_START_HOUR", str(nightly_start_hour())))
    end_h = int(env_str("NIGHTLY_ENRICHMENT_CONTEXT_END_HOUR", str(nightly_end_hour())))
    now_local = datetime.now(zi)
    start = now_local.replace(hour=start_h, minute=0, second=0, microsecond=0)
    end = now_local.replace(hour=end_h, minute=0, second=0, microsecond=0)
    return start <= now_local < end


def nightly_ingest_exclusive_automation_enabled() -> bool:
    return env_str("NIGHTLY_INGEST_EXCLUSIVE_AUTOMATION", "0").lower() in (
        "1",
        "true",
        "yes",
    )


def _ingest_allowlist() -> frozenset[str]:
    raw = env_str("NIGHTLY_INGEST_ALLOW", _DEFAULT_NIGHTLY_INGEST_ALLOW)
    return frozenset(x.strip() for x in raw.split(",") if x.strip())


def task_allowed_during_nightly_ingest_exclusive(task_name: str) -> bool:
    return task_name in _ingest_allowlist()


def _phase_loop_cap(phase_name: str, default_max_loops: int) -> int:
    """
    Per-phase loop cap for nightly sequential drain.
    Env format:
    NIGHTLY_SEQUENTIAL_PHASE_LOOP_CAPS="claim_extraction:12,claims_to_facts:10,event_tracking:4"
    """
    raw = env_str(
        "NIGHTLY_SEQUENTIAL_PHASE_LOOP_CAPS",
        (
            "claim_extraction:18,claims_to_facts:24,"
            "extracted_claims_dedupe:8,claim_subject_gap_refresh:6,"
            "entity_extraction:12,event_tracking:10,topic_clustering:10,"
            "entity_profile_sync:6,entity_profile_build:6,"
            "event_extraction:6,proactive_detection:4,storyline_discovery:4"
        ),
    ).strip()
    if not raw:
        return max(1, int(default_max_loops))
    parsed: dict[str, int] = {}
    for piece in raw.split(","):
        token = piece.strip()
        if not token or ":" not in token:
            continue
        name, val = token.split(":", 1)
        name = name.strip()
        if not name:
            continue
        try:
            parsed[name] = int(val.strip())
        except ValueError:
            continue
    cap = parsed.get(phase_name)
    if cap is None:
        return max(1, int(default_max_loops))
    return max(1, min(int(default_max_loops), int(cap)))


def _nightly_sequential_phase_list() -> list[str]:
    raw = env_str("NIGHTLY_SEQUENTIAL_PHASES", "").strip()
    if raw:
        return [x.strip() for x in raw.split(",") if x.strip()]
    try:
        from shared.spine_phase_order import intake_fusion_enabled, spine_phases_for_nightly_prefix

        if intake_fusion_enabled():
            prefix = spine_phases_for_nightly_prefix()
            try:
                from shared.assembly_phase_order import (
                    assembly_pipeline_ordered_active,
                    assembly_phases_for_nightly_suffix,
                )

                if assembly_pipeline_ordered_active():
                    tail = list(assembly_phases_for_nightly_suffix())
                    return list(prefix) + tail
            except Exception:
                pass
            tail = [p for p in DEFAULT_NIGHTLY_SEQUENTIAL_PHASES if p not in prefix]
            return list(prefix) + tail
    except Exception:
        pass
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

    if env_str("NIGHTLY_PIPELINE_KICKOFF_RSS", "1").lower() not in ("1", "true", "yes"):
        return
    if env_str("AUTOMATION_SKIP_RSS_IN_COLLECTION_CYCLE", "").lower() in (
        "1",
        "true",
        "yes",
    ):
        return
    try:
        from shared.pipeline_article_selection import pipeline_backfill_collection_should_pause

        if pipeline_backfill_collection_should_pause():
            return
    except Exception:
        pass
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

    phase_max_loops = _phase_loop_cap(phase_name, max_backlog_loops)
    i = 0
    while i < phase_max_loops and window_active():
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

    enrich_bs = int(env_str("NIGHTLY_ENRICHMENT_BATCH_SIZE", "80"))
    sync_limit = int(env_str("NIGHTLY_CONTEXT_SYNC_LIMIT_PER_DOMAIN", "200"))
    max_enrich_loops = int(env_str("NIGHTLY_ENRICHMENT_MAX_LOOPS", "2000"))
    max_sync_loops = int(env_str("NIGHTLY_CONTEXT_SYNC_MAX_LOOPS", "2000"))
    max_seq_backlog_loops = int(env_str("NIGHTLY_SEQUENTIAL_PHASE_MAX_LOOPS", "2000"))
    sequential_phases = _nightly_sequential_phase_list()

    async with _nightly_ingest_lock:
        if not window_active():
            stats["stopped_reason"] = "outside_window_after_lock"
            return stats

        from shared.content_enrichment_drain import run_content_enrichment_batch
        from services.backlog_metrics import get_all_pending_counts, invalidate_backlog_metrics_cache
        from services.context_processor_service import sync_domain_articles_to_contexts
        from services.content_refinement_queue_service import process_nightly_gpu_refinement_drain

        loop = asyncio.get_event_loop()

        while window_active():
            cycle_t0 = time.monotonic()
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
                enrich_started = datetime.now(timezone.utc)
                n = int(
                    await loop.run_in_executor(
                        None, lambda bs=enrich_bs: run_content_enrichment_batch(batch_size=bs)
                    )
                )
                enrich_finished = datetime.now(timezone.utc)
                enrich_i += 1
                stats["enrichment_batches"] += 1
                stats["enrichment_articles"] += n
                # Attribute productive nightly batches to content_enrichment runs_1h
                # (standalone CE task no-ops during this window).
                if n > 0:
                    try:
                        from shared.services.phase_batch_run_history import (
                            record_phase_batch_completion,
                        )

                        await loop.run_in_executor(
                            None,
                            lambda s=enrich_started, f=enrich_finished, nn=n: record_phase_batch_completion(
                                "content_enrichment",
                                s,
                                f,
                                stats={"round_processed": nn, "processed": nn},
                                scheduler_path="nightly_unified_pipeline",
                            ),
                        )
                    except Exception as e:
                        logger.debug("Nightly enrichment run history: %s", e)
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

    try:
        from services.pipeline_phase_heartbeat_service import record_phase_heartbeat

        record_phase_heartbeat(
            "nightly_enrichment_context",
            scheduler_path="nightly_unified",
            success=stats.get("stopped_reason") not in ("pending_counts_error",),
            items_processed=int(stats.get("contexts_created") or 0)
            + int(stats.get("enrichment_articles") or 0)
            + int(stats.get("sequential_phase_runs") or 0),
            detail={
                "stopped_reason": stats.get("stopped_reason"),
                "outer_cycles": stats.get("outer_cycles"),
                "context_sync_rounds": stats.get("context_sync_rounds"),
                "sequential_by_phase": stats.get("sequential_by_phase"),
            },
        )
    except Exception:
        pass

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
