"""Dual-lane LLM routing for bulk catch-up (PopOS GPU + Widow local Ollama/GPU)."""

from __future__ import annotations

from config.runtime import env_bool, env_float, env_int, env_pop, env_set, env_setdefault, env_str
import asyncio
import json
import logging
import os
import urllib.request

logger = logging.getLogger(__name__)


def is_retryable_bulk_llm_error(exc_or_msg: str) -> bool:
    """Transient LLM errors worth retrying during bulk catch-up."""
    err = (exc_or_msg or "").lower()
    return (
        "503" in err
        or "server busy" in err
        or "pending requests" in err
        or "timed out" in err
        or "timeout" in err
        or "circuit breaker" in err
        or "cannot connect" in err
    )


def bulk_dual_lane_catchup_active() -> bool:
    return env_str("BULK_DUAL_LANE_CATCHUP", "").lower() in ("1", "true", "yes")


def dual_lane_extraction_active() -> bool:
    """Dual PopOS GPU + Widow CPU lanes for structured extraction (catch-up or automation)."""
    if bulk_dual_lane_catchup_active():
        return True
    raw = env_str("AUTOMATION_DUAL_LANE", "").strip().lower()
    if raw in ("1", "true", "yes"):
        return True
    if raw in ("0", "false", "no"):
        return False
    try:
        from shared.automation_llm_routing import automation_use_popos_gpu

        if automation_use_popos_gpu():
            return env_str("OLLAMA_DUAL_HOST_ROUTING_ENABLED", "").lower() in ("1", "true", "yes")
    except Exception:
        pass
    return False


def parse_lane_parallel(
    *,
    parallel: int = 4,
    gpu_parallel: int | None = None,
    cpu_parallel: int | None = None,
) -> tuple[int, int, bool]:
    """
    Return (gpu_parallel, cpu_parallel, dual_lane).

    When dual lane is off, returns (0, 0, False) — caller uses ``parallel`` only.
    """
    if not dual_lane_extraction_active():
        return 0, 0, False

    gpu = gpu_parallel
    if gpu is None:
        try:
            if bulk_dual_lane_catchup_active():
                gpu = int(env_str("BULK_GPU_PARALLEL", str(parallel)))
            else:
                gpu = int(env_str("AUTOMATION_GPU_PARALLEL", env_str("EVENT_EXTRACTION_PARALLEL", str(parallel))))
        except ValueError:
            gpu = parallel
    cpu = cpu_parallel
    if cpu is None:
        try:
            if bulk_dual_lane_catchup_active():
                cpu = int(env_str("BULK_CPU_PARALLEL", "2"))
            else:
                cpu = int(env_str("AUTOMATION_CPU_PARALLEL", "2"))
        except ValueError:
            cpu = 2
    gpu = max(0, gpu)
    cpu = max(0, cpu)
    if gpu == 0 and cpu == 0:
        gpu, cpu = max(1, parallel), 2
    return gpu, cpu, True


def create_lane_semaphores(
    *,
    parallel: int = 4,
) -> tuple[asyncio.Semaphore | None, asyncio.Semaphore | None, asyncio.Semaphore | None, int, int, bool]:
    """
    Shared lane semaphores for cross-domain bulk extraction.

    Returns (gpu_sem, cpu_sem, single_sem, gpu_parallel, cpu_parallel, dual_lane).
    """
    gpu_parallel, cpu_parallel, dual_lane = parse_lane_parallel(parallel=parallel)
    if dual_lane:
        return (
            asyncio.Semaphore(max(1, gpu_parallel)),
            asyncio.Semaphore(max(1, cpu_parallel)),
            None,
            gpu_parallel,
            cpu_parallel,
            True,
        )
    return None, None, asyncio.Semaphore(max(1, parallel)), 0, 0, False


def assign_extraction_lane(index: int, *, gpu_parallel: int, cpu_parallel: int) -> str:
    """Weighted round-robin: PopOS (gpu lane) + Widow local Ollama (cpu lane)."""
    cycle = gpu_parallel + cpu_parallel
    if cycle <= 0:
        return "gpu"
    return "gpu" if (index % cycle) < gpu_parallel else "cpu"


def configure_catchup_extraction_routing(
    *,
    use_popos_gpu: bool = True,
    dual_lane: bool = True,
    gpu_parallel: int = 4,
    cpu_parallel: int = 2,
    ollama_timeout: int | None = None,
) -> None:
    """
    Catch-up extraction routing.

    - ``use_popos_gpu``: enable dual-host mode with PopOS as GPU lane.
    - ``dual_lane``: when true, STRUCTURED_EXTRACTION uses both PopOS GPU and local CPU.
      When false, all extraction LLM calls go to PopOS only (legacy bulk behaviour).
    """
    if not use_popos_gpu:
        env_pop("BULK_USE_POPOS_EXTRACTION", None)
        env_pop("BULK_DUAL_LANE_CATCHUP", None)
        return

    pop = env_str("OLLAMA_POP_OS_HOST", "http://192.168.93.99:11434").rstrip("/")
    local = env_str("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    if ollama_timeout is None:
        try:
            ollama_timeout = int(env_str("BULK_OLLAMA_TIMEOUT", "600"))
        except ValueError:
            ollama_timeout = 600
    bulk_timeout = max(120, ollama_timeout)
    env_set("OLLAMA_TIMEOUT", str(bulk_timeout))
    env_setdefault("OLLAMA_GPU_TIMEOUT", str(max(bulk_timeout, 600)))
    env_setdefault("OLLAMA_CPU_TIMEOUT", str(min(bulk_timeout, 300)))
    env_setdefault("OLLAMA_EXTRACTION_NUM_CTX", "8192")
    env_setdefault("BULK_GPU_RETRIES_BEFORE_FALLBACK", "1")
    env_set("OLLAMA_DUAL_HOST_ROUTING_ENABLED", "true")
    env_setdefault("OLLAMA_CPU_HOST", local)
    env_set("OLLAMA_GPU_HOST", pop)
    env_set("BULK_USE_POPOS_EXTRACTION", "1")
    env_set("BULK_DUAL_LANE_CATCHUP", "1" if dual_lane else "0")

    gpu_parallel = max(1, gpu_parallel)
    cpu_parallel = max(0, cpu_parallel) if dual_lane else 0
    env_set("BULK_GPU_PARALLEL", str(gpu_parallel))
    if dual_lane:
        cpu_parallel = max(1, cpu_parallel)
        env_set("BULK_CPU_PARALLEL", str(cpu_parallel))
        env_set("OLLAMA_GPU_CONCURRENCY", str(gpu_parallel))
        env_set("OLLAMA_CPU_CONCURRENCY", str(cpu_parallel))
    else:
        env_pop("BULK_CPU_PARALLEL", None)
        env_set("OLLAMA_GPU_CONCURRENCY", str(gpu_parallel))

    extraction_model = env_str("BULK_EXTRACTION_MODEL", "").strip()
    if not extraction_model:
        extraction_model = env_str("OLLAMA_MODEL_EXTRACTION", "qwen2.5:32b-instruct").strip()
        if extraction_model in ("llama3.1:8b", "qwen2.5:7b"):
            extraction_model = "qwen2.5:32b-instruct"
    if extraction_model:
        env_set("OLLAMA_MODEL_EXTRACTION", extraction_model)
        env_set(
            "OLLAMA_USE_QWEN_FOR_EXTRACTION",
            "true" if "qwen" in extraction_model.lower() else "false",
        )
    cpu_extraction_model = env_str("BULK_CPU_EXTRACTION_MODEL", "llama3.1:8b").strip()
    if cpu_extraction_model and dual_lane:
        env_set("BULK_CPU_EXTRACTION_MODEL", cpu_extraction_model)

    try:
        with urllib.request.urlopen(f"{pop}/api/tags", timeout=5) as resp:
            tags = json.loads(resp.read().decode())
        names = {m.get("name", "") for m in tags.get("models") or []}
        if extraction_model not in names and f"{extraction_model}:latest" not in names:
            logger.warning(
                "BULK_EXTRACTION_MODEL %s not on PopOS (%s). Pull it or set BULK_EXTRACTION_MODEL=llama3.1:8b",
                extraction_model,
                pop,
            )
    except Exception as e:
        logger.warning("PopOS Ollama probe failed (%s): %s", pop, e)

    if dual_lane:
        try:
            with urllib.request.urlopen(f"{local}/api/tags", timeout=5) as resp:
                tags = json.loads(resp.read().decode())
            names = {m.get("name", "") for m in tags.get("models") or []}
            if extraction_model not in names and f"{extraction_model}:latest" not in names:
                logger.warning(
                    "BULK_EXTRACTION_MODEL %s not on local CPU host (%s); CPU lane may fail",
                    extraction_model,
                    local,
                )
        except Exception as e:
            logger.warning("Local Ollama probe failed (%s): %s", local, e)

    try:
        from shared.services.llm_service import reset_llm_service
        from shared.services.ollama_model_caller import reset_ollama_model_caller

        reset_llm_service()
        reset_ollama_model_caller()
    except Exception as e:
        logger.debug("LLM service reset after catchup routing: %s", e)

    if dual_lane:
        logger.info(
            "Bulk catch-up dual-lane extraction: gpu=%s@%s cpu=%s@%s model=%s timeout=%ss",
            gpu_parallel,
            pop,
            cpu_parallel,
            local,
            env_str("OLLAMA_MODEL_EXTRACTION"),
            env_str("OLLAMA_TIMEOUT"),
        )
    else:
        logger.info(
            "Bulk extraction GPU-only: host=%s model=%s parallel=%s",
            pop,
            env_str("OLLAMA_MODEL_EXTRACTION"),
            gpu_parallel,
        )
