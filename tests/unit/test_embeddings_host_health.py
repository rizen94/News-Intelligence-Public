"""Dockside embeddings host pause gate + prometheus samples."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_PATH = _ROOT / "api" / "services" / "embeddings_host_health_service.py"


def _load_module():
    # Avoid api/services/__init__.py (pulls AutomationManager / DB).
    runtime = types.ModuleType("config.runtime")

    def env_str(key, default=""):
        import os

        return os.environ.get(key, default)

    def env_int(key, default=0):
        import os

        try:
            return int(os.environ.get(key, default))
        except (TypeError, ValueError):
            return int(default)

    def env_float(key, default=0.0):
        import os

        try:
            return float(os.environ.get(key, default))
        except (TypeError, ValueError):
            return float(default)

    runtime.env_str = env_str
    runtime.env_int = env_int
    runtime.env_float = env_float
    sys.modules.setdefault("config", types.ModuleType("config"))
    sys.modules["config.runtime"] = runtime

    name = "embeddings_host_health_service_under_test"
    if name in sys.modules:
        del sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()
EmbeddingsHostHealthService = _mod.EmbeddingsHostHealthService


@pytest.fixture
def health(monkeypatch):
    monkeypatch.setenv("OLLAMA_EMBEDDINGS_HOST", "http://127.0.0.1:11435")
    monkeypatch.setenv("EMBEDDINGS_HOST_FAIL_THRESHOLD", "2")  # explicit for multi-fail tests
    monkeypatch.setenv("EMBEDDINGS_HOST_RECOVERY_SUCCESSES", "1")
    monkeypatch.setenv("EMBEDDINGS_HOST_PROBE_INTERVAL_SEC", "3600")
    return EmbeddingsHostHealthService()


def test_unconfigured_never_pauses(monkeypatch):
    monkeypatch.delenv("OLLAMA_EMBEDDINGS_HOST", raising=False)
    svc = EmbeddingsHostHealthService()
    paused, reason = svc.should_pause_embeddings()
    assert paused is False
    assert reason == ""
    samples = svc.prometheus_samples()
    assert samples["configured"] == 0.0
    assert samples["paused"] == 0.0
    # snapshot() for unconfigured reports up=True (no dedicated host to fail).
    assert samples["up"] == 1.0


def test_prometheus_samples_do_not_http_probe(health, monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("scrape path must not HTTP probe")

    monkeypatch.setattr(health, "ensure_probed", _boom)
    samples = health.prometheus_samples()
    assert samples["configured"] == 1.0
    assert samples["up"] == 0.0  # unknown until first success


def test_pause_after_consecutive_embed_failures(health):
    health.record_embed_failure("boom1")
    paused, _ = health.should_pause_embeddings()
    assert paused is False
    health.record_embed_failure("boom2")
    paused, reason = health.should_pause_embeddings()
    assert paused is True
    assert "embeddings_host_errors" in reason
    samples = health.prometheus_samples()
    assert samples["paused"] == 1.0
    assert samples["up"] == 0.0
    assert samples["consecutive_failures"] >= 2.0


def test_recover_on_embed_success(health):
    health.record_embed_failure("a")
    health.record_embed_failure("b")
    assert health.should_pause_embeddings()[0] is True
    health.record_embed_success()
    paused, reason = health.should_pause_embeddings()
    assert paused is False
    assert reason == ""
    assert health.prometheus_samples()["up"] == 1.0


def test_probe_failure_pauses(health, monkeypatch):
    class _Resp:
        status_code = 503

    class _Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url):
            return _Resp()

    monkeypatch.setattr(_mod.httpx, "Client", _Client)
    monkeypatch.setenv("EMBEDDINGS_HOST_PROBE_INTERVAL_SEC", "1")
    health._last_probe_mono = 0.0
    health.ensure_probed(force=True)
    health.ensure_probed(force=True)
    paused, reason = health.should_pause_embeddings()
    assert paused is True
    assert "unreachable" in reason


def test_worker_yield_counter(health):
    health.record_embed_failure("x")
    health.record_embed_failure("y")
    health.note_worker_yielded("embeddings_host_paused")
    assert health.prometheus_samples()["yield_total"] == 1.0
