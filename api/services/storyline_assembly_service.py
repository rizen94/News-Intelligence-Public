"""
Per-domain storyline assembly — tie proactive detection, AI discovery, and automation together.

Runs when new articles arrive (post-enrichment hook) or when operators/API request assembly
so each domain keeps storylines current as RSS and detection add material.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

from shared.database.connection import get_db_connection_context
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema
from config.runtime import env_bool, env_str

logger = logging.getLogger(__name__)

_VALID_MODES = frozenset({"auto_approve", "suggest_only", "manual"})

# Process-local mirror of DB flat cooldown (epoch seconds).
_flat_domain_cooldown_until_epoch: dict[str, float] = {}
_flat_domain_consecutive: dict[str, int] = {}
_discovery_last_at_epoch: dict[str, float] = {}


def _wm_name(kind: str, domain_key: str) -> str:
    return f"storyline_assembly_{kind}:{domain_key}"


def _wm_get(name: str) -> int | None:
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT last_value FROM intelligence.investigation_watermarks
                    WHERE name = %s
                    """,
                    (name,),
                )
                row = cur.fetchone()
                if not row or row[0] is None:
                    return None
                return int(row[0])
    except Exception as e:
        logger.debug("assembly watermark get %s: %s", name, e)
        return None


def _wm_set(name: str, value: int) -> None:
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO intelligence.investigation_watermarks (name, last_value, updated_at)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (name) DO UPDATE
                    SET last_value = EXCLUDED.last_value, updated_at = NOW()
                    """,
                    (name, int(value)),
                )
            conn.commit()
    except Exception as e:
        logger.debug("assembly watermark set %s: %s", name, e)


def _assembly_flat_cooldown_seconds() -> int:
    """Short base cooldown when residual may still be attachable soon."""
    try:
        return max(0, min(3600, int(env_str("STORYLINE_ASSEMBLY_FLAT_COOLDOWN_SECONDS", "120"))))
    except (TypeError, ValueError):
        return 120


def _assembly_flat_cooldown_max_seconds() -> int:
    """Cap for frequency-window / hard-flat idle (minutes–hours)."""
    try:
        return max(
            300,
            min(86400, int(env_str("STORYLINE_ASSEMBLY_FLAT_COOLDOWN_MAX_SECONDS", "21600"))),
        )
    except (TypeError, ValueError):
        return 21600


def _assembly_discovery_interval_seconds() -> int:
    try:
        return max(
            300,
            min(86400, int(env_str("STORYLINE_ASSEMBLY_DISCOVERY_INTERVAL_SECONDS", "3600"))),
        )
    except (TypeError, ValueError):
        return 3600


def _flat_streak(domain_key: str) -> int:
    if domain_key in _flat_domain_consecutive:
        return int(_flat_domain_consecutive[domain_key])
    stored = _wm_get(_wm_name("flat_streak", domain_key))
    streak = int(stored or 0)
    _flat_domain_consecutive[domain_key] = streak
    return streak


def _set_flat_streak(domain_key: str, streak: int) -> None:
    streak = max(0, int(streak))
    _flat_domain_consecutive[domain_key] = streak
    _wm_set(_wm_name("flat_streak", domain_key), streak)


def seconds_until_auto_approve_due(domain_key: str) -> float | None:
    """
    Seconds until the soonest auto_approve storyline exits its frequency window.
    None = no AA storylines; 0 = at least one is due now.
    """
    schema = resolve_domain_schema(domain_key)
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT COALESCE(
                        MIN(
                            GREATEST(
                                0,
                                EXTRACT(EPOCH FROM (
                                    (last_automation_run
                                     + (COALESCE(automation_frequency_hours, 6) || ' hours')::interval)
                                    - NOW()
                                ))
                            )
                        ),
                        NULL
                    )
                    FROM {schema}.storylines
                    WHERE automation_enabled = true
                      AND COALESCE(automation_mode, '') = 'auto_approve'
                    """
                )
                row = cur.fetchone()
                if not row or row[0] is None:
                    return None
                return float(row[0])
    except Exception as e:
        logger.debug("seconds_until_auto_approve_due %s: %s", domain_key, e)
        return None


def all_auto_approve_inside_frequency(domain_key: str) -> bool:
    """True when AA storylines exist and every one is still inside its frequency window."""
    due = seconds_until_auto_approve_due(domain_key)
    if due is None:
        return False
    return due > 0.0


def _discovery_last_epoch(domain_key: str) -> float:
    if domain_key in _discovery_last_at_epoch:
        return float(_discovery_last_at_epoch[domain_key])
    stored = _wm_get(_wm_name("discovery_at", domain_key))
    epoch = float(stored or 0)
    _discovery_last_at_epoch[domain_key] = epoch
    return epoch


def _mark_discovery_ran(domain_key: str) -> None:
    now = time.time()
    _discovery_last_at_epoch[domain_key] = now
    _wm_set(_wm_name("discovery_at", domain_key), int(now))


def discovery_due(domain_key: str) -> bool:
    last = _discovery_last_epoch(domain_key)
    if last <= 0:
        return True
    return (time.time() - last) >= float(_assembly_discovery_interval_seconds())


def should_run_assembly_discovery(domain_key: str, *, force: bool = False) -> tuple[bool, str]:
    """
    Gate expensive re-clustering on a durable interval.

    Automation may still run when individual auto_approve storylines are due;
    discovery must not re-cluster on every AA wake (linking clears flat streak).
    """
    if force:
        return True, "force"
    if _domain_in_flat_cooldown(domain_key):
        return False, "flat_cooldown"
    last = _discovery_last_epoch(domain_key)
    if last <= 0:
        return True, "due"
    interval = float(_assembly_discovery_interval_seconds())
    elapsed = time.time() - last
    aa_due = seconds_until_auto_approve_due(domain_key)
    wait = interval
    # When every AA is inside its frequency window, stretch wait toward next due.
    if all_auto_approve_inside_frequency(domain_key) and aa_due is not None and aa_due > 0:
        wait = max(interval, min(float(_assembly_flat_cooldown_max_seconds()), float(aa_due)))
    if elapsed < wait:
        reason = (
            "freq_window_interval"
            if all_auto_approve_inside_frequency(domain_key)
            else "discovery_interval"
        )
        return False, reason
    return True, "due"


def _mark_domain_flat_cooldown(domain_key: str, *, idle_seconds: float | None = None) -> None:
    streak = _flat_streak(domain_key) + 1
    _set_flat_streak(domain_key, streak)
    # Frequency-window idle: enter durable cooldown immediately.
    # Otherwise require 2 consecutive flats (avoid one-off empty scans thrashing).
    if idle_seconds is None and streak < 2:
        return
    base = float(_assembly_flat_cooldown_seconds())
    if base <= 0 and idle_seconds is None:
        return
    secs = float(idle_seconds) if idle_seconds is not None else base
    aa_due = seconds_until_auto_approve_due(domain_key)
    if aa_due is not None and aa_due > 0:
        # Frequency window: back off until AA can run again (capped), not 30–120s.
        secs = max(secs, min(float(_assembly_flat_cooldown_max_seconds()), max(900.0, aa_due)))
    else:
        secs = max(secs, base)
    until_epoch = time.time() + secs
    _flat_domain_cooldown_until_epoch[domain_key] = until_epoch
    _wm_set(_wm_name("flat_until", domain_key), int(until_epoch))
    logger.info(
        "storyline assembly flat cooldown domain=%s streak=%s secs=%.0f aa_due=%s",
        domain_key,
        streak,
        secs,
        None if aa_due is None else round(aa_due, 1),
    )


def _clear_domain_flat_cooldown(domain_key: str) -> None:
    _flat_domain_cooldown_until_epoch.pop(domain_key, None)
    _set_flat_streak(domain_key, 0)
    _wm_set(_wm_name("flat_until", domain_key), 0)


def _domain_in_flat_cooldown(domain_key: str) -> bool:
    until = _flat_domain_cooldown_until_epoch.get(domain_key)
    if until is None:
        stored = _wm_get(_wm_name("flat_until", domain_key))
        until = float(stored or 0)
        if until > 0:
            _flat_domain_cooldown_until_epoch[domain_key] = until
    if not until or until <= 0:
        return False
    if time.time() >= until:
        _flat_domain_cooldown_until_epoch.pop(domain_key, None)
        _set_flat_streak(domain_key, 0)
        _wm_set(_wm_name("flat_until", domain_key), 0)
        return False
    return True


def _assembly_run_proactive() -> bool:
    """Proactive keyword pass is on-demand unless outbreak fast-path is enabled."""
    if env_bool("PROACTIVE_OUTBREAK_ONLY", False):
        return True
    return env_bool("STORYLINE_ASSEMBLY_RUN_PROACTIVE", False)


def assembly_lookback_hours(domain_key: str) -> int:
    """Lookback used for unlinked pending and (by default) discovery window."""
    try:
        from services.domain_synthesis_config import get_domain_synthesis_config

        hours = int(
            get_domain_synthesis_config(domain_key).storyline_development.proactive.lookback_hours
        )
        return max(1, hours)
    except Exception:
        return 72


def get_storyline_automation_mode(domain_key: str) -> str:
    """Domain-configured automation_mode for new/promoted storylines."""
    try:
        from services.domain_synthesis_config import get_domain_synthesis_config

        mode = get_domain_synthesis_config(domain_key).storyline_development.automation.default_mode
        if mode in _VALID_MODES:
            return mode
    except Exception as e:
        logger.debug("get_storyline_automation_mode %s: %s", domain_key, e)
    env_mode = (env_str("STORYLINE_DEFAULT_AUTOMATION_MODE") or "auto_approve").strip()
    return env_mode if env_mode in _VALID_MODES else "auto_approve"


def count_unlinked_articles(domain_key: str, *, lookback_hours: int | None = None) -> int:
    """Articles in lookback window with no storyline_articles link."""
    schema = resolve_domain_schema(domain_key)
    if lookback_hours is None:
        lookback_hours = assembly_lookback_hours(domain_key)
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM {schema}.articles a
                    WHERE a.created_at >= NOW() - (%s || ' hours')::interval
                      AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                      AND NOT EXISTS (
                          SELECT 1 FROM {schema}.storyline_articles sa
                          WHERE sa.article_id = a.id
                      )
                    """,
                    (lookback_hours,),
                )
                return int(cur.fetchone()[0] or 0)
    except Exception as e:
        logger.debug("count_unlinked_articles %s: %s", domain_key, e)
        return 0


def count_auto_approve_automation_storylines(domain_key: str) -> int:
    """Storylines that can clear unlinked pending via automation (auto_approve)."""
    schema = resolve_domain_schema(domain_key)
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM {schema}.storylines
                    WHERE automation_enabled = true
                      AND COALESCE(automation_mode, '') = 'auto_approve'
                    """
                )
                return int(cur.fetchone()[0] or 0)
    except Exception as e:
        logger.debug("count_auto_approve_automation_storylines %s: %s", domain_key, e)
        return 0


def storyline_assembly_rows_per_run() -> int:
    """ETA batch size: auto_approve storylines scanned per domain × domains (not suggest_only)."""
    try:
        per_domain = max(1, min(50, int(env_str("STORYLINE_ASSEMBLY_AUTOMATION_LIMIT", "20"))))
    except (TypeError, ValueError):
        per_domain = 20
    try:
        from shared.adaptive_batch_policy import get_persisted_adaptive_batch

        adaptive = get_persisted_adaptive_batch("storyline_assembly")
        if adaptive is not None:
            per_domain = max(1, min(50, int(adaptive)))
    except Exception:
        pass
    total = 0
    for dk in get_pipeline_active_domain_keys():
        n = count_auto_approve_automation_storylines(dk)
        total += min(per_domain, n) if n > 0 else 0
    # Discovery can still link unlinked articles even with zero auto_approve storylines.
    return max(10, total) if total > 0 else max(10, per_domain)


def domain_unlinked_above_threshold(domain_key: str) -> bool:
    """True when unlinked count meets the domain's assembly threshold (inventory gate)."""
    try:
        from services.domain_synthesis_config import get_domain_synthesis_config

        cfg = get_domain_synthesis_config(domain_key)
        if not cfg.storyline_development.automation.assembly_after_enrichment:
            return False
        threshold = cfg.storyline_development.automation.unlinked_article_threshold
    except Exception:
        threshold = int(env_str("STORYLINE_ASSEMBLY_UNLINKED_THRESHOLD", "25"))
    return count_unlinked_articles(domain_key) >= threshold


def domain_has_actionable_assembly_work(domain_key: str) -> bool:
    """
    True when assembly can productively run now (not just residual unlinked inventory).

    Skips domains in durable flat cooldown, and when every auto_approve storyline is
    inside its frequency window *and* discovery is gated by interval.
    """
    if not domain_unlinked_above_threshold(domain_key):
        return False
    if _domain_in_flat_cooldown(domain_key):
        return False
    aa_due = seconds_until_auto_approve_due(domain_key)
    disc_ok, _disc_reason = should_run_assembly_discovery(domain_key)
    # AA due now → actionable even if discovery gated.
    if aa_due is not None and aa_due <= 0:
        return True
    # No AA storylines: discovery is the only linker.
    if aa_due is None:
        return disc_ok
    # All AA inside frequency: only actionable if discovery is due.
    if not disc_ok:
        return False
    return True


def domains_needing_assembly() -> list[str]:
    """Pipeline domains with actionable assembly work (idle-gate / drain SSOT)."""
    return [dk for dk in get_pipeline_active_domain_keys() if domain_has_actionable_assembly_work(dk)]


def count_assembly_actionable_pending() -> int:
    """
    Actionable storyline_assembly queue_depth: unlinked articles only in domains
    that ``domains_needing_assembly()`` / PopOS idle gate would drain.
    """
    return sum(count_unlinked_articles(dk) for dk in domains_needing_assembly())


async def run_storyline_assembly_for_domain(
    domain_key: str,
    *,
    run_proactive: bool | None = None,
    run_discovery: bool = True,
    run_automation: bool = True,
    discovery_hours: int | None = None,
    max_automation_storylines: int | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """
    Full storyline assembly for one domain:
    1. Proactive detection (on-demand / outbreak only — demoted from default schedule)
    2. AI storyline discovery (save new clusters when threshold met)
    3. Storyline automation (attach new articles to enabled storylines)
    """
    if run_proactive is None:
        run_proactive = _assembly_run_proactive()
    schema = resolve_domain_schema(domain_key)
    steps: dict[str, Any] = {}
    assembly_started = datetime.now(timezone.utc)
    lookback = assembly_lookback_hours(domain_key)
    unlinked_before = count_unlinked_articles(domain_key, lookback_hours=lookback)

    if not force and _domain_in_flat_cooldown(domain_key):
        until = _flat_domain_cooldown_until_epoch.get(domain_key) or 0
        rem = max(0.0, float(until) - time.time()) if until else float(_assembly_flat_cooldown_seconds())
        return {
            "success": True,
            "domain": domain_key,
            "skipped": "flat_cooldown",
            "unlinked_before": unlinked_before,
            "unlinked_after": unlinked_before,
            "articles_linked": 0,
            "frequency_skip_only": True,
            "idle_backoff_seconds": round(rem, 1),
            "steps": steps,
        }

    try:
        from services.event_tracking_service import link_tracked_events_to_storylines

        linked_te = link_tracked_events_to_storylines(limit=25)
        if linked_te:
            steps["tracked_event_storyline_links"] = linked_te
    except Exception as e:
        logger.debug("storyline assembly tracked_event link %s: %s", domain_key, e)

    if run_proactive:
        try:
            from domains.storyline_management.services.proactive_detection_service import (
                ProactiveDetectionService,
            )

            svc = ProactiveDetectionService(domain=domain_key)
            result = await svc.detect_emerging_storylines()
            steps["proactive_detection"] = result.get("data") or result
        except Exception as e:
            logger.warning("storyline assembly proactive %s: %s", domain_key, e)
            steps["proactive_detection"] = {"error": str(e)}

    # Align discovery with unlinked pending window unless caller overrides hours.
    # Never leave hours unset for scheduled assembly — that loads all-time up to 10k and O(n²) RAM.
    if discovery_hours is not None and int(discovery_hours) > 0:
        effective_discovery_hours = int(discovery_hours)
    else:
        effective_discovery_hours = lookback

    from services.ai_storyline_discovery import (
        assembly_discovery_article_cap,
        get_discovery_service,
    )

    assembly_article_cap = assembly_discovery_article_cap()

    run_discovery_effective = bool(run_discovery)
    discovery_gate_reason = "caller_disabled"
    if run_discovery:
        run_discovery_effective, discovery_gate_reason = should_run_assembly_discovery(
            domain_key, force=force
        )
        if not run_discovery_effective:
            logger.info(
                "storyline assembly discovery gated domain=%s reason=%s",
                domain_key,
                discovery_gate_reason,
            )

    if run_discovery_effective:
        try:
            loop = asyncio.get_event_loop()
            discovery = await loop.run_in_executor(
                None,
                lambda: get_discovery_service().discover_storylines(
                    domain=domain_key,
                    hours=effective_discovery_hours,
                    save_to_db=True,
                    article_limit=assembly_article_cap,
                ),
            )
            summary = discovery.get("summary") or {}
            steps["storyline_discovery"] = {
                "clusters_found": summary.get("clusters_found", 0),
                "saved_storylines": len(discovery.get("saved_storylines") or []),
                "articles_analyzed": summary.get("articles_analyzed", 0),
                "time_window": summary.get("time_window"),
                "hours_analyzed": summary.get("hours_analyzed"),
                "merged_into_existing": int(summary.get("merged_into_existing") or 0),
                "narrative_merged": int(summary.get("narrative_merged") or 0),
                "coherence_rejected": int(summary.get("coherence_rejected") or 0),
                "articles_attached": int(summary.get("articles_attached") or 0),
            }
            _mark_discovery_ran(domain_key)
        except Exception as e:
            logger.warning("storyline assembly discovery %s: %s", domain_key, e)
            steps["storyline_discovery"] = {"error": str(e)}
    elif run_discovery:
        steps["storyline_discovery"] = {
            "skipped": discovery_gate_reason,
            "articles_attached": 0,
        }

    if run_automation:
        try:
            from services.storyline_automation_service import StorylineAutomationService

            if max_automation_storylines is None:
                try:
                    from services.domain_synthesis_config import get_domain_synthesis_config

                    max_automation_storylines = get_domain_synthesis_config(
                        domain_key
                    ).storyline_development.automation.automation_batch_per_assembly
                except Exception:
                    max_automation_storylines = int(
                        env_str("STORYLINE_ASSEMBLY_AUTOMATION_LIMIT", "20")
                    )
            try:
                from shared.adaptive_batch_policy import resolve_adaptive_batch

                max_automation_storylines, _meta = resolve_adaptive_batch(
                    "storyline_assembly", int(max_automation_storylines)
                )
            except Exception:
                pass

            svc = StorylineAutomationService(domain=domain_key)
            articles_added = 0
            articles_suggested = 0
            articles_matched = 0
            scanned = 0
            auto_approve_scanned = 0
            frequency_skipped = 0
            productive_scans = 0
            # Prefer auto_approve so assembly burns unlinked pending; suggest_only does not.
            with get_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT id, COALESCE(automation_mode, 'manual') AS automation_mode
                        FROM {schema}.storylines
                        WHERE automation_enabled = true
                        ORDER BY
                          CASE WHEN COALESCE(automation_mode, '') = 'auto_approve' THEN 0 ELSE 1 END,
                          last_automation_run ASC NULLS FIRST
                        LIMIT %s
                        """,
                        (max(1, max_automation_storylines),),
                    )
                    storyline_rows = [(int(r[0]), str(r[1] or "manual")) for r in cur.fetchall()]

            # Default false so frequency stamps / cool-downs stop thrash; set env true for catch-up.
            force_refresh = env_bool("STORYLINE_ASSEMBLY_FORCE_REFRESH", False)
            for sid, mode in storyline_rows:
                scanned += 1
                if mode == "auto_approve":
                    auto_approve_scanned += 1
                result = await svc.discover_articles_for_storyline(
                    sid, force_refresh=force_refresh
                )
                if not result.get("success"):
                    continue
                if result.get("skipped_frequency"):
                    frequency_skipped += 1
                    continue
                productive_scans += 1
                found = int(result.get("articles_found") or len(result.get("articles") or []) or 0)
                articles_matched += found
                if (result.get("mode") or mode) == "auto_approve":
                    articles_added += int(result.get("articles_added") or 0)
                else:
                    articles_suggested += int(
                        result.get("articles_suggested")
                        or found
                        or 0
                    )

            frequency_skip_only = (
                scanned > 0
                and frequency_skipped == scanned
                and articles_added == 0
                and articles_suggested == 0
            )
            steps["storyline_automation"] = {
                "storylines_scanned": scanned,
                "auto_approve_scanned": auto_approve_scanned,
                "frequency_skipped": frequency_skipped,
                "productive_scans": productive_scans,
                "frequency_skip_only": frequency_skip_only,
                "articles_matched": articles_matched,
                "articles_added": articles_added,
                "articles_suggested": articles_suggested,
                # Honest link metric — only auto_approve clears unlinked pending.
                "articles_linked": articles_added,
            }
        except Exception as e:
            logger.warning("storyline assembly automation %s: %s", domain_key, e)
            steps["storyline_automation"] = {"error": str(e)}

    unlinked_after = count_unlinked_articles(domain_key, lookback_hours=lookback)
    assembly_finished = datetime.now(timezone.utc)
    automation_step = (
        steps.get("storyline_automation")
        if isinstance(steps.get("storyline_automation"), dict)
        else {}
    )
    discovery_step = (
        steps.get("storyline_discovery")
        if isinstance(steps.get("storyline_discovery"), dict)
        else {}
    )
    scanned = int(automation_step.get("storylines_scanned") or 0)
    discovery_attached = int(discovery_step.get("articles_attached") or 0)
    automation_linked = int(automation_step.get("articles_linked") or 0)
    articles_linked = automation_linked + discovery_attached
    unlinked_cleared = max(0, unlinked_before - unlinked_after)
    frequency_skip_only = bool(automation_step.get("frequency_skip_only"))

    idle_backoff_seconds = 0.0
    if unlinked_cleared == 0 and articles_linked == 0 and not force:
        aa_due = seconds_until_auto_approve_due(domain_key)
        suggested = None
        # Pure freq-skip OR all AA inside window with zero links → long idle immediately.
        if (frequency_skip_only or all_auto_approve_inside_frequency(domain_key)) and (
            aa_due is not None and aa_due > 0
        ):
            suggested = min(float(_assembly_flat_cooldown_max_seconds()), max(900.0, float(aa_due)))
        _mark_domain_flat_cooldown(domain_key, idle_seconds=suggested)
        until = _flat_domain_cooldown_until_epoch.get(domain_key) or 0
        if until > time.time():
            idle_backoff_seconds = max(0.0, until - time.time())
    elif unlinked_cleared > 0 or articles_linked > 0:
        _clear_domain_flat_cooldown(domain_key)

    # Skip Monitor batch history for frequency-skip-only / zero-link idle drains.
    if not frequency_skip_only and articles_linked > 0:
        try:
            from shared.services.phase_batch_run_history import record_phase_batch_completion_async

            await record_phase_batch_completion_async(
                "storyline_assembly",
                assembly_started,
                assembly_finished,
                stats={
                    "round_processed": unlinked_cleared,
                    "processed": unlinked_cleared,
                    "articles_linked": articles_linked,
                    "articles_linked_automation": automation_linked,
                    "articles_attached_discovery": discovery_attached,
                    "storylines_scanned": scanned,
                    "articles_matched": int(automation_step.get("articles_matched") or 0),
                    "articles_suggested": int(automation_step.get("articles_suggested") or 0),
                    "unlinked_before": unlinked_before,
                    "unlinked_after": unlinked_after,
                    "discovery_hours": effective_discovery_hours,
                    "domain": domain_key,
                },
                scheduler_path="storyline_assembly_service",
            )
            if scanned > 0:
                await record_phase_batch_completion_async(
                    "storyline_automation",
                    assembly_started,
                    assembly_finished,
                    stats={
                        "storylines_scanned": scanned,
                        "articles_linked": automation_linked,
                        "articles_suggested": int(automation_step.get("articles_suggested") or 0),
                        "articles_matched": int(automation_step.get("articles_matched") or 0),
                        "round_processed": max(
                            automation_linked, scanned if automation_linked else 0
                        ),
                        "domain": domain_key,
                    },
                    scheduler_path="storyline_assembly_service",
                )
        except Exception as e:
            logger.debug("storyline assembly batch history %s: %s", domain_key, e)
    return {
        "success": True,
        "domain": domain_key,
        "unlinked_before": unlinked_before,
        "unlinked_after": unlinked_after,
        "articles_linked": articles_linked,
        "frequency_skip_only": frequency_skip_only,
        "idle_backoff_seconds": round(idle_backoff_seconds, 1),
        "steps": steps,
    }


async def run_storyline_assembly_all_domains(**kwargs: Any) -> dict[str, Any]:
    """Run assembly for pipeline domains that need it (optional domain parallelism)."""
    try:
        parallel = max(1, min(5, int(env_str("STORYLINE_ASSEMBLY_DOMAIN_PARALLEL", "1"))))
    except (TypeError, ValueError):
        parallel = 1
    force_all = bool(kwargs.pop("force_all_domains", False) or kwargs.get("force"))
    if force_all:
        domains = list(get_pipeline_active_domain_keys())
    else:
        domains = domains_needing_assembly()
        if not domains and env_bool("STORYLINE_ASSEMBLY_RUN_ALL_WHEN_EMPTY_NEEDING", False):
            domains = list(get_pipeline_active_domain_keys())
        # Prefer largest unlinked piles first so catch-up burns medicine/AI before small domains.
        if domains:
            domains = sorted(
                domains,
                key=lambda dk: count_unlinked_articles(dk),
                reverse=True,
            )
    results: dict[str, Any] = {}
    if not domains:
        return {
            "success": True,
            "domains": results,
            "domain_parallel": parallel,
            "articles_linked": 0,
            "frequency_skip_only": True,
            "idle_backoff_seconds": float(_assembly_flat_cooldown_seconds()),
            "skipped": "no_domains_above_unlinked_threshold",
        }
    if parallel <= 1 or len(domains) <= 1:
        for dk in domains:
            results[dk] = await run_storyline_assembly_for_domain(dk, **kwargs)
    else:
        sem = asyncio.Semaphore(parallel)

        async def _one(dk: str) -> tuple[str, dict[str, Any]]:
            async with sem:
                return dk, await run_storyline_assembly_for_domain(dk, **kwargs)

        gathered = await asyncio.gather(*[_one(dk) for dk in domains], return_exceptions=True)
        for item in gathered:
            if isinstance(item, BaseException):
                logger.warning("storyline assembly domain failed: %s", item)
                continue
            dk, payload = item
            results[dk] = payload

    total_linked = 0
    max_idle = 0.0
    freq_only = True
    for res in results.values():
        if not isinstance(res, dict):
            freq_only = False
            continue
        linked = int(res.get("articles_linked") or 0)
        total_linked += linked
        max_idle = max(max_idle, float(res.get("idle_backoff_seconds") or 0))
        if linked > 0:
            freq_only = False
            continue
        if res.get("skipped") == "flat_cooldown" or res.get("frequency_skip_only"):
            continue
        auto = (res.get("steps") or {}).get("storyline_automation") or {}
        scanned = int(auto.get("storylines_scanned") or 0)
        fskip = int(auto.get("frequency_skipped") or 0)
        if scanned > 0 and fskip >= scanned:
            continue
        # Productive empty scan (ran attach logic, linked nothing) — still not "work" for
        # Monitor busy, but not pure frequency-skip; keep freq_only False so callers can tell.
        freq_only = False

    if total_linked > 0:
        freq_only = False

    return {
        "success": True,
        "domains": results,
        "domain_parallel": parallel if parallel > 1 and len(domains) > 1 else 1,
        "articles_linked": total_linked,
        "frequency_skip_only": freq_only and total_linked == 0,
        "idle_backoff_seconds": round(max_idle, 1),
    }
