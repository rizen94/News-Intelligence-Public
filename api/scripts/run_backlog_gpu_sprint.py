#!/usr/bin/env python3
"""
One-off full-pipeline backlog burndown on PopOS GPU (GPU-only, large batches).

  PYTHONPATH=api python3 api/scripts/run_backlog_gpu_sprint.py --dry-run
  PYTHONPATH=api python3 api/scripts/run_backlog_gpu_sprint.py --force

Checkpoint: data/backlog_gpu_sprint_state.json
Operator shell: scripts/run_backlog_gpu_sprint.sh
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

_API_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _API_ROOT.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

CHECKPOINT_PATH = _REPO_ROOT / "data" / "backlog_gpu_sprint_state.json"

logger = logging.getLogger(__name__)


def _load_env() -> None:
    from shared.catchup_bootstrap import bootstrap_catchup

    bootstrap_catchup(bulk_active=False)


def _load_checkpoint() -> dict:
    if CHECKPOINT_PATH.is_file():
        try:
            return json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"started_at": None, "phases": {}, "current_phase": None}


def _save_checkpoint(state: dict) -> None:
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    CHECKPOINT_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _pending_for_phase(phase: str) -> int:
    from services.backlog_metrics import get_all_pending_counts, invalidate_backlog_metrics_cache

    invalidate_backlog_metrics_cache()
    return int(get_all_pending_counts().get(phase) or 0)


def _probe_popos_models(gpu_host: str) -> list[str]:
    try:
        with urllib.request.urlopen(f"{gpu_host.rstrip('/')}/api/tags", timeout=8) as resp:
            data = json.loads(resp.read().decode())
        return [m.get("name", "") for m in data.get("models") or []]
    except Exception as e:
        logger.warning("PopOS model probe failed: %s", e)
        return []


def _story_batch(profile) -> dict[str, int]:
    return {
        "fact_batch": max(50, profile.batch_story_enrich // 3),
        "queue_batch": max(50, profile.batch_story_enrich // 5),
        "enrich_limit": profile.batch_story_enrich,
        "build_limit": profile.batch_story_build,
    }


def _bulk_args(profile) -> SimpleNamespace:
    return SimpleNamespace(
        enrich_batch=profile.batch_content,
        metadata_limit=profile.batch_metadata,
        context_sync_limit=profile.batch_context_sync,
        entity_max=profile.batch_entity_per_domain,
        claim_limit=profile.batch_claim,
        event_limit=500,
        embed_batch=profile.batch_embed,
        parallel=profile.gpu_parallel_fast,
        cpu_parallel=0,
        domains=None,
    )


def _run_bulk_phase(phase: str, args: SimpleNamespace) -> dict:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "bulk_catchup_mod", _API_ROOT / "scripts" / "bulk_catchup.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._execute_phase(phase, args)


def _run_major_phase(phase: str, batch: int | dict, profile) -> dict:
    import importlib.util

    from shared.catchup_host_metrics import sample_resources

    spec = importlib.util.spec_from_file_location(
        "major_catchup_mod", _API_ROOT / "scripts" / "run_major_backlog_catchup.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    resources = sample_resources()
    return mod._execute_phase(
        phase,
        batch,
        resources,
        story_facts_only=True,
    )


def _phase_progress(phase: str, result: dict) -> int:
    if phase == "story_enhancement":
        return int(result.get("backlog_progress") or result.get("processed") or 0)
    if phase == "event_extraction":
        return int(result.get("articles_processed") or result.get("processed") or 0)
    if phase == "entity_extraction":
        return int(result.get("ok") or result.get("processed") or 0)
    return int(result.get("processed") or 0)


def _major_batch_for_phase(phase: str, profile) -> int | dict:
    if phase == "story_enhancement":
        return _story_batch(profile)
    if phase == "event_extraction":
        return profile.batch_event
    if phase == "entity_profile_build":
        return profile.batch_profile
    if phase == "entity_dossier_compile":
        return profile.batch_dossier
    return profile.batch_event


def _prepare_model_for_phase(phase: str, profile) -> str:
    from shared.backlog_orchestration import prepare_model_for_phase

    active = prepare_model_for_phase(profile, phase)
    logger.info("=== phase %s active_llm_model=%s ===", phase, active)
    return active


def print_dry_run(profile) -> int:
    from shared.backlog_orchestration import SPRINT_PHASE_ORDER

    models = _probe_popos_models(profile.gpu_host)
    print("=== Backlog GPU sprint (dry-run) ===")
    print(f"PopOS: {profile.gpu_host}")
    print(f"Heavy model: {profile.gpu_model_extraction}")
    print(f"Fast model: {profile.gpu_model_fast}")
    print(f"GPU parallel heavy/fast: {profile.gpu_parallel_heavy}/{profile.gpu_parallel_fast}")
    print(f"Floor: {profile.floor}  max_loops/phase: {profile.max_loops}")
    if models:
        print(f"PopOS models ({len(models)}): {', '.join(models[:8])}{'...' if len(models) > 8 else ''}")
    else:
        print("PopOS models: UNREACHABLE")
    print("--- pending ---")
    for phase in SPRINT_PHASE_ORDER:
        pending = _pending_for_phase(phase)
        if pending > 0:
            print(f"  {phase}: {pending}")
    return 0


def main() -> int:
    _load_env()
    from config.runtime import env_pop, env_set
    from shared.backlog_orchestration import (
        BacklogRunProfile,
        SPRINT_PHASE_ORDER,
        apply_sprint_base,
        unload_ollama_model,
    )
    from shared.bulk_catchup_pause import clear_pause_marker, write_pause_marker

    parser = argparse.ArgumentParser(description="Full-pipeline PopOS GPU backlog sprint")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Required to run (safety)")
    parser.add_argument("--floor", type=int, default=None)
    parser.add_argument("--max-loops", type=int, default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from dataclasses import replace

    profile = BacklogRunProfile.from_env()
    if args.floor is not None:
        profile = replace(profile, floor=args.floor)
    if args.max_loops is not None:
        profile = replace(profile, max_loops=args.max_loops)

    if args.dry_run:
        return print_dry_run(profile)

    if not args.force:
        print("Refusing to run without --force (stops competing automation via pause marker).", file=sys.stderr)
        return 2

    write_pause_marker(reason="run_backlog_gpu_sprint.py", by="operator")
    env_set("BULK_CATCHUP_ACTIVE", "1")
    apply_sprint_base(profile)
    unload_ollama_model(profile.gpu_host, profile.gpu_model_extraction)

    state = _load_checkpoint()
    if not state.get("started_at"):
        state["started_at"] = datetime.now(timezone.utc).isoformat()
    state["profile"] = profile.__dict__

    bulk_args = _bulk_args(profile)
    print("=== Backlog GPU sprint ===", flush=True)
    print(
        f"PopOS GPU-only | heavy={profile.gpu_model_extraction} fast={profile.gpu_model_fast} "
        f"| floor={profile.floor}",
        flush=True,
    )

    try:
        for phase in SPRINT_PHASE_ORDER:
            pending = _pending_for_phase(phase)
            print(f"Phase {phase}: pending={pending}", flush=True)
            if pending <= profile.floor:
                state["phases"][phase] = {"status": "skipped_floor", "pending": pending}
                _save_checkpoint(state)
                continue

            state["current_phase"] = phase
            _save_checkpoint(state)
            active_model = _prepare_model_for_phase(phase, profile)
            print(f"Phase {phase}: pending={pending} model={active_model}", flush=True)

            loops = 0
            last_pending = pending
            stall = 0
            while loops < profile.max_loops:
                pending = _pending_for_phase(phase)
                if pending <= profile.floor:
                    break
                loops += 1
                t0 = time.monotonic()
                logger.info("%s loop %s/%s pending=%s model=%s", phase, loops, profile.max_loops, pending, active_model)

                if phase in (
                    "context_sync",
                    "entity_extraction",
                    "claim_extraction",
                    "content_enrichment",
                    "metadata_enrichment",
                    "embeddings_worker",
                    "event_tracking",
                    "storyline_discovery",
                ):
                    result = _run_bulk_phase(phase, bulk_args)
                elif phase in (
                    "event_extraction",
                    "story_enhancement",
                    "entity_profile_build",
                    "entity_dossier_compile",
                ):
                    batch = _major_batch_for_phase(phase, profile)
                    result = _run_major_phase(phase, batch, profile)
                else:
                    result = {"error": "unknown_phase"}

                progress = _phase_progress(phase, result)
                elapsed = time.monotonic() - t0
                logger.info(
                    "%s loop %s done progress=%s elapsed=%.0fs result=%s",
                    phase,
                    loops,
                    progress,
                    elapsed,
                    {k: v for k, v in result.items() if k not in ("batches",)},
                )
                print(f"  loop {loops}: progress={progress} elapsed={elapsed:.0f}s", flush=True)

                pending_after = _pending_for_phase(phase)
                if progress <= 0 and pending_after >= last_pending:
                    stall += 1
                    if stall >= 5:
                        logger.warning("%s stalled %s loops — advancing", phase, stall)
                        state["phases"][phase] = {
                            "status": "stalled",
                            "pending": pending_after,
                            "loops": loops,
                        }
                        _save_checkpoint(state)
                        break
                else:
                    stall = 0
                last_pending = pending_after
                state["phases"][phase] = {
                    "status": "running",
                    "pending": pending_after,
                    "loops": loops,
                    "last_result": result,
                }
                _save_checkpoint(state)

            if state["phases"].get(phase, {}).get("status") != "stalled":
                state["phases"][phase] = {
                    "status": "done",
                    "pending": _pending_for_phase(phase),
                    "loops": loops,
                }
                _save_checkpoint(state)

        state["finished_at"] = datetime.now(timezone.utc).isoformat()
        _save_checkpoint(state)
        print("=== Backlog GPU sprint complete ===", flush=True)
        print(f"Resume routine ops: { _REPO_ROOT / 'scripts' / 'run_backlog_gpu_sprint.sh' } resume")
        return 0
    finally:
        clear_pause_marker()
        env_pop("BULK_CATCHUP_ACTIVE", None)
        env_pop("BACKLOG_SPRINT_ACTIVE", None)
        env_pop("BACKLOG_SPRINT_GPU_ONLY", None)


if __name__ == "__main__":
    raise SystemExit(main())
