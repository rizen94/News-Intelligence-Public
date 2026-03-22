"""
Unit tests for FRED adapter — mocked HTTP, no real API calls.
"""

import pytest
import requests  # ensure module loaded before monkeypatch


@pytest.fixture(autouse=True)
def _fred_test_env(monkeypatch, tmp_path):
    """Use temp paths and fake API key. Patch fred module's FRED_API_KEY (imported at load)."""
    monkeypatch.setattr("config.settings.FRED_API_KEY", "test_key_12345")
    monkeypatch.setattr("domains.finance.data_sources.fred.FRED_API_KEY", "test_key_12345")
    monkeypatch.setattr("config.settings.FINANCE_CACHE_DB", tmp_path / "cache.db")
    monkeypatch.setattr("config.settings.FINANCE_MARKET_DB", tmp_path / "market.db")
    monkeypatch.setattr("domains.finance.data.api_cache.FINANCE_CACHE_DB", tmp_path / "cache.db")
    monkeypatch.setattr(
        "domains.finance.data.market_data_store.FINANCE_MARKET_DB", tmp_path / "market.db"
    )


def test_fetch_observations_mocked_http(monkeypatch):
    """FRED fetch_observations returns parsed observations when HTTP returns valid data."""
    from domains.finance.data_sources.fred import get_client

    mock_response = {
        "observations": [
            {
                "date": "2024-01-15",
                "value": "100.5",
                "realtime_start": "2024-01-01",
                "realtime_end": "2024-01-15",
            },
            {
                "date": "2024-01-16",
                "value": "101.0",
                "realtime_start": "2024-01-01",
                "realtime_end": "2024-01-16",
            },
            {"date": "2024-01-17", "value": ".", "realtime_start": "", "realtime_end": ""},  # skip
        ]
    }

    def fake_get(url, params=None, timeout=None):
        assert "api.stlouisfed.org" in url
        assert params and params.get("series_id") == "IQ12260"
        m = type("Response", (), {})()
        m.status_code = 200
        m.raise_for_status = lambda: None
        m.json = lambda: mock_response
        return m

    monkeypatch.setattr(requests, "get", fake_get)

    client = get_client({"name": "FRED Test"})
    result = client.fetch_observations("IQ12260", start="2024-01-01", end="2024-01-31", store=False)

    assert result.success
    out = result.data or []
    assert len(out) == 2
    assert out[0]["date"] == "2024-01-15"
    assert out[0]["value"] == 100.5
    assert out[1]["value"] == 101.0


def test_fetch_observations_no_api_key(monkeypatch, _fred_test_env):
    """When FRED_API_KEY is empty, fetch returns DataResult fail with auth error."""
    monkeypatch.setattr("domains.finance.data_sources.fred.FRED_API_KEY", "")

    from domains.finance.data_sources.fred import get_client

    client = get_client()
    result = client.fetch_observations("IQ12260", store=False)
    assert not result.success
    assert result.error_type == "auth"


def test_fetch_observations_http_error(monkeypatch, _fred_test_env):
    """When HTTP fails, fetch returns DataResult fail with network error."""

    def fake_get(url, params=None, timeout=None):
        raise Exception("Connection refused")

    monkeypatch.setattr(requests, "get", fake_get)

    from domains.finance.data_sources.fred import get_client

    client = get_client()
    result = client.fetch_observations("IQ12260", store=False)
    assert not result.success
    assert result.error_type == "network"


def test_get_fred_series_id_env_overrides_registry(monkeypatch):
    """FRED_OIL_SERIES_ID overrides commodity_registry.yaml when set."""
    import domains.finance.commodity_registry as cr

    monkeypatch.setenv("FRED_OIL_SERIES_ID", "CUSTOM_OIL_SERIES")
    cr._cached = None
    try:
        assert cr.get_fred_series_id("oil") == "CUSTOM_OIL_SERIES"
    finally:
        cr._cached = None


def test_get_fred_series_id_registry_default(monkeypatch):
    """Without env override, oil uses registry default DCOILWTICO."""
    import domains.finance.commodity_registry as cr

    monkeypatch.delenv("FRED_OIL_SERIES_ID", raising=False)
    cr._cached = None
    try:
        assert cr.get_fred_series_id("oil") == "DCOILWTICO"
    finally:
        cr._cached = None
