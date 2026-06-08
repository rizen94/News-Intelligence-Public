"""
Per-domain storyline assembly — tie proactive detection, AI discovery, and automation together.

Runs when new articles arrive (post-enrichment hook) or when operators/API request assembly
so each domain keeps storylines current as RSS and detection add material.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from shared.database.connection import get_db_connection_context
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema

logger = logging.getLogger(__name__)

_VALID_MODES = frozenset({"auto_approve", "suggest_only", "manual"})


def get_storyline_automation_mode(domain_key: str) -> str:
    """Domain-configured automation_mode for new/promoted storylines."""
    try:
        from services.domain_synthesis_config import get_domain_synthesis_config

        mode = get_domain_synthesis_config(domain_key).storyline_development.automation.default_mode
        if mode in _VALID_MODES:
            return mode
    except Exception as e:
        logger.debug("get_storyline_automation_mode %s: %s", domain_key, e)
    env_mode = (os.environ.get("STORYLINE_DEFAULT_AUTOMATION_MODE") or "auto_approve").strip()
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
            threshold = int(os.environ.get("STORYLINE_ASSEMBLY_UNLINKED_THRESHOLD", "25"))
        if count_unlinked_articles(dk) >= threshold:
            out.append(dk)
    return out


async def run_storyline_assembly_for_domain(
    domain_key: str,
    *,
    run_proactive: bool = True,
    run_discovery: bool = True,
    run_automation: bool = True,
    discovery_hours: int | None = None,
    max_automation_storylines: int | None = None,
) -> dict[str, Any]:
    """
    Full storyline assembly for one domain:
    1. Proactive detection (promote emerging clusters)
    2. AI storyline discovery (save new clusters)
    3. Storyline automation (attach new articles to enabled storylines)
    """
    schema = resolve_domain_schema(domain_key)
    steps: dict[str, Any] = {}
    unlinked_before = count_unlinked_articles(domain_key)

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
                        os.environ.get("STORYLINE_ASSEMBLY_AUTOMATION_LIMIT", "20")
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
