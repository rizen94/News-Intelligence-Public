"""
Unified backlog catch-up routing: single profile, PopOS GPU lane pool.

Used by run_backlog_gpu_sprint.py and wired into major/bulk catch-up executors.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import urllib.request
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from config.runtime import env_set, env_str
from shared.bulk_catchup_llm_routing import configure_catchup_extraction_routing

logger = logging.getLogger(__name__)

T = TypeVar("T")

SPRINT_ACTIVE_ENV = "BACKLOG_SPRINT_ACTIVE"
SPRINT_GPU_ONLY_ENV = "BACKLOG_SPRINT_GPU_ONLY"


@dataclass(frozen=True)
class BacklogRunProfile:
    """Single catch-up profile — env prefix BACKLOG_SPRINT_*."""

    gpu_host: str = "http://192.168.93.99:11434"
    gpu_model_extraction: str = "qwen2.5:32b-instruct"
    gpu_model_fast: str = "llama3.1:8b"
    gpu_parallel_heavy: int = 3
    gpu_parallel_fast: int = 8
    dual_lane: bool = False
    floor: int = 200
    max_loops: int = 50
    batch_event: int = 500
    batch_entity_per_domain: int = 500
    batch_claim: int = 5000
    batch_story_enrich: int = 500
    batch_story_build: int = 200
    batch_profile: int = 200
    batch_dossier: int = 200
    batch_embed: int = 500
    batch_context_sync: int = 500
    batch_metadata: int = 80
    batch_content: int = 120
    ollama_timeout: int = 900

    @classmethod
    def from_env(cls) -> BacklogRunProfile:
        def _i(name: str, default: int) -> int:
            try:
                return int(env_str(name, str(default)))
            except ValueError:
                return default

        return cls(
            gpu_host=env_str("BACKLOG_SPRINT_GPU_HOST", "http://192.168.93.99:11434").rstrip("/"),
            gpu_model_extraction=env_str(
                "BACKLOG_SPRINT_GPU_MODEL_EXTRACTION", "qwen2.5:32b-instruct"
            ),
            gpu_model_fast=env_str("BACKLOG_SPRINT_GPU_MODEL_FAST", "llama3.1:8b"),
            gpu_parallel_heavy=_i("BACKLOG_SPRINT_GPU_PARALLEL_HEAVY", 3),
            gpu_parallel_fast=_i("BACKLOG_SPRINT_GPU_PARALLEL_FAST", 8),
            dual_lane=env_str("BACKLOG_SPRINT_DUAL_LANE", "false").lower() in ("1", "true", "yes"),
            floor=_i("BACKLOG_SPRINT_FLOOR", 200),
            max_loops=_i("BACKLOG_SPRINT_MAX_LOOPS", 50),
            batch_event=_i("BACKLOG_SPRINT_BATCH_EVENT", 500),
            batch_entity_per_domain=_i("BACKLOG_SPRINT_BATCH_ENTITY_PER_DOMAIN", 500),
            batch_claim=_i("BACKLOG_SPRINT_BATCH_CLAIM", 5000),
            batch_story_enrich=_i("BACKLOG_SPRINT_BATCH_STORY_ENRICH", 500),
            batch_story_build=_i("BACKLOG_SPRINT_BATCH_STORY_BUILD", 200),
            batch_profile=_i("BACKLOG_SPRINT_BATCH_PROFILE", 200),
            batch_dossier=_i("BACKLOG_SPRINT_BATCH_DOSSIER", 200),
            batch_embed=_i("BACKLOG_SPRINT_BATCH_EMBED", 500),
            batch_context_sync=_i("BACKLOG_SPRINT_BATCH_CONTEXT_SYNC", 500),
            batch_metadata=_i("BACKLOG_SPRINT_BATCH_METADATA", 80),
            batch_content=_i("BACKLOG_SPRINT_BATCH_CONTENT", 120),
            ollama_timeout=_i("BACKLOG_SPRINT_OLLAMA_TIMEOUT", 900),
        )


def sprint_active() -> bool:
    return env_str(SPRINT_ACTIVE_ENV, "").lower() in ("1", "true", "yes")


def sprint_gpu_only() -> bool:
    return env_str(SPRINT_GPU_ONLY_ENV, "").lower() in ("1", "true", "yes")


def unload_ollama_model(gpu_host: str, model: str, *, blocking: bool = False) -> bool:
    """Evict a model from PopOS VRAM (Ollama keep_alive=0). Best-effort; non-blocking by default."""
    name = (model or "").strip()
    host = (gpu_host or "").rstrip("/")
    if not name or not host:
        return False

    def _unload() -> bool:
        payload = json.dumps({"model": name, "keep_alive": 0}).encode()
        try:
            req = urllib.request.Request(
                f"{host}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp.read()
            logger.info("ollama unload ok: model=%s host=%s", name, host)
            return True
        except Exception as e:
            logger.warning("ollama unload failed model=%s host=%s: %s", name, host, e)
            return False

    if blocking:
        return _unload()
    threading.Thread(target=_unload, daemon=True, name=f"ollama-unload-{name}").start()
    return True


def _reset_llm_clients() -> None:
    try:
        from shared.services.llm_service import reset_llm_service
        from shared.services.ollama_model_caller import reset_ollama_model_caller

        reset_llm_service()
        reset_ollama_model_caller()
    except Exception as e:
        logger.debug("LLM client reset: %s", e)


def _set_sprint_env_flags(profile: BacklogRunProfile) -> None:
    env_set(SPRINT_ACTIVE_ENV, "1")
    if not profile.dual_lane:
        env_set(SPRINT_GPU_ONLY_ENV, "1")
    env_set("BULK_CATCHUP_ACTIVE", "1")
    env_set("OLLAMA_POP_OS_HOST", profile.gpu_host)
    env_set("BACKLOG_SPRINT_GPU_HOST", profile.gpu_host)
    env_set("BACKLOG_SPRINT_GPU_MODEL_FAST", profile.gpu_model_fast)
    env_set("BULK_USE_POPOS_GPU", "1")
    env_set("MAJOR_CATCHUP_USE_POPOS_GPU", "1")
    env_set("MAJOR_CATCHUP_FLOOR", str(profile.floor))
    env_set("MAJOR_CATCHUP_LOOPS", str(profile.max_loops))
    env_set("BULK_STEADY_STATE_FLOOR", str(profile.floor))
    env_set("MAJOR_CATCHUP_STORY_FACTS_ONLY", "true")
    env_set("MAJOR_CATCHUP_BATCH_INITIAL", str(profile.batch_event))
    env_set("MAJOR_CATCHUP_BUILD_BATCH_INITIAL", str(profile.batch_story_build))


def _apply_extraction_model(profile: BacklogRunProfile, model: str, *, parallel: int) -> None:
    """Point STRUCTURED_EXTRACTION at ``model`` on PopOS with given concurrency."""
    name = model.strip()
    parallel = max(1, parallel)
    env_set("BULK_EXTRACTION_MODEL", name)
    env_set("OLLAMA_MODEL_EXTRACTION", name)
    env_set(
        "OLLAMA_USE_QWEN_FOR_EXTRACTION",
        "true" if "qwen" in name.lower() else "false",
    )
    configure_catchup_extraction_routing(
        use_popos_gpu=True,
        dual_lane=profile.dual_lane,
        gpu_parallel=parallel,
        cpu_parallel=0 if not profile.dual_lane else 2,
        ollama_timeout=max(120, profile.ollama_timeout),
    )
    env_set("OLLAMA_GPU_CONCURRENCY", str(parallel))
    env_set("BULK_GPU_PARALLEL", str(parallel))
    env_set("EVENT_EXTRACTION_PARALLEL", str(parallel))
    env_set("MAJOR_CATCHUP_GPU_PARALLEL", str(parallel))
    _reset_llm_clients()
    logger.info(
        "sprint extraction model=%s parallel=%s host=%s",
        name,
        parallel,
        profile.gpu_host,
    )


def apply_sprint_base(profile: BacklogRunProfile) -> None:
    """Sprint routing bootstrap — fast model only (do not preload 32B)."""
    _set_sprint_env_flags(profile)
    _apply_extraction_model(
        profile,
        profile.gpu_model_fast,
        parallel=profile.gpu_parallel_fast,
    )


def apply_run_profile(profile: BacklogRunProfile, *, extraction_model: str | None = None) -> None:
    """
    Apply sprint routing (legacy entry). Defaults to **fast** model unless overridden.
    """
    model = extraction_model or profile.gpu_model_fast
    _set_sprint_env_flags(profile)
    parallel = (
        profile.gpu_parallel_heavy
        if "32b" in model.lower()
        else profile.gpu_parallel_fast
    )
    _apply_extraction_model(profile, model, parallel=parallel)
    logger.info(
        "backlog sprint profile: gpu=%s model=%s fast=%s parallel_heavy=%s parallel_fast=%s "
        "dual_lane=%s floor=%s",
        profile.gpu_host,
        model,
        profile.gpu_model_fast,
        profile.gpu_parallel_heavy,
        profile.gpu_parallel_fast,
        profile.dual_lane,
        profile.floor,
    )


def apply_fast_extraction_model(profile: BacklogRunProfile) -> None:
    """Switch PopOS to fast tier (entity/claim) — unload heavy model first."""
    heavy = profile.gpu_model_extraction.strip()
    if heavy:
        unload_ollama_model(profile.gpu_host, heavy)
    _apply_extraction_model(
        profile,
        profile.gpu_model_fast,
        parallel=profile.gpu_parallel_fast,
    )


def apply_heavy_extraction_model(profile: BacklogRunProfile) -> None:
    """Switch PopOS to heavy tier (event extraction) — unload fast model first."""
    fast = profile.gpu_model_fast.strip()
    if fast:
        unload_ollama_model(profile.gpu_host, fast)
    _apply_extraction_model(
        profile,
        profile.gpu_model_extraction,
        parallel=profile.gpu_parallel_heavy,
    )


def prepare_model_for_phase(profile: BacklogRunProfile, phase: str) -> str:
    """Phase-aware model selection + VRAM hygiene. Returns active model name."""
    if phase == "event_extraction":
        apply_heavy_extraction_model(profile)
        return profile.gpu_model_extraction
    if phase in ("entity_extraction", "claim_extraction"):
        apply_fast_extraction_model(profile)
        return profile.gpu_model_fast
    # Non-structured phases: keep fast loaded, ensure heavy is not resident
    heavy = profile.gpu_model_extraction.strip()
    if heavy:
        unload_ollama_model(profile.gpu_host, heavy)
    active = profile.gpu_model_fast.strip() or profile.gpu_model_extraction
    logger.info("sprint phase=%s active_llm_model=%s (no tier switch)", phase, active)
    return active


def gpu_lane_semaphore(parallel: int) -> asyncio.Semaphore:
    return asyncio.Semaphore(max(1, parallel))


async def run_with_gpu_lane(
    sem: asyncio.Semaphore,
    coro_factory: Callable[[], Awaitable[T]],
) -> T:
    """Run one LLM-bound unit of work on the PopOS GPU lane."""
    from shared.services.llm_service import pop_llm_execution_lane, push_llm_execution_lane

    async with sem:
        token = push_llm_execution_lane("gpu")
        try:
            return await coro_factory()
        finally:
            pop_llm_execution_lane(token)


async def run_with_gpu_lane_pool(
    items: list[Any],
    parallel: int,
    worker: Callable[[int, Any], Awaitable[T]],
) -> list[T | BaseException]:
    """Process items with fixed GPU-lane concurrency."""
    sem = gpu_lane_semaphore(parallel)

    async def _one(i: int, item: Any) -> T:
        return await run_with_gpu_lane(sem, lambda: worker(i, item))

    return await asyncio.gather(
        *[_one(i, item) for i, item in enumerate(items)],
        return_exceptions=True,
    )


# Unified full-pipeline phase order (dependency-aware).
SPRINT_PHASE_ORDER: tuple[str, ...] = (
    "context_sync",
    "entity_extraction",
    "claim_extraction",
    "content_enrichment",
    "metadata_enrichment",
    "event_extraction",
    "story_enhancement",
    "entity_profile_build",
    "entity_dossier_compile",
    "embeddings_worker",
    "event_tracking",
    "storyline_discovery",
)
