#!/usr/bin/env python3
"""
One-shot claims_to_facts (CTF) backlog burndown — PopOS catch-up with auto-tune.

Does **not** change Widow ownership or PopOS phase workers. Shares rows with the live
AutomationManager drain via ``FOR UPDATE … SKIP LOCKED``.

Auto-tune (default on):
  - batch size via ``resolve_adaptive_batch("claims_to_facts", …)`` (headroom + yield gate)
  - ``CLAIMS_TO_FACTS_CHUNK_SIZE`` raised to match batch so large limits are not chopped to 50
  - concurrency (parallel promote workers) scaled from CPU/RAM headroom + recent promote rate

Examples:

  PYTHONPATH=api .venv/bin/python api/scripts/burn_down_claims_to_facts.py --hours 4
  PYTHONPATH=api .venv/bin/python api/scripts/burn_down_claims_to_facts.py --hours 4 --no-auto
  PYTHONPATH=api .venv/bin/python api/scripts/burn_down_claims_to_facts.py --hours 2 --max-workers 4
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
from typing import Any

_API = Path(__file__).resolve().parent.parent
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [ctf-burndown] %(message)s",
)
logger = logging.getLogger("ctf_burndown")

PHASE = "claims_to_facts"


def _queue_depth() -> int | None:
    try:
        from shared.pipeline_queue_counts import get_phase_queue_depth

        return int(get_phase_queue_depth(PHASE) or 0)
    except Exception as exc:
        logger.debug("queue_depth failed: %s", exc)
        return None


def _deferred_count() -> int | None:
    try:
        from shared.database.connection import get_db_connection_context

        with get_db_connection_context() as conn:
            if not conn:
                return None
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM intelligence.extracted_claims
                    WHERE metadata->>'promotion_skip' = 'unresolved_subject'
                    """
                )
                return int(cur.fetchone()[0] or 0)
    except Exception as exc:
        logger.debug("deferred_count failed: %s", exc)
        return None


def _sample_headroom() -> dict[str, float]:
    """Return cpu_avail / ram_avail in 0..1 (best-effort)."""
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


@dataclass
class BurndownTuner:
    """Shared adaptive state for batch size + concurrency."""

    auto: bool = True
    fixed_batch: int = 200
    fixed_workers: int = 2
    min_workers: int = 1
    max_workers: int = 4
    default_batch: int = 500
    batch_cap: int = 2000
    concurrency: int = 2
    batch_limit: int = 500
    chunk_size: int = 100
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    # rolling promote rate (claims/sec) for concurrency decisions
    _rate_samples: list[float] = field(default_factory=list)
    last_meta: dict[str, Any] = field(default_factory=dict)
    tune_count: int = 0

    def _apply_chunk_env(self, batch: int) -> int:
        """Align promote TX chunk with batch (cap 1000 per service helper)."""
        chunk = max(50, min(1000, int(batch)))
        os.environ["CLAIMS_TO_FACTS_CHUNK_SIZE"] = str(chunk)
        self.chunk_size = chunk
        return chunk

    def _cap_batch(self, batch: int) -> int:
        """Burndown soft-cap — adaptive catchup_boost can jump to 10k–100k otherwise."""
        return max(1, min(int(batch), int(self.batch_cap)))

    async def resolve_batch(self) -> tuple[int, dict[str, Any]]:
        async with self.lock:
            if not self.auto:
                self.batch_limit = self._cap_batch(max(1, int(self.fixed_batch)))
                self._apply_chunk_env(self.batch_limit)
                meta = {"adaptive": False, "action": "fixed", "batch_after": self.batch_limit}
                self.last_meta = meta
                return self.batch_limit, meta

            def _resolve() -> tuple[int, dict[str, Any]]:
                from shared.adaptive_batch_policy import resolve_adaptive_batch

                return resolve_adaptive_batch(PHASE, int(self.default_batch))

            batch, meta = await asyncio.to_thread(_resolve)
            raw = max(1, int(batch))
            capped = self._cap_batch(raw)
            meta = dict(meta or {})
            if capped < raw:
                meta["burndown_cap"] = capped
                meta["adaptive_raw"] = raw
                meta["action"] = f"{meta.get('action') or 'ok'},capped"
            self.batch_limit = capped
            self._apply_chunk_env(capped)
            self.last_meta = meta
            self.tune_count += 1
            return capped, meta

    async def record_yield(self, stats: dict[str, Any], *, batch_limit: int, elapsed: float) -> None:
        promoted = int(stats.get("promoted") or 0)
        candidates = int(stats.get("candidates") or 0)
        unresolved = int(stats.get("unresolved_subject") or 0)
        deferred = int(stats.get("deferred_unresolved") or 0)
        failed = int(stats.get("insert_failed") or 0)
        skipped = unresolved + deferred
        if elapsed > 0 and promoted > 0:
            self._rate_samples.append(promoted / elapsed)
            self._rate_samples = self._rate_samples[-12:]

        if not self.auto:
            return

        def _record() -> None:
            from shared.adaptive_batch_policy import record_adaptive_batch_yield

            record_adaptive_batch_yield(
                PHASE,
                approved=promoted,
                rejected=0,
                skipped=skipped,
                errors=failed,
                batch_limit=batch_limit,
            )

        try:
            await asyncio.to_thread(_record)
        except Exception as exc:
            logger.debug("record_yield: %s", exc)

    async def retune_concurrency(self) -> int:
        """Adjust parallel workers from headroom + recent promote throughput."""
        async with self.lock:
            if not self.auto:
                self.concurrency = max(1, int(self.fixed_workers))
                return self.concurrency

            head = await asyncio.to_thread(_sample_headroom)
            cpu = float(head.get("cpu_avail") or 0.5)
            ram = float(head.get("ram_avail") or 0.5)
            headroom = min(cpu, ram)
            avg_rate = (
                sum(self._rate_samples) / len(self._rate_samples) if self._rate_samples else 0.0
            )
            prev = int(self.concurrency)
            desired = prev
            # Scale up when headroom and throughput look healthy
            if headroom >= 0.40 and avg_rate >= 5.0 and prev < self.max_workers:
                desired = prev + 1
            elif headroom >= 0.55 and prev < self.max_workers and avg_rate >= 2.0:
                desired = prev + 1
            # Scale down when tight
            elif headroom < 0.20 and prev > self.min_workers:
                desired = prev - 1
            elif headroom < 0.12:
                desired = self.min_workers
            desired = max(self.min_workers, min(self.max_workers, desired))
            self.concurrency = desired
            if desired != prev:
                logger.info(
                    "auto concurrency %s→%s (cpu_avail=%.2f ram_avail=%.2f rate=%.1f/s)",
                    prev,
                    desired,
                    cpu,
                    ram,
                    avg_rate,
                )
            return desired


async def _promote_once(batch_limit: int) -> dict[str, Any]:
    from services.claim_extraction_service import promote_claims_to_versioned_facts

    t0 = time.monotonic()
    stats = await asyncio.to_thread(promote_claims_to_versioned_facts, None, int(batch_limit))
    elapsed = time.monotonic() - t0
    if not isinstance(stats, dict):
        stats = {"promoted": 0, "candidates": 0}
    stats = dict(stats)
    stats["_elapsed"] = elapsed
    return stats


async def _worker_loop(
    *,
    worker_id: int,
    tuner: BurndownTuner,
    max_seconds: float,
    stop_event: asyncio.Event,
    slot_sem: asyncio.Semaphore,
) -> dict[str, int]:
    totals = {"promoted": 0, "batches": 0, "rounds": 0}
    t0 = time.monotonic()
    while not stop_event.is_set():
        remaining = max_seconds - (time.monotonic() - t0)
        if remaining <= 0:
            break
        async with slot_sem:
            if stop_event.is_set():
                break
            batch, meta = await tuner.resolve_batch()
            stats = await _promote_once(batch)
            await tuner.record_yield(
                stats, batch_limit=batch, elapsed=float(stats.get("_elapsed") or 0.0)
            )
            promoted = int(stats.get("promoted") or 0)
            candidates = int(stats.get("candidates") or 0)
            totals["promoted"] += promoted
            totals["batches"] += 1
            totals["rounds"] += 1
            logger.info(
                "worker=%s round=%s batch=%s action=%s promoted=%s/%s deferred=%s "
                "elapsed=%.1fs total_promoted=%s",
                worker_id,
                totals["rounds"],
                batch,
                (meta or {}).get("action"),
                promoted,
                candidates,
                stats.get("deferred_unresolved") or stats.get("unresolved_subject") or 0,
                float(stats.get("_elapsed") or 0.0),
                totals["promoted"],
            )
            if candidates == 0:
                await asyncio.sleep(2.0)
            elif promoted == 0:
                await asyncio.sleep(0.5)
        # Periodically retune concurrency (all workers may call; lock serializes)
        if totals["rounds"] % 3 == 0:
            await tuner.retune_concurrency()
            # Resize semaphore capacity by releasing/acquiring is awkward;
            # concurrency is enforced via a shared desired count checked below.
        await asyncio.sleep(0)
    return totals


class DynamicSemaphore:
    """Semaphore whose max permits can grow/shrink (best-effort)."""

    def __init__(self, value: int) -> None:
        self._value = max(1, int(value))
        self._sem = asyncio.Semaphore(self._value)
        self._lock = asyncio.Lock()

    @property
    def value(self) -> int:
        return self._value

    async def set_value(self, new: int) -> None:
        new = max(1, int(new))
        async with self._lock:
            if new == self._value:
                return
            if new > self._value:
                for _ in range(new - self._value):
                    self._sem.release()
            # shrinking: just lower target; excess in-flight finish naturally
            self._value = new

    async def __aenter__(self):
        await self._sem.acquire()
        return self

    async def __aexit__(self, *args):
        self._sem.release()


async def _run(args: argparse.Namespace) -> dict:
    started = datetime.now(timezone.utc).isoformat()
    auto = bool(args.auto)
    max_workers = max(1, int(args.max_workers))
    min_workers = max(1, min(int(args.min_workers), max_workers))
    if args.workers and int(args.workers) > 0:
        initial = max(min_workers, min(max_workers, int(args.workers)))
    else:
        initial = min(2, max_workers) if auto else 2

    fixed_batch = int(args.batch_limit) if int(args.batch_limit) > 0 else 500
    tuner = BurndownTuner(
        auto=auto,
        fixed_batch=fixed_batch,
        fixed_workers=initial,
        min_workers=min_workers,
        max_workers=max_workers,
        default_batch=max(500, fixed_batch),
        batch_cap=max(100, int(args.batch_cap)),
        concurrency=initial,
        batch_limit=fixed_batch,
    )
    # Seed first batch immediately
    batch0, meta0 = await tuner.resolve_batch()
    logger.info(
        "start hours=%.2f auto=%s batch=%s action=%s workers=%s..%s (initial=%s) "
        "chunk=%s batch_cap=%s max_seconds=%.0f meta=%s",
        args.hours if args.hours else args.max_seconds / 3600.0,
        auto,
        batch0,
        (meta0 or {}).get("action"),
        min_workers,
        max_workers,
        initial,
        tuner.chunk_size,
        tuner.batch_cap,
        float(args.max_seconds),
        {
            k: (meta0 or {}).get(k)
            for k in (
                "adaptive",
                "reason",
                "batch_before",
                "batch_after",
                "yield_gate",
                "burndown_cap",
                "adaptive_raw",
            )
            if (meta0 or {}).get(k) is not None
        },
    )

    stop_event = asyncio.Event()
    max_seconds = float(args.max_seconds)
    slot_sem = DynamicSemaphore(initial)

    depth_task = asyncio.create_task(asyncio.to_thread(_queue_depth))
    deferred_task = asyncio.create_task(asyncio.to_thread(_deferred_count))

    async def _log_baseline() -> tuple[int | None, int | None]:
        d0 = await depth_task
        def0 = await deferred_task
        logger.info("baseline depth=%s deferred=%s", d0, def0)
        return d0, def0

    baseline_task = asyncio.create_task(_log_baseline())

    # Launch max_workers loops; DynamicSemaphore caps how many promote at once
    worker_tasks = [
        asyncio.create_task(
            _worker_loop(
                worker_id=i + 1,
                tuner=tuner,
                max_seconds=max_seconds,
                stop_event=stop_event,
                slot_sem=slot_sem,  # type: ignore[arg-type]
            )
        )
        for i in range(max_workers)
    ]

    async def _concurrency_controller() -> None:
        while not stop_event.is_set():
            desired = await tuner.retune_concurrency()
            await slot_sem.set_value(desired)
            await asyncio.sleep(15.0)

    ctrl = asyncio.create_task(_concurrency_controller())
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*worker_tasks, return_exceptions=True),
            timeout=max_seconds + 90.0,
        )
    except asyncio.TimeoutError:
        stop_event.set()
        results = await asyncio.gather(*worker_tasks, return_exceptions=True)
    finally:
        stop_event.set()
        ctrl.cancel()
        try:
            await ctrl
        except asyncio.CancelledError:
            pass

    try:
        depth0, deferred0 = await baseline_task
    except Exception:
        depth0, deferred0 = None, None

    promoted = 0
    batches = 0
    rounds = 0
    errors: list[str] = []
    for r in results:
        if isinstance(r, Exception):
            errors.append(str(r)[:300])
            continue
        if isinstance(r, dict):
            promoted += int(r.get("promoted") or 0)
            batches += int(r.get("batches") or 0)
            rounds += int(r.get("rounds") or 0)

    depth_after = await asyncio.to_thread(_queue_depth)
    deferred_after = await asyncio.to_thread(_deferred_count)
    summary = {
        "started": started,
        "finished": datetime.now(timezone.utc).isoformat(),
        "promoted": promoted,
        "batches": batches,
        "rounds": rounds,
        "depth_before": depth0,
        "depth_after": depth_after,
        "deferred_before": deferred0,
        "deferred_after": deferred_after,
        "auto": auto,
        "final_batch_limit": tuner.batch_limit,
        "final_chunk_size": tuner.chunk_size,
        "final_concurrency": tuner.concurrency,
        "tune_count": tuner.tune_count,
        "last_meta": {
            k: tuner.last_meta.get(k)
            for k in ("action", "reason", "batch_before", "batch_after", "yield_gate")
            if tuner.last_meta.get(k) is not None
        },
        "errors": errors,
        "host": os.uname().nodename if hasattr(os, "uname") else "",
    }
    logger.info("done %s", json.dumps(summary))
    return summary


def main() -> int:
    p = argparse.ArgumentParser(description="One-shot CTF backlog burndown with auto-tune")
    p.add_argument("--hours", type=float, default=0.0)
    p.add_argument("--max-seconds", type=float, default=14400.0)
    p.add_argument(
        "--batch-limit",
        type=int,
        default=0,
        help="Fixed batch when --no-auto; with --auto used as adaptive default seed (0→500)",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=0,
        help="Initial concurrency (0→auto pick 2, capped by --max-workers)",
    )
    p.add_argument("--min-workers", type=int, default=1)
    p.add_argument("--max-workers", type=int, default=4)
    p.add_argument(
        "--batch-cap",
        type=int,
        default=2000,
        help="Max claims per promote() under --auto (default 2000; prevents catchup_boost 50k+)",
    )
    p.add_argument(
        "--auto",
        dest="auto",
        action="store_true",
        default=True,
        help="Enable adaptive batch + concurrency (default)",
    )
    p.add_argument(
        "--no-auto",
        dest="auto",
        action="store_false",
        help="Disable auto-tune; use fixed --batch-limit / --workers",
    )
    p.add_argument("--log-file", default="")
    p.add_argument("--once", action="store_true", help="Short single-pass budget (~15 min)")
    args = p.parse_args()
    if args.hours and args.hours > 0:
        args.max_seconds = float(args.hours) * 3600.0
    if args.once:
        args.max_seconds = min(float(args.max_seconds), 900.0)
        args.max_workers = 1
        args.workers = 1

    if args.log_file:
        fh = logging.FileHandler(args.log_file)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [ctf-burndown] %(message)s"))
        logging.getLogger().addHandler(fh)

    summary = asyncio.run(_run(args))
    print(json.dumps(summary, indent=2))
    return 1 if summary.get("errors") else 0


if __name__ == "__main__":
    raise SystemExit(main())
