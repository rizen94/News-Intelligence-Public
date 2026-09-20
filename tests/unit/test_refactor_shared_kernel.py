"""Tests for refactoring shared utilities (Phases 3–5)."""

import json

from shared.api_deprecation import deprecated_gone_response
from shared.services.service_result import service_err, service_ok
from shared.text_similarity import sequence_similarity


def test_deprecated_gone_response_status_and_headers():
    resp = deprecated_gone_response("use /api/politics/articles")
    assert resp.status_code == 410
    assert resp.headers.get("Deprecation") == "true"
    body = json.loads(resp.body)
    assert body["success"] is False
    assert "politics" in body["message"]


def test_service_result_helpers():
    ok = service_ok(updated=3)
    assert ok["success"] is True
    assert ok["updated"] == 3
    err = service_err("boom", recoverable=False)
    assert err["success"] is False
    assert err["recoverable"] is False


def test_sequence_similarity():
    assert sequence_similarity("Donald Trump", "donald trump") == 1.0
    assert sequence_similarity("", "x") == 0.0
    assert 0.0 < sequence_similarity("Biden", "Joe Biden") < 1.0


def _load_api_module(module_name: str, filename: str):
    """Import an api module without executing services/__init__.py (avoids DB at import)."""
    import importlib.util
    import os

    api_root = os.path.join(os.path.dirname(__file__), "..", "..", "api")
    path = os.path.join(api_root, filename)
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_entity_service_facade_imports():
    facade = _load_api_module("entity_service_facade", "services/entity_service_facade.py")

    assert callable(facade.resolve_with_candidates)
    assert callable(facade.run_resolution_batch)


def test_consolidation_scheduler_reads_yaml():
    sched = _load_api_module("consolidation_scheduler", "services/consolidation_scheduler.py")

    assert sched.CONSOLIDATION_INTERVAL_SECONDS >= 60
    assert "storylines" in sched.CONSOLIDATION_TYPES
