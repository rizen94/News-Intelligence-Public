"""Steady-state adaptive batch sizing (headroom probes from catchup_host_metrics)."""

from __future__ import annotations

import json
import logging
from typing import Any

from config.runtime import env_bool, env_float, env_int, env_str
from shared.catchup_host_metrics import (
    TRACK_BUILD,
    TRACK_CHEMISTRY_LOCAL,
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
from shared.phase_spec import overlay_adaptive_bounds

logger = logging.getLogger(__name__)

_STATE_PREFIX = "adaptive_batch:"

_PHASE_BOUNDS: dict[str, dict[str, Any]] = {
    # --- GPU / PopOS LLM drains ---
    "unified_intake_extraction": {
        "track": TRACK_GPU,
        "min": 80,
        "max": None,
        "step": 40,
    },
    "claim_extraction": {
        "track": TRACK_GPU,
        "min": 64,
        "max": None,
        "step": 32,
    },
    "topic_clustering": {
        "track": TRACK_GPU,
        "min": 80,
        "max": None,
        "step": 40,
    },
    "storyline_assembly": {
        "track": TRACK_GPU,
        "min": 40,
        "max": None,
        "step": 20,
    },
    "storyline_automation": {
        "track": TRACK_GPU,
        "min": 25,
        "max": None,
        "step": 15,
    },
    "storyline_review_agent": {
        "track": TRACK_GPU,
        "min": 40,
        "max": None,  # headroom / yield gate only — no arbitrary ceiling
        "step": 20,
        "yield_gate": True,
    },
    "fact_verification": {
        "track": TRACK_GPU,
        "min": 40,
        "max": None,
        "step": 20,
    },
    "content_refinement_queue": {
        "track": TRACK_GPU,
        "min": 8,
        "max": None,
        "step": 4,
    },
    "ml_processing": {
        "track": TRACK_GPU,
        "min": 50,
        "max": None,
        "step": 25,
    },
    "sentiment_analysis": {
        "track": TRACK_GPU,
        "min": 100,
        "max": None,
        "step": 50,
    },
    "entity_extraction": {
        "track": TRACK_GPU,
        "min": 40,
        "max": None,
        "step": 20,
    },
    "event_extraction": {
        "track": TRACK_GPU,
        "min": 40,
        "max": None,
        "step": 20,
    },
    # --- Widow local LLM (8B) ---
    "entity_profile_build": {
        "track": TRACK_BUILD,
        "min": 50,
        "max": None,
        "step": 25,
    },
    # --- Widow fetch / enrich ---
    "content_enrichment": {
        "track": TRACK_ENRICH,
        "min": 100,
        "max": None,
        "step": 40,
    },
    "document_processing": {
        "track": TRACK_ENRICH,
        "min": 15,
        "max": None,
        "step": 5,
    },
    "entity_enrichment": {
        "track": TRACK_ENRICH,
        "min": 40,
        "max": None,
        "step": 20,
    },
    "rag_enhancement": {
        "track": TRACK_ENRICH,
        "min": 20,
        "max": None,
        "step": 10,
    },
    # --- Widow DB / CPU local ---
    "entity_dossier_compile": {
        "track": TRACK_DOSSIER_FAST,
        "min": 80,
        "max": None,
        "step": 40,
    },
    "event_tracking": {
        "track": TRACK_LOCAL,
        "min": 100,
        "max": None,
        "step": 50,
    },
    "graph_connection_distillation": {
        "track": TRACK_LOCAL,
        "min": 100,
        "max": None,
        "step": 50,
    },
    "graph_link_drift_review": {
        "track": TRACK_LOCAL,
        "min": 80,
        "max": None,
        "step": 40,
    },
    "context_sync": {
        "track": TRACK_LOCAL,
        "min": 100,
        "max": None,
        "step": 50,
    },
    "claims_to_facts": {
        "track": TRACK_LOCAL,
        "min": 500,
        "max": None,
        "step": 250,
    },
    "embeddings_worker": {
        "track": TRACK_LOCAL,
        "min": 100,
        "max": None,
        "step": 50,
    },
    "spine_sql_tail": {
        "track": TRACK_LOCAL,
        "min": 200,
        "max": None,
        "step": 100,
    },
    "quality_scoring": {
        "track": TRACK_LOCAL,
        "min": 50,
        "max": None,
        "step": 25,
    },
    "metadata_enrichment": {
        "track": TRACK_LOCAL,
        "min": 25,
        "max": None,
        "step": 10,
    },
    # Mega-thread membership audit (per-domain storyline limit)
    "storyline_membership_review": {
        "track": TRACK_LOCAL,
        "min": 100,
        "max": None,
        "step": 50,
    },
    "storyline_hygiene": {
        "track": TRACK_LOCAL,
        "min": 40,
        "max": None,
        "step": 20,
    },
    # --- Chemistry beaker (DB-light sampling; phase_spec overlay is SSOT) ---
    "embedding_link_candidates": {
        "track": TRACK_CHEMISTRY_LOCAL,
        "min": 40,
        "max": None,
        "step": 20,
    },
    "collision_sampling": {
        "track": TRACK_CHEMISTRY_LOCAL,
        "min": 64,
        "max": None,
        "step": 32,
    },
    "stimulus_rag": {
        "track": TRACK_ENRICH,
        "min": 40,
        "max": None,
        "step": 20,
    },
    "protein_harden": {
        "track": TRACK_LOCAL,
        "min": 80,
        "max": None,
        "step": 40,
    },
    # --- Other active drains ---
    "mention_resolution": {
        "track": TRACK_LOCAL,
        "min": 200,
        "max": None,
        "step": 100,
    },
    "legislative_references": {
        "track": TRACK_ENRICH,
        "min": 20,
        "max": None,
        "step": 10,
    },
    "entity_organizer": {
        "track": TRACK_LOCAL,
        "min": 200,
        "max": None,
        "step": 100,
    },
    "event_deduplication": {
        "track": TRACK_LOCAL,
        "min": 100,
        "max": 500,
        "step": 50,
    },
    "story_continuation": {
        "track": TRACK_LOCAL,
        "min": 40,
        "max": 200,
        "step": 20,
    },
}

# High-churn phases: PhaseSpec overlays adaptive min/max/step (spec wins).
_PHASE_BOUNDS = overlay_adaptive_bounds(_PHASE_BOUNDS)

# Additional batchable phases from Monitor BATCH_SIZE_PER_TASK that lack explicit bounds above.
# Tracks are inferred; min/max/step derived from the Monitor batch default.
_EXTRA_BATCH_DEFAULTS: dict[str, int] = {
    "investigation_report_refresh": 8,
    "entity_profile_sync": 500,
    "story_enhancement": 50,
    "storyline_synthesis": 16,
    "storyline_processing": 24,
    "timeline_generation": 36,
    "storyline_discovery": 50,
    "proactive_detection": 1000,
    "pending_db_flush": 200,
    "content_enrichment": 80,  # already bounded; harmless if re-seed skipped
    "event_tracking": 100,
    "claim_extraction": 64,
}

_GPU_INFER = frozenset(
    {
        "unified_intake_extraction",
        "claim_extraction",
        "topic_clustering",
        "storyline_assembly",
        "storyline_automation",
        "storyline_review_agent",
        "fact_verification",
        "content_refinement_queue",
        "ml_processing",
        "sentiment_analysis",
        "entity_extraction",
        "event_extraction",
        "storyline_synthesis",
        "storyline_discovery",
        "investigation_report_refresh",
    }
)
_ENRICH_INFER = frozenset(
    {
        "content_enrichment",
        "document_processing",
        "entity_enrichment",
        "rag_enhancement",
        "legislative_references",
        "stimulus_rag",
        "story_enhancement",
        "timeline_generation",
    }
)
_BUILD_INFER = frozenset({"entity_profile_build"})
_DOSSIER_INFER = frozenset({"entity_dossier_compile"})


def _infer_track(phase_key: str) -> str:
    if phase_key in _GPU_INFER:
        return TRACK_GPU
    if phase_key in _ENRICH_INFER:
        return TRACK_ENRICH
    if phase_key in _BUILD_INFER:
        return TRACK_BUILD
    if phase_key in _DOSSIER_INFER:
        return TRACK_DOSSIER_FAST
    return TRACK_LOCAL


def synthesize_phase_bounds(phase_key: str, default: int) -> dict[str, Any]:
    """Derive min/max/step around a phase default so any batchable phase can auto-tune."""
    d = max(1, int(default))
    if d >= 200:
        step = max(25, d // 10)
    elif d >= 50:
        step = max(10, d // 10)
    elif d >= 20:
        step = max(5, d // 5)
    elif d >= 8:
        step = max(2, d // 4)
    else:
        step = 1
    mn = max(1, d - 2 * step)
    # No artificial ceiling — headroom / yield-gate balance batch size.
    return {
        "track": _infer_track(phase_key),
        "min": mn,
        "max": None,
        "step": step,
    }


def _seed_extra_phase_bounds() -> None:
    for name, default in _EXTRA_BATCH_DEFAULTS.items():
        if name in _PHASE_BOUNDS:
            continue
        _PHASE_BOUNDS[name] = synthesize_phase_bounds(name, default)


_seed_extra_phase_bounds()


def ensure_phase_bounds(phase_key: str, default: int) -> dict[str, Any]:
    """Return bounds for ``phase_key``, synthesizing + caching when unregistered."""
    key = (phase_key or "").strip().lower().replace("-", "_")
    existing = _PHASE_BOUNDS.get(key)
    if existing is not None:
        return existing
    base = max(1, int(default or 10))
    try:
        from services.backlog_metrics import BATCH_SIZE_PER_TASK

        mon = BATCH_SIZE_PER_TASK.get(key)
        if mon is not None and int(mon) > 0:
            base = int(mon)
    except Exception:
        pass
    bounds = synthesize_phase_bounds(key, base)
    _PHASE_BOUNDS[key] = bounds
    return bounds


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
        "storyline_hygiene",
        "embedding_link_candidates",
        "legislative_references",
        "story_continuation",
    }
)


def is_adaptive_batch_phase(phase: str) -> bool:
    """True for any non-empty phase name (bounds are explicit or synthesized on resolve)."""
    key = (phase or "").strip().lower().replace("-", "_")
    return bool(key)


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
    """
    Headroom auto-tune for automation batch sizes.

    Default **on**. Set ``AUTOMATION_ADAPTIVE_BATCH_ENABLED=false`` to freeze at
    env/defaults (persisted batch still returned when present).
    """
    raw = env_str("AUTOMATION_ADAPTIVE_BATCH_ENABLED", "").strip()
    if raw:
        return env_bool("AUTOMATION_ADAPTIVE_BATCH_ENABLED", True)
    return True


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
        "increase_headroom": env_float("ADAPTIVE_BATCH_INCREASE_HEADROOM", 0.35),
        "decrease_headroom": env_float("ADAPTIVE_BATCH_DECREASE_HEADROOM", 0.25),
        "memory_pressure_pct": env_float("ADAPTIVE_BATCH_MEMORY_PRESSURE_PCT", 88.0),
        "memory_critical_pct": env_float("ADAPTIVE_BATCH_MEMORY_CRITICAL_PCT", 94.0),
        "gpu_temp_decrease_c": env_int("ADAPTIVE_BATCH_GPU_TEMP_DECREASE_C", 82),
        "gpu_temp_increase_max_c": env_int("ADAPTIVE_BATCH_GPU_TEMP_INCREASE_MAX_C", 78),
    }


def _clamp_batch(value: int, *, batch_min: int, batch_max: int | None) -> int:
    n = max(int(batch_min), int(value))
    if batch_max is not None:
        n = min(int(batch_max), n)
    return n


def ensure_routing_context() -> None:
    dual = env_bool("OLLAMA_DUAL_HOST_ROUTING_ENABLED", False)
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
    return {
        "min_attempted": max(1, env_int("ADAPTIVE_BATCH_YIELD_MIN_ATTEMPTED", 40)),
        "min_decision_rate": env_float("ADAPTIVE_BATCH_YIELD_MIN_DECISION_RATE", 0.10),
        "max_skip_rate": env_float("ADAPTIVE_BATCH_YIELD_MAX_SKIP_RATE", 0.80),
        "severe_decision_rate": env_float("ADAPTIVE_BATCH_YIELD_SEVERE_DECISION_RATE", 0.05),
        "severe_skip_rate": env_float("ADAPTIVE_BATCH_YIELD_SEVERE_SKIP_RATE", 0.90),
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


def _pending_for_phase(phase_key: str) -> int | None:
    """Best-effort queue depth for catch-up boost (never raises)."""
    try:
        from services.backlog_metrics import get_all_pending_counts

        pending = get_all_pending_counts() or {}
        return max(0, int(pending.get(phase_key, 0) or 0))
    except Exception:
        return None


def _apply_catchup_boost(
    phase_key: str,
    bounds: dict[str, Any],
    *,
    current: int,
    new_batch: int,
    action: str,
    meta: dict[str, Any],
) -> tuple[int, str, dict[str, Any]]:
    """
    When backlog dwarfs the current batch, ramp hard so drains can catch up.

    No hard ceiling — host headroom will pull back on later resolves if needed.

    Severe backlog may still lift off ``hold_floor`` (tempered); ``decrease`` under
    active pressure is left alone so hot hosts can shed load.
    """
    if action == "decrease":
        return new_batch, action, meta
    pending = _pending_for_phase(phase_key)
    if pending is None or pending <= 0:
        return new_batch, action, meta

    step = max(1, int(bounds.get("step") or 1))
    batch = max(int(new_batch), int(current), int(bounds["min"]))
    track = str(bounds.get("track") or "")
    # Severe backlog: jump toward clearing in far fewer runs.
    if pending >= max(200, batch * 20):
        # Aim to clear in ~200 runs, but never more than 8× current in one resolve.
        eta_target = max(batch, (pending + 199) // 200)
        jump = max(batch * 2, batch + step * 8, eta_target)
        jump = min(jump, max(batch * 8, batch + step * 16))
        if track == TRACK_GPU:
            jump = min(jump, max(batch * 4, batch + step * 12))
        # hold_floor = low headroom: only a modest lift so we do not sit at min forever.
        if action == "hold_floor":
            jump = min(jump, max(batch * 2, batch + step * 4, int(bounds["min"]) * 2))
        if jump > new_batch:
            meta = {
                **meta,
                "catchup_boost": True,
                "pending": pending,
                "reason": f"{meta.get('reason') or 'headroom_ok'},catchup_boost",
            }
            return int(jump), "increase_catchup", meta
    if pending >= max(50, batch * 8) and action in ("increase", "hold"):
        jump = max(new_batch + step * 3, batch + step * 3)
        jump = min(jump, max(batch * 4, batch + step * 8))
        if jump > new_batch:
            meta = {
                **meta,
                "catchup_boost": True,
                "pending": pending,
                "reason": f"{meta.get('reason') or 'headroom_ok'},catchup_boost",
            }
            return int(jump), "increase_catchup", meta
    return new_batch, action, meta


def resolve_adaptive_batch(
    phase: str,
    default: int,
    *,
    resources: ResourceSnapshot | None = None,
) -> tuple[int, dict[str, Any]]:
    """
    Return tuned batch size for ``phase`` and tuning metadata.

    Unknown phases get synthesized bounds from ``default`` / Monitor
    ``BATCH_SIZE_PER_TASK`` so every batchable drain can auto-tune.
    When adaptive batching is disabled, returns clamped default/persisted size.

    Batch sizing uses host CPU/RAM (and GPU for GPU tracks) only — **never**
    worker DB pool utilization. Pool capacity is owned by worker/exec limits and
    ``DB_POOL_WORKER_MAX``. Large backlogs get an extra catch-up boost when
    host headroom allows.
    """
    phase_key = (phase or "").strip().lower().replace("-", "_")
    bounds = ensure_phase_bounds(phase_key, default)

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

    if track in (
        TRACK_BUILD,
        TRACK_GPU,
        TRACK_ENRICH,
        TRACK_LOCAL,
        TRACK_CHEMISTRY_LOCAL,
        TRACK_DOSSIER_FAST,
    ):
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

    new_batch, action, meta = _apply_catchup_boost(
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
    meta["bounds"] = {
        "min": bounds.get("min"),
        "max": bounds.get("max"),
        "step": bounds.get("step"),
        "track": bounds.get("track"),
    }
    _persist_batch(phase, new_batch, meta)
    return new_batch, meta


def list_adaptive_batch_phases() -> list[str]:
    """Registered phase keys (explicit + seeded extras)."""
    return sorted(_PHASE_BOUNDS.keys())


def get_persisted_adaptive_batch(phase: str) -> int | None:
    """Last persisted per-domain batch for Monitor config fallbacks."""
    return _load_persisted_batch(phase)
