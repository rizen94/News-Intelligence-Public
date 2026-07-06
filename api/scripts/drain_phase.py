#!/usr/bin/env python3
"""
Unified operator drain command (v10.1).

  PYTHONPATH=api python api/scripts/drain_phase.py --phase unified_intake_extraction --budget-seconds 900
  PYTHONPATH=api python api/scripts/drain_phase.py --phase topic_clustering --budget-seconds 600 --force
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

_API = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_API))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PHASE_RUNNERS = {
    "unified_intake_extraction",
    "content_enrichment",
    "topic_clustering",
    "claim_extraction",
    "entity_profile_build",
    "spine_sql_tail",
}


async def _drain(phase: str, budget_seconds: int, per_schema: int, force: bool) -> dict:
    if phase == "unified_intake_extraction":
        from shared.unified_intake_extraction_runner import run_unified_intake_extraction_batch_drain

        return await run_unified_intake_extraction_batch_drain(
            articles_per_domain=per_schema,
            budget_seconds=budget_seconds,
        )
    if phase == "content_enrichment":
        from services.article_content_enrichment_service import enrich_articles_batch

        processed = enrich_articles_batch(batch_size=per_schema)
        return {"processed": processed}
    if phase == "topic_clustering":
        from config.settings import topic_clustering_batch_size, topic_clustering_concurrency
        from shared.domain_registry import get_pipeline_active_domain_keys

        _scripts = str(_API / "scripts")
        if _scripts not in sys.path:
            sys.path.insert(0, _scripts)
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
    if phase == "claim_extraction":
        from services.claim_extraction_service import drain_claim_extraction_for_automation_task

        inserted, batches = await drain_claim_extraction_for_automation_task()
        return {"claims_inserted": inserted, "batches": batches}
    if phase == "entity_profile_build":
        from services.entity_profile_builder_service import run_profile_builder_batch

        batch_result = await run_profile_builder_batch(limit=per_schema)
        return {"profiles_updated": batch_result.updated}
    if phase == "spine_sql_tail":
        from services.spine_sql_tail_service import run_spine_sql_tail_drain

        return await run_spine_sql_tail_drain(budget_seconds=budget_seconds)
  # legacy burn-down wrapper
    if phase in ("entity_extraction", "event_extraction"):
        logger.warning("phase %s is deprecated — use unified_intake_extraction", phase)
        return {"skipped": "deprecated"}

    raise ValueError(f"unsupported phase: {phase}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Drain a single pipeline phase (v10.1)")
    parser.add_argument("--phase", required=True, choices=sorted(PHASE_RUNNERS | {"entity_extraction", "event_extraction"}))
    parser.add_argument("--budget-seconds", type=int, default=900)
    parser.add_argument("--per-schema", type=int, default=40)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.force:
        from config.catchup_defaults import apply_catchup_env_defaults
        from config.runtime import env_set

        apply_catchup_env_defaults(bulk_active=True)
        env_set("AUTOMATION_BULK_CATCHUP_PAUSE", "1")

    result = asyncio.run(
        _drain(args.phase, args.budget_seconds, args.per_schema, args.force)
    )
    logger.info("drain_phase %s finished: %s", args.phase, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
