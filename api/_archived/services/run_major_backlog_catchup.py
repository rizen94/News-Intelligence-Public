#!/usr/bin/env python3
"""
Expedited catch-up for the four dominant intelligence backlogs:
  entity_dossier_compile, entity_profile_build, story_enhancement, event_extraction

Bypasses quiet-hour gating with --force. Pauses competing automation (bulk_catchup marker).
Batch sizes auto-tune per resource track: enrich (Widow RAM/CPU), build (PopOS GPU),
and single-knob phases (dossier=local, profile_build=build, event_extraction=gpu).
GPU LLM work routes to PopOS (OLLAMA_POP_OS_HOST) by default — same routing as bulk_catchup.py.

  cd /opt/news-intelligence && set -a && source .env && set +a
  PYTHONPATH=api python3 api/scripts/run_major_backlog_catchup.py --dry-run
  PYTHONPATH=api python3 api/scripts/run_major_backlog_catchup.py --force --loops 100
  PYTHONPATH=api python3 api/scripts/run_major_backlog_catchup.py --force --no-dual-lane
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_API_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _API_ROOT.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from shared.catchup_host_metrics import (
    ResourceSnapshot,
    RoutingContext,
    TRACK_BUILD,
    TRACK_ENRICH,
    merge_resource_snapshots,
    sample_resources,
    set_routing_context,
    tune_batch_size,
    tune_batch_track,
)

CHECKPOINT_PATH = _REPO_ROOT / "data" / "major_backlog_catchup_state.json"

MAJOR_PHASE_ORDER: tuple[str, ...] = (
    "entity_dossier_compile",
    "entity_profile_build",
    "story_enhancement",
    "event_extraction",
)

# Companion phase: PopOS GPU narrative backfill for fast-compiled dossiers (run in parallel).
COMPANION_PHASES: tuple[str, ...] = ("entity_dossier_narrative",)

CATCHUP_PHASE_CHOICES: tuple[str, ...] = MAJOR_PHASE_ORDER + COMPANION_PHASES

# PopOS GPU phases first — dossier/story are Widow CPU+Postgres heavy (see catchup_host_metrics TRACK_LOCAL).
MAJOR_PHASE_ORDER_GPU_FIRST: tuple[str, ...] = (
    "event_extraction",
    "entity_profile_build",
    "story_enhancement",
    "entity_dossier_compile",
)


def _resolve_phase_order(*, use_popos_gpu: bool, explicit_phases: tuple[str, ...] | None) -> tuple[str, ...]:
    if explicit_phases:
        phases = explicit_phases
    elif use_popos_gpu:
        phases = MAJOR_PHASE_ORDER_GPU_FIRST
    else:
        phases = MAJOR_PHASE_ORDER
    try:
        from shared.pipeline_resource_policy import intake_extraction_suppressed

        if intake_extraction_suppressed():
            phases = tuple(p for p in phases if p != "event_extraction")
    except Exception:
        pass
    return phases


def _dossier_phases_in_run(phases: tuple[str, ...]) -> bool:
    return "entity_dossier_compile" in phases

logger = logging.getLogger(__name__)


def _load_env() -> None:
    from shared.catchup_bootstrap import bootstrap_catchup

    bootstrap_catchup(bulk_active=False)


def _tuning_config() -> dict[str, int | float]:
    from config.runtime import env_str

    def _f(name: str, default: str) -> float:
        try:
            return float(env_str(name, default))
        except ValueError:
            return float(default)

    def _i(name: str, default: str) -> int:
        try:
            return int(env_str(name, default))
        except ValueError:
            return int(default)

    return {
        "batch_min": _i("MAJOR_CATCHUP_BATCH_MIN", "10"),
        "batch_max": _i("MAJOR_CATCHUP_BATCH_MAX", "500"),
        "batch_step": _i("MAJOR_CATCHUP_BATCH_STEP", "10"),
        "batch_initial": _i("MAJOR_CATCHUP_BATCH_INITIAL", "200"),
        "build_batch_initial": _i("MAJOR_CATCHUP_BUILD_BATCH_INITIAL", "120"),
        "build_batch_max": _i("MAJOR_CATCHUP_BUILD_BATCH_MAX", "200"),
        "enrich_batch_max": _i("MAJOR_CATCHUP_ENRICH_BATCH_MAX", "500"),
        "increase_headroom": _f("MAJOR_CATCHUP_INCREASE_HEADROOM", "0.50"),
        "decrease_headroom": _f("MAJOR_CATCHUP_DECREASE_HEADROOM", "0.25"),
        "memory_pressure_pct": _f("MAJOR_CATCHUP_MEMORY_PRESSURE_PCT", "85"),
        "memory_critical_pct": _f("MAJOR_CATCHUP_MEMORY_CRITICAL_PCT", "90"),
        "gpu_temp_increase_max_c": _i("MAJOR_CATCHUP_GPU_TEMP_INCREASE_MAX_C", "80"),
        "gpu_temp_decrease_c": _i("GPU_TEMP_THROTTLE_C", "82"),
        "dossier_fast_batch_min": _i("MAJOR_CATCHUP_DOSSIER_BATCH_MIN", "100"),
        "narrative_batch_initial": _i("MAJOR_CATCHUP_NARRATIVE_BATCH_INITIAL", "40"),
    }


def _clamp_batch(n: int) -> int:
    cfg = _tuning_config()
    return max(int(cfg["batch_min"]), min(int(cfg["batch_max"]), n))


def _clamp_enrich_batch(n: int) -> int:
    cfg = _tuning_config()
    return max(int(cfg["batch_min"]), min(int(cfg["enrich_batch_max"]), n))


def _clamp_build_batch(n: int) -> int:
    cfg = _tuning_config()
    return max(int(cfg["batch_min"]), min(int(cfg["build_batch_max"]), n))


def _story_limits_from_enrich_build(enrich: int, build: int) -> dict[str, int]:
    enrich = _clamp_enrich_batch(enrich)
    build = _clamp_build_batch(build)
    return {
        "fact_batch": max(10, enrich // 3),
        "queue_batch": max(10, enrich // 5),
        "enrich_limit": enrich,
        "build_limit": build,
    }


def _story_enhancement_limits(primary: int) -> dict[str, int]:
    """Legacy: single primary knob → derived enrich/build fractions."""
    primary = _clamp_batch(primary)
    return _story_limits_from_enrich_build(primary, max(10, primary // 5))


def _get_story_batches(state: dict) -> dict[str, int]:
    tuning = state.get("batch_tuning") or {}
    raw = tuning.get("story_enhancement")
    cfg = _tuning_config()
    enrich_init = int(cfg["batch_initial"])
    build_init = int(cfg["build_batch_initial"])
    if isinstance(raw, dict):
        enrich = int(raw.get("enrich", enrich_init))
        build = int(raw.get("build", build_init))
    elif isinstance(raw, int):
        limits = _story_enhancement_limits(raw)
        enrich = limits["enrich_limit"]
        build = limits["build_limit"]
    else:
        enrich = enrich_init
        build = build_init
    return _story_limits_from_enrich_build(enrich, build)


def _set_story_batches(state: dict, enrich: int, build: int) -> None:
    if "batch_tuning" not in state:
        state["batch_tuning"] = {}
    state["batch_tuning"]["story_enhancement"] = {
        "enrich": _clamp_enrich_batch(enrich),
        "build": _clamp_build_batch(build),
    }


def _get_batch_for_phase(state: dict, phase: str) -> int | dict[str, int]:
    if phase == "story_enhancement":
        return _get_story_batches(state)
    tuning = state.get("batch_tuning") or {}
    if phase in tuning:
        val = tuning[phase]
        if isinstance(val, dict):
            return val
        return int(val)
    cfg = _tuning_config()
    if phase == "entity_profile_build":
        return int(cfg["build_batch_initial"])
    if phase == "entity_dossier_narrative":
        return int(cfg["narrative_batch_initial"])
    return int(cfg["batch_initial"])


def _set_batch_for_phase(state: dict, phase: str, batch: int) -> None:
    if phase == "story_enhancement":
        raise ValueError("use _set_story_batches for story_enhancement")
    if "batch_tuning" not in state:
        state["batch_tuning"] = {}
    if phase == "entity_profile_build":
        state["batch_tuning"][phase] = _clamp_build_batch(batch)
    else:
        state["batch_tuning"][phase] = _clamp_batch(batch)


def _batch_display(batch: int | dict[str, int]) -> str:
    if isinstance(batch, dict):
        return f"enrich={batch['enrich_limit']} build={batch['build_limit']}"
    return str(batch)


def _tune_story_batches(
    batches: dict[str, int],
    resources: ResourceSnapshot,
    *,
    auto_tune: bool,
    tuning_config: dict[str, int | float],
) -> tuple[dict[str, int], dict[str, Any]]:
    enrich = batches["enrich_limit"]
    build = batches["build_limit"]
    new_enrich, act_e, meta_e = tune_batch_track(
        TRACK_ENRICH, enrich, resources, auto_tune=auto_tune, tuning_config=tuning_config
    )
    new_build, act_b, meta_b = tune_batch_track(
        TRACK_BUILD, build, resources, auto_tune=auto_tune, tuning_config=tuning_config
    )
    new_batches = _story_limits_from_enrich_build(new_enrich, new_build)
    tune_meta: dict[str, Any] = {
        "action": f"enrich:{act_e}|build:{act_b}",
        "enrich": {**meta_e, "batch_before": enrich, "batch_after": new_enrich},
        "build": {**meta_b, "batch_before": build, "batch_after": new_build},
        "headroom": meta_e.get("headroom"),
    }
    return new_batches, tune_meta


def _get_backlog_metrics_module():
    import importlib.util

    path = _API_ROOT / "services" / "backlog_metrics.py"
    spec = importlib.util.spec_from_file_location("_major_backlog_metrics", path)
    if not spec or not spec.loader:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pending_for_phase(phase: str) -> int:
    if phase == "entity_dossier_narrative":
        from services.dossier_compiler_service import count_dossier_narrative_pending

        return count_dossier_narrative_pending()
    if phase == "entity_profile_build":
        from services.backlog_metrics import _count_entity_profile_build_backlog

        return int(_count_entity_profile_build_backlog() or 0)
    mod = _get_backlog_metrics_module()
    mod.invalidate_backlog_metrics_cache()
    return int(mod.get_all_pending_counts().get(phase) or 0)


def _schedule_allowed(force: bool) -> bool:
    if force:
        return True
    from services.pipeline_schedule_service import automation_phase_allowed

    return automation_phase_allowed("entity_dossier_compile")


def _load_checkpoint() -> dict:
    if CHECKPOINT_PATH.is_file():
        try:
            return json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"started_at": None, "phases": {}, "current_phase": None, "batch_tuning": {}}


def _save_checkpoint(state: dict) -> None:
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    CHECKPOINT_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _run_dossier_narrative_backfill(batch: int) -> int:
    from services.dossier_compiler_service import (
        _dossier_narrative_parallel_workers,
        _dossier_narrative_cpu_parallel_workers,
        _dossier_narrative_model,
        backfill_dossier_narratives,
    )
    from shared.bulk_catchup_llm_routing import dual_lane_extraction_active

    batch = _clamp_batch(batch)
    gpu_workers = _dossier_narrative_parallel_workers()
    cpu_workers = _dossier_narrative_cpu_parallel_workers()
    use_gpu = gpu_workers > 0
    model = _dossier_narrative_model() if use_gpu else None
    if not use_gpu:
        cpu_parallel = cpu_workers
    elif dual_lane_extraction_active():
        cpu_parallel = cpu_workers
    else:
        cpu_parallel = 0
    return int(
        backfill_dossier_narratives(
            batch,
            parallel=gpu_workers if use_gpu else 0,
            cpu_parallel=cpu_parallel,
            model=model,
            use_gpu=use_gpu,
        )
        or 0
    )


def _run_dossier_compile(batch: int) -> int:
    from services.dossier_compiler_service import _run_scheduled_dossier_compiles

    batch = _clamp_batch(batch)
    return int(_run_scheduled_dossier_compiles(batch, None) or 0)


async def _run_profile_build(batch: int) -> int:
    from services.entity_profile_builder_service import run_profile_builder_batch

    result = await run_profile_builder_batch(limit=_clamp_build_batch(batch))
    return int(result.updated or 0)


async def _run_story_enhancement(
    limits: dict[str, int], *, facts_only: bool = False
) -> dict[str, Any]:
    from services.enhancement_orchestrator_service import run_enhancement_cycle

    enrich_limit = 0 if facts_only else limits["enrich_limit"]
    build_limit = 0 if facts_only else limits["build_limit"]
    result = await run_enhancement_cycle(
        fact_batch=limits["fact_batch"],
        queue_batch=limits["queue_batch"],
        enrich_limit=enrich_limit,
        build_limit=build_limit,
    )
    fact = int(result.get("fact_change_log_processed") or 0)
    queue = int(result.get("story_update_queue_processed") or 0)
    enrich = int(result.get("entity_profiles_enriched") or 0)
    build = int(result.get("entity_profiles_built") or 0)
    backlog_progress = fact + queue
    total_work = backlog_progress + enrich + build
    return {
        **result,
        "facts_only": facts_only,
        "backlog_progress": backlog_progress,
        "total_work": total_work,
        "processed": backlog_progress,
    }


def _cut_stale_fact_change_log(days: int) -> int:
    """Mark old unprocessed fact_change_log rows processed (drain tail without story updates)."""
    if days <= 0:
        return 0
    from shared.database.connection import get_db_connection_context

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE intelligence.fact_change_log
                SET processed = TRUE,
                    processed_at = NOW(),
                    story_updates_triggered = 0
                WHERE processed = FALSE
                  AND changed_at < NOW() - INTERVAL '{int(days)} days'
                """
            )
            updated = int(cur.rowcount or 0)
        conn.commit()
    return updated


def _phase_progress(phase: str, result: dict[str, Any]) -> int:
    """Metric that must move for stall detection (aligned with backlog counters)."""
    if phase == "story_enhancement":
        return int(result.get("backlog_progress") or result.get("processed") or 0)
    if phase == "event_extraction":
        return int(result.get("articles_processed") or result.get("processed") or 0)
    return int(result.get("processed") or 0)


async def _run_unified_intake_extraction(batch: int, resources: ResourceSnapshot) -> dict[str, Any]:
    """Unified intake extract catch-up (replaces event_extraction when flag enabled)."""
    from config.runtime import env_str
    from shared.backlog_orchestration import sprint_gpu_only
    from shared.database.db_availability import schema_has_table
    from shared.domain_registry import get_pipeline_schema_names_active
    from shared.pipeline_batch_drain import phase_run_budget_seconds
    from shared.unified_intake_extraction_runner import run_unified_intake_extraction_batch_drain

    batch = _clamp_batch(batch)
    active_schemas = [s for s in get_pipeline_schema_names_active() if schema_has_table(s, "articles")]
    n_schemas = max(1, len(active_schemas))
    if sprint_gpu_only():
        try:
            sprint_batch = int(env_str("BACKLOG_SPRINT_BATCH_EVENT", str(batch)))
        except ValueError:
            sprint_batch = batch
        batch = max(batch, sprint_batch)
        per_domain = max(20, min(100, batch // n_schemas))
    else:
        per_domain = max(20, min(80, batch // n_schemas))

    logger.info(
        "unified_intake_extraction catch-up per_domain=%s (~%s articles) batch_size=%s",
        per_domain,
        per_domain * n_schemas,
        env_str("UNIFIED_INTAKE_EXTRACTION_BATCH_SIZE", "3"),
    )
    return await run_unified_intake_extraction_batch_drain(
        articles_per_domain=per_domain,
        budget_seconds=phase_run_budget_seconds("unified_intake_extraction", 900),
    )


async def _run_event_extraction(batch: int, resources: ResourceSnapshot) -> dict[str, Any]:
    """One automation-scale batch across active domain schemas."""
    from shared.pipeline_resource_policy import intake_extraction_suppressed

    if intake_extraction_suppressed():
        return await _run_unified_intake_extraction(batch, resources)

    from config.runtime import env_str
    from shared.backlog_orchestration import sprint_gpu_only
    from shared.database.db_availability import schema_has_table
    from shared.domain_registry import get_pipeline_schema_names_active
    from shared.legacy_intake_rollback import legacy_intake_rollback_active, load_event_extraction_runner

    if not legacy_intake_rollback_active():
        return await _run_unified_intake_extraction(batch, resources)

    run_event_extraction_batch_drain = load_event_extraction_runner().run_event_extraction_batch_drain
    from shared.pipeline_batch_drain import phase_run_budget_seconds

    batch = _clamp_batch(batch)
    active_schemas = [s for s in get_pipeline_schema_names_active() if schema_has_table(s, "articles")]
    n_schemas = max(1, len(active_schemas))
    if sprint_gpu_only():
        try:
            sprint_batch = int(env_str("BACKLOG_SPRINT_BATCH_EVENT", str(batch)))
        except ValueError:
            sprint_batch = batch
        batch = max(batch, sprint_batch)
        per_schema = max(20, min(100, batch // n_schemas))
    else:
        per_schema = max(20, min(80, batch // n_schemas))

    logger.info(
        "event_extraction catch-up per_schema=%s (~%s articles) batch_size=%s",
        per_schema,
        per_schema * n_schemas,
        env_str("EVENT_EXTRACTION_BATCH_SIZE", "3"),
    )
    return await run_event_extraction_batch_drain(
        articles_per_schema=per_schema,
        budget_seconds=phase_run_budget_seconds("event_extraction", 900),
    )


def _execute_phase(
    phase: str,
    batch: int | dict[str, int],
    resources: ResourceSnapshot,
    *,
    story_facts_only: bool = False,
) -> dict:
    if phase == "entity_dossier_compile":
        assert isinstance(batch, int)
        n = _run_dossier_compile(batch)
        return {"processed": n, "batch": batch}
    if phase == "entity_dossier_narrative":
        assert isinstance(batch, int)
        n = _run_dossier_narrative_backfill(batch)
        return {"processed": n, "batch": batch}
    if phase == "entity_profile_build":
        assert isinstance(batch, int)
        n = asyncio.run(_run_profile_build(batch))
        return {"processed": n, "batch": batch}
    if phase == "story_enhancement":
        limits = batch if isinstance(batch, dict) else _story_enhancement_limits(batch)
        out = asyncio.run(_run_story_enhancement(limits, facts_only=story_facts_only))
        return {"batch": limits, "limits": limits, **out}
    if phase == "event_extraction":
        assert isinstance(batch, int)
        out = asyncio.run(_run_event_extraction(batch, resources))
        return {"batch": batch, **out}
    return {"error": "unknown_phase"}


def _log_resource_line(
    phase: str,
    loop: int,
    batch: int | dict[str, int] | str,
    resources: ResourceSnapshot,
    tune: dict,
) -> None:
    batch_label = batch if isinstance(batch, str) else _batch_display(batch)
    headroom = tune.get("headroom")
    if headroom is None:
        headroom = resources.phase_headroom(phase)
    reason = tune.get("reason", "")
    if phase == "story_enhancement" and tune.get("enrich"):
        reason = (
            f"enrich:{tune['enrich'].get('action')}({tune['enrich'].get('reason', '')}) "
            f"build:{tune['build'].get('action')}({tune['build'].get('reason', '')})"
        )
    logger.info(
        "%s loop %s batch=%s action=%s headroom=%.2f "
        "local(cpu=%s%% mem=%s%%) gpu@%s(util=%s%% vram=%s%% temp=%sC src=%s) db=%.0f%% | %s",
        phase,
        loop,
        batch_label,
        tune.get("action"),
        float(headroom),
        f"{resources.local_cpu_percent:.0f}" if resources.local_cpu_percent is not None else "?",
        f"{resources.local_memory_percent:.0f}" if resources.local_memory_percent is not None else "?",
        resources.gpu_host,
        f"{resources.gpu_util_percent:.0f}" if resources.gpu_util_percent is not None else "?",
        f"{resources.gpu_vram_percent:.0f}" if resources.gpu_vram_percent is not None else "?",
        resources.gpu_temp_c if resources.gpu_temp_c is not None else "?",
        resources.gpu_probe_source,
        resources.db_worker_util * 100,
        reason,
    )


def main() -> int:
    _load_env()
    from config.runtime import env_pop, env_set, env_str
    from shared.bulk_catchup_pause import clear_pause_marker, write_pause_marker

    parser = argparse.ArgumentParser(description="Major backlog catch-up (4 phases)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Ignore quiet hours")
    parser.add_argument("--loops", type=int, default=int(env_str("MAJOR_CATCHUP_LOOPS", "80")))
    parser.add_argument("--floor", type=int, default=int(env_str("MAJOR_CATCHUP_FLOOR", "1000")))
    parser.add_argument(
        "--phases",
        nargs="*",
        choices=CATCHUP_PHASE_CHOICES,
        default=None,
        help="Subset of phases (default: all four in order)",
    )
    parser.add_argument(
        "--stall-loops",
        type=int,
        default=int(env_str("MAJOR_CATCHUP_STALL_LOOPS", "8")),
    )
    parser.add_argument(
        "--no-auto-tune",
        action="store_true",
        help="Keep batch size fixed (MAJOR_CATCHUP_BATCH_INITIAL / checkpoint)",
    )
    parser.add_argument(
        "--gpu-parallel",
        type=int,
        default=int(env_str("MAJOR_CATCHUP_GPU_PARALLEL", env_str("BULK_GPU_PARALLEL", "4"))),
        help="PopOS GPU lane concurrency (profile build, event extraction)",
    )
    parser.add_argument(
        "--cpu-parallel",
        type=int,
        default=int(env_str("MAJOR_CATCHUP_CPU_PARALLEL", env_str("BULK_CPU_PARALLEL", "2"))),
        help="Widow CPU Ollama lane concurrency when --dual-lane",
    )
    parser.add_argument(
        "--ollama-timeout",
        type=int,
        default=int(env_str("MAJOR_CATCHUP_OLLAMA_TIMEOUT", env_str("BULK_OLLAMA_TIMEOUT", "600"))),
        help="HTTP timeout (seconds) for PopOS GPU Ollama during catch-up",
    )
    parser.add_argument(
        "--use-popos-gpu",
        action=argparse.BooleanOptionalAction,
        default=env_str("MAJOR_CATCHUP_USE_POPOS_GPU", env_str("BULK_USE_POPOS_GPU", "true")).lower()
        in ("1", "true", "yes"),
        help="Route GPU LLM work to PopOS (OLLAMA_POP_OS_HOST); default on",
    )
    parser.add_argument(
        "--dual-lane",
        action=argparse.BooleanOptionalAction,
        default=env_str("MAJOR_CATCHUP_DUAL_LANE", "false").lower() in ("1", "true", "yes"),
        help="Split extraction across PopOS GPU + Widow CPU (default off — PopOS GPU only)",
    )
    parser.add_argument(
        "--story-facts-only",
        action=argparse.BooleanOptionalAction,
        default=env_str("MAJOR_CATCHUP_STORY_FACTS_ONLY", "true").lower() in ("1", "true", "yes"),
        help="Story enhancement: drain fact_change_log + queue only (no enrich/build); default on",
    )
    parser.add_argument(
        "--cut-stale-facts-days",
        type=int,
        default=int(env_str("MAJOR_CATCHUP_CUT_STALE_FACTS_DAYS", "30")),
        help="At startup mark fact_change_log older than N days processed (0=skip); default 30",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(line_buffering=True)
    write_pause_marker(reason="run_major_backlog_catchup.py")

    try:
        if not _schedule_allowed(args.force):
            print("Outside schedule window — use --force", file=sys.stderr)
            return 2

        env_set("BULK_CATCHUP_ACTIVE", "1")
        from config.catchup_defaults import apply_catchup_env_defaults

        apply_catchup_env_defaults(bulk_active=True)
        narrative_only = bool(args.phases and set(args.phases) == {"entity_dossier_narrative"})
        if args.phases and "entity_dossier_narrative" in args.phases:
            env_set("DOSSIER_CATCHUP_GPU_NARRATIVE", "1")
        if narrative_only:
            env_set("DOSSIER_CATCHUP_SKIP_NARRATIVE", "0")
        from shared.bulk_catchup_llm_routing import configure_catchup_extraction_routing

        configure_catchup_extraction_routing(
            use_popos_gpu=args.use_popos_gpu,
            dual_lane=args.dual_lane and args.use_popos_gpu,
            gpu_parallel=max(1, args.gpu_parallel),
            cpu_parallel=max(1, args.cpu_parallel),
            ollama_timeout=max(120, args.ollama_timeout),
        )
        set_routing_context(
            RoutingContext(
                popos_gpu=bool(args.use_popos_gpu),
                dual_lane=bool(args.dual_lane and args.use_popos_gpu),
                gpu_ollama_url=env_str("OLLAMA_GPU_HOST", env_str("OLLAMA_POP_OS_HOST", "")),
                cpu_ollama_url=env_str("OLLAMA_CPU_HOST", env_str("OLLAMA_HOST", "http://localhost:11434")),
            )
        )
        phases = _resolve_phase_order(
            use_popos_gpu=bool(args.use_popos_gpu),
            explicit_phases=tuple(args.phases) if args.phases else None,
        )
        state = _load_checkpoint()
        if not state.get("started_at"):
            state["started_at"] = datetime.now(timezone.utc).isoformat()
        if not state.get("batch_tuning"):
            state["batch_tuning"] = {}
        state["llm_routing"] = {
            "use_popos_gpu": args.use_popos_gpu,
            "dual_lane": args.dual_lane and args.use_popos_gpu,
            "gpu_host": env_str("OLLAMA_GPU_HOST", ""),
            "cpu_host": env_str("OLLAMA_CPU_HOST", ""),
            "gpu_parallel": args.gpu_parallel,
            "cpu_parallel": args.cpu_parallel if args.dual_lane else 0,
            "story_facts_only": args.story_facts_only,
        }

        if args.cut_stale_facts_days > 0 and not args.dry_run:
            if not state.get("stale_facts_cut_days"):
                cut_n = _cut_stale_fact_change_log(args.cut_stale_facts_days)
                state["stale_facts_cut_days"] = args.cut_stale_facts_days
                state["stale_facts_cut_rows"] = cut_n
                _save_checkpoint(state)
                print(
                    f"Cut stale fact_change_log (>{args.cut_stale_facts_days}d): marked {cut_n} processed"
                )
            else:
                print(
                    f"Stale fact cut already applied this run (days={state.get('stale_facts_cut_days')})"
                )

        auto_tune = not args.no_auto_tune
        print("=== Major backlog catch-up ===", flush=True)
        if args.use_popos_gpu:
            mode = "dual-lane (PopOS GPU + Widow CPU)" if args.dual_lane else "PopOS GPU only"
            print(f"LLM routing: {mode} — gpu_host={state['llm_routing']['gpu_host']}", flush=True)
        else:
            print("LLM routing: local Widow Ollama only", flush=True)
        tune_cfg = _tuning_config()
        if auto_tune:
            res_probe = sample_resources()
            print(
                f"Auto-tune metrics: local mem={res_probe.local_memory_percent}% "
                f"gpu@{res_probe.gpu_host} util={res_probe.gpu_util_percent}% "
                f"probe={res_probe.gpu_probe_source}"
            )
            print(
                f"Auto-tune: enrich {tune_cfg['batch_min']}-{tune_cfg['enrich_batch_max']} "
                f"build {tune_cfg['batch_min']}-{tune_cfg['build_batch_max']} "
                f"step={tune_cfg['batch_step']} "
                f"(initial enrich={tune_cfg['batch_initial']} build={tune_cfg['build_batch_initial']})"
            )
        else:
            print("Auto-tune: disabled")
        if args.use_popos_gpu and not args.phases:
            print(f"Phase order (GPU-first): {' → '.join(phases)}")
        if args.story_facts_only:
            print("Story enhancement: facts-only (no Wikipedia enrich / profile build)")
        if _dossier_phases_in_run(phases):
            from services.dossier_compiler_service import (
                _dossier_compile_parallel_workers,
                _dossier_skip_narrative_enabled,
            )

            print(
                f"Dossier compile: skip_narrative={_dossier_skip_narrative_enabled()} "
                f"parallel_workers={_dossier_compile_parallel_workers()}"
            )
        if "entity_dossier_narrative" in phases:
            from services.dossier_compiler_service import (
                _dossier_narrative_parallel_workers,
                _dossier_narrative_cpu_parallel_workers,
            )

            print(
                f"Dossier narrative GPU backfill: parallel_workers="
                f"{_dossier_narrative_parallel_workers()}"
            )
            cpu_workers = _dossier_narrative_cpu_parallel_workers()
            if cpu_workers:
                print(
                    f"Dossier narrative CPU backfill: parallel_workers={cpu_workers}"
                )

        for phase in phases:
            pending = _pending_for_phase(phase)
            batch = _get_batch_for_phase(state, phase)
            print(f"Phase {phase}: pending={pending} batch={_batch_display(batch)}", flush=True)
            if args.dry_run:
                res = sample_resources()
                print(f"  resources: {res.to_log_dict()}")
                continue
            if pending <= args.floor:
                state["phases"][phase] = {"status": "skipped_floor", "pending": pending}
                _save_checkpoint(state)
                continue

            state["current_phase"] = phase
            _save_checkpoint(state)
            loops = 0
            stall_count = 0
            last_pending = pending
            phase_status = "done"
            t0 = time.monotonic()
            while loops < args.loops:
                pending = _pending_for_phase(phase)
                if pending <= args.floor:
                    break
                loops += 1
                batch = _get_batch_for_phase(state, phase)
                res_before = sample_resources()
                logger.info(
                    "%s loop %s/%s pending=%s batch=%s",
                    phase,
                    loops,
                    args.loops,
                    pending,
                    _batch_display(batch),
                )
                loop_resources = res_before
                tune_meta: dict[str, Any] = {}
                progress = 0
                result: dict[str, Any] = {}
                try:
                    result = _execute_phase(
                        phase,
                        batch,
                        res_before,
                        story_facts_only=args.story_facts_only,
                    )
                    progress = _phase_progress(phase, result)
                    res_after = sample_resources()
                    loop_resources = merge_resource_snapshots(res_before, res_after)
                    if phase == "story_enhancement":
                        assert isinstance(batch, dict)
                        new_batches, tune_meta = _tune_story_batches(
                            batch,
                            loop_resources,
                            auto_tune=auto_tune,
                            tuning_config=tune_cfg,
                        )
                        _set_story_batches(
                            state, new_batches["enrich_limit"], new_batches["build_limit"]
                        )
                        _log_resource_line(phase, loops, batch, loop_resources, tune_meta)
                        logger.info(
                            "%s loop %s backlog_progress=%s total_work=%s "
                            "(fact=%s queue=%s enrich=%s build=%s) "
                            "enrich_batch %s->%s build %s->%s (%s)",
                            phase,
                            loops,
                            progress,
                            result.get("total_work"),
                            result.get("fact_change_log_processed"),
                            result.get("story_update_queue_processed"),
                            result.get("entity_profiles_enriched"),
                            result.get("entity_profiles_built"),
                            batch["enrich_limit"],
                            new_batches["enrich_limit"],
                            batch["build_limit"],
                            new_batches["build_limit"],
                            tune_meta.get("action"),
                        )
                    elif phase == "event_extraction":
                        assert isinstance(batch, int)
                        new_batch, action, tune_meta = tune_batch_size(
                            phase,
                            batch,
                            loop_resources,
                            auto_tune=auto_tune,
                            tuning_config=tune_cfg,
                        )
                        _set_batch_for_phase(state, phase, new_batch)
                        tune_meta["action"] = action
                        tune_meta["batch_before"] = batch
                        tune_meta["batch_after"] = new_batch
                        _log_resource_line(phase, loops, batch, loop_resources, tune_meta)
                        logger.info(
                            "%s loop %s articles=%s events_saved=%s batch %s->%s (%s)",
                            phase,
                            loops,
                            progress,
                            result.get("events_saved"),
                            batch,
                            new_batch,
                            action,
                        )
                    else:
                        assert isinstance(batch, int)
                        new_batch, action, tune_meta = tune_batch_size(
                            phase,
                            batch,
                            loop_resources,
                            auto_tune=auto_tune,
                            tuning_config=tune_cfg,
                        )
                        _set_batch_for_phase(state, phase, new_batch)
                        tune_meta["action"] = action
                        tune_meta["batch_before"] = batch
                        tune_meta["batch_after"] = new_batch
                        _log_resource_line(phase, loops, batch, loop_resources, tune_meta)
                        print(
                            f"    processed={progress} batch {batch}->{new_batch} ({action}) "
                            f"headroom={tune_meta.get('headroom')}"
                        )
                    if progress == 0 and pending >= last_pending:
                        stall_count += 1
                        if stall_count >= args.stall_loops:
                            logger.warning(
                                "%s: stalled %s loops at pending=%s — next phase",
                                phase,
                                stall_count,
                                pending,
                            )
                            state["phases"][phase] = {
                                "status": "skipped_stall",
                                "pending": pending,
                                "loops": loops,
                            }
                            phase_status = "skipped_stall"
                            _save_checkpoint(state)
                            break
                    else:
                        stall_count = 0
                    last_pending = pending
                except Exception as e:
                    logger.exception("%s loop %s failed: %s", phase, loops, e)
                    stall_count += 1
                    if stall_count >= args.stall_loops:
                        break
                    res_after = sample_resources()
                    loop_resources = merge_resource_snapshots(res_before, res_after)
                    step = int(_tuning_config()["batch_step"])
                    batch_min = int(_tuning_config()["batch_min"])
                    if phase == "story_enhancement":
                        batches = _get_story_batches(state)
                        new_enrich = max(batch_min, batches["enrich_limit"] - step)
                        new_build = max(batch_min, batches["build_limit"] - step)
                        _set_story_batches(state, new_enrich, new_build)
                        tune_meta = {"action": "decrease_error", "enrich_after": new_enrich, "build_after": new_build}
                        _log_resource_line(phase, loops, batches, loop_resources, tune_meta)
                    else:
                        batch = _get_batch_for_phase(state, phase)
                        assert isinstance(batch, int)
                        new_batch, action, tune_meta = tune_batch_size(
                            phase,
                            batch,
                            loop_resources,
                            auto_tune=auto_tune,
                            tuning_config=tune_cfg,
                        )
                        new_batch = max(batch_min, new_batch - step)
                        _set_batch_for_phase(state, phase, new_batch)
                        tune_meta["action"] = "decrease_error"
                        _log_resource_line(phase, loops, batch, loop_resources, tune_meta)

                phase_state = {
                    "loops": loops,
                    "pending": pending,
                    "batch": _get_batch_for_phase(state, phase),
                    "progress": progress,
                    "result": {k: v for k, v in result.items() if k != "batch"},
                    "elapsed_sec": round(time.monotonic() - t0, 1),
                    "last_resources": loop_resources.to_log_dict(),
                    "last_tune": tune_meta,
                }
                _save_checkpoint(
                    {
                        **state,
                        "phases": {**state.get("phases", {}), phase: phase_state},
                    }
                )

            state["phases"][phase] = {
                "status": phase_status,
                "loops": loops,
                "pending_end": _pending_for_phase(phase),
                "batch_end": _get_batch_for_phase(state, phase),
                "elapsed_sec": round(time.monotonic() - t0, 1),
            }
            _save_checkpoint(state)
            print(
                f"  {phase} finished loops={loops} pending_now={_pending_for_phase(phase)} "
                f"batch={_batch_display(_get_batch_for_phase(state, phase))}"
            )

        print("=== Complete ===")
        for phase in phases:
            print(f"  {phase}: pending={_pending_for_phase(phase)}")
        return 0
    finally:
        clear_pause_marker()
        env_pop("BULK_CATCHUP_ACTIVE", None)


if __name__ == "__main__":
    raise SystemExit(main())
