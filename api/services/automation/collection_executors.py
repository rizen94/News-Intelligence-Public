"""Data collection, enrichment & context-sourcing executors.

Migrated from ``api/services/automation_manager.py`` ~L4400-5247.
Each exported function accepts a single :class:`Task` instance and handles its
own lazy imports to avoid circular dependencies with the monolith.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers (no-lock mutual exclusion for enrichment)
# ---------------------------------------------------------------------------

_enrichment_lock: asyncio.Lock | None = None

def _get_enrichment_lock() -> asyncio.Lock:  # type: ignore[no-untyped-def]
    global _enrichment_lock
    if _enrichment_lock is None:
        _enrichment_lock = asyncio.Lock()
    return _enrichment_lock


# ---------------------------------------------------------------------------
# Phase: content enrichment
# ---------------------------------------------------------------------------

async def execute_content_enrichment(task) -> None:  # type: ignore[name-defined]
    """Fetch full article text with trafilatura for articles with short content."""
    from services.nightly_ingest_window_service import in_nightly_pipeline_window_est
    from services.article_content_enrichment_service import enrich_articles_batch

    meta = task.metadata or {}
    # Nightly unified drain owns enrichment in-window — but PipelineController /
    # Monitor operator requests must still run.
    if (
        in_nightly_pipeline_window_est()
        and not meta.get("nightly_sequential_drain")
        and not meta.get("controller")
        and not meta.get("operator_request")
        and not meta.get("requested_activity_id")
    ):
        logger.debug("Content enrichment: nightly pipeline window — handled by nightly_enrichment_context")
        return

    bs = max(20, int(os.environ.get("CONTENT_ENRICHMENT_BATCH_SIZE", "120") or "120"))
    lock = _get_enrichment_lock()
    async with lock:
        enriched = await asyncio.get_event_loop().run_in_executor(None, lambda: enrich_articles_batch(batch_size=bs))
    if enriched and enriched > 0:
        await _maybe_request_storyline_assembly_after_enrichment()


async def _maybe_request_storyline_assembly_after_enrichment() -> None:  # type: ignore[no-untyped-def]
    """Queue per-domain storyline assembly when unlinked article backlog exceeds threshold."""
    try:
        from services.storyline_assembly_service import domains_needing_assembly
        for domain_key in domains_needing_assembly():
            _request_phase("storyline_assembly", domain=domain_key)  # type: ignore[name-defined]
    except Exception as e:
        logger.debug("Storyline assembly after enrichment: %s", e)


# ---------------------------------------------------------------------------
# Phase: context sync (1.2) / entity profile sync (1.3)
# ---------------------------------------------------------------------------

async def execute_context_sync(task) -> None:  # type: ignore[name-defined]
    """Backfill: sync domain articles to intelligence.contexts (Phase 1.2 context-centric)."""
    from services.nightly_ingest_window_service import in_nightly_pipeline_window_est
    from api.config.context_centric_config import is_context_centric_task_enabled

    if in_nightly_pipeline_window_est() and not (task.metadata or {}).get("nightly_sequential_drain"):
        logger.debug("Context sync: nightly pipeline window — handled by nightly_enrichment_context")
        return
    if not is_context_centric_task_enabled("context_sync"):
        return

    from services.context_processor_service import sync_domain_articles_to_contexts

    for domain_key in _get_pipeline_active_domains():  # type: ignore[name-defined]
        try:
            total = await asyncio.get_event_loop().run_in_executor(
                None, lambda d=domain_key: sync_domain_articles_to_contexts(d, limit=100)
            )
            if total > 0:
                logger.info("Context sync %s: %d contexts created", domain_key, total)
        except Exception as e:
            logger.warning("Context sync %s failed: %s", domain_key, e)


async def execute_entity_profile_sync(task) -> None:  # type: ignore[name-defined]
    """Sync entity_canonical → entity_profiles + old_entity_to_new (Phase 1.3)."""
    from api.config.context_centric_config import is_context_centric_task_enabled

    if not is_context_centric_task_enabled("entity_profile_sync"):
        return

    from services.entity_profile_sync_service import sync_domain_entity_profiles

    for domain_key in _get_pipeline_active_domains():  # type: ignore[name-defined]
        try:
            total = await asyncio.get_event_loop().run_in_executor(
                None, lambda d=domain_key: sync_domain_entity_profiles(d, limit=50)
            )
            if total > 0:
                logger.info("Entity profile sync %s: %d synced", domain_key, total)
        except Exception as e:
            logger.warning("Entity profile sync %s failed: %s", domain_key, e)


# ---------------------------------------------------------------------------
# Phase: document collection & processing
# ---------------------------------------------------------------------------

async def execute_document_collection(task) -> None:  # type: ignore[name-defined]
    """Discover government and academic PDF documents (invoked from collection_cycle)."""
    try:
        result = await asyncio.get_event_loop().run_in_executor(None, _doc_collection_sync)
        if result:
            logger.info("Document collection: %d new documents discovered", result)
    except Exception as e:
        logger.warning("Document collection failed: %s", e)


def _doc_collection_sync() -> int | None:  # type: ignore[no-untyped-def]
    from api.collectors.document_collector import discover_documents
    result = discover_documents(limit=50)
    return len(result) if isinstance(result, list) else None


async def execute_document_processing(task) -> None:  # type: ignore[name-defined]
    """Process pending document ingest queue entries."""
    try:
        processed = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _doc_process_sync()
        )
        if processed > 0:
            logger.info("Document processing: %d documents processed", processed)
    except Exception as e:
        logger.warning("Document processing failed: %s", e)


def _doc_process_sync() -> int:  # type: ignore[no-untyped-def]
    from api.collectors.document_processor import process_pending_documents
    return process_pending_documents(limit=30)


# ---------------------------------------------------------------------------
# Phase: story enhancement (state triggers for enrichment/build)
# ---------------------------------------------------------------------------

async def execute_story_enhancement(task) -> None:  # type: ignore[name-defined]
    """Phase 3 RAG: story state triggers; enrich/build only when facts_only policy allows."""
    from services.enhancement_orchestrator_service import run_enhancement_cycle
    api.shared.pipeline_resource_policy import (
        story_enhancement_facts_only,
        story_enhancement_run_limits,
    )

    try:
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
                "Story enhancement cycle: facts_only=%s fact_log=%d queue=%d enriched=%d built=%d",
                facts_only,
                result.get("fact_change_log_processed", 0),
                result.get("story_update_queue_processed", 0),
                result.get("entity_profiles_enriched", 0),
                result.get("entity_profiles_built", 0),
            )
        if result.get("errors"):
            logger.warning("Story enhancement errors: %s", result["errors"])
    except Exception as e:
        logger.warning("Story enhancement failed: %s", e)


# ---------------------------------------------------------------------------
# Phase: entity dossier compile (chronicle_data, relationships, positions)
# ---------------------------------------------------------------------------

async def execute_entity_dossier_compile(task) -> None:  # type: ignore[name-defined]
    """Compile entity dossiers for entities missing or stale (Phase 2.6)."""
    from api.config.context_centric_config import is_context_centric_task_enabled

    if not is_context_centric_task_enabled("entity_dossier_compile"):
        return

    from services.dossier_compiler_service import _run_scheduled_dossier_compiles

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

    loop = asyncio.get_event_loop()
    compiled = await loop.run_in_executor(
        None, lambda: _run_scheduled_dossier_compiles(max_dossiers, None, stale_days)
    )
    if compiled > 0:
        logger.info("Entity dossier compile: %d dossiers compiled", compiled)


# ---------------------------------------------------------------------------
# Phase: metadata enrichment (auto-tagging & classification)
# ---------------------------------------------------------------------------

async def execute_metadata_enrichment(task) -> None:  # type: ignore[name-defined]
    """Auto-tag articles with topic tags, sentiment tags, and relevance scores."""
    from services.metadata_enrichment_service import MetadataEnrichmentService

    meta = task.metadata or {}
    limit = int(meta.get("limit", 50))
    
    svc = await loop.run_in_executor(None, lambda: MetadataEnrichmentService())  # type: ignore[name-defined]
    enriched = await loop.run_in_executor(None, lambda: svc.enrich_pending(limit))  # type: ignore[name-defined]
    if enriched > 0:
        logger.info("Metadata enrichment: %d articles tagged", enriched)


# ---------------------------------------------------------------------------
# Phase: entity enrichment (RAG-based profile enhancement)
# ---------------------------------------------------------------------------

async def execute_entity_enrichment(task) -> None:  # type: ignore[name-defined]
    """Phase 3 RAG: Run entity enrichment batch (Wikipedia → entity_profiles + versioned_facts)."""
    from services.entity_enrichment_service import run_enrichment_batch

    try:
        updated = run_enrichment_batch(limit=20)
        if updated > 0:
            logger.info("Entity enrichment: %d profiles enriched", updated)
    except Exception as e:
        logger.warning("Entity enrichment failed: %s", e)


# ---------------------------------------------------------------------------
# Phase: entity profile build (v8 pipeline builder)
# ---------------------------------------------------------------------------

async def execute_entity_profile_build(task) -> None:  # type: ignore[name-defined]
    """Build entity profiles from canonical entities + context_data (Phase 2.4)."""
    from api.config.context_centric_config import is_context_centric_task_enabled

    if not is_context_centric_task_enabled("entity_profile_build"):
        return
    from services.entity_profile_builder_service import run_profile_builder_batch

    try:
        updated = await run_profile_builder_batch(limit=25)  # v8
        if updated > 0:
            logger.info("Entity profile build: %d profiles updated", updated)
    except Exception as e:
        logger.warning("Entity profile build failed: %s", e)
