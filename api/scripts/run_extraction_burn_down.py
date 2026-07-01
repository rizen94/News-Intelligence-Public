#!/usr/bin/env python3
"""
Phased extraction burn-down: unified_intake_extraction → topic_clustering (default).

PopOS GPU saturation, automation competition pause, unlimited drain budgets.
Legacy entity/event/claim phases available via --phases but omitted by default.

  PYTHONPATH=api python3 api/scripts/run_extraction_burn_down.py --force
  PYTHONPATH=api python3 api/scripts/run_extraction_burn_down.py --force --loops 0
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Any

_API_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _API_ROOT.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_PHASE_ORDER: tuple[str, ...] = (
    "unified_intake_extraction",
    "topic_clustering",
)
LEGACY_PHASE_ORDER: tuple[str, ...] = (
    "claim_extraction",
    "entity_extraction",
    "event_extraction",
)
ALL_PHASES: tuple[str, ...] = DEFAULT_PHASE_ORDER + LEGACY_PHASE_ORDER


def _bootstrap(*, gpu_parallel: int, cpu_parallel: int, dual_lane: bool, ollama_timeout: int) -> None:
    from config.catchup_defaults import apply_catchup_env_defaults
    from config.runtime import env_set, env_str
    from shared.catchup_bootstrap import bootstrap_catchup
    from shared.bulk_catchup_llm_routing import configure_catchup_extraction_routing

    bootstrap_catchup(repo_root=_REPO_ROOT, bulk_active=True)
    apply_catchup_env_defaults(bulk_active=True)
    env_set("AUTOMATION_BULK_CATCHUP_PAUSE", "1")
    env_set("UNIFIED_INTAKE_EXTRACTION_ENABLED", "true")
    configure_catchup_extraction_routing(
        use_popos_gpu=True,
        dual_lane=dual_lane,
        gpu_parallel=gpu_parallel,
        cpu_parallel=cpu_parallel,
        ollama_timeout=ollama_timeout,
    )
    logger.info(
        "extraction model=%s batch_unified=%s cpu_parallel=%s",
        env_str("BULK_EXTRACTION_MODEL", env_str("OLLAMA_MODEL_EXTRACTION", "?")),
        env_str("UNIFIED_INTAKE_EXTRACTION_BATCH_SIZE", "6"),
        cpu_parallel,
    )


def _active_phases(args: argparse.Namespace) -> tuple[str, ...]:
    if args.phases:
        return tuple(args.phases)
    return DEFAULT_PHASE_ORDER


def _backlog_snapshot(phases: tuple[str, ...]) -> dict[str, int]:
    from services.backlog_metrics import get_all_backlog_counts

    raw = get_all_backlog_counts()
    return {p: int(raw.get(p, 0) or 0) for p in phases}


async def _drain_unified_intake(*, budget_seconds: int, per_schema: int) -> dict[str, Any]:
    from shared.unified_intake_extraction_runner import run_unified_intake_extraction_batch_drain

    return await run_unified_intake_extraction_batch_drain(
        articles_per_domain=per_schema,
        budget_seconds=budget_seconds,
    )


async def _drain_claims() -> tuple[int, int]:
    from services.claim_extraction_service import drain_claim_extraction_for_automation_task

    return await drain_claim_extraction_for_automation_task()


async def _drain_entity(*, budget_seconds: int) -> dict[str, Any]:
    from shared.entity_extraction_runner import run_entity_extraction_batch_drain

    return await run_entity_extraction_batch_drain(budget_seconds=budget_seconds)


async def _drain_event(*, budget_seconds: int, per_schema: int, batch_size: int) -> dict[str, Any]:
    from shared.event_extraction_runner import run_event_extraction_batch_drain

    return await run_event_extraction_batch_drain(
        articles_per_schema=per_schema,
        budget_seconds=budget_seconds,
        batch_size=batch_size,
    )


async def _drain_topic_clustering(*, max_batches: int) -> int:
    from config.settings import topic_clustering_batch_size, topic_clustering_concurrency
    from shared.domain_registry import get_pipeline_active_domain_keys

    _scripts = str(_API_ROOT / "scripts")
    if _scripts not in sys.path:
        sys.path.insert(0, _scripts)
    from catchup_topic_clustering import catchup_domain

    total = 0
    batch_size = topic_clustering_batch_size()
    concurrency = topic_clustering_concurrency()
    for domain_key in get_pipeline_active_domain_keys():
        stats = await catchup_domain(
            domain_key,
            batch_size=batch_size,
            concurrency=concurrency,
            max_batches=max_batches,
            dry_run=False,
        )
        total += int(stats.get("processed", 0) or 0)
    return total


async def _run_phase(phase: str, args: argparse.Namespace) -> dict[str, Any]:
    if phase == "unified_intake_extraction":
        return await _drain_unified_intake(
            budget_seconds=args.budget_seconds,
            per_schema=args.per_schema,
        )
    if phase == "claim_extraction":
        claims, batches = await _drain_claims()
        return {"claims_inserted": claims, "batches": batches}
    if phase == "entity_extraction":
        return await _drain_entity(budget_seconds=args.budget_seconds)
    if phase == "event_extraction":
        return await _drain_event(
            budget_seconds=args.budget_seconds,
            per_schema=args.per_schema,
            batch_size=args.event_batch_size,
        )
    if phase == "topic_clustering":
        processed = await _drain_topic_clustering(max_batches=args.topic_max_batches)
        return {"processed": processed}
    return {}


def _phase_moved(phase: str, result: dict[str, Any]) -> int:
    if phase == "claim_extraction":
        return int(result.get("claims_inserted") or 0) + int(result.get("batches") or 0)
    if phase in ("event_extraction", "unified_intake_extraction"):
        return int(result.get("articles_processed") or result.get("processed") or 0)
    return int(result.get("processed") or result.get("articles_processed") or 0)


async def _main_async(args: argparse.Namespace) -> int:
    from config.runtime import env_pop, env_set
    from shared.bulk_catchup_pause import clear_pause_marker, write_pause_marker

    phases = _active_phases(args)
    _bootstrap(
        gpu_parallel=args.gpu_parallel,
        cpu_parallel=args.cpu_parallel,
        dual_lane=args.dual_lane,
        ollama_timeout=args.ollama_timeout,
    )
    write_pause_marker(reason="run_extraction_burn_down.py")

    try:
        before = _backlog_snapshot(phases)
        logger.info("burn-down start backlog: %s phases=%s", before, phases)

        stall = 0
        max_loops = args.loops if args.loops > 0 else 10_000
        for loop_i in range(1, max_loops + 1):
            loop_start = time.monotonic()
            moved_any = False
            for phase in phases:
                pending = _backlog_snapshot(phases).get(phase, 0)
                if pending <= args.floor:
                    logger.info("skip %s loop %s: pending=%s <= floor=%s", phase, loop_i, pending, args.floor)
                    continue
                logger.info(
                    "=== loop %s/%s phase=%s pending=%s ===",
                    loop_i,
                    max_loops if args.loops > 0 else "∞",
                    phase,
                    pending,
                )
                result = await _run_phase(phase, args)
                moved = _phase_moved(phase, result)
                after = _backlog_snapshot(phases).get(phase, 0)
                logger.info(
                    "phase %s done: moved=%s backlog_now=%s detail=%s",
                    phase,
                    moved,
                    after,
                    {k: v for k, v in result.items() if k != "by_domain"},
                )
                if moved > 0:
                    moved_any = True

            elapsed = time.monotonic() - loop_start
            after_all = _backlog_snapshot(phases)
            logger.info("loop %s finished in %.0fs backlog: %s", loop_i, elapsed, after_all)

            if all(after_all.get(p, 0) <= args.floor for p in phases):
                logger.info("all phases at or below floor — done")
                break
            if not moved_any:
                stall += 1
                if stall >= args.stall_loops:
                    logger.warning("stall limit %s — stopping", args.stall_loops)
                    break
            else:
                stall = 0

        logger.info("burn-down finished backlog: %s", _backlog_snapshot(phases))
        return 0
    finally:
        clear_pause_marker()
        env_pop("BULK_CATCHUP_ACTIVE", None)
        env_pop("AUTOMATION_BULK_CATCHUP_PAUSE", None)


def main() -> int:
    from config.runtime import env_str

    parser = argparse.ArgumentParser(description="Phased extraction burn-down (PopOS GPU)")
    parser.add_argument("--loops", type=int, default=int(env_str("EXTRACTION_BURN_DOWN_LOOPS", "10")))
    parser.add_argument("--floor", type=int, default=int(env_str("EXTRACTION_BURN_DOWN_FLOOR", "50")))
    parser.add_argument("--stall-loops", type=int, default=int(env_str("EXTRACTION_BURN_DOWN_STALL_LOOPS", "3")))
    parser.add_argument(
        "--phases",
        nargs="*",
        choices=ALL_PHASES,
        default=None,
        help="Default: unified_intake_extraction then topic_clustering",
    )
    parser.add_argument(
        "--budget-seconds",
        type=int,
        default=int(env_str("UNIFIED_INTAKE_EXTRACTION_RUN_BUDGET_SECONDS", "14400")),
    )
    parser.add_argument("--per-schema", type=int, default=80)
    parser.add_argument("--event-batch-size", type=int, default=3)
    parser.add_argument("--topic-max-batches", type=int, default=20)
    parser.add_argument("--gpu-parallel", type=int, default=int(env_str("BULK_GPU_PARALLEL", "8")))
    parser.add_argument("--cpu-parallel", type=int, default=int(env_str("BULK_CPU_PARALLEL", "8")))
    parser.add_argument(
        "--dual-lane",
        action=argparse.BooleanOptionalAction,
        default=env_str("BULK_DUAL_LANE_CATCHUP", "true").lower() in ("1", "true", "yes"),
    )
    parser.add_argument("--ollama-timeout", type=int, default=int(env_str("BULK_OLLAMA_TIMEOUT", "600")))
    parser.add_argument("--force", action="store_true", help="Reserved for schedule bypass (always runs)")
    args = parser.parse_args()
    _ = args.force
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
