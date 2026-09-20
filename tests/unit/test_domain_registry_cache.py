"""Unit tests for the domain registry cache and lazy back-compat snapshots."""

from __future__ import annotations

import pytest

from shared import domain_registry as dr

_ROWS = [
    {
        "domain_key": "politics",
        "schema_name": "politics",
        "display_name": "Politics",
        "display_order": 1,
        "is_active": True,
    },
    {
        "domain_key": "artificial-intelligence",
        "schema_name": "artificial_intelligence",
        "display_name": "AI",
        "display_order": 2,
        "is_active": True,
    },
]


@pytest.fixture(autouse=True)
def _clear_cache():
    dr.invalidate_domain_registry_cache()
    yield
    dr.invalidate_domain_registry_cache()


@pytest.fixture
def db_calls(monkeypatch):
    calls = {"n": 0}

    def _fake_load():
        calls["n"] += 1
        return [dict(r) for r in _ROWS]

    monkeypatch.setattr(dr, "_load_domain_entries_from_db", _fake_load)
    return calls


def test_repeated_lookups_hit_the_db_once(monkeypatch, db_calls):
    monkeypatch.setenv("DOMAIN_REGISTRY_CACHE_TTL_SECONDS", "60")

    for _ in range(25):
        assert (
            dr.resolve_domain_schema("artificial-intelligence")
            == "artificial_intelligence"
        )
        assert dr.get_pipeline_active_domain_keys()
        assert dr.is_valid_domain_key("politics")

    assert db_calls["n"] == 1


def test_invalidate_forces_a_reload(monkeypatch, db_calls):
    monkeypatch.setenv("DOMAIN_REGISTRY_CACHE_TTL_SECONDS", "60")

    dr.get_active_domain_keys()
    assert db_calls["n"] == 1

    dr.invalidate_domain_registry_cache()
    dr.get_active_domain_keys()
    assert db_calls["n"] == 2


def test_zero_ttl_disables_the_cache(monkeypatch, db_calls):
    monkeypatch.setenv("DOMAIN_REGISTRY_CACHE_TTL_SECONDS", "0")

    dr.get_active_domain_keys()
    dr.get_active_domain_keys()
    assert db_calls["n"] == 2


def test_yaml_bootstrap_uses_the_short_ttl(monkeypatch):
    calls = {"n": 0}

    def _unavailable():
        calls["n"] += 1
        return None

    monkeypatch.setattr(dr, "_load_domain_entries_from_db", _unavailable)
    monkeypatch.setenv("DOMAIN_REGISTRY_CACHE_TTL_SECONDS", "3600")
    monkeypatch.setenv("DOMAIN_REGISTRY_BOOTSTRAP_CACHE_TTL_SECONDS", "0")

    dr.get_active_domain_keys()
    dr.get_active_domain_keys()

    # A process that started before Postgres was ready must keep retrying, not cache YAML-only
    # for the full DB TTL.
    assert calls["n"] == 2


def test_db_connect_failure_falls_back_instead_of_raising(monkeypatch):
    def _boom(*_a, **_kw):
        raise RuntimeError("no password supplied")

    monkeypatch.setattr("shared.database.connection.get_ui_db_connection", _boom)

    # YAML-only bootstrap: importing or touching the registry without DB credentials must not
    # explode inside an unrelated caller.
    assert isinstance(dr.get_domain_entries(), list)


def test_lazy_back_compat_snapshots(db_calls):
    assert dr.ACTIVE_DOMAIN_KEYS == ("politics", "artificial-intelligence")
    assert dr.ACTIVE_DOMAIN_KEYS_SET == frozenset(
        {"politics", "artificial-intelligence"}
    )

    with pytest.raises(AttributeError):
        dr.NOT_A_REAL_ATTRIBUTE
