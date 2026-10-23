"""Probe Ollama tag lists and remap missing role models to installed images."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from config.runtime import env_set, env_str

logger = logging.getLogger(__name__)

# Prefer currently installed mid-size models; avoid jumping straight to absent 32b/70b.
_PREFERRED_FALLBACKS: tuple[str, ...] = (
    "qwen3.6:latest",
    "qwen3.6",
    "mistral-nemo:12b",
    "mistral-nemo:latest",
    "mistral-nemo",
    "llama3.1:8b",
    "llama3.1:latest",
    "llama3.1",
    "phi3.5:latest",
    "phi3.5",
    "nomic-embed-text:latest",
    "nomic-embed-text",
)

# Roles that prefer a qwen-family tag when remapping.
_EXTRACTION_ISH_KEYS = frozenset(
    {
        "OLLAMA_MODEL_EXTRACTION",
        "BULK_EXTRACTION_MODEL",
        "BULK_CPU_EXTRACTION_MODEL",
        "DOSSIER_NARRATIVE_MODEL",
        "OLLAMA_NARRATIVE_FINISHER_MODEL",
        "OLLAMA_OPTIONAL_QUALITY_MODEL",
    }
)

_ROLE_ENV_DEFAULTS: tuple[tuple[str, str], ...] = (
    ("OLLAMA_MODEL_PRIMARY", "llama3.1:8b"),  # default tier
    ("OLLAMA_MODEL_SECONDARY", "mistral-nemo:12b"),  # high tier
    ("OLLAMA_MODEL_PHI", "phi3.5:latest"),  # low tier
    ("OLLAMA_MODEL_EXTRACTION", "qwen3.6:latest"),  # extract tier
    ("OLLAMA_MODEL_EMBEDDING", "nomic-embed-text"),
    ("BULK_EXTRACTION_MODEL", "qwen3.6:latest"),
    ("OLLAMA_NARRATIVE_FINISHER_MODEL", "qwen3.6:latest"),  # finish tier
    ("OLLAMA_OPTIONAL_QUALITY_MODEL", "qwen3.6:latest"),
    ("DOSSIER_NARRATIVE_MODEL", "qwen3.6:latest"),
)


def _normalize_tag_name(name: str) -> str:
    return (name or "").strip()


def _model_available(names: set[str], model: str) -> bool:
    model = _normalize_tag_name(model)
    if not model:
        return False
    if model in names:
        return True
    base, _, tag = model.partition(":")
    if tag and f"{base}:latest" in names:
        return True
    if f"{model}:latest" in names:
        return True
    # installed "foo:latest" satisfies configured "foo"
    if ":" not in model and f"{model}:latest" in names:
        return True
    return False


def _fetch_tag_names(host: str, *, timeout: float = 5.0) -> set[str]:
    base = (host or "").strip().rstrip("/")
    if not base:
        return set()
    with urllib.request.urlopen(f"{base}/api/tags", timeout=timeout) as resp:
        payload = json.loads(resp.read().decode())
    names: set[str] = set()
    for item in payload.get("models") or []:
        if isinstance(item, dict):
            name = _normalize_tag_name(str(item.get("name") or ""))
            if name:
                names.add(name)
    return names


def _pick_fallback(names: set[str], configured: str, *, prefer_qwen: bool = False) -> str | None:
    if _model_available(names, configured):
        return configured
    preferred = _PREFERRED_FALLBACKS
    if prefer_qwen:
        preferred = tuple(t for t in preferred if "qwen" in t.lower()) + preferred
    for candidate in preferred:
        if _model_available(names, candidate):
            return candidate
    for pattern in ("qwen", "llama", "nomic"):
        for name in sorted(names):
            if pattern in name.lower():
                return name
    return next(iter(sorted(names)), None)


def _remap_env_key(key: str, names: set[str], *, host: str) -> str | None:
    default = next((d for k, d in _ROLE_ENV_DEFAULTS if k == key), "llama3.1:8b")
    configured = env_str(key, "").strip() or default
    prefer_qwen = key in _EXTRACTION_ISH_KEYS
    resolved = _pick_fallback(names, configured, prefer_qwen=prefer_qwen)
    if not resolved:
        return None
    if resolved != configured:
        logger.warning(
            "%s %s not on host %s; remapped to %s",
            key,
            configured,
            host,
            resolved,
        )
        env_set(key, resolved)
    else:
        env_set(key, resolved)
    return resolved


def resolve_extraction_models_for_hosts(
    *,
    gpu_host: str | None = None,
    cpu_host: str | None = None,
    run_id: str = "startup",
) -> dict[str, str | None]:
    """Remap OLLAMA_MODEL_* (and related) when absent on GPU/CPU hosts."""
    del run_id  # reserved for callers / logging context
    gpu = (
        gpu_host
        or env_str("OLLAMA_GPU_HOST", "").strip()
        or env_str("OLLAMA_POP_OS_HOST", "")
        or env_str("OLLAMA_HOST", "http://127.0.0.1:11434")
    ).rstrip("/")
    cpu = (
        cpu_host
        or env_str("OLLAMA_CPU_HOST", "").strip()
        or env_str("OLLAMA_HOST", "http://localhost:11434")
    ).rstrip("/")

    gpu_names: set[str] = set()
    cpu_names: set[str] = set()
    gpu_error: str | None = None
    cpu_error: str | None = None

    try:
        gpu_names = _fetch_tag_names(gpu)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        gpu_error = str(exc)[:200]

    resolved_gpu: str | None = None
    if gpu_names:
        remapped: dict[str, str | None] = {}
        for key, _default in _ROLE_ENV_DEFAULTS:
            remapped[key] = _remap_env_key(key, gpu_names, host=gpu)
        # Keep BULK_EXTRACTION in sync with extraction when unset historically.
        if not env_str("BULK_EXTRACTION_MODEL", "").strip():
            ext = remapped.get("OLLAMA_MODEL_EXTRACTION")
            if ext:
                env_set("BULK_EXTRACTION_MODEL", ext)
        resolved_gpu = remapped.get("OLLAMA_MODEL_EXTRACTION")
        env_set(
            "OLLAMA_USE_QWEN_FOR_EXTRACTION",
            "true" if resolved_gpu and "qwen" in resolved_gpu.lower() else "false",
        )

    if cpu and cpu != gpu:
        try:
            cpu_names = _fetch_tag_names(cpu)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            cpu_error = str(exc)[:200]
        if cpu_names:
            cpu_model = env_str("BULK_CPU_EXTRACTION_MODEL", "").strip() or env_str(
                "OLLAMA_MODEL_EXTRACTION", "qwen3.6:latest"
            )
            if not _model_available(cpu_names, cpu_model):
                cpu_fallback = _pick_fallback(cpu_names, cpu_model, prefer_qwen=True)
                if cpu_fallback and cpu_fallback != cpu_model:
                    logger.warning(
                        "BULK_CPU_EXTRACTION_MODEL %s not on CPU host %s; remapped to %s",
                        cpu_model,
                        cpu,
                        cpu_fallback,
                    )
                    env_set("BULK_CPU_EXTRACTION_MODEL", cpu_fallback)

    try:
        from shared.services.llm_service import reset_llm_service
        from shared.services.ollama_model_caller import reset_ollama_model_caller

        reset_llm_service()
        reset_ollama_model_caller()
    except Exception as exc:
        logger.debug("LLM service reset after model resolve: %s", exc)

    return {
        "gpu_host": gpu or None,
        "resolved_model": resolved_gpu,
        "gpu_error": gpu_error,
        "cpu_error": cpu_error,
    }


def resolve_extraction_models_at_startup() -> dict[str, str | None]:
    return resolve_extraction_models_for_hosts(run_id="startup")
