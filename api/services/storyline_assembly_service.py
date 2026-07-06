"""
Per-domain storyline assembly — tie proactive detection, AI discovery, and automation together.

Runs when new articles arrive (post-enrichment hook) or when operators/API request assembly
so each domain keeps storylines current as RSS and detection add material.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any

from shared.database.connection import get_db_connection_context
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema
from config.runtime import env_bool, env_float, env_int, env_pop, env_set, env_setdefault, env_str

logger = logging.getLogger(__name__)

_VALID_MODES = frozenset({"auto_approve", "suggest_only", "manual"})


def _assembly_run_proactive() -> bool:
    """Proactive keyword pass is on-demand unless outbreak fast-path is enabled."""
    if env_bool("PROACTIVE_OUTBREAK_ONLY", False):
        return True
    return env_bool("STORYLINE_ASSEMBLY_RUN_PROACTIVE", False)


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
        try:
            from services.domain_synthesis_config import get_domain_synthesis_config

            lookback_hours = get_domain_synthesis_config(
                domain_key
            ).storyline_development.proactive.lookback_hours
        except Exception:
            lookback_hours = 72
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


def domains_needing_assembly() -> list[str]:
    """Pipeline domains with unlinked-article count above per-domain threshold."""
    out: list[str] = []
    for dk in get_pipeline_active_domain_keys():
        try:
            from services.domain_synthesis_config import get_domain_synthesis_config

            cfg = get_domain_synthesis_config(dk)
            if not cfg.storyline_development.automation.assembly_after_enrichment:
                continue
            threshold = cfg.storyline_development.automation.unlinked_article_threshold
        except Exception:
            threshold = int(env_str("STORYLINE_ASSEMBLY_UNLINKED_THRESHOLD", "25"))
        if count_unlinked_articles(dk) >= threshold:
            out.append(dk)
    return out


async def run_storyline_assembly_for_domain(
    domain_key: str,
    *,
    run_proactive: bool | None = None,
    run_discovery: bool = True,
    run_automation: bool = True,
    discovery_hours: int | None = None,
    max_automation_storylines: int | None = None,
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
    unlinked_before = count_unlinked_articles(domain_key)

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

    if run_discovery:
        try:
            from services.ai_storyline_discovery import get_discovery_service

            loop = asyncio.get_event_loop()
            discovery = await loop.run_in_executor(
                None,
                lambda: get_discovery_service().discover_storylines(
                    domain=domain_key,
                    hours=discovery_hours,
                    save_to_db=True,
                ),
            )
            steps["storyline_discovery"] = {
                "clusters_found": (discovery.get("summary") or {}).get("clusters_found", 0),
                "saved_storylines": len(discovery.get("saved_storylines") or []),
            }
        except Exception as e:
            logger.warning("storyline assembly discovery %s: %s", domain_key, e)
            steps["storyline_discovery"] = {"error": str(e)}

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

            svc = StorylineAutomationService(domain=domain_key)
            linked = 0
            scanned = 0
            with get_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT id FROM {schema}.storylines
                        WHERE automation_enabled = true
                        ORDER BY last_automation_run ASC NULLS FIRST
                        LIMIT %s
                        """,
                        (max(1, max_automation_storylines),),
                    )
                    storyline_ids = [int(r[0]) for r in cur.fetchall()]
            for sid in storyline_ids:
                scanned += 1
                result = await svc.discover_articles_for_storyline(sid, force_refresh=False)
                articles = result.get("articles") or []
                linked += len(articles)
            steps["storyline_automation"] = {
                "storylines_scanned": scanned,
                "articles_matched": linked,
            }
        except Exception as e:
            logger.warning("storyline assembly automation %s: %s", domain_key, e)
            steps["storyline_automation"] = {"error": str(e)}

    unlinked_after = count_unlinked_articles(domain_key)
    assembly_finished = datetime.now(timezone.utc)
    automation_step = steps.get("storyline_automation") if isinstance(steps.get("storyline_automation"), dict) else {}
    scanned = int(automation_step.get("storylines_scanned") or 0)
    if scanned > 0 or unlinked_before > unlinked_after:
        try:
            from shared.services.phase_batch_run_history import record_phase_batch_completion_async

            await record_phase_batch_completion_async(
                "storyline_assembly",
                assembly_started,
                assembly_finished,
                stats={
                    "round_processed": max(0, unlinked_before - unlinked_after),
                    "storylines_scanned": scanned,
                    "articles_matched": int(automation_step.get("articles_matched") or 0),
                    "unlinked_before": unlinked_before,
                    "unlinked_after": unlinked_after,
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
                        "articles_matched": int(automation_step.get("articles_matched") or 0),
                        "round_processed": scanned,
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
        "steps": steps,
    }


async def run_storyline_assembly_all_domains(**kwargs: Any) -> dict[str, Any]:
    """Run assembly for every active pipeline domain."""
    results: dict[str, Any] = {}
    for dk in get_pipeline_active_domain_keys():
        results[dk] = await run_storyline_assembly_for_domain(dk, **kwargs)
    return {"success": True, "domains": results}
