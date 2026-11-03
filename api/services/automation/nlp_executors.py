"""NLP/ML task executors — migrated from automation_manager.py.

Migrating: entity profiles, dossiers, positions, claims extraction/promotion,
legislative references, metadata enrichment, content refinement, and story enhancement.
"""
from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger(__name__)


def _is_context_centric_task_enabled(task_name: str) -> bool:
    """Check if a context-centric task is enabled. Returns True by default."""
    try:
        from config.context_centric_config import is_context_centric_task_enabled as _icc
        return _icc(task_name)
    except ImportError:
        return False


def _get_pipeline_active_domain_keys():
    """Return list of active domain keys for pipeline tasks."""
    try:
        from config.pipeline_config import get_pipeline_active_domain_keys as _gpdk
        return _gpdk()
    except ImportError:
        return []


def _story_enhancement_facts_only() -> bool:
    """Return whether story enhancement is limited to facts-only policy."""
    try:
        from shared.pipeline_resource_policy import story_enhancement_facts_only as _fef
        return _fef()
    except ImportError:
        return False


def _story_enhancement_run_limits(*, fact_batch=20, queue_batch=150, enrich_limit=30, build_limit=4) -> dict:
    """Return run limits for story enhancement based on facts_only policy."""
    try:
        from shared.pipeline_resource_policy import story_enhancement_run_limits as _srl
        return _srl(fact_batch=fact_batch, queue_batch=queue_batch, enrich_limit=enrich_limit, build_limit=build_limit)
    except ImportError:
        return {"fact_batch": fact_batch, "queue_batch": queue_batch, "enrich_limit": enrich_limit, "build_limit": build_limit}


def _in_nightly_pipeline_window_est() -> bool:
    """Check if we are inside the nightly pipeline window."""
    try:
        from services.nightly_ingest_window_service import in_nightly_pipeline_window_est as _ni
        return _ni()
    except ImportError:
        return False


# ── Entity Profile & Dossier Executors ──────────────────────────────────────

async def execute_entity_profile_build(task) -> None:
    """Build Wikipedia-style sections for entity_profiles from contexts (Phase 1.3)."""
    if not _is_context_centric_task_enabled("entity_profile_build"):
        return
    try:
        from services.entity_profile_builder_service import run_profile_builder_batch
        updated = await run_profile_builder_batch(limit=25)  # v8
        if updated > 0:
            logger.info("Entity profile build: %s profiles updated", updated)
    except Exception as e:
        logger.warning("Entity profile build failed: %s", e)


async def execute_entity_dossier_compile(task, automation) -> None:
    """Compile Wikipedia-style entity dossiers from contexts and sources."""
    if not _is_context_centric_task_enabled("entity_dossier_compile"):
        return
    try:
        max_dossiers = 25
    except ValueError:
        max_dossiers = 25
    try:
        stale_days = int(os.environ.get("ENTITY_DOSSIER_STALE_DAYS", "7") or "7")
    except ValueError:
        stale_days = 7
    stale_days = max(0, min(365, stale_days))
    try:
        loop = asyncio.get_event_loop()
        compiled = await loop.run_in_executor(
            automation._executor,
            _run_scheduled_dossier_compiles,
            max_dossiers,
            None,
            stale_days,
        )
        if compiled > 0:
            logger.info("Entity dossier compile: %s dossiers compiled", compiled)
    except Exception as e:
        logger.warning("Entity dossier compile failed: %s", e)


def _run_scheduled_dossier_compiles(max_dossiers, get_db_connection_fn, stale_days):
    """Background job that compiles entity dossiers."""
    try:
        from services.entity_dossier_service import run_scheduled_dossier_compiles
        return run_scheduled_dossier_compiles(
            max_dossiers=max_dossiers,
            get_db_connection_fn=get_db_connection_fn,
            stale_days=stale_days,
        )
    except ImportError:
        return 0


async def execute_entity_position_tracker(task) -> None:
    """Extract entity positions (stances, votes, policy) from articles."""
    if not _is_context_centric_task_enabled("entity_position_tracker"):
        return
    from services.entity_position_tracker_service import run_position_tracker_batch
    try:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            run_position_tracker_batch,
            None,  # domain_key -> all domains
            5,  # min_mentions
            8,  # max_entities
            25,  # max_articles_per_entity (v8)
        )
        total = sum(
            r.get("total_positions", 0) for r in (results or {}).values() if isinstance(r, dict)
        )
        if total > 0:
            logger.info("Entity position tracker: %s positions extracted", total)
    except Exception as e:
        logger.warning("Entity position tracker failed: %s", e)


# ── Claim Extraction & Promotion Executors ──────────────────────────────────

async def execute_claim_extraction(task) -> None:
    """Extract claims (subject/predicate/object) from contexts without claims (Phase 2.1 context-centric)."""
    if not _is_context_centric_task_enabled("claim_extraction"):
        return
    try:
        from services.claim_extraction_service import (
            claim_extraction_drain_enabled,
            drain_claim_extraction_for_automation_task,
            run_claim_extraction_batch,
        )
        task.metadata = task.metadata or {}
        run_limit = (task.metadata or {}).get("nightly_limit")
        nlim = int(run_limit) if run_limit else None
        if claim_extraction_drain_enabled():
            task.metadata["skip_automation_run_history"] = True
            total, batches = await drain_claim_extraction_for_automation_task(
                nightly_limit=nlim,
            )
            if total > 0:
                logger.info(
                    "Claim extraction: %s claims inserted (%s batch(es) in one task)",
                    total,
                    batches,
                )
        else:
            res = await run_claim_extraction_batch(limit=nlim)
            if res.claims_inserted > 0:
                logger.info("Claim extraction: %s claims inserted", res.claims_inserted)
    except Exception as e:
        logger.warning("Claim extraction failed: %s", e)


async def execute_claims_to_facts(task) -> None:
    """Promote high-confidence extracted_claims to versioned_facts (activates story state chain)."""
    from services.claim_extraction_service import (
        claims_to_facts_drain_enabled,
        drain_claims_to_facts_for_automation_task,
        promote_claims_to_versioned_facts,
    )
    task.metadata = task.metadata or {}
    try:
        run_limit = task.metadata.get("nightly_limit")
        per_batch = int(run_limit) if run_limit else None
        is_nightly_seq = bool(task.metadata.get("nightly_sequential_drain"))
        # Daytime scheduled: optional multi-batch drain in one task.
        # Nightly sequential: one promote per run — outer NIGHTLY_SEQUENTIAL_PHASE_LOOP_CAPS repeats.
        if claims_to_facts_drain_enabled() and not is_nightly_seq:
            task.metadata["skip_automation_run_history"] = True
            total, batches = await drain_claims_to_facts_for_automation_task(
                per_batch_limit=per_batch,
            )
            if total > 0:
                logger.info(
                    "Claims to facts: %s rows promoted (%s batch(es) in one task)",
                    total,
                    batches,
                )
        else:
            if per_batch is not None:
                stats = await asyncio.to_thread(promote_claims_to_versioned_facts, None, per_batch)
            else:
                stats = await asyncio.to_thread(promote_claims_to_versioned_facts)
            if not isinstance(stats, dict):
                return
            if stats.get("candidates", 0) == 0:
                logger.debug("Claims to facts: no promotable claims in batch")
    except Exception as e:
        logger.warning("Claims to facts failed: %s", e)


async def execute_claim_subject_gap_refresh(task) -> None:
    """Rebuild intelligence.claim_subject_gap_catalog (open subjects lacking profiles/canonicals)."""
    if not _is_context_centric_task_enabled("claim_subject_gap_refresh"):
        return
    try:
        from services.claim_subject_gap_service import refresh_claim_subject_gap_catalog
        out = await asyncio.to_thread(refresh_claim_subject_gap_catalog)
        if isinstance(out, dict) and out.get("success"):
            logger.info(
                "Claim subject gap refresh: upserted=%s deleted_stale=%s",
                out.get("rows_upserted"),
                out.get("rows_deleted_stale"),
            )
    except Exception as e:
        logger.warning("Claim subject gap refresh failed: %s", e)


async def execute_extracted_claims_dedupe(task) -> None:
    """Delete duplicate extracted_claims rows (same context + normalized triple)."""
    if not _is_context_centric_task_enabled("extracted_claims_dedupe"):
        return
    try:
        from services.extracted_claims_dedupe_service import run_dedupe_cycle
        out = await asyncio.to_thread(run_dedupe_cycle)
        if isinstance(out, dict) and int(out.get("deleted") or 0) > 0:
            logger.info(
                "Extracted claims dedupe: deleted=%s remaining_dup_estimate=%s",
                out.get("deleted"),
                out.get("duplicates_after"),
            )
    except Exception as e:
        logger.warning("Extracted claims dedupe failed: %s", e)



# ── Legacy NLP Executor Stubs (delegate to automation_manager) ────────────────
# These methods were migrated with full implementations.
# To migrate additional executors, copy from automation_manager.py and adapt helpers.

async def execute_legislative_references(task) -> None:
    """Detect bill citations in politics/legal articles; fetch Congress.gov pointers."""
    if not _is_context_centric_task_enabled("legislative_references"):
        return
    try:
        from services.legislative_reference_service import run_legislative_reference_batch
        stats = await asyncio.to_thread(run_legislative_reference_batch)
        if stats and not stats.get("skipped") and int(stats.get("articles_scanned") or 0) > 0:
            logger.info(
                "Legislative references: scanned %s articles, %s snapshots",
                stats.get("articles_scanned"),
                stats.get("references_upserted"),
            )
    except Exception as e:
        logger.warning("Legislative references failed: %s", e)


async def execute_metadata_enrichment(task) -> None:
    """Run metadata enrichment batch for domain articles (language, categories, sentiment, quality)."""
    try:
        from services.metadata_enrichment_service import run_metadata_enrichment_batch_for_domains
        total = await run_metadata_enrichment_batch_for_domains(limit_per_domain=5)
        if total > 0:
            logger.info("Metadata enrichment: %d articles enriched", total)
    except Exception as e:
        logger.warning("Metadata enrichment failed: %s", e)


async def execute_story_enhancement(task) -> None:
    """Phase 3 RAG: story state triggers; enrich/build only when facts_only policy allows."""
    from services.enhancement_orchestrator_service import run_enhancement_cycle
    from shared.pipeline_resource_policy import (
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
            result.get("factual_enriched", 0)
            + result.get("queue_processed", 0)
            + result.get("enriched", 0)
            + result.get("built", 0)
        )
        if total > 0:
            logger.info(
                "Story enhancement: factual_enriched=%s queue=%s enrich=%s build=%s",
                result.get("factual_enriched"),
                result.get("queue_processed"),
                result.get("enriched"),
                result.get("built"),
            )
    except Exception as e:
        logger.warning("Story enhancement failed: %s", e)


async def execute_content_refinement_queue(task) -> None:
    """Enqueue and process content refinement queue (RAG enrichment for documents)."""
    try:
        from services.comprehensive_enhancement_service import (
            auto_enqueue_comprehensive_rag_for_automation,
            process_content_refinement_queue_batch,
        )
        if _in_nightly_pipeline_window_est():
            logger.debug(
                "Content refinement queue: nightly pipeline active — handled by nightly_enrichment_context"
            )
            return
        auto_enqueue_comprehensive_rag_for_automation()
        stats = await process_content_refinement_queue_batch()
        logger.info(
            "Content refinement queue: pending_before=%s processed=%s failed=%s by_type=%s pending_after=%s",
            stats.get("pending_before"),
            stats.get("processed"),
            stats.get("failed"),
            stats.get("by_type"),
            stats.get("pending_after"),
        )
    except Exception as e:
        logger.warning("Content refinement queue failed: %s", e)
