"""
Unit tests for finance api_cache (SQLite).
Uses tmp_path for isolation; patches config paths before importing.
"""

import json
import pytest
from pathlib import Path

# Patch before importing finance modules
@pytest.fixture(autouse=True)
def _finance_cache_db(monkeypatch, tmp_path):
    cache_db = tmp_path / "test_api_cache.db"
    monkeypatch.setattr("config.settings.FINANCE_CACHE_DB", cache_db)
    monkeypatch.setattr("domains.finance.data.api_cache.FINANCE_CACHE_DB", cache_db)


def test_cache_miss():
    from domains.finance.data import api_cache

    result = api_cache.get("fred", {"series_id": "IQ12260"})
    assert result is None


def test_cache_set_and_get():
    from domains.finance.data import api_cache

    params = {"service": "fred", "series_id": "IQ12260"}
    data = {"observations": [{"date": "2024-01-01", "value": 100}]}
    ok = api_cache.set("fred", params, data, ttl_seconds=3600)
    assert ok is True

    result = api_cache.get("fred", params)
    assert result is not None
    assert result.get("observations")[0]["value"] == 100


def test_cache_same_params_same_key():
    from domains.finance.data import api_cache

    params = {"series_id": "IQ12260", "a": 1, "b": 2}
    api_cache.set("fred", params, {"v": 1})

    # Same params, different order
    params2 = {"b": 2, "a": 1, "series_id": "IQ12260"}
    result = api_cache.get("fred", params2)
    assert result is not None
    assert result.get("v") == 1


def test_cache_different_params_different_key():
    from domains.finance.data import api_cache

    api_cache.set("fred", {"series_id": "IQ12260"}, {"v": 1})
    result = api_cache.get("fred", {"series_id": "DCOILWTICO"})
    assert result is None


def test_cache_prune_expired():
    from domains.finance.data import api_cache

    api_cache.set("fred", {"id": "A"}, {"v": 1}, ttl_seconds=-10)  # already expired
    api_cache.set("fred", {"id": "B"}, {"v": 2}, ttl_seconds=3600)
    n = api_cache.prune_expired()
    assert n >= 1
    assert api_cache.get("fred", {"id": "A"}) is None
    assert api_cache.get("fred", {"id": "B"}) is not None
