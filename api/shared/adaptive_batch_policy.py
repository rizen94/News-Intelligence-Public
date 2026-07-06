"""Steady-state adaptive batch sizing (headroom probes from catchup_host_metrics)."""

from __future__ import annotations

import json
import logging
from typing import Any

from config.runtime import env_bool, env_str
from shared.catchup_host_metrics import (
    TRACK_BUILD,
    TRACK_DOSSIER_FAST,
    TRACK_ENRICH,
    TRACK_GPU,
    TRACK_LOCAL,
    ResourceSnapshot,
    RoutingContext,
    sample_resources,
    set_routing_context,
    tune_batch_size,
    tune_batch_track,
)
from shared.pipeline_article_selection import pipeline_backfill_mode_enabled

logger = logging.getLogger(__name__)

_STATE_PREFIX = "adaptive_batch:"

_PHASE_BOUNDS: dict[str, dict[str, Any]] = {
    "unified_intake_extraction": {
        "track": TRACK_GPU,
        "min": 40,
        "max": 120,
        "step": 10,
    },
    "entity_profile_build": {
        "track": TRACK_BUILD,
        "min": 25,
        "max": 150,
        "step": 10,
    },
    "entity_dossier_compile": {
        "track": TRACK_DOSSIER_FAST,
        "min": 20,
        "max": 100,
        "step": 10,
    },
    "event_tracking": {
        "track": TRACK_LOCAL,
        "min": 25,
        "max": 300,
        "step": 25,
    },
    "content_enrichment": {
        "track": TRACK_ENRICH,
        "min": 60,
        "max": 120,
        "step": 10,
    },
}


def adaptive_batch_enabled() -> bool:
    raw = env_str("AUTOMATION_ADAPTIVE_BATCH_ENABLED", "").strip()
    if raw:
        return env_bool("AUTOMATION_ADAPTIVE_BATCH_ENABLED", False)
    return pipeline_backfill_mode_enabled()


def _tuning_config(bounds: dict[str, Any]) -> dict[str, int | float]:
    return {
        "batch_min": int(bounds["min"]),
        "batch_max": int(bounds["max"]),
        "batch_step": int(bounds["step"]),
        "build_batch_max": int(bounds["max"]),
        "enrich_batch_max": int(bounds["max"]),
        "dossier_fast_batch_min": int(bounds["min"]),
        "increase_headroom": float(env_str("ADAPTIVE_BATCH_INCREASE_HEADROOM", "0.50")),
        "decrease_headroom": float(env_str("ADAPTIVE_BATCH_DECREASE_HEADROOM", "0.25")),
        "memory_pressure_pct": float(env_str("ADAPTIVE_BATCH_MEMORY_PRESSURE_PCT", "88")),
        "memory_critical_pct": float(env_str("ADAPTIVE_BATCH_MEMORY_CRITICAL_PCT", "94")),
        "gpu_temp_decrease_c": int(env_str("ADAPTIVE_BATCH_GPU_TEMP_DECREASE_C", "82")),
        "gpu_temp_increase_max_c": int(env_str("ADAPTIVE_BATCH_GPU_TEMP_INCREASE_MAX_C", "78")),
    }


def ensure_routing_context() -> None:
    dual = env_str("OLLAMA_DUAL_HOST_ROUTING_ENABLED", "").lower() in ("1", "true", "yes")
    gpu_url = env_str("OLLAMA_GPU_HOST", env_str("OLLAMA_POP_OS_HOST", "")).strip()
    cpu_url = env_str("OLLAMA_CPU_HOST", env_str("OLLAMA_HOST", "http://localhost:11434")).strip()
    set_routing_context(
        RoutingContext(
            popos_gpu=bool(gpu_url),
            dual_lane=dual and bool(gpu_url),
            gpu_ollama_url=gpu_url,
            cpu_ollama_url=cpu_url,
        )
    )


def _state_key(phase: str) -> str:
    return f"{_STATE_PREFIX}{(phase or '').strip().lower().replace('-', '_')}"


def _load_persisted_batch(phase: str) -> int | None:
    try:
        from shared.database.connection import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT value FROM public.automation_state WHERE key = %s",
                    (_state_key(phase),),
                )
                row = cur.fetchone()
        if not row or row[0] is None:
            return None
        payload = row[0]
        if isinstance(payload, str):
            payload = json.loads(payload)
        if isinstance(payload, dict) and payload.get("batch") is not None:
            return int(payload["batch"])
        if isinstance(payload, (int, float)):
            return int(payload)
    except Exception as e:
        logger.debug("adaptive_batch load %s: %s", phase, e)
    return None


def _persist_batch(phase: str, batch: int, meta: dict[str, Any]) -> None:
    try:
        from shared.database.connection import get_db_connection_context

        payload = {"batch": int(batch), **meta}
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.automation_state (key, value, updated_at)
                    VALUES (%s, %s::jsonb, NOW())
                    ON CONFLICT (key) DO UPDATE
                      SET value = EXCLUDED.value, updated_at = NOW()
                    """,
                    (_state_key(phase), json.dumps(payload)),
                )
            conn.commit()
    except Exception as e:
        logger.debug("adaptive_batch persist %s: %s", phase, e)


def resolve_adaptive_batch(
    phase: str,
    default: int,
    *,
    resources: ResourceSnapshot | None = None,
) -> tuple[int, dict[str, Any]]:
    """
    Return tuned batch size for ``phase`` and tuning metadata.

    When adaptive batching is disabled, returns ``default`` unchanged.
    """
    bounds = _PHASE_BOUNDS.get((phase or "").strip().lower().replace("-", "_"))
    if bounds is None:
        return default, {"phase": phase, "adaptive": False}

    current = _load_persisted_batch(phase) or default
    current = max(int(bounds["min"]), min(int(bounds["max"]), int(current)))

    if not adaptive_batch_enabled():
        return current, {"phase": phase, "adaptive": False, "action": "disabled"}

    ensure_routing_context()
    snap = resources if resources is not None else sample_resources()
    cfg = _tuning_config(bounds)
    track = str(bounds["track"])

    if track in (TRACK_BUILD, TRACK_GPU, TRACK_ENRICH, TRACK_LOCAL, TRACK_DOSSIER_FAST):
        if phase in ("entity_dossier_compile", "entity_profile_build", "event_extraction"):
            new_batch, action, meta = tune_batch_size(
                phase, current, snap, auto_tune=True, tuning_config=cfg
            )
        else:
            new_batch, action, meta = tune_batch_track(
                track, current, snap, auto_tune=True, tuning_config=cfg
            )
            meta["phase"] = phase
    else:
        new_batch, action, meta = tune_batch_track(
            track, current, snap, auto_tune=True, tuning_config=cfg
        )
        meta["phase"] = phase

    new_batch = max(int(bounds["min"]), min(int(bounds["max"]), int(new_batch)))
    meta["adaptive"] = True
    meta["batch_before"] = current
    meta["batch_after"] = new_batch
    _persist_batch(phase, new_batch, meta)
    return new_batch, meta


def get_persisted_adaptive_batch(phase: str) -> int | None:
    """Last persisted per-domain batch for Monitor config fallbacks."""
    return _load_persisted_batch(phase)
