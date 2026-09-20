import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "api"))

from shared.services.llm_service import LLMService, pop_llm_execution_lane, push_llm_execution_lane


def test_default_gpu_batch_ollama_url_uses_gpu_when_dual(monkeypatch):
    monkeypatch.setenv("OLLAMA_DUAL_HOST_ROUTING_ENABLED", "true")
    monkeypatch.setenv("OLLAMA_CPU_HOST", "http://cpu-topic:11434")
    monkeypatch.setenv("OLLAMA_GPU_HOST", "http://gpu-topic:11434")
    monkeypatch.setenv("OLLAMA_HOST", "http://fallback:11434")

    from domains.content_analysis.services.topic_clustering_service import (
        default_gpu_batch_ollama_url,
    )

    assert default_gpu_batch_ollama_url() == "http://gpu-topic:11434"


def test_default_batch_ollama_url_uses_cpu_when_dual(monkeypatch):
    monkeypatch.setenv("OLLAMA_DUAL_HOST_ROUTING_ENABLED", "true")
    monkeypatch.setenv("OLLAMA_CPU_HOST", "http://cpu-topic:11434")
    monkeypatch.setenv("OLLAMA_HOST", "http://fallback:11434")

    from domains.content_analysis.services.topic_clustering_service import default_batch_ollama_url

    assert default_batch_ollama_url() == "http://cpu-topic:11434"


def test_llm_dual_host_routes_by_lane(monkeypatch):
    monkeypatch.setenv("OLLAMA_DUAL_HOST_ROUTING_ENABLED", "true")
    monkeypatch.setenv("OLLAMA_CPU_HOST", "http://cpu-host:11434")
    monkeypatch.setenv("OLLAMA_GPU_HOST", "http://gpu-host:11434")

    svc = LLMService()
    base_url, _, cb_key = svc._resolve_execution_target(execution_lane="cpu")
    assert base_url == "http://cpu-host:11434"
    assert cb_key == "ollama_cpu"

    base_url, _, cb_key = svc._resolve_execution_target(execution_lane="gpu")
    assert base_url == "http://gpu-host:11434"
    assert cb_key == "ollama_gpu"


def test_llm_context_lane_defaults_when_omitted(monkeypatch):
    monkeypatch.setenv("OLLAMA_DUAL_HOST_ROUTING_ENABLED", "true")
    monkeypatch.setenv("OLLAMA_CPU_HOST", "http://cpu-host:11434")
    monkeypatch.setenv("OLLAMA_GPU_HOST", "http://gpu-host:11434")

    svc = LLMService()
    token = push_llm_execution_lane("cpu")
    try:
        base_url, _, cb_key = svc._resolve_execution_target(None)
        assert base_url == "http://cpu-host:11434"
        assert cb_key == "ollama_cpu"
    finally:
        pop_llm_execution_lane(token)


def test_ollama_caller_embedding_uses_cpu_host_when_dual(monkeypatch):
    monkeypatch.setenv("OLLAMA_DUAL_HOST_ROUTING_ENABLED", "true")
    monkeypatch.setenv("OLLAMA_CPU_HOST", "http://cpu-embed:11434")
    monkeypatch.setenv("OLLAMA_GPU_HOST", "http://gpu-narrative:11434")
    monkeypatch.setenv("OLLAMA_HOST", "http://legacy:11434")

    from shared.services.llm_service import LLMService
    from shared.services.ollama_model_caller import OllamaModelCaller

    c = OllamaModelCaller(LLMService())
    assert c._embedding_base_url() == "http://cpu-embed:11434"


def test_structured_extraction_respects_context_lane_during_bulk(monkeypatch):
    monkeypatch.setenv("BULK_USE_POPOS_EXTRACTION", "1")
    monkeypatch.setenv("BULK_DUAL_LANE_CATCHUP", "1")

    from shared.services.ollama_model_caller import OllamaModelCaller
    from shared.services.ollama_model_policy import InvocationKind
    from shared.services.llm_service import pop_llm_execution_lane, push_llm_execution_lane

    token = push_llm_execution_lane("cpu")
    try:
        assert OllamaModelCaller._execution_lane_for_kind(InvocationKind.STRUCTURED_EXTRACTION) == "cpu"
    finally:
        pop_llm_execution_lane(token)

    assert OllamaModelCaller._execution_lane_for_kind(InvocationKind.STRUCTURED_EXTRACTION) == "gpu"


def test_retryable_bulk_llm_error_includes_gpu_timeout():
    from shared.bulk_catchup_llm_routing import is_retryable_bulk_llm_error

    assert is_retryable_bulk_llm_error("ollama_gpu request timed out")
    assert is_retryable_bulk_llm_error("HTTPConnectionPool: Read timed out")
    assert not is_retryable_bulk_llm_error("json parse failed")


def test_assign_extraction_lane_weighted_round_robin():
    from shared.bulk_catchup_llm_routing import assign_extraction_lane

    lanes = [assign_extraction_lane(i, gpu_parallel=4, cpu_parallel=2) for i in range(12)]
    assert lanes.count("gpu") == 8
    assert lanes.count("cpu") == 4


def test_llm_single_host_compat(monkeypatch):
    monkeypatch.setenv("OLLAMA_DUAL_HOST_ROUTING_ENABLED", "false")
    monkeypatch.setenv("OLLAMA_HOST", "http://single-host:11434")
    monkeypatch.delenv("OLLAMA_CPU_HOST", raising=False)
    monkeypatch.delenv("OLLAMA_GPU_HOST", raising=False)

    svc = LLMService(ollama_base_url=os.environ.get("OLLAMA_HOST"))
    base_url, _, cb_key = svc._resolve_execution_target(execution_lane="cpu")
    assert base_url == "http://single-host:11434"
    assert cb_key == "ollama"
