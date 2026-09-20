#!/usr/bin/env python3
"""
News Intelligence — PopOS phase worker.

Claims spine / phase work from Widow Postgres (PgBouncer) and runs drains locally
against PopOS Ollama. Widow API must set REMOTE_PHASE_WORKER_OWNED_PHASES (or
REMOTE_PHASE_WORKER_ENABLED=true) so AutomationManager does not also drain those phases.

Deploy on PopOS only (not Widow):
  WORKER_EXECUTION_HOST=popos
  WORKER_PHASES=unified_intake_extraction
  DB_HOST=192.168.93.101 DB_PORT=6432
  OLLAMA_HOST=http://127.0.0.1:11434
  OLLAMA_DUAL_HOST_ROUTING_ENABLED=false

Usage:
  python scripts/run_popos_phase_worker.py
  python scripts/run_popos_phase_worker.py --once
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_DIR = PROJECT_ROOT / "api"
sys.path.insert(0, str(API_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

env_file = PROJECT_ROOT / ".env"
if env_file.exists():
    try:
        from dotenv import load_dotenv

        load_dotenv(env_file, override=False)
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("popos_phase_worker")

DEFAULT_SLEEP_IDLE_SEC = 15
DEFAULT_BUDGET_SEC = 900
# When Widow/DB is unreachable, back off hard so workers do not storm a dying host.
DEFAULT_DB_UNREACHABLE_BACKOFF_SEC = 120
DEFAULT_DB_UNREACHABLE_BACKOFF_MAX_SEC = 600


def _ensure_worker_env() -> None:
    os.environ.setdefault("WORKER_EXECUTION_HOST", "popos")
    os.environ.setdefault("WORKER_PHASES", "unified_intake_extraction,claim_extraction,topic_clustering,storyline_assembly")
    # Local Ollama on PopOS — do not bounce back to Widow.
    os.environ.setdefault("OLLAMA_HOST", "http://127.0.0.1:11434")
    os.environ.setdefault("OLLAMA_DUAL_HOST_ROUTING_ENABLED", "false")
    os.environ.setdefault("AUTOMATION_DUAL_LANE", "false")
    os.environ.setdefault("BULK_DUAL_LANE_CATCHUP", "false")
    os.environ.setdefault("OLLAMA_MODEL_EXTRACTION", "qwen3.6:latest")
    os.environ.setdefault("OLLAMA_USE_QWEN_FOR_EXTRACTION", "true")


def _db_unreachable_error_text(err: str) -> bool:
    low = (err or "").lower()
    needles = (
        "no route to host",
        "connection refused",
        "could not connect",
        "network is unreachable",
        "server closed the connection unexpectedly",
        "connection timed out",
        "timeout expired",
        "database connection failed",
        "pool timeout",
    )
    return any(n in low for n in needles)


def _summary_indicates_db_unreachable(summary: dict[str, object]) -> bool:
    phases = summary.get("phases") or {}
    if not isinstance(phases, dict):
        return False
    for payload in phases.values():
        if not isinstance(payload, dict):
            continue
        err = payload.get("error")
        if err is not None and _db_unreachable_error_text(str(err)):
            return True
    return False


def _probe_widow_db(timeout_sec: float = 3.0) -> tuple[bool, str]:
    """Cheap TCP/SQL probe before a drain cycle. Returns (ok, detail)."""
    import socket

    host = (os.getenv("DB_HOST") or "127.0.0.1").strip()
    try:
        port = int(os.getenv("DB_PORT") or "6432")
    except ValueError:
        port = 6432
    try:
        with socket.create_connection((host, port), timeout=timeout_sec):
            return True, f"{host}:{port} open"
    except OSError as exc:
        return False, f"{host}:{port} {exc}"


def _db_unreachable_backoff_sec(streak: int) -> int:
    try:
        base = max(30, int(os.getenv("POPOS_DB_UNREACHABLE_BACKOFF_SEC", str(DEFAULT_DB_UNREACHABLE_BACKOFF_SEC))))
    except ValueError:
        base = DEFAULT_DB_UNREACHABLE_BACKOFF_SEC
    try:
        cap = max(base, int(os.getenv("POPOS_DB_UNREACHABLE_BACKOFF_MAX_SEC", str(DEFAULT_DB_UNREACHABLE_BACKOFF_MAX_SEC))))
    except ValueError:
        cap = DEFAULT_DB_UNREACHABLE_BACKOFF_MAX_SEC
    # 120, 240, 480, ... capped
    return min(cap, base * (2 ** max(0, streak - 1)))


async def _run_one_cycle(
    phases: list[str],
    budget_seconds: int,
    *,
    worker_id: str = "default",
    idle_backoff: object | None = None,
) -> dict[str, object]:
    from services.pipeline_phase_heartbeat_service import record_phase_heartbeat
    from shared.phase_drain_dispatch import drain_phase
    from shared.phase_idle_gate import (
        PhaseIdleBackoff,
        decide_phase_action,
        drain_result_had_work,
        idle_gate_enabled,
    )
    from shared.remote_phase_worker import phase_supported_by_popos_worker

    if idle_backoff is None:
        idle_backoff = PhaseIdleBackoff()
    assert isinstance(idle_backoff, PhaseIdleBackoff)

    summary: dict[str, object] = {"phases": {}, "min_backoff_remaining_sec": None}
    gate_on = idle_gate_enabled()
    min_rem: float | None = None

    for phase in phases:
        if not phase_supported_by_popos_worker(phase):
            logger.warning("skip unsupported phase %s", phase)
            continue

        decision = decide_phase_action(phase, idle_backoff, enabled=gate_on)
        action = str(decision.get("action") or "drain")
        if action == "skip_backoff":
            rem = float(decision.get("delay_sec") or 0.0)
            logger.info(
                "skip %s: idle backoff %.0fs remaining (streak=%s)",
                phase,
                rem,
                idle_backoff.streak(phase),
            )
            summary["phases"][phase] = {
                "skipped": "backoff",
                "backoff_remaining_sec": round(rem, 1),
                "idle_streak": idle_backoff.streak(phase),
            }
            min_rem = rem if min_rem is None else min(min_rem, rem)
            continue
        if action == "skip_idle":
            delay = float(decision.get("delay_sec") or 0.0)
            logger.info(
                "skip %s: no eligible work (backoff %.0fs, streak=%s)",
                phase,
                delay,
                idle_backoff.streak(phase),
            )
            summary["phases"][phase] = {
                "skipped": "idle",
                "backoff_sec": round(delay, 1),
                "idle_streak": idle_backoff.streak(phase),
            }
            rem = idle_backoff.remaining_seconds(phase)
            min_rem = rem if min_rem is None else min(min_rem, rem)
            continue

        # Start heartbeat so Monitor Current activity can show in-flight PopOS work.
        record_phase_heartbeat(
            phase,
            scheduler_path="popos_worker",
            success=True,
            items_processed=0,
            detail={
                "host": "popos",
                "status": "running",
                "worker_id": worker_id,
            },
        )
        try:
            result = await drain_phase(phase, budget_seconds=budget_seconds)
            summary["phases"][phase] = result
            logger.info("phase %s result=%s", phase, result)
            items = 0
            if isinstance(result, dict):
                for key in (
                    "processed",
                    "claims_inserted",
                    "profiles_updated",
                    "articles_processed",
                    "articles_linked",
                    "llm_processed",
                ):
                    if isinstance(result.get(key), int):
                        items = max(items, int(result[key]))
            if drain_result_had_work(result):
                idle_backoff.mark_work(phase)
                # UIE runs on PopOS under REMOTE_PHASE_WORKER_OWNED_PHASES — Widow never
                # executes after_unified_intake. Nudge CE catchup + coref via Widow API.
                if phase == "unified_intake_extraction" and items > 0:
                    try:
                        from shared.pipeline_handoffs import nudge_event_rail_after_uie

                        nudged = nudge_event_rail_after_uie(articles_processed=items)
                        if nudged:
                            logger.info(
                                "uie handoff nudged %s Widow phase(s) after %s articles",
                                nudged,
                                items,
                            )
                    except Exception as e:
                        logger.debug("uie remote handoff nudge: %s", e)
                # CE catchup on PopOS → wake Widow coreference (local DB phase).
                if phase == "chronological_events_catchup":
                    saved = 0
                    if isinstance(result, dict):
                        saved = int(result.get("saved_total") or 0)
                    if saved > 0:
                        try:
                            from shared.pipeline_handoffs import nudge_widow_phases

                            n = nudge_widow_phases(
                                ["event_deduplication"],
                                reason="after_ce_catchup_remote",
                            )
                            if n:
                                logger.info(
                                    "catchup handoff nudged event_deduplication (%s saved)",
                                    saved,
                                )
                        except Exception as e:
                            logger.debug("catchup remote handoff nudge: %s", e)
            else:
                hint = None
                if isinstance(result, dict):
                    raw_hint = result.get("idle_backoff_seconds")
                    if isinstance(raw_hint, (int, float)) and float(raw_hint) > 0:
                        hint = float(raw_hint)
                delay = idle_backoff.mark_idle(phase, delay_seconds=hint)
                logger.info(
                    "phase %s empty drain — idle backoff %.0fs (streak=%s hint=%s)",
                    phase,
                    delay,
                    idle_backoff.streak(phase),
                    hint,
                )
                rem = idle_backoff.remaining_seconds(phase)
                min_rem = rem if min_rem is None else min(min_rem, rem)
            record_phase_heartbeat(
                phase,
                scheduler_path="popos_worker",
                success=not (isinstance(result, dict) and result.get("error")),
                items_processed=items,
                detail={
                    "host": "popos",
                    "status": "complete",
                    "worker_id": worker_id,
                    "result_keys": list(result) if isinstance(result, dict) else [],
                },
            )
        except Exception as exc:
            logger.exception("phase %s failed: %s", phase, exc)
            summary["phases"][phase] = {"error": str(exc)[:300]}
            record_phase_heartbeat(
                phase,
                scheduler_path="popos_worker",
                success=False,
                items_processed=0,
                detail={
                    "host": "popos",
                    "status": "failed",
                    "worker_id": worker_id,
                    "error": str(exc)[:200],
                },
            )

    if min_rem is not None:
        summary["min_backoff_remaining_sec"] = round(min_rem, 1)
    return summary


def _cycle_sleep_seconds(
    idle_sleep: int,
    summary: dict[str, object],
    idle_backoff: object,
    phases: list[str],
) -> int:
    """Sleep at least idle_sleep; when all phases are idle/backed-off, wait for wake."""
    base = max(5, int(idle_sleep))
    phase_results = summary.get("phases") or {}
    if not isinstance(phase_results, dict):
        return base
    # If any phase actually drained (not skipped), keep the short poll interval.
    for payload in phase_results.values():
        if not isinstance(payload, dict):
            continue
        if payload.get("skipped") in ("idle", "backoff"):
            continue
        if payload.get("error"):
            continue
        return base

    try:
        from shared.phase_idle_gate import PhaseIdleBackoff

        if not isinstance(idle_backoff, PhaseIdleBackoff):
            return base
        rems = [idle_backoff.remaining_seconds(p) for p in phases]
        rems = [r for r in rems if r > 0]
        if not rems:
            return base
        wake = int(min(rems)) + 1
        return max(base, min(wake, int(idle_backoff.max)))
    except Exception:
        return base


def main() -> int:
    parser = argparse.ArgumentParser(description="PopOS NI phase worker")
    parser.add_argument("--once", action="store_true", help="Single drain cycle then exit")
    parser.add_argument("--budget-seconds", type=int, default=DEFAULT_BUDGET_SEC)
    parser.add_argument(
        "--idle-sleep",
        type=int,
        default=DEFAULT_SLEEP_IDLE_SEC,
        help="Seconds between cycles when idle",
    )
    parser.add_argument(
        "--phases",
        default="",
        help=(
            "Comma-separated phase list (overrides WORKER_PHASES). "
            "Use for split workers: e.g. unified_intake_extraction"
        ),
    )
    parser.add_argument(
        "--worker-id",
        default="",
        help="Optional label for logs/heartbeats (e.g. uie, claim_topic, assembly)",
    )
    args = parser.parse_args()

    _ensure_worker_env()
    if args.phases.strip():
        os.environ["WORKER_PHASES"] = args.phases.strip()

    # Remap missing extraction tags (e.g. qwen2.5:7b → installed qwen3.6:latest).
    try:
        from shared.ollama_extraction_model_resolver import (
            resolve_extraction_models_at_startup,
        )

        resolved = resolve_extraction_models_at_startup()
        logger.info(
            "extraction model resolve: %s",
            resolved.get("resolved_model") or resolved,
        )
    except Exception as exc:
        logger.warning("extraction model resolve failed (continuing): %s", exc)

    from shared.phase_idle_gate import PhaseIdleBackoff, idle_gate_enabled
    from shared.remote_phase_worker import is_remote_phase_worker_process, worker_phases

    if not is_remote_phase_worker_process():
        logger.error("WORKER_EXECUTION_HOST must be popos/remote/worker")
        return 2

    # Preserve --phases CSV order when set; otherwise stable sort of WORKER_PHASES.
    raw_phases = (os.environ.get("WORKER_PHASES") or "").strip()
    if raw_phases:
        phases = [x.strip() for x in raw_phases.split(",") if x.strip()]
        # Keep only supported / configured worker phases, in given order.
        allowed = worker_phases()
        phases = [p for p in phases if p in allowed] or sorted(allowed)
    else:
        phases = sorted(worker_phases())
    if not phases:
        logger.error("WORKER_PHASES empty")
        return 2

    worker_id = (args.worker_id or "").strip() or "default"
    idle_backoff = PhaseIdleBackoff()
    logger.info(
        "Starting PopOS phase worker id=%s phases=%s idle_gate=%s "
        "backoff_base=%.0fs backoff_max=%.0fs DB=%s:%s/%s OLLAMA=%s",
        worker_id,
        phases,
        idle_gate_enabled(),
        idle_backoff.base,
        idle_backoff.max,
        os.getenv("DB_HOST", ""),
        os.getenv("DB_PORT", ""),
        os.getenv("DB_NAME", "news_intel"),
        os.getenv("OLLAMA_HOST", ""),
    )

    cycle = 0
    db_fail_streak = 0
    while True:
        cycle += 1
        logger.info("=== Cycle %d ===", cycle)
        ok, probe_detail = _probe_widow_db()
        if not ok:
            db_fail_streak += 1
            backoff = _db_unreachable_backoff_sec(db_fail_streak)
            logger.error(
                "Widow DB unreachable (%s); skipping cycle and backing off %ss "
                "(streak=%s) — refuse to storm a down/OOM host",
                probe_detail,
                backoff,
                db_fail_streak,
            )
            if args.once:
                return 2
            time.sleep(backoff)
            continue

        t0 = time.monotonic()
        try:
            from services.pipeline_phase_heartbeat_service import record_phase_heartbeat
            from services.pipeline_schedule_service import (
                automation_phase_allowed,
                popos_gpu_work_allowed,
                active_pipeline_window,
            )

            if not popos_gpu_work_allowed():
                runnable = [p for p in phases if automation_phase_allowed(p)]
                if not runnable:
                    win = active_pipeline_window()
                    logger.info(
                        "schedule window=%s — PopOS GPU deferred (desk_light); "
                        "skipping phases=%s",
                        win,
                        phases,
                    )
                    try:
                        record_phase_heartbeat(
                            f"__popos_worker__{worker_id}",
                            scheduler_path="popos_worker",
                            success=True,
                            items_processed=0,
                            detail={
                                "host": "popos",
                                "status": "desk_gpu_deferred",
                                "worker_id": worker_id,
                                "cycle": cycle,
                                "phases": phases,
                                "active_window": win,
                            },
                        )
                    except Exception:
                        pass
                    if args.once:
                        return 0
                    time.sleep(max(int(args.idle_sleep), 60))
                    continue
                cycle_phases = runnable
            else:
                cycle_phases = phases

            record_phase_heartbeat(
                f"__popos_worker__{worker_id}",
                scheduler_path="popos_worker",
                success=True,
                items_processed=0,
                detail={
                    "host": "popos",
                    "status": "running",
                    "worker_id": worker_id,
                    "cycle": cycle,
                    "phases": cycle_phases,
                },
            )
        except Exception as hb_exc:
            logger.debug("popos worker cycle start heartbeat: %s", hb_exc)
            cycle_phases = phases
        summary = asyncio.run(
            _run_one_cycle(
                cycle_phases,
                args.budget_seconds,
                worker_id=worker_id,
                idle_backoff=idle_backoff,
            )
        )
        elapsed = time.monotonic() - t0
        logger.info("cycle %d done in %.1fs summary=%s", cycle, elapsed, summary)
        if _summary_indicates_db_unreachable(summary):
            db_fail_streak += 1
            backoff = _db_unreachable_backoff_sec(db_fail_streak)
            logger.error(
                "Cycle reported DB unreachable; backing off %ss (streak=%s)",
                backoff,
                db_fail_streak,
            )
            if args.once:
                return 2
            time.sleep(backoff)
            continue
        db_fail_streak = 0
        try:
            from services.pipeline_phase_heartbeat_service import record_phase_heartbeat

            record_phase_heartbeat(
                f"__popos_worker__{worker_id}",
                scheduler_path="popos_worker",
                success=True,
                items_processed=0,
                detail={
                    "host": "popos",
                    "status": "complete",
                    "worker_id": worker_id,
                    "cycle": cycle,
                    "phases": phases,
                    "elapsed_sec": round(elapsed, 1),
                    "summary_phases": list((summary.get("phases") or {}).keys()),
                },
            )
        except Exception as hb_exc:
            logger.debug("popos worker cycle heartbeat: %s", hb_exc)
        if args.once:
            return 0
        sleep_s = _cycle_sleep_seconds(args.idle_sleep, summary, idle_backoff, phases)
        if sleep_s > int(args.idle_sleep):
            logger.info("all/most phases idle — sleeping %ss (backoff-aware)", sleep_s)
        time.sleep(sleep_s)


if __name__ == "__main__":
    raise SystemExit(main())
