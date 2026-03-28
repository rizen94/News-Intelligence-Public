import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "api"))

from shared.services.llm_service import LLMService, pop_llm_execution_lane, push_llm_execution_lane


def test_llm_dual_host_routes_by_lane(monkeypatch):
    monkeypatch.setenv("OLLAMA_DUAL_HOST_ROUTING_ENABLED", "true")
    monkeypatch.setenv("OLLAMA_CPU_HOST", "http://cpu-host:11434")
    monkeypatch.setenv("OLLAMA_GPU_HOST", "http://gpu-host:11434")

    svc = LLMService()
    base_url, _, cb_key = svc._resolve_execution_target("cpu")
    assert base_url == "http://cpu-host:11434"
    assert cb_key == "ollama_cpu"

    base_url, _, cb_key = svc._resolve_execution_target("gpu")
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


def test_llm_single_host_compat(monkeypatch):
    monkeypatch.setenv("OLLAMA_DUAL_HOST_ROUTING_ENABLED", "false")
    monkeypatch.setenv("OLLAMA_HOST", "http://single-host:11434")
    monkeypatch.delenv("OLLAMA_CPU_HOST", raising=False)
    monkeypatch.delenv("OLLAMA_GPU_HOST", raising=False)

    svc = LLMService(ollama_base_url=os.environ.get("OLLAMA_HOST"))
    base_url, _, cb_key = svc._resolve_execution_target("cpu")
    assert base_url == "http://single-host:11434"
    assert cb_key == "ollama"
