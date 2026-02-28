"""
Unit tests for finance market_data_store (SQLite).
Uses tmp_path; patches FINANCE_MARKET_DB.
"""

import pytest


@pytest.fixture(autouse=True)
def _finance_market_db(monkeypatch, tmp_path):
    db = tmp_path / "test_market.db"
    monkeypatch.setattr("config.settings.FINANCE_MARKET_DB", db)
    monkeypatch.setattr("domains.finance.data.market_data_store.FINANCE_MARKET_DB", db)


def test_upsert_and_get_series():
    from domains.finance.data.market_data_store import upsert_observations, get_series

    obs = [
        {"date": "2024-01-01", "value": 100.5},
        {"date": "2024-01-02", "value": 101.2},
    ]
    res = upsert_observations("fred", "IQ12260", obs)
    assert res.success is True
    assert res.data == 2

    series = get_series("fred", "IQ12260")
    assert series.success is True
    assert len(series.data) == 2
    assert series.data[0]["date"] == "2024-01-01"
    assert series.data[0]["value"] == 100.5


def test_upsert_replaces_same_date():
    from domains.finance.data.market_data_store import upsert_observations, get_series

    upsert_observations("fred", "IQ12260", [{"date": "2024-01-01", "value": 100}])
    upsert_observations("fred", "IQ12260", [{"date": "2024-01-01", "value": 200}])

    series = get_series("fred", "IQ12260")
    assert series.success and len(series.data) == 1
    assert series.data[0]["value"] == 200


def test_get_series_date_range():
    from domains.finance.data.market_data_store import upsert_observations, get_series

    obs = [
        {"date": "2024-01-01", "value": 1},
        {"date": "2024-01-02", "value": 2},
        {"date": "2024-01-03", "value": 3},
    ]
    upsert_observations("fred", "X", obs)

    r = get_series("fred", "X", start_date="2024-01-02", end_date="2024-01-02")
    assert r.success and len(r.data) == 1
    assert r.data[0]["value"] == 2


def test_list_symbols():
    from domains.finance.data.market_data_store import upsert_observations, list_symbols

    upsert_observations("fred", "IQ12260", [{"date": "2024-01-01", "value": 1}])
    upsert_observations("fred", "DCOILWTICO", [{"date": "2024-01-01", "value": 70}])

    symbols = list_symbols("fred")
    assert "IQ12260" in symbols
    assert "DCOILWTICO" in symbols
    assert len(symbols) == 2
