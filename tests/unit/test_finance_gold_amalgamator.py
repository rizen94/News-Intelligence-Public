"""
Unit tests for gold amalgamator — storage and retrieval logic.
Fetch functions are mocked to avoid network calls.
"""

import pytest


@pytest.fixture(autouse=True)
def _finance_paths(monkeypatch, tmp_path):
    """Use temp dir for market DB and ledger."""
    market_db = tmp_path / "test_market.db"
    monkeypatch.setattr("config.settings.FINANCE_MARKET_DB", market_db)
    monkeypatch.setattr("config.settings.FINANCE_DATA_DIR", tmp_path)
    monkeypatch.setattr("domains.finance.data.market_data_store.FINANCE_MARKET_DB", market_db)
    monkeypatch.setattr("domains.finance.data.evidence_ledger.LEDGER_DB", tmp_path / "ledger.db")


def test_get_stored_empty():
    from domains.finance.gold_amalgamator import get_stored

    out = get_stored(source_id="freegoldapi")
    assert out == {"freegoldapi": []}


def test_list_sources():
    from domains.finance.gold_amalgamator import list_sources

    sources = list_sources()
    assert len(sources) >= 2
    ids = [s["id"] for s in sources]
    assert "freegoldapi" in ids
    assert "fred_iq12260" in ids


def test_fetch_all_mocked(monkeypatch):
    """Test fetch_all with mocked sources — no network."""
    from domains.finance.gold_amalgamator import fetch_all
    from shared.data_result import DataResult

    def mock_freegoldapi(start=None, end=None):
        return DataResult.ok([
            {"date": "2024-01-01", "value": 2050.0, "unit": "USD/oz", "source_id": "freegoldapi"},
        ])

    def mock_fred(start=None, end=None):
        return DataResult.ok([
            {"date": "2024-01-01", "value": 100.0, "unit": "index", "source_id": "fred_iq12260"},
        ])

    monkeypatch.setattr("domains.finance.gold_sources.freegoldapi.fetch", mock_freegoldapi)
    monkeypatch.setattr("domains.finance.gold_sources.fred_gold.fetch", mock_fred)

    results = fetch_all(start="2024-01-01", end="2024-01-01", store=True)

    assert "freegoldapi" in results
    assert "fred_iq12260" in results
    assert len(results["freegoldapi"]) == 1
    assert results["freegoldapi"][0]["value"] == 2050.0

    # Stored data
    from domains.finance.gold_amalgamator import get_stored
    stored = get_stored()
    assert "freegoldapi" in stored
    assert len(stored["freegoldapi"]) == 1
