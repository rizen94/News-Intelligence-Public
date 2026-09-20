#!/usr/bin/env python3
"""
Drain event_extraction backlog using batched PopOS GPU runner.

  cd /opt/news-intelligence && set -a && source .env && set +a
  PYTHONPATH=api python3 api/scripts/run_event_extraction_catchup.py --loops 20
  PYTHONPATH=api python3 api/scripts/run_event_extraction_catchup.py --loops 50 --budget-seconds 1800
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _load_env() -> None:
    from config.catchup_defaults import apply_catchup_env_defaults
    from config.runtime import env_set
    from config.runtime import env_str
    from shared.bulk_catchup_llm_routing import configure_catchup_extraction_routing
    from shared.catchup_bootstrap import bootstrap_catchup

    bootstrap_catchup(bulk_active=True)
    apply_catchup_env_defaults(bulk_active=True)
    env_set("AUTOMATION_BULK_CATCHUP_PAUSE", "1")
    configure_catchup_extraction_routing(
        use_popos_gpu=True,
        dual_lane=True,
        gpu_parallel=int(env_str("BULK_GPU_PARALLEL", "8")),
        cpu_parallel=int(env_str("BULK_CPU_PARALLEL", "4")),
    )


async def _drain_once(*, budget_seconds: int, per_schema: int, batch_size: int) -> dict:
    from shared.event_extraction_runner import run_event_extraction_batch_drain

    return await run_event_extraction_batch_drain(
        articles_per_schema=per_schema,
        budget_seconds=budget_seconds,
        batch_size=batch_size,
    )


async def _run_claim_drain_once() -> tuple[int, int]:
    from services.claim_extraction_service import drain_claim_extraction_for_automation_task

    return await drain_claim_extraction_for_automation_task()


async def _main_async(args: argparse.Namespace) -> int:
    total_articles = 0
    total_events = 0
    total_claims = 0
    claim_batches = 0

    for loop_i in range(1, args.loops + 1):
        if args.claims:
            claims, batches = await _run_claim_drain_once()
            total_claims += claims
            claim_batches += batches
            logger.info(
                "claim_extraction loop %s/%s: claims=%s batches=%s",
                loop_i,
                args.loops,
                claims,
                batches,
            )
            if claims == 0 and not args.events:
                break
            if args.events and claims == 0:
                pass
            elif not args.events:
                continue

        if args.events:
            result = await _drain_once(
                budget_seconds=args.budget_seconds,
                per_schema=args.per_schema,
                batch_size=args.batch_size,
            )
            articles = int(result.get("articles_processed") or 0)
            events = int(result.get("events_saved") or 0)
            total_articles += articles
            total_events += events
            logger.info(
                "event_extraction loop %s/%s: articles=%s events=%s rounds=%s",
                loop_i,
                args.loops,
                articles,
                events,
                result.get("batch_rounds", 0),
            )
            if articles == 0 and not args.claims:
                break
            if args.claims and articles == 0:
                if total_claims == 0:
                    break

    logger.info(
        "catch-up finished: event_articles=%s event_rows=%s claim_rows=%s claim_batches=%s",
        total_articles,
        total_events,
        total_claims,
        claim_batches,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Event/claim extraction catch-up drain")
    parser.add_argument("--loops", type=int, default=20, help="Max drain iterations")
    parser.add_argument("--budget-seconds", type=int, default=900)
    parser.add_argument("--per-schema", type=int, default=60)
    parser.add_argument("--batch-size", type=int, default=3)
    parser.add_argument("--phase", choices=("both", "event_extraction", "claim_extraction"), default="both")
    args = parser.parse_args()
    args.events = args.phase in ("both", "event_extraction")
    args.claims = args.phase in ("both", "claim_extraction")

    _load_env()
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
