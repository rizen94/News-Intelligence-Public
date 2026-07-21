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
    # --- GPU / PopOS LLM drains ---
    "unified_intake_extraction": {
        "track": TRACK_GPU,
        "min": 40,
        "max": 120,
        "step": 10,
    },
    "claim_extraction": {
        "track": TRACK_GPU,
        "min": 32,
        "max": 128,
        "step": 16,
    },
    "topic_clustering": {
        "track": TRACK_GPU,
        "min": 10,
        "max": 40,
        "step": 5,
    },
    "storyline_assembly": {
        "track": TRACK_GPU,
        "min": 10,
        "max": 40,
        "step": 5,
    },
    "storyline_automation": {
        "track": TRACK_GPU,
        "min": 5,
        "max": 25,
        "step": 5,
    },
    "storyline_review_agent": {
        "track": TRACK_GPU,
        "min": 20,
        "max": None,  # headroom / yield gate only — no arbitrary ceiling
        "step": 10,
        "yield_gate": True,
    },
    "fact_verification": {
        "track": TRACK_GPU,
        "min": 10,
        "max": 40,
        "step": 5,
    },
    "content_refinement_queue": {
        "track": TRACK_GPU,
        "min": 2,
        "max": 8,
        "step": 1,
    },
    "ml_processing": {
        "track": TRACK_GPU,
        "min": 25,
        "max": 100,
        "step": 25,
    },
    "sentiment_analysis": {
        "track": TRACK_GPU,
        "min": 50,
        "max": 150,
        "step": 25,
    },
    "entity_extraction": {
        "track": TRACK_GPU,
        "min": 20,
        "max": 80,
        "step": 10,
    },
    "event_extraction": {
        "track": TRACK_GPU,
        "min": 10,
        "max": 60,
        "step": 10,
    },
    # --- Widow local LLM (8B) ---
    "entity_profile_build": {
        "track": TRACK_BUILD,
        "min": 25,
        "max": 150,
        "step": 10,
    },
    # --- Widow fetch / enrich ---
    "content_enrichment": {
        "track": TRACK_ENRICH,
        "min": 60,
        "max": 120,
        "step": 10,
    },
    "document_processing": {
        "track": TRACK_ENRICH,
        "min": 3,
        "max": 15,
        "step": 3,
    },
    "entity_enrichment": {
        "track": TRACK_ENRICH,
        "min": 10,
        "max": 40,
        "step": 5,
    },
    "rag_enhancement": {
        "track": TRACK_ENRICH,
        "min": 3,
        "max": 10,
        "step": 1,
    },
    # --- Widow DB / CPU local ---
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
    "graph_connection_distillation": {
        "track": TRACK_LOCAL,
        "min": 25,
        "max": 200,
        "step": 25,
    },
    "context_sync": {
        "track": TRACK_LOCAL,
        "min": 50,
        "max": 200,
        "step": 25,
    },
    "claims_to_facts": {
        "track": TRACK_LOCAL,
        "min": 2000,
        "max": 15000,
        "step": 1000,
    },
    "embeddings_worker": {
        "track": TRACK_LOCAL,
        "min": 25,
        "max": 100,
        "step": 25,
    },
    "spine_sql_tail": {
        "track": TRACK_LOCAL,
        "min": 50,
        "max": 500,
        "step": 50,
    },
    "quality_scoring": {
        "track": TRACK_LOCAL,
        "min": 25,
        "max": 100,
        "step": 25,
    },
    "metadata_enrichment": {
        "track": TRACK_LOCAL,
        "min": 5,
        "max": 30,
        "step": 5,
    },
    # Mega-thread membership audit (per-domain storyline limit)
    "storyline_membership_review": {
        "track": TRACK_LOCAL,
        "min": 8,
        "max": 48,
        "step": 8,
    },
}


# Phases whose adaptive batch is per-domain (Monitor multiplies by active domain count).
_PER_DOMAIN_BATCH_PHASES = frozenset(
    {
        "unified_intake_extraction",
        "topic_clustering",
        "storyline_assembly",
        "storyline_automation",
        # storyline_review_agent: per-domain limit, but Monitor/backlog must use the
        # single-run limit (not × all domains) — otherwise pending < 5×batch looks idle.
        "context_sync",
        "ml_processing",
        "sentiment_analysis",
        "entity_extraction",
        "event_extraction",
        "quality_scoring",
        "fact_verification",
        "rag_enhancement",
        "metadata_enrichment",
        "storyline_membership_review",
    }
)


def is_adaptive_batch_phase(phase: str) -> bool:
    key = (phase or "").strip().lower().replace("-", "_")
    return key in _PHASE_BOUNDS


def is_per_domain_adaptive_batch(phase: str) -> bool:
    key = (phase or "").strip().lower().replace("-", "_")
    return key in _PER_DOMAIN_BATCH_PHASES


def resolve_phase_batch_limit(
    phase: str,
    default: int,
    *,
    env_suffix: str = "ARTICLES_PER_DOMAIN",
) -> int:
    """Env default via ``phase_batch_limit``, then headroom auto-tune when enabled."""
    from shared.pipeline_batch_drain import phase_batch_limit

    base = phase_batch_limit(phase, default, env_suffix=env_suffix)
    tuned, _meta = resolve_adaptive_batch(phase, base)
    return tuned


def adaptive_batch_enabled() -> bool:
    raw = env_str("AUTOMATION_ADAPTIVE_BATCH_ENABLED", "").strip()
    if raw:
        return env_bool("AUTOMATION_ADAPTIVE_BATCH_ENABLED", False)
    return pipeline_backfill_mode_enabled()


def _tuning_config(bounds: dict[str, Any]) -> dict[str, int | float | None]:
    raw_max = bounds.get("max")
    batch_max = None if raw_max is None else int(raw_max)
    batch_min = int(bounds["min"])
    return {
        "batch_min": batch_min,
        "batch_max": batch_max,
        "batch_step": int(bounds["step"]),
        # Track helpers fall back to batch_max; unbounded → no artificial track cap.
        "build_batch_max": batch_max,
        "enrich_batch_max": batch_max,
        "dossier_fast_batch_min": batch_min,
        "increase_headroom": float(env_str("ADAPTIVE_BATCH_INCREASE_HEADROOM", "0.50")),
        "decrease_headroom": float(env_str("ADAPTIVE_BATCH_DECREASE_HEADROOM", "0.25")),
        "memory_pressure_pct": float(env_str("ADAPTIVE_BATCH_MEMORY_PRESSURE_PCT", "88")),
        "memory_critical_pct": float(env_str("ADAPTIVE_BATCH_MEMORY_CRITICAL_PCT", "94")),
        "gpu_temp_decrease_c": int(env_str("ADAPTIVE_BATCH_GPU_TEMP_DECREASE_C", "82")),
        "gpu_temp_increase_max_c": int(env_str("ADAPTIVE_BATCH_GPU_TEMP_INCREASE_MAX_C", "78")),
    }


def _clamp_batch(value: int, *, batch_min: int, batch_max: int | None) -> int:
    n = max(int(batch_min), int(value))
    if batch_max is not None:
        n = min(int(batch_max), n)
    return n


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


def _load_persisted_state(phase: str) -> dict[str, Any]:
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
            return {}
        payload = row[0]
        if isinstance(payload, str):
            payload = json.loads(payload)
        return payload if isinstance(payload, dict) else {}
    except Exception as e:
        logger.debug("adaptive_batch load_state %s: %s", phase, e)
        return {}


def _load_persisted_batch(phase: str) -> int | None:
    payload = _load_persisted_state(phase)
    if payload.get("batch") is not None:
        try:
            return int(payload["batch"])
        except (TypeError, ValueError):
            return None
    return None


def _persist_batch(phase: str, batch: int, meta: dict[str, Any]) -> None:
    try:
        from shared.database.connection import get_db_connection_context

        # Preserve last_yield across tune writes so yield-gate can see prior run.
        existing = _load_persisted_state(phase)
        payload = {**existing, "batch": int(batch), **meta}
        if "last_yield" in existing and "last_yield" not in meta:
            payload["last_yield"] = existing["last_yield"]
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.automation_state (key, value, updated_at)
                    VALUES (%s, %s::jsonb, NOW())
                    ON CONFLICT (key) DO UPDATE
                      SET value = EXCLUDED.value, updated_at = NOW()
                    """,
                    (_state_key(phase), json.dumps(payload, default=str)),
                )
            conn.commit()
    except Exception as e:
        logger.debug("adaptive_batch persist %s: %s", phase, e)


def record_adaptive_batch_yield(
    phase: str,
    *,
    approved: int = 0,
    rejected: int = 0,
    skipped: int = 0,
    errors: int = 0,
    batch_limit: int | None = None,
) -> dict[str, Any]:
    """
    Persist per-run decision yield for phases with ``yield_gate``.

    Used on the next ``resolve_adaptive_batch`` to hold/decrease when headroom
    looks fine but the prior drain was mostly skips / empty decisions.
    """
    phase_key = (phase or "").strip().lower().replace("-", "_")
    decided = max(0, int(approved) + int(rejected))
    skipped_n = max(0, int(skipped))
    errors_n = max(0, int(errors))
    attempted = decided + skipped_n + errors_n
    yield_info = {
        "approved": max(0, int(approved)),
        "rejected": max(0, int(rejected)),
        "skipped": skipped_n,
        "errors": errors_n,
        "attempted": attempted,
        "decided": decided,
        "decision_rate": (float(decided) / float(attempted)) if attempted > 0 else None,
        "skip_rate": (float(skipped_n) / float(attempted)) if attempted > 0 else None,
        "batch_limit": int(batch_limit) if batch_limit is not None else None,
    }
    try:
        from shared.database.connection import get_db_connection_context

        existing = _load_persisted_state(phase_key)
        payload = {**existing, "last_yield": yield_info}
        if existing.get("batch") is not None:
            payload["batch"] = int(existing["batch"])
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.automation_state (key, value, updated_at)
                    VALUES (%s, %s::jsonb, NOW())
                    ON CONFLICT (key) DO UPDATE
                      SET value = EXCLUDED.value, updated_at = NOW()
                    """,
                    (_state_key(phase_key), json.dumps(payload, default=str)),
                )
            conn.commit()
    except Exception as e:
        logger.debug("adaptive_batch record_yield %s: %s", phase_key, e)
    return yield_info


def _yield_gate_thresholds() -> dict[str, float | int]:
    def _f(name: str, default: float) -> float:
        try:
            return float(env_str(name, str(default)) or default)
        except (TypeError, ValueError):
            return default

    def _i(name: str, default: int) -> int:
        try:
            return max(1, int(env_str(name, str(default)) or default))
        except (TypeError, ValueError):
            return default

    return {
        "min_attempted": _i("ADAPTIVE_BATCH_YIELD_MIN_ATTEMPTED", 40),
        "min_decision_rate": _f("ADAPTIVE_BATCH_YIELD_MIN_DECISION_RATE", 0.10),
        "max_skip_rate": _f("ADAPTIVE_BATCH_YIELD_MAX_SKIP_RATE", 0.80),
        "severe_decision_rate": _f("ADAPTIVE_BATCH_YIELD_SEVERE_DECISION_RATE", 0.05),
        "severe_skip_rate": _f("ADAPTIVE_BATCH_YIELD_SEVERE_SKIP_RATE", 0.90),
    }


def _apply_yield_gate(
    phase_key: str,
    bounds: dict[str, Any],
    *,
    current: int,
    new_batch: int,
    action: str,
    meta: dict[str, Any],
) -> tuple[int, str, dict[str, Any]]:
    """Hold or decrease when prior-run decision yield was poor."""
    if not bounds.get("yield_gate"):
        return new_batch, action, meta

    state = _load_persisted_state(phase_key)
    last = state.get("last_yield") if isinstance(state.get("last_yield"), dict) else None
    if not last:
        meta["yield_gate"] = "no_prior_yield"
        return new_batch, action, meta

    thr = _yield_gate_thresholds()
    attempted = int(last.get("attempted") or 0)
    if attempted < int(thr["min_attempted"]):
        meta["yield_gate"] = "attempted_below_min"
        meta["last_yield"] = last
        return new_batch, action, meta

    decision_rate = last.get("decision_rate")
    skip_rate = last.get("skip_rate")
    try:
        decision_rate_f = float(decision_rate) if decision_rate is not None else 0.0
    except (TypeError, ValueError):
        decision_rate_f = 0.0
    try:
        skip_rate_f = float(skip_rate) if skip_rate is not None else 0.0
    except (TypeError, ValueError):
        skip_rate_f = 0.0

    meta["last_yield"] = last
    poor = (
        decision_rate_f < float(thr["min_decision_rate"])
        or skip_rate_f > float(thr["max_skip_rate"])
    )
    severe = (
        decision_rate_f < float(thr["severe_decision_rate"])
        or skip_rate_f >= float(thr["severe_skip_rate"])
    )
    step = max(1, int(bounds.get("step") or 1))
    batch_min = int(bounds["min"])

    if severe:
        tuned = max(batch_min, int(current) - step)
        meta["yield_gate"] = "decrease_low_yield"
        meta["yield_decision_rate"] = decision_rate_f
        meta["yield_skip_rate"] = skip_rate_f
        return tuned, "decrease_low_yield", meta

    if poor:
        # Do not climb on headroom when prior drain was mostly skips.
        meta["yield_gate"] = "hold_low_yield"
        meta["yield_decision_rate"] = decision_rate_f
        meta["yield_skip_rate"] = skip_rate_f
        if action == "increase" or int(new_batch) > int(current):
            return int(current), "hold_low_yield", meta
        return new_batch, action, meta

    meta["yield_gate"] = "ok"
    meta["yield_decision_rate"] = decision_rate_f
    meta["yield_skip_rate"] = skip_rate_f
    return new_batch, action, meta


def apply_adaptive_batch_yield_gate(phase: str) -> tuple[int, dict[str, Any]]:
    """
    Re-apply yield gate to the persisted batch without a headroom probe.

    Call after ``record_adaptive_batch_yield`` so skip-heavy runs shrink (or hold)
    immediately for Monitor / the next candidate, without double-stepping an increase.
    """
    phase_key = (phase or "").strip().lower().replace("-", "_")
    bounds = _PHASE_BOUNDS.get(phase_key)
    if bounds is None or not bounds.get("yield_gate"):
        current = _load_persisted_batch(phase_key)
        return int(current or 0), {"phase": phase_key, "adaptive": False, "yield_gate": "n/a"}

    current = _load_persisted_batch(phase_key)
    if current is None:
        current = int(bounds["min"])
    current = _clamp_batch(
        int(current), batch_min=int(bounds["min"]), batch_max=bounds.get("max")
    )
    meta: dict[str, Any] = {"phase": phase_key, "adaptive": True, "track": bounds.get("track")}
    new_batch, action, meta = _apply_yield_gate(
        phase_key,
        bounds,
        current=current,
        new_batch=current,
        action="hold",
        meta=meta,
    )
    new_batch = _clamp_batch(
        int(new_batch), batch_min=int(bounds["min"]), batch_max=bounds.get("max")
    )
    meta["action"] = action
    meta["batch_before"] = current
    meta["batch_after"] = new_batch
    if int(new_batch) != int(current):
        _persist_batch(phase_key, new_batch, meta)
    else:
        # Still refresh metadata (yield_gate status) alongside existing batch.
        state = _load_persisted_state(phase_key)
        payload = {**state, **meta, "batch": int(new_batch)}
        try:
            from shared.database.connection import get_db_connection_context

            with get_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO public.automation_state (key, value, updated_at)
                        VALUES (%s, %s::jsonb, NOW())
                        ON CONFLICT (key) DO UPDATE
                          SET value = EXCLUDED.value, updated_at = NOW()
                        """,
                        (_state_key(phase_key), json.dumps(payload, default=str)),
                    )
                conn.commit()
        except Exception as e:
            logger.debug("adaptive_batch yield_gate refresh %s: %s", phase_key, e)
    return int(new_batch), meta


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
    phase_key = (phase or "").strip().lower().replace("-", "_")
    bounds = _PHASE_BOUNDS.get(phase_key)
    if bounds is None:
        return default, {"phase": phase, "adaptive": False}

    current = _load_persisted_batch(phase) or default
    current = _clamp_batch(
        int(current), batch_min=int(bounds["min"]), batch_max=bounds.get("max")
    )

    if not adaptive_batch_enabled():
        return current, {"phase": phase, "adaptive": False, "action": "disabled"}

    ensure_routing_context()
    snap = resources if resources is not None else sample_resources()
    cfg = _tuning_config(bounds)
    track = str(bounds["track"])

    if track in (TRACK_BUILD, TRACK_GPU, TRACK_ENRICH, TRACK_LOCAL, TRACK_DOSSIER_FAST):
        if phase_key in ("entity_dossier_compile", "entity_profile_build", "event_extraction"):
            new_batch, action, meta = tune_batch_size(
                phase_key, current, snap, auto_tune=True, tuning_config=cfg
            )
        else:
            new_batch, action, meta = tune_batch_track(
                track, current, snap, auto_tune=True, tuning_config=cfg
            )
            meta["phase"] = phase_key
    else:
        new_batch, action, meta = tune_batch_track(
            track, current, snap, auto_tune=True, tuning_config=cfg
        )
        meta["phase"] = phase_key

    new_batch, action, meta = _apply_yield_gate(
        phase_key,
        bounds,
        current=current,
        new_batch=int(new_batch),
        action=action,
        meta=meta,
    )

    new_batch = _clamp_batch(
        int(new_batch), batch_min=int(bounds["min"]), batch_max=bounds.get("max")
    )
    meta["adaptive"] = True
    meta["action"] = action
    meta["batch_before"] = current
    meta["batch_after"] = new_batch
    _persist_batch(phase, new_batch, meta)
    return new_batch, meta


def get_persisted_adaptive_batch(phase: str) -> int | None:
    """Last persisted per-domain batch for Monitor config fallbacks."""
    return _load_persisted_batch(phase)
