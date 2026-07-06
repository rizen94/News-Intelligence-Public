#!/usr/bin/env python3
"""
Runtime snapshot: scheduling env, pipeline windows, phase gates, pool pressure.
Prints structured JSON snapshots to stdout.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_API_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _API_ROOT.parent

_SCHEDULING_ENV_KEYS = (
    "UNIFIED_INTAKE_EXTRACTION_ENABLED",
    "LEGACY_INTAKE_EXTRACTION_ENABLED",
    "UNIFIED_INTAKE_LEGACY_AWARE_BACKLOG",
    "AUTOMATION_DUAL_LANE",
    "BULK_DUAL_LANE_CATCHUP",
    "BACKLOG_SPRINT_GPU_ONLY",
    "OLLAMA_DUAL_HOST_ROUTING_ENABLED",
    "OLLAMA_HOST",
    "OLLAMA_POP_OS_HOST",
    "OLLAMA_GPU_HOST",
    "OLLAMA_TIMEOUT",
    "OLLAMA_GPU_CONCURRENCY",
    "OLLAMA_CPU_CONCURRENCY",
    "AUTOMATION_SKIP_RSS_IN_COLLECTION_CYCLE",
    "AUTOMATION_DISABLED_SCHEDULES",
    "AUTOMATION_MAX_CONCURRENT_TASKS",
    "MAX_CONCURRENT_OLLAMA_TASKS",
    "AUTOMATION_PER_PHASE_CONCURRENT_CAP",
    "AUTOMATION_DB_POOL_PRESSURE_GATE_ENABLED",
    "AUTOMATION_DB_WORKER_UTILIZATION_SKIP_THRESHOLD",
    "AUTOMATION_QUEUE_SOFT_CAP",
    "PIPELINE_QUIET_HOURS_DISABLED",
    "PIPELINE_SCHEDULE_TZ",
    "PIPELINE_NIGHTLY_START_HOUR",
    "PIPELINE_NIGHTLY_END_HOUR",
    "PIPELINE_DAYTIME_START_HOUR",
    "PIPELINE_DAYTIME_END_HOUR",
    "PIPELINE_QUIET_ALLOWED_PHASES",
    "PIPELINE_BACKFILL_MODE",
    "PIPELINE_REFINEMENT_BULK_CLEAR_THRESHOLD",
    "PIPELINE_REFINEMENT_ANYTIME",
    "ENTITY_PROFILE_BUILD_ANYTIME",
    "NIGHTLY_PIPELINE_EXCLUSIVE",
    "DB_POOL_WORKER_MAX",
    "DB_POOL_UI_MAX",
    "DB_PORT",
    "COLLECTION_THROTTLE_PENDING_THRESHOLD",
)


def _load_env() -> None:
    env_file = _REPO_ROOT / ".env"
    if env_file.is_file():
        from dotenv import load_dotenv

        load_dotenv(env_file, override=False)


def _emit(section: str, message: str, data: dict[str, Any]) -> None:
    payload = {
        "section": section,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": message,
        "data": data,
    }
    print(json.dumps(payload, default=str))


def _redact_env_value(key: str, val: str) -> str:
    if not val:
        return "(unset)"
    if any(x in key for x in ("PASSWORD", "SECRET", "TOKEN", "KEY")):
        return "***"
    return val


def _env_conflicts(env: dict[str, str]) -> list[str]:
    conflicts: list[str] = []
    unified = env.get("UNIFIED_INTAKE_EXTRACTION_ENABLED", "").lower() in ("1", "true", "yes")
    legacy = env.get("LEGACY_INTAKE_EXTRACTION_ENABLED", "").lower() in ("1", "true", "yes")
    if unified and legacy:
        conflicts.append("UNIFIED_INTAKE_EXTRACTION_ENABLED and LEGACY_INTAKE_EXTRACTION_ENABLED both true")
    dual_lane = env.get("AUTOMATION_DUAL_LANE", "").lower() in ("1", "true", "yes")
    dual_ollama = env.get("OLLAMA_DUAL_HOST_ROUTING_ENABLED", "").lower() in ("1", "true", "yes")
    sprint_gpu = env.get("BACKLOG_SPRINT_GPU_ONLY", "").lower() in ("1", "true", "yes")
    bulk_dual = env.get("BULK_DUAL_LANE_CATCHUP", "").lower() in ("1", "true", "yes")
    if sprint_gpu and bulk_dual:
        conflicts.append("BACKLOG_SPRINT_GPU_ONLY and BULK_DUAL_LANE_CATCHUP both true")
    if dual_lane and not dual_ollama:
        conflicts.append("AUTOMATION_DUAL_LANE on but OLLAMA_DUAL_HOST_ROUTING_ENABLED off")
    pop = (env.get("OLLAMA_POP_OS_HOST") or env.get("OLLAMA_GPU_HOST") or "").strip()
    if dual_ollama and pop and "127.0.0.1" in pop:
        conflicts.append("GPU routing points at localhost — PopOS offload disabled in practice")
    return conflicts


def _probe_url(url: str, timeout: float = 3.0) -> dict[str, Any]:
    base = (url or "").rstrip("/")
    if not base:
        return {"reachable": False, "error": "empty_url"}
    try:
        with urllib.request.urlopen(f"{base}/api/tags", timeout=timeout) as resp:
            raw = json.loads(resp.read().decode())
        models = [m.get("name") for m in (raw.get("models") or []) if m.get("name")]
        return {"reachable": True, "model_count": len(models), "models_sample": models[:5]}
    except Exception as e:
        return {"reachable": False, "error": str(e)[:120]}


def _phase_gate_reason(phase: str, pending: int) -> dict[str, Any]:
    from services.pipeline_schedule_service import (
        automation_phase_allowed,
        pipeline_schedule_info,
    )
    from shared.pipeline_resource_policy import (
        entity_profile_build_allowed,
        intake_extraction_suppressed,
        legacy_intake_extraction_phases,
        refinement_phase_allowed,
    )

    reasons: list[str] = []
    sched = pipeline_schedule_info()
    if not automation_phase_allowed(phase, pending_count=pending):
        reasons.append(f"pipeline_window={sched.get('active_window')} blocks phase")
    if intake_extraction_suppressed() and phase in legacy_intake_extraction_phases():
        reasons.append("legacy_intake_suppressed_by_unified_mode")
    if phase == "unified_intake_extraction" and not intake_extraction_suppressed():
        reasons.append("unified_intake_disabled_legacy_mode_active")
    if not refinement_phase_allowed(phase, {phase: pending}):
        reasons.append("refinement_phase_gated_bulk_not_clear")
    if phase == "entity_profile_build" and not entity_profile_build_allowed({phase: pending}):
        reasons.append("entity_profile_build_gated")
    return {
        "phase": phase,
        "pending": pending,
        "allowed": len(reasons) == 0,
        "block_reasons": reasons,
    }


def main() -> int:
    _load_env()
    from config.runtime import env_str
    import importlib.util

    bm_path = _API_ROOT / "services" / "backlog_metrics.py"
    spec = importlib.util.spec_from_file_location("backlog_metrics_diag", bm_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load backlog_metrics")
    bm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bm)
    get_all_pending_counts = bm.get_all_pending_counts
    from shared.database.connection import get_db_pool_snapshot

    env_snapshot = {
        k: _redact_env_value(k, env_str(k, "")) for k in _SCHEDULING_ENV_KEYS
    }
    conflicts = _env_conflicts(env_snapshot)

    _emit(
        "env",
        "scheduling env snapshot",
        {"env": env_snapshot, "conflicts": conflicts},
    )

    try:
        from services.pipeline_schedule_service import pipeline_schedule_info

        sched = pipeline_schedule_info()
        _emit("window", "pipeline schedule window", sched)
    except Exception as e:
        _emit("window", "schedule info failed", {"error": str(e)})

    widow_ollama = _probe_url(env_str("OLLAMA_HOST", "http://127.0.0.1:11434"))
    pop_ollama = _probe_url(
        env_str("OLLAMA_POP_OS_HOST") or env_str("OLLAMA_GPU_HOST", "")
    )
    _emit(
        "ollama",
        "ollama reachability",
        {
            "widow": widow_ollama,
            "popos": pop_ollama,
            "dual_routing": env_snapshot.get("OLLAMA_DUAL_HOST_ROUTING_ENABLED"),
        },
    )

    try:
        pools = get_db_pool_snapshot()
        worker = pools.get("worker") or {}
        util = float(worker.get("utilization") or 0)
        thr_raw = env_snapshot.get("AUTOMATION_DB_WORKER_UTILIZATION_SKIP_THRESHOLD")
        try:
            thr = float(thr_raw) if thr_raw and thr_raw != "(unset)" else 0.82
        except (TypeError, ValueError):
            thr = 0.82
        _emit(
            "pools",
            "db pool stats",
            {
                "pools": pools,
                "pressure_gate_enabled": env_snapshot.get(
                    "AUTOMATION_DB_POOL_PRESSURE_GATE_ENABLED"
                ),
                "skip_threshold": env_snapshot.get(
                    "AUTOMATION_DB_WORKER_UTILIZATION_SKIP_THRESHOLD"
                ),
                "worker_util_above_threshold": util >= thr,
            },
        )
    except Exception as e:
        _emit("pools", "pool stats failed", {"error": str(e)})

    try:
        pending = get_all_pending_counts()
        top = sorted(
            ((k, int(v or 0)) for k, v in pending.items()),
            key=lambda x: -x[1],
        )[:15]
        gates = [_phase_gate_reason(p, n) for p, n in top if n > 0]
        blocked = [g for g in gates if not g["allowed"]]
        _emit(
            "gates",
            "top pending phase gates",
            {
                "top_pending": top,
                "blocked_count": len(blocked),
                "blocked_phases": blocked[:10],
                "extract_bulk_total": sum(
                    int(pending.get(k, 0) or 0)
                    for k in (
                        "unified_intake_extraction",
                        "entity_extraction",
                        "event_extraction",
                        "claim_extraction",
                    )
                ),
            },
        )
    except Exception as e:
        _emit("gates", "pending gates failed", {"error": str(e)})

    try:
        from services.backlog_metrics import get_all_pending_counts
        from services.pipeline_controller import (
            assess_all_phase_health,
            host_state_dict,
            is_catchup_active,
            pick_next_phases,
            sample_host_resources,
        )

        pending = get_all_pending_counts()
        resources = sample_host_resources(force=True)
        health = assess_all_phase_health(pending, {})
        fake_schedules = {
            p: {"enabled": True, "interval": 300, "phase": 0}
            for p, n in pending.items()
            if int(n or 0) > 0
        }
        fake_schedules.update(
            {
                "collection_cycle": {"enabled": True, "interval": 7200, "phase": 0},
                "health_check": {"enabled": True, "interval": 30, "phase": 0},
                "spine_sql_tail": {"enabled": True, "interval": 300, "phase": 4},
            }
        )

        class _FakeAM:
            schedules = fake_schedules
            _pending_collection_queue = []

        desired, branch = pick_next_phases(
            pending,
            resources,
            health,
            _FakeAM(),
            stall_holds={},
            catchup=is_catchup_active(pending),
        )
        _emit(
            "controller",
            "pipeline controller dry-run",
            {
                "catchup_active": is_catchup_active(pending),
                "tree_branch": branch,
                "desired_phases": desired[:12],
                "hosts": host_state_dict(resources),
                "phase_health": {
                    k: {"status": v.status, "detail": v.detail}
                    for k, v in list(health.items())[:10]
                },
            },
        )
    except Exception as e:
        _emit("controller", "pipeline controller preview failed", {"error": str(e)})

    print(json.dumps({"ok": True, "conflicts": conflicts}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
