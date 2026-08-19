"""Async phase drain dispatch for operators and the PopOS phase worker."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_API = Path(__file__).resolve().parents[1]

# Phases with a working drain callable (expand carefully; prefer PopOS for LLM-heavy).
DRAINABLE_PHASES: frozenset[str] = frozenset(
    {
        "unified_intake_extraction",
        "claim_extraction",
        "topic_clustering",
        "storyline_assembly",
        "content_enrichment",
        "entity_profile_build",
        "spine_sql_tail",
        "editorial_research_pass",
        "editorial_narrative_pass",
        "editorial_evidence_expand_pass",
        "editorial_reduction_pass",
        "chronological_events_catchup",
        "story_continuation",
        "content_refinement_queue",
    }
)


async def drain_phase(
    phase: str,
    *,
    budget_seconds: int = 900,
    articles_per_domain: int | None = None,
) -> dict[str, Any]:
    """Run one drain round for ``phase``. Raises ValueError if unsupported."""
    name = (phase or "").strip()
    per = articles_per_domain if articles_per_domain is not None else 40

    if name == "unified_intake_extraction":
        from shared.unified_intake_extraction_runner import run_unified_intake_extraction_batch_drain

        if articles_per_domain is None:
            try:
                from shared.adaptive_batch_policy import resolve_phase_batch_limit

                per = resolve_phase_batch_limit(
                    "unified_intake_extraction", 40, env_suffix="ARTICLES_PER_DOMAIN"
                )
            except Exception:
                per = 40
        return await run_unified_intake_extraction_batch_drain(
            articles_per_domain=per,
            budget_seconds=budget_seconds,
            use_spine_work_queues=True,
        )

    if name == "claim_extraction":
        from services.claim_extraction_service import drain_claim_extraction_for_automation_task

        inserted, batches = await drain_claim_extraction_for_automation_task()
        return {"claims_inserted": inserted, "batches": batches}

    if name == "topic_clustering":
        from config.settings import topic_clustering_batch_size, topic_clustering_concurrency
        from shared.domain_registry import get_pipeline_active_domain_keys

        scripts = str(_API / "scripts")
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        from catchup_topic_clustering import catchup_domain

        total = 0
        for domain_key in get_pipeline_active_domain_keys():
            stats = await catchup_domain(
                domain_key,
                batch_size=topic_clustering_batch_size(),
                concurrency=topic_clustering_concurrency(),
                max_batches=50,
                dry_run=False,
            )
            total += int(stats.get("processed", 0) or 0)
        return {"processed": total}

    if name == "storyline_assembly":
        from services.storyline_assembly_service import run_storyline_assembly_all_domains

        return await run_storyline_assembly_all_domains()

    if name == "content_enrichment":
        from shared.content_enrichment_drain import run_content_enrichment_batch

        try:
            from shared.adaptive_batch_policy import resolve_adaptive_batch

            per, _meta = resolve_adaptive_batch("content_enrichment", per)
        except Exception:
            pass
        processed = run_content_enrichment_batch(batch_size=per)
        return {"processed": processed}

    if name == "entity_profile_build":
        from services.entity_profile_builder_service import (
            entity_profile_build_batch_limit,
            run_profile_builder_batch,
        )

        try:
            lim = articles_per_domain if articles_per_domain is not None else entity_profile_build_batch_limit()
        except Exception:
            lim = per
        batch_result = await run_profile_builder_batch(limit=lim)
        return {"profiles_updated": batch_result.updated}

    if name == "spine_sql_tail":
        from services.spine_sql_tail_service import run_spine_sql_tail_drain

        return await run_spine_sql_tail_drain(budget_seconds=budget_seconds)

    if name == "editorial_research_pass":
        from config.runtime import env_int
        from services.editorial_package_research_service import (
            is_enabled,
            list_research_due,
            run_research_pass,
        )

        if not is_enabled():
            return {"skipped": True, "reason": "EDITORIAL_RESEARCH_ENABLED=false", "processed": 0}
        batch = (
            articles_per_domain
            if articles_per_domain is not None
            else env_int("EDITORIAL_RESEARCH_BATCH", 5)
        )
        ids = list_research_due(limit=batch)
        results: list[dict[str, Any]] = []
        for pid in ids:
            try:
                results.append(await run_research_pass(pid))
            except Exception as e:
                logger.warning("editorial_research drain item failed package_id=%s: %s", pid, e)
                results.append({"ok": False, "package_id": pid, "error": str(e)})
        return {
            "processed": len(results),
            "package_ids": ids,
            "results": results,
            "changed_total": sum(int(r.get("changed") or 0) for r in results),
        }

    if name == "editorial_narrative_pass":
        from config.runtime import env_int
        from services.editorial_package_narrative_service import (
            is_enabled,
            list_narrative_due,
            run_narrative_pass,
        )

        if not is_enabled():
            return {"skipped": True, "reason": "EDITORIAL_NARRATIVE_ENABLED=false", "processed": 0}
        batch = (
            articles_per_domain
            if articles_per_domain is not None
            else env_int("EDITORIAL_NARRATIVE_BATCH", 5)
        )
        ids = list_narrative_due(limit=batch)
        results = []
        for pid in ids:
            try:
                results.append(await run_narrative_pass(pid))
            except Exception as e:
                logger.warning("editorial_narrative drain item failed package_id=%s: %s", pid, e)
                results.append({"ok": False, "package_id": pid, "error": str(e)})
        return {
            "processed": len(results),
            "package_ids": ids,
            "results": results,
            "changed_total": sum(int(r.get("changed") or 0) for r in results),
        }

    if name == "editorial_evidence_expand_pass":
        from config.runtime import env_int
        from services.editorial_package_evidence_expand_service import (
            is_enabled,
            run_evidence_expand_batch,
        )

        if not is_enabled():
            return {
                "skipped": True,
                "reason": "EDITORIAL_EVIDENCE_EXPAND_ENABLED=false",
                "processed": 0,
            }
        batch = (
            articles_per_domain
            if articles_per_domain is not None
            else env_int("EVIDENCE_EXPAND_BATCH_LIMIT", 3)
        )
        return await asyncio.to_thread(run_evidence_expand_batch, limit=batch)

    if name == "editorial_reduction_pass":
        from config.runtime import env_int
        from services.editorial_package_reduction_service import (
            is_enabled,
            list_reduction_due,
            run_reduction_pass,
        )

        if not is_enabled():
            return {"skipped": True, "reason": "EDITORIAL_REDUCTION_ENABLED=false", "processed": 0}
        batch = (
            articles_per_domain
            if articles_per_domain is not None
            else env_int("EDITORIAL_REDUCTION_BATCH", 5)
        )
        ids = list_reduction_due(limit=batch)
        results = []
        for pid in ids:
            try:
                results.append(await run_reduction_pass(pid))
            except Exception as e:
                logger.warning("editorial_reduction drain item failed package_id=%s: %s", pid, e)
                results.append({"ok": False, "package_id": pid, "error": str(e)})
        return {
            "processed": len(results),
            "package_ids": ids,
            "results": results,
            "changed_total": sum(int(r.get("changed") or 0) for r in results),
        }

    if name == "chronological_events_catchup":
        import asyncio

        from services.chronological_events_catchup_service import (
            is_enabled,
            run_catchup_batch_sync,
        )

        if not is_enabled():
            return {
                "skipped": True,
                "reason": "CHRONOLOGICAL_EVENTS_CATCHUP_ENABLED=false",
                "processed": 0,
            }
        limit = articles_per_domain if articles_per_domain is not None else 5
        return await asyncio.to_thread(run_catchup_batch_sync, limit=limit)

    if name == "story_continuation":
        from shared.domain_processing_mode import domain_runs_phase
        from shared.domain_registry import pipeline_url_schema_pairs
        from shared.database.connection import get_db_connection
        from shared.services.llm_service import llm_service
        from services.story_continuation_service import StoryContinuationService

        cont_limit = articles_per_domain if articles_per_domain is not None else 30
        try:
            from shared.adaptive_batch_policy import resolve_adaptive_batch

            cont_limit, _meta = resolve_adaptive_batch("story_continuation", cont_limit)
        except Exception:
            pass
        total = {
            "checked": 0,
            "linked": 0,
            "flagged": 0,
            "backed_off": 0,
            "inherited": 0,
            "processed": 0,
        }
        schemas = [
            sch
            for dk, sch in pipeline_url_schema_pairs()
            if domain_runs_phase(dk, "story_continuation")
        ]
        for schema in schemas:
            conn = get_db_connection()
            if not conn:
                continue
            try:
                svc = StoryContinuationService(conn, llm=llm_service, schema=schema)
                stats = await svc.process_recent_events(limit=cont_limit)
                svc.update_lifecycle_states()
                total["checked"] += int(stats.get("checked") or 0)
                total["linked"] += int(stats.get("linked") or 0)
                total["flagged"] += int(stats.get("flagged") or 0)
                total["backed_off"] += int(stats.get("backed_off") or 0)
                total["inherited"] += int(stats.get("inherited") or 0)
            except Exception as e:
                logger.warning("story_continuation drain schema=%s: %s", schema, e)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        total["processed"] = total["linked"] + total["flagged"] + total["inherited"]
        return total

    if name == "content_refinement_queue":
        from services.content_refinement_queue_service import (
            auto_enqueue_comprehensive_rag_for_automation,
            process_content_refinement_queue_batch,
        )

        # Do not mirror Widow's nightly-window skip here. That skip exists so
        # AutomationManager defers to nightly_enrichment_context. When this phase
        # is REMOTE_PHASE_WORKER_OWNED, the PopOS drain is the owner.
        try:
            auto_enqueue_comprehensive_rag_for_automation()
        except Exception as e:
            logger.debug("content_refinement auto-enqueue: %s", e)
        return await process_content_refinement_queue_batch()

    raise ValueError(f"unsupported phase drain: {name}")
