#!/usr/bin/env python3
"""
One-shot catch-up burndown for selected pipeline phases (PopOS / operator).

Supports:
  - graph_link_drift_review
  - storyline_membership_review

Auto-tunes batch size via ``resolve_adaptive_batch`` + yield recording (same pattern
as ``burn_down_claims_to_facts.py``). Does not change Widow ownership / workers.

Examples:

  PYTHONPATH=api .venv/bin/python api/scripts/burn_down_phase_catchup.py \\
      --phases graph_link_drift_review --hours 2 --batch-cap 2000

  PYTHONPATH=api .venv/bin/python api/scripts/burn_down_phase_catchup.py \\
      --phases graph_link_drift_review,storyline_membership_review --hours 3
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

_API = Path(__file__).resolve().parent.parent
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [phase-burndown] %(message)s",
)
logger = logging.getLogger("phase_burndown")

SUPPORTED = frozenset(
    {
        "graph_link_drift_review",
        "storyline_membership_review",
    }
)

# Soft caps for catch-up (adaptive catchup_boost can otherwise jump huge).
_DEFAULT_CAPS = {
    "graph_link_drift_review": 500,
    "storyline_membership_review": 200,
}
_DEFAULT_SEEDS = {
    "graph_link_drift_review": 80,
    "storyline_membership_review": 100,
}


def _queue_depth(phase: str) -> int | None:
    try:
        from shared.pipeline_queue_counts import get_phase_queue_depth

        return int(get_phase_queue_depth(phase) or 0)
    except Exception as exc:
        logger.debug("queue_depth(%s): %s", phase, exc)
        return None


def _sample_headroom() -> dict[str, float]:
    out = {"cpu_avail": 0.5, "ram_avail": 0.5}
    try:
        from shared.catchup_host_metrics import sample_resources

        snap = sample_resources()
        cpu = getattr(snap, "local_cpu_headroom", None)
        ram = getattr(snap, "local_memory_headroom", None)
        if cpu is not None:
            out["cpu_avail"] = max(0.0, min(1.0, float(cpu)))
        if ram is not None:
            out["ram_avail"] = max(0.0, min(1.0, float(ram)))
    except Exception as exc:
        logger.debug("sample_headroom: %s", exc)
    return out


def _run_graph_link_drift(limit: int) -> dict[str, Any]:
    from services.graph_link_drift_service import rescore_active_graph_links

    # Bypass automation env gate — this is an explicit catch-up apply.
    os.environ.setdefault("GRAPH_LINK_DRIFT_REVIEW_ENABLED", "true")
    stats = rescore_active_graph_links(limit=int(limit))
    if not isinstance(stats, dict):
        stats = {}
    examined = int(stats.get("examined") or 0)
    updated = int(stats.get("updated") or 0)
    quarantined = int(stats.get("quarantined") or 0)
    skipped = int(stats.get("skipped") or 0)
    errors = int(stats.get("errors") or 0)
    return {
        **stats,
        "processed": examined,
        "approved": updated + quarantined,
        "skipped": skipped,
        "errors": errors,
        "idle": examined == 0,
    }


def _run_storyline_membership(limit: int) -> dict[str, Any]:
    from services.storyline_membership_review_service import (
        run_storyline_membership_review_all_domains,
    )

    result = run_storyline_membership_review_all_domains(
        limit_per_domain=int(limit), dry_run=False
    )
    totals = (result or {}).get("totals") or {}
    by_domain = (result or {}).get("by_domain") or {}
    scanned = 0
    if isinstance(by_domain, dict):
        for domain_res in by_domain.values():
            if isinstance(domain_res, dict):
                scanned += len(domain_res.get("storylines") or [])
    action_total = sum(int(totals.get(k, 0) or 0) for k in totals)
    return {
        "totals": totals,
        "processed": scanned,
        "approved": action_total,
        "skipped": max(0, scanned - action_total) if scanned else 0,
        "errors": 0,
        "idle": scanned == 0,
        "storylines_scanned": scanned,
    }


_RUNNERS: dict[str, Callable[[int], dict[str, Any]]] = {
    "graph_link_drift_review": _run_graph_link_drift,
    "storyline_membership_review": _run_storyline_membership,
}


@dataclass
class PhaseTuner:
    phase: str
    auto: bool = True
    batch_cap: int = 500
    default_batch: int = 100
    batch_limit: int = 100
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_meta: dict[str, Any] = field(default_factory=dict)
    tune_count: int = 0
    idle_streak: int = 0

    def _cap(self, batch: int) -> int:
        return max(1, min(int(batch), int(self.batch_cap)))

    async def resolve_batch(self) -> tuple[int, dict[str, Any]]:
        async with self.lock:
            if not self.auto:
                self.batch_limit = self._cap(self.default_batch)
                return self.batch_limit, {"adaptive": False, "action": "fixed"}

            def _resolve() -> tuple[int, dict[str, Any]]:
                from shared.adaptive_batch_policy import resolve_adaptive_batch

                return resolve_adaptive_batch(self.phase, int(self.default_batch))

            batch, meta = await asyncio.to_thread(_resolve)
            raw = max(1, int(batch))
            capped = self._cap(raw)
            meta = dict(meta or {})
            if capped < raw:
                meta["burndown_cap"] = capped
                meta["adaptive_raw"] = raw
                meta["action"] = f"{meta.get('action') or 'ok'},capped"
            self.batch_limit = capped
            self.last_meta = meta
            self.tune_count += 1
            return capped, meta

    async def record_yield(self, stats: dict[str, Any], *, batch_limit: int) -> None:
        if not self.auto:
            return

        def _record() -> None:
            from shared.adaptive_batch_policy import record_adaptive_batch_yield

            record_adaptive_batch_yield(
                self.phase,
                approved=int(stats.get("approved") or 0),
                rejected=0,
                skipped=int(stats.get("skipped") or 0),
                errors=int(stats.get("errors") or 0),
                batch_limit=batch_limit,
            )

        try:
            await asyncio.to_thread(_record)
        except Exception as exc:
            logger.debug("record_yield: %s", exc)


async def burn_phase(
    phase: str,
    *,
    max_seconds: float,
    auto: bool,
    batch_cap: int,
    max_idle_rounds: int,
) -> dict[str, Any]:
    runner = _RUNNERS[phase]
    seed = _DEFAULT_SEEDS.get(phase, 100)
    cap = batch_cap if batch_cap > 0 else _DEFAULT_CAPS.get(phase, 500)
    tuner = PhaseTuner(
        phase=phase,
        auto=auto,
        batch_cap=cap,
        default_batch=seed,
        batch_limit=seed,
    )
    started = datetime.now(timezone.utc).isoformat()
    depth0 = await asyncio.to_thread(_queue_depth, phase)
    batch0, meta0 = await tuner.resolve_batch()
    logger.info(
        "phase=%s start depth=%s batch=%s cap=%s action=%s max_seconds=%.0f",
        phase,
        depth0,
        batch0,
        cap,
        (meta0 or {}).get("action"),
        max_seconds,
    )

    totals = {
        "rounds": 0,
        "processed": 0,
        "approved": 0,
        "skipped": 0,
        "errors": 0,
    }
    t0 = time.monotonic()
    while True:
        remaining = max_seconds - (time.monotonic() - t0)
        if remaining <= 0:
            logger.info("phase=%s stopping: wall clock exhausted", phase)
            break
        batch, meta = await tuner.resolve_batch()
        head = await asyncio.to_thread(_sample_headroom)
        # Light throttle if host is tight
        if min(head["cpu_avail"], head["ram_avail"]) < 0.12:
            logger.info("phase=%s low headroom — pausing 15s", phase)
            await asyncio.sleep(15.0)
            continue

        t_batch = time.monotonic()
        stats = await asyncio.to_thread(runner, batch)
        elapsed = time.monotonic() - t_batch
        await tuner.record_yield(stats, batch_limit=batch)

        processed = int(stats.get("processed") or 0)
        approved = int(stats.get("approved") or 0)
        skipped = int(stats.get("skipped") or 0)
        errors = int(stats.get("errors") or 0)
        totals["rounds"] += 1
        totals["processed"] += processed
        totals["approved"] += approved
        totals["skipped"] += skipped
        totals["errors"] += errors

        logger.info(
            "phase=%s round=%s batch=%s action=%s processed=%s approved=%s "
            "skipped=%s errors=%s elapsed=%.1fs idle=%s",
            phase,
            totals["rounds"],
            batch,
            (meta or {}).get("action"),
            processed,
            approved,
            skipped,
            errors,
            elapsed,
            bool(stats.get("idle")),
        )

        if stats.get("idle") or processed == 0:
            tuner.idle_streak += 1
            if tuner.idle_streak >= max_idle_rounds:
                logger.info(
                    "phase=%s idle for %s rounds — backlog clear",
                    phase,
                    tuner.idle_streak,
                )
                break
            await asyncio.sleep(3.0)
        else:
            tuner.idle_streak = 0
            await asyncio.sleep(0)

    depth1 = await asyncio.to_thread(_queue_depth, phase)
    summary = {
        "phase": phase,
        "started": started,
        "finished": datetime.now(timezone.utc).isoformat(),
        "depth_before": depth0,
        "depth_after": depth1,
        "batch_cap": cap,
        "final_batch": tuner.batch_limit,
        "tune_count": tuner.tune_count,
        **totals,
        "host": os.uname().nodename if hasattr(os, "uname") else "",
    }
    logger.info("phase=%s done %s", phase, json.dumps(summary))
    return summary


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    phases = [p.strip() for p in args.phases.split(",") if p.strip()]
    unknown = [p for p in phases if p not in SUPPORTED]
    if unknown:
        raise SystemExit(f"unsupported phases: {unknown}; supported={sorted(SUPPORTED)}")
    if not phases:
        raise SystemExit("no phases specified")

    max_seconds = float(args.max_seconds)
    if args.hours and args.hours > 0:
        max_seconds = float(args.hours) * 3600.0

    # Equal wall-clock share per phase (last phase gets any remainder).
    per = max_seconds / len(phases)
    results: list[dict[str, Any]] = []
    t_chain = time.monotonic()
    for i, phase in enumerate(phases):
        elapsed = time.monotonic() - t_chain
        remaining = max(60.0, max_seconds - elapsed)
        if i < len(phases) - 1:
            budget = min(per, remaining)
        else:
            budget = remaining
        logger.info("=== burning %s (budget=%.0fs) ===", phase, budget)
        results.append(
            await burn_phase(
                phase,
                max_seconds=budget,
                auto=bool(args.auto),
                batch_cap=int(args.batch_cap) if int(args.batch_cap) > 0 else 0,
                max_idle_rounds=int(args.max_idle_rounds),
            )
        )
    return {
        "phases": results,
        "finished": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Phase catch-up burndown (membership / graph drift)")
    p.add_argument(
        "--phases",
        default="graph_link_drift_review,storyline_membership_review",
        help="Comma-separated phase list",
    )
    p.add_argument("--hours", type=float, default=0.0)
    p.add_argument("--max-seconds", type=float, default=7200.0)
    p.add_argument(
        "--batch-cap",
        type=int,
        default=0,
        help="Max adaptive batch (0 = per-phase default cap)",
    )
    p.add_argument("--max-idle-rounds", type=int, default=3)
    p.add_argument("--auto", dest="auto", action="store_true", default=True)
    p.add_argument("--no-auto", dest="auto", action="store_false")
    p.add_argument("--log-file", default="")
    args = p.parse_args()

    if args.log_file:
        fh = logging.FileHandler(args.log_file)
        fh.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [phase-burndown] %(message)s")
        )
        logging.getLogger().addHandler(fh)

    summary = asyncio.run(_run(args))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
