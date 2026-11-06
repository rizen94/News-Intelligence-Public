"""
Phase executors extracted from AutomationManager.

New investigation-related phases live here; legacy phases remain in automation_manager
until incremental extraction completes.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from services.automation.registry import MENTION_RESOLUTION_PHASE

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PhaseResult:
    """Outcome of a phase execution.

    Success/failure status surfaces through ``dispatch_phase`` so the outer
    ``_execute_task`` handler can retry failed phases instead of silently marking
    them completed.
    """

    success: bool  # True = no exception; False = caught an error
    stats: Any = None
    error: str = ""


PhaseExecutor = Callable[[Any], Awaitable[PhaseResult]]


def _ok(stats: Any) -> PhaseResult:
    return PhaseResult(success=True, stats=stats)


def _fail(error: Exception) -> PhaseResult:
    return PhaseResult(success=False, error=str(error))

VAULT_TAG_LINK_SYNC_PHASE = "vault_tag_link_sync"
VAULT_NOTES_WRITER_PHASE = "vault_notes_writer"
VAULT_CLUSTER_HUB_REFRESH_PHASE = "vault_cluster_hub_refresh"
VAULT_MORNING_PRIME_PHASE = "vault_morning_prime"
STORYLINE_HYGIENE_PHASE = "storyline_hygiene"
RSS_FEED_HEALTH_PHASE = "rss_feed_health"

# ── Legacy enrichment phases (extracted from automation_manager.py) ──────────────

ENTITY_PROFILE_BUILD_PHASE = "entity_profile_build"
ENTITY_DOSSIER_COMPILE_PHASE = "entity_dossier_compile"
STORY_ENHANCEMENT_PHASE = "story_enhancement"
EVENT_EXTRACTION_V5_PHASE = "event_extraction_v5"


async def execute_mention_resolution(task: Any) -> PhaseResult:
    """Drain CEM mention resolver (replaces nri-mention-resolver.timer)."""
    from api.nri_core.resolver_runner import run_mention_resolution_drain
    api.shared.pipeline_batch_drain import phase_run_budget_seconds

    budget = phase_run_budget_seconds(MENTION_RESOLUTION_PHASE, 900)
    loop = asyncio.get_event_loop()
    try:
        stats = await loop.run_in_executor(
            None,
            lambda: run_mention_resolution_drain(budget_seconds=float(budget)),
        )
        logger.info("%s drain: %s", MENTION_RESOLUTION_PHASE, stats)
        return _ok(stats)
    except Exception as e:
        logger.error("%s failed: %s", MENTION_RESOLUTION_PHASE, e)
        return _fail(e)


async def execute_vault_tag_link_sync(task: Any) -> PhaseResult:
    """Mirror Obsidian tags/wikilinks into Postgres (Obsidian wins)."""
    from services.vault_tag_link_sync_service import sync_vault_tags_and_links

    loop = asyncio.get_event_loop()
    try:
        stats = await loop.run_in_executor(None, sync_vault_tags_and_links)
        logger.info("%s: %s", VAULT_TAG_LINK_SYNC_PHASE, stats)
        return _ok(stats)
    except Exception as e:
        logger.error("%s failed: %s", VAULT_TAG_LINK_SYNC_PHASE, e)
        return _fail(e)


async def execute_vault_notes_writer(task: Any) -> PhaseResult:
    """Drain vault_update_queue — fence-safe note patches."""
    from services.vault_note_writer_service import run_vault_notes_writer_cycle

    try:
        stats = await run_vault_notes_writer_cycle()
        logger.info("%s: %s", VAULT_NOTES_WRITER_PHASE, stats)
        return _ok(stats)
    except Exception as e:
        logger.error("%s failed: %s", VAULT_NOTES_WRITER_PHASE, e)
        return _fail(e)


async def execute_vault_cluster_hub_refresh(task: Any) -> PhaseResult:
    """Discover + refresh Obsidian cluster hubs (index only; no bag merge)."""
    from services.vault_cluster_discovery_service import run_cluster_hub_discovery_cycle

    loop = asyncio.get_event_loop()
    try:
        stats = await loop.run_in_executor(None, run_cluster_hub_discovery_cycle)
        logger.info("%s: %s", VAULT_CLUSTER_HUB_REFRESH_PHASE, stats)
        return _ok(stats)
    except Exception as e:
        logger.error("%s failed: %s", VAULT_CLUSTER_HUB_REFRESH_PHASE, e)
        return _fail(e)


async def execute_vault_morning_prime(task: Any) -> PhaseResult:
    """Batch expansions + daily briefing for reader (cache-only web path)."""
    from services.vault_morning_prime_service import run_vault_morning_prime

    loop = asyncio.get_event_loop()
    try:
        stats = await loop.run_in_executor(None, run_vault_morning_prime)
        logger.info("%s: %s", VAULT_MORNING_PRIME_PHASE, stats)
        return _ok(stats)
    except Exception as e:
        logger.error("%s failed: %s", VAULT_MORNING_PRIME_PHASE, e)
        return _fail(e)


async def execute_storyline_hygiene(task: Any) -> PhaseResult:
    """Tight bags: core prune + near-dup merge across pipeline domains."""
    from services.storyline_hygiene_service import run_storyline_hygiene_all_domains

    loop = asyncio.get_event_loop()
    try:
        stats = await loop.run_in_executor(None, run_storyline_hygiene_all_domains)
        logger.info("%s: %s", STORYLINE_HYGIENE_PHASE, stats)
        return _ok(stats)
    except Exception as e:
        logger.error("%s failed: %s", STORYLINE_HYGIENE_PHASE, e)
        return _fail(e)


async def execute_rss_feed_health(task: Any) -> PhaseResult:
    """Weekly quality cull (or legacy warn/silence) for active RSS feeds."""
    from services.rss_feed_health_service import run_feed_health_cycle

    loop = asyncio.get_event_loop()
    try:
        stats = await loop.run_in_executor(None, run_feed_health_cycle)
        logger.info("%s: %s", RSS_FEED_HEALTH_PHASE, stats)
        return _ok(stats)
    except Exception as e:
        logger.error("%s failed: %s", RSS_FEED_HEALTH_PHASE, e)
        return _fail(e)


# ── Legacy enrichment phase executors (PhaseResult-based) ────────────────────────

async def execute_entity_profile_build(task: Any) -> PhaseResult:
    """Build Wikipedia-style sections for entity_profiles from contexts (Phase 1.3)."""
    try:
        from api.config.context_centric_config import is_context_centric_task_enabled

        if not is_context_centric_task_enabled(ENTITY_PROFILE_BUILD_PHASE):
            return _ok({"skipped": "task disabled by context_centric_config"})
    except Exception:
        pass

    try:
        from services.entity_profile_builder_service import run_profile_builder_batch

        updated = await run_profile_builder_batch(limit=25)
        if updated > 0:
            logger.info("%s: %d profiles built", ENTITY_PROFILE_BUILD_PHASE, updated)
        return _ok({"profiles_built": updated})
    except Exception as e:
        logger.error("%s failed: %s", ENTITY_PROFILE_BUILD_PHASE, e)
        return _fail(e)


async def execute_entity_dossier_compile(task: Any) -> PhaseResult:
    """Compile entity dossiers (chronicle_data, relationships, positions) for entities missing or stale (Phase 2.6)."""
    try:
        from api.config.context_centric_config import is_context_centric_task_enabled

        if not is_context_centric_task_enabled(ENTITY_DOSSIER_COMPILE_PHASE):
            return _ok({"skipped": "task disabled by context_centric_config"})
    except Exception:
        pass

    try:
        max_dossiers = int(os.environ.get("ENTITY_DOSSIER_COMPILE_MAX", "20") or "20")
    except ValueError:
        max_dossiers = 20
    max_dossiers = max(1, min(200, max_dossiers))
    try:
        stale_days = int(os.environ.get("ENTITY_DOSSIER_STALE_DAYS", "7") or "7")
    except ValueError:
        stale_days = 7
    stale_days = max(0, min(365, stale_days))

    try:
        from services.dossier_compiler_service import _run_scheduled_dossier_compiles

        loop = asyncio.get_event_loop()
        compiled = await loop.run_in_executor(
            None,
            lambda: _run_scheduled_dossier_compiles(max_dossiers, None, stale_days),
        )
        if compiled > 0:
            logger.info("%s: %d dossiers compiled", ENTITY_DOSSIER_COMPILE_PHASE, compiled)
        return _ok({"dossiers_compiled": compiled})
    except Exception as e:
        logger.error("%s failed: %s", ENTITY_DOSSIER_COMPILE_PHASE, e)
        return _fail(e)


async def execute_story_enhancement(task: Any) -> PhaseResult:
    """Phase 3 RAG: story state triggers; enrich/build only when facts_only policy allows."""
    try:
        from services.enhancement_orchestrator_service import run_enhancement_cycle
        api.shared.pipeline_resource_policy import (
            story_enhancement_facts_only,
            story_enhancement_run_limits,
        )

        facts_only = story_enhancement_facts_only()
        limits = story_enhancement_run_limits(facts_only=facts_only)
        result = await run_enhancement_cycle(
            fact_batch=limits["fact_batch"],
            queue_batch=limits["queue_batch"],
            enrich_limit=limits["enrich_limit"],
            build_limit=limits["build_limit"],
        )
        total = (
            result.get("fact_change_log_processed", 0)
            + result.get("story_update_queue_processed", 0)
            + result.get("entity_profiles_enriched", 0)
            + result.get("entity_profiles_built", 0)
        )
        if total > 0 or result.get("errors"):
            logger.info(
                "Story enhancement cycle: facts_only=%s fact_log=%s queue=%s enriched=%s built=%s",
                facts_only,
                result.get("fact_change_log_processed", 0),
                result.get("story_update_queue_processed", 0),
                result.get("entity_profiles_enriched", 0),
                result.get("entity_profiles_built", 0),
            )
        if result.get("errors"):
            logger.warning("Story enhancement errors: %s", result["errors"])
        return _ok(result)
    except Exception as e:
        logger.error("%s failed: %s", STORY_ENHANCEMENT_PHASE, e)
        return _fail(e)


async def execute_event_extraction_v5(task: Any) -> PhaseResult:
    """v5.0 -- Extract structured events with temporal grounding from domain articles."""
    try:
        from api.config.context_centric_config import is_context_centric_task_enabled
        if not is_context_centric_task_enabled(EVENT_EXTRACTION_V5_PHASE):
            return _ok({"skipped": "task disabled by context_centric_config"})
    except Exception:
        pass

    async def _process_article(
        schema_: str, domain_for_events: str, row,
    ) -> int:
        article_id, content, pub_date_raw, storyline_id = (
            row[0], row[1], row[2], row[3] if len(row) > 3 else None,
        )
        svc = EventExtractionService()
        loop = asyncio.get_event_loop()
        try:
            sem = getattr(svc, "_sema", None)
            if sem is not None:
                async with sem:
                    return await _extract_and_save(schema_, domain_for_events, article_id, content, pub_date_raw, storyline_id, loop)
            else:
                return await _extract_and_save(schema_, domain_for_events, article_id, content, pub_date_raw, storyline_id, loop)
        finally:
            await svc.close()

    async def _extract_and_save(
        schema_: str, domain_for_events: str, article_id, content, pub_date_raw, storyline_id, loop,
    ) -> int:
        try:
            svc = EventExtractionService()
            conn = await loop.run_in_executor(None, get_db_connection)
            if not conn:
                return 0
            cur = conn.cursor()
            events = await svc.extract_events_from_article(
                article_id=article_id, content=content, pub_date=pub_date_raw,
                storyline_id=storyline_id, domain=domain_for_events,
            )
            saved = await svc.save_events(events, conn)
            cur.execute(
                f"""UPDATE {schema_}.articles SET timeline_processed = true, timeline_events_generated = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s""",
                (len(events), article_id),
            )
            conn.commit()
            try:
                api.shared.pipeline_pass_marker import record_article_phase_pass
                record_article_phase_pass(schema_, article_id, "event_extraction", "timeline_saved")
            except Exception:
                pass
            cur.close()
            return saved
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise

    schemas = get_pipeline_schema_names_active()
    if not schemas:
        return _ok({"events_extracted": 0, "articles_scanned": 0})
    total_events = 0
    total_articles = 0
    loop = asyncio.get_event_loop()
    for schema in schemas:
        domain_for_events = (schema.split("_", 1)[1] if "_" in schema else None) or ""
        try:
            conn = await loop.run_in_executor(None, get_db_connection)
            if not conn:
                continue
            cursor = conn.cursor()
            cursor.execute(
                f"""SELECT a.id, a.content, COALESCE(a.published_at, a.created_at), (SELECT DISTINCT s.id FROM {schema}.storyline_associations sa JOIN {schema}.storylines s ON sa.storyline_id = s.id WHERE sa.article_id = a.id) AS storyline_id FROM {schema}.articles a WHERE a.timeline_processed = false AND a.content IS NOT NULL AND LENGTH(a.content) > 100 AND (a.processing_status = %s OR a.enrichment_status IN (%s, %s)) ORDER BY COALESCE(a.updated_at, a.published_at) DESC LIMIT 30""",
                (ML_COMPLETED, ML_COMPLETED, ARTICLE_ENRICHED),
            )
            articles = cursor.fetchall()
            cursor.close()
        except Exception as e:
            logger.error("Event extraction schema query failed for %s: %s", schema, e)
            continue
        finally:
            try:
                conn.close()
            except Exception:
                pass
        total_articles += len(articles)
        if not articles:
            continue
        results = await asyncio.gather(
            *[_process_article(schema, domain_for_events, row) for row in articles], return_exceptions=True,
        )
        for r in results:
            if isinstance(r, int):
                total_events += r
            elif isinstance(r, Exception):
                logger.debug("event_extraction gather: %s", r)
    return _ok({"events_extracted": total_events, "articles_scanned": total_articles})





PHASE_EXECUTORS: dict[str, PhaseExecutor] = {
    MENTION_RESOLUTION_PHASE: execute_mention_resolution,
    VAULT_TAG_LINK_SYNC_PHASE: execute_vault_tag_link_sync,
    VAULT_NOTES_WRITER_PHASE: execute_vault_notes_writer,
    VAULT_CLUSTER_HUB_REFRESH_PHASE: execute_vault_cluster_hub_refresh,
    VAULT_MORNING_PRIME_PHASE: execute_vault_morning_prime,
    STORYLINE_HYGIENE_PHASE: execute_storyline_hygiene,
    RSS_FEED_HEALTH_PHASE: execute_rss_feed_health,
    ENTITY_PROFILE_BUILD_PHASE: execute_entity_profile_build,
    ENTITY_DOSSIER_COMPILE_PHASE: execute_entity_dossier_compile,
    STORY_ENHANCEMENT_PHASE: execute_story_enhancement,
    EVENT_EXTRACTION_V5_PHASE: execute_event_extraction_v5,
}

async def dispatch_phase(task: Any) -> bool:
    """Run a registered phase executor. Returns True if handled (even on failure).

    On failure the executor returns a PhaseResult with *success*=False; this
    function re-raises so the outer ``_execute_task`` handler can retry instead of
    silently marking the task completed.
    """
    handler = PHASE_EXECUTORS.get(task.name)
    if handler is None:
        return False

    result = await handler(task)
    if not result.success:
        logger.error("Phase %s failed: %s", task.name, result.error)
        raise RuntimeError(f"{task.name} failed") from RuntimeError(result.error)

    return True
