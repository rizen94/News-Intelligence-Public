"""Deduplication routes: mounted under /api, destructive verbs opt-in only."""

from __future__ import annotations

import importlib
import sys

import pytest


def _dedup_module():
    """Import with a real config.runtime (see tests/unit/conftest.py for why)."""
    for name in ("config.runtime", "config"):
        mod = sys.modules.get(name)
        if mod is not None and not getattr(mod, "__file__", None):
            sys.modules.pop(name, None)
    return importlib.import_module("domains.content_analysis.routes.deduplication")


READ_ONLY_PATHS = {
    "/api/deduplication/feeds/detect",
    "/api/deduplication/feeds/exact",
    "/api/deduplication/feeds/similar",
    "/api/deduplication/feeds/stats",
    "/api/deduplication/articles/detect",
    "/api/deduplication/articles/url",
    "/api/deduplication/articles/content",
    "/api/deduplication/articles/similar",
}

DESTRUCTIVE_PATHS = {
    "/api/deduplication/feeds/merge",
    "/api/deduplication/feeds/auto_merge",
    "/api/deduplication/feeds/prevent",
    "/api/deduplication/articles/merge",
    "/api/deduplication/articles/auto_merge",
}


def _mounted_paths() -> set[str]:
    mod = _dedup_module()
    return {r.path for r in mod.main_router.routes}


def test_every_route_is_mounted_under_api():
    paths = _mounted_paths()
    # The router sat at a bare /deduplication prefix, which no nginx config proxies, so the whole
    # surface was unreachable in production.
    assert paths, "deduplication router exposes no routes"
    assert all(p.startswith("/api/deduplication/") for p in paths), sorted(paths)


def test_expected_paths_exist():
    paths = _mounted_paths()
    assert READ_ONLY_PATHS <= paths, sorted(READ_ONLY_PATHS - paths)
    assert DESTRUCTIVE_PATHS <= paths, sorted(DESTRUCTIVE_PATHS - paths)


def test_articles_has_no_stats_or_prevent_route():
    # The SPA used to call both; there is no such route, so those calls were dropped rather than
    # inventing endpoints.
    paths = _mounted_paths()
    assert "/api/deduplication/articles/stats" not in paths
    assert "/api/deduplication/articles/prevent" not in paths


def test_destructive_ops_are_disabled_by_default(monkeypatch):
    mod = _dedup_module()
    monkeypatch.delenv(mod.DESTRUCTIVE_OPS_ENV, raising=False)

    assert mod.destructive_ops_enabled() is False
    with pytest.raises(Exception) as excinfo:
        mod.require_destructive_ops_enabled()
    assert getattr(excinfo.value, "status_code", None) == 403


@pytest.mark.parametrize("value", ["true", "1", "yes", "TRUE"])
def test_destructive_ops_can_be_opted_in(monkeypatch, value):
    mod = _dedup_module()
    monkeypatch.setenv(mod.DESTRUCTIVE_OPS_ENV, value)

    assert mod.destructive_ops_enabled() is True
    mod.require_destructive_ops_enabled()  # must not raise


@pytest.mark.parametrize("value", ["false", "0", "no", ""])
def test_explicit_falsey_values_stay_gated(monkeypatch, value):
    mod = _dedup_module()
    monkeypatch.setenv(mod.DESTRUCTIVE_OPS_ENV, value)

    assert mod.destructive_ops_enabled() is False


def test_every_destructive_handler_calls_the_gate():
    import inspect

    mod = _dedup_module()
    src = inspect.getsource(mod)
    # One definition plus one call per destructive endpoint.
    assert src.count("require_destructive_ops_enabled()") == 1 + len(DESTRUCTIVE_PATHS)


@pytest.mark.parametrize(
    "handler,kwargs",
    [
        ("auto_merge_all_duplicates", {"dry_run": False}),
        ("auto_merge_url_duplicates", {"dry_run": False}),
        ("add_duplicate_prevention", {}),
    ],
)
def test_destructive_handlers_refuse_before_touching_the_db(monkeypatch, handler, kwargs):
    """The gate has to fire ahead of any connection, not inside the try/except that returns 500."""
    import asyncio

    from fastapi import HTTPException

    mod = _dedup_module()
    monkeypatch.delenv(mod.DESTRUCTIVE_OPS_ENV, raising=False)

    def _no_db(*_a, **_kw):
        raise AssertionError("handler reached the database despite the gate")

    monkeypatch.setattr("shared.database.connection.get_db_connection", _no_db)

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(getattr(mod, handler)(**kwargs))
    assert excinfo.value.status_code == 403
