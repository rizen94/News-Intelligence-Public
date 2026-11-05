"""OLLAMA_EMBEDDINGS_HOST routes embeds off the primary generate host."""

from __future__ import annotations

import os

import pytest


@pytest.fixture
def clear_embeddings_host(monkeypatch):
    monkeypatch.delenv("OLLAMA_EMBEDDINGS_HOST", raising=False)
    yield


def test_embedding_target_uses_dedicated_host(monkeypatch, clear_embeddings_host):
    monkeypatch.setenv("OLLAMA_EMBEDDINGS_HOST", "http://192.168.93.95:11434")
    monkeypatch.setenv("OLLAMA_HOST", "http://192.168.93.99:11434")
    monkeypatch.setenv("OLLAMA_DUAL_HOST_ROUTING_ENABLED", "false")
    # Fresh instance picks up env
    from shared.services import llm_service as ls_mod

    svc = ls_mod.LLMService(ollama_base_url="http://192.168.93.99:11434")
    base, cb = svc._embedding_target("cpu")
    assert base == "http://192.168.93.95:11434"
    assert cb == "ollama_embeddings"


def test_embedding_target_falls_back_without_dedicated_host(monkeypatch, clear_embeddings_host):
    monkeypatch.setenv("OLLAMA_HOST", "http://192.168.93.99:11434")
    monkeypatch.setenv("OLLAMA_DUAL_HOST_ROUTING_ENABLED", "false")
    from shared.services import llm_service as ls_mod

    svc = ls_mod.LLMService(ollama_base_url="http://192.168.93.99:11434")
    assert not svc.ollama_embeddings_host
    base, cb = svc._embedding_target("cpu")
    assert base == "http://192.168.93.99:11434"
    assert cb == "ollama"
